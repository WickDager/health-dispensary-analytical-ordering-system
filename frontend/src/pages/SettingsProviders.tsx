import { useState, useEffect, useCallback } from 'react'
import {
  Server, ToggleLeft, ToggleRight, Radio, GripVertical,
  Eye, EyeOff, Wifi, Save, Zap,
} from 'lucide-react'
import api, { extractResults } from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import EmptyState from '../components/ui/EmptyState'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface LLMProvider {
  name: string
  enabled: boolean
  is_default: boolean
  model: string
  base_url: string | null
  api_key_masked: string | null
  fallback_priority: number
  updated_at: string
}

interface PaginatedProviders {
  count: number
  next: string | null
  previous: string | null
  results: LLMProvider[]
}

export default function SettingsProviders() {
  const { isAdmin } = useRoleAccess()
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [testingId, setTestingId] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<Record<string, { ok: boolean; message: string }>>({})
  const [isSaving, setIsSaving] = useState(false)
  const [visibleKeys, setVisibleKeys] = useState<Record<string, boolean>>({})
  const [newKeys, setNewKeys] = useState<Record<string, string>>({})

  const fetchProviders = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<PaginatedProviders | LLMProvider[]>('/llm/providers/')
      setProviders(extractResults(data))
    } catch {
      setError('Failed to load LLM providers.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchProviders() }, [fetchProviders])

  const updateProvider = (name: string, patch: Partial<LLMProvider>) => {
    setProviders(prev => prev.map(p => p.name === name ? { ...p, ...patch } : p))
  }

  const handleSave = async () => {
    setIsSaving(true)
    setError('')
    setSuccess('')
    try {
      const patches = providers.map(p => {
        const body: Record<string, unknown> = {
          name: p.name,
          enabled: p.enabled,
          is_default: p.is_default,
          model: p.model,
          base_url: p.base_url || '',
          fallback_priority: p.fallback_priority,
        }
        if (newKeys[p.name]?.trim()) {
          body['api_key_raw'] = newKeys[p.name].trim()
        }
        return api.put(`/llm/providers/${p.name}/`, body)
      })
      await Promise.all(patches)
      setNewKeys({})
      setSuccess('All provider settings saved successfully.')
      fetchProviders()
    } catch {
      setError('Failed to save provider settings.')
    } finally {
      setIsSaving(false)
    }
  }

  const testProvider = async (p: LLMProvider) => {
    setTestingId(p.name)
    setTestResult(prev => { const c = { ...prev }; delete c[p.name]; return c })
    try {
      await api.post(`/llm/providers/test/`, { text: 'test', provider: p.name })
      setTestResult(prev => ({ ...prev, [p.name]: { ok: true, message: 'Connection successful' } }))
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Test failed'
      setTestResult(prev => ({ ...prev, [p.name]: { ok: false, message: msg } }))
    } finally {
      setTestingId(null)
    }
  }

  if (!isAdmin) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>Access Denied</h2>
        <p style={{ fontSize: '0.85rem', marginTop: '4px' }}>Only administrators can manage LLM providers.</p>
      </div>
    )
  }

  if (isLoading) return <LoadingSpinner message="Loading LLM providers..." />

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {error && <div style={bannerStyle('danger')}>{error}</div>}
        {success && <div style={bannerStyle('ok')}>{success}</div>}

        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
            <div>
              <h2 style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text)' }}>LLM Providers</h2>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                Configure API keys, models, and fallback priority for each provider
              </p>
            </div>
            <button onClick={handleSave} disabled={isSaving} style={saveBtn}>
              <Save size={16} /> {isSaving ? 'Saving...' : 'Save All Changes'}
            </button>
          </div>

          {providers.length === 0 ? (
            <EmptyState icon={<Server size={48} />} title="No providers configured" description="Run: python manage.py seed_intelligence to create default providers." />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {providers.map((p, idx) => (
                <div key={p.name}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData('text/plain', String(idx))}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault()
                    const from = Number(e.dataTransfer.getData('text/plain'))
                    if (from === idx) return
                    const reordered = [...providers]
                    const [moved] = reordered.splice(from, 1)
                    reordered.splice(idx, 0, moved)
                    setProviders(reordered.map((pp, i) => ({ ...pp, fallback_priority: i + 1 })))
                  }}
                  style={cardStyle}
                >
                  {/* Header */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <GripVertical size={16} style={{ color: 'var(--text-muted)', cursor: 'grab', flexShrink: 0 }} />
                      <span style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text)', textTransform: 'capitalize' }}>{p.name}</span>
                      {p.is_default && <Badge variant="accent">Default</Badge>}
                      <Badge variant={p.enabled ? 'ok' : 'danger'} dot>{p.enabled ? 'Enabled' : 'Disabled'}</Badge>
                      <Badge variant="info" size="sm">Priority: {p.fallback_priority}</Badge>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <button onClick={() => testProvider(p)} disabled={testingId === p.name || !p.enabled} style={{ ...secBtn, opacity: testingId === p.name || !p.enabled ? 0.5 : 1 }}>
                        <Wifi size={12} /> {testingId === p.name ? 'Testing...' : 'Test'}
                      </button>
                      <button onClick={() => updateProvider(p.name, { enabled: !p.enabled })} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }} title={p.enabled ? 'Disable' : 'Enable'}>
                        {p.enabled ? <ToggleRight size={24} style={{ color: 'var(--ok)' }} /> : <ToggleLeft size={24} style={{ color: 'var(--text-muted)' }} />}
                      </button>
                      <button onClick={() => { if (p.enabled) updateProvider(p.name, { is_default: true }) }} disabled={p.is_default || !p.enabled}
                        style={{ background: 'none', border: 'none', cursor: p.is_default ? 'default' : 'pointer', padding: 0 }} title="Set as default">
                        <Radio size={18} style={{ color: p.is_default ? 'var(--accent)' : 'var(--text-muted)', opacity: p.is_default ? 1 : 0.5 }} />
                      </button>
                    </div>
                  </div>

                  {/* Fields */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                    <Field label="Model" value={p.model} onChange={v => updateProvider(p.name, { model: v })} disabled={!p.enabled} />
                    <Field label="Base URL" value={p.base_url || ''} onChange={v => updateProvider(p.name, { base_url: v })} disabled={!p.enabled} placeholder="https://api.example.com/v1" />
                    <div>
                      <label style={fieldLabel}>API Key</label>
                      <div style={{ position: 'relative', display: 'flex' }}>
                        <input
                          type={visibleKeys[p.name] ? 'text' : 'password'}
                          value={newKeys[p.name] ?? ''}
                          onChange={e => setNewKeys(prev => ({ ...prev, [p.name]: e.target.value }))}
                          placeholder={p.api_key_masked ? `Current: ${p.api_key_masked}` : 'Enter API key...'}
                          disabled={!p.enabled}
                          style={{ ...fieldInput, paddingRight: '36px', opacity: p.enabled ? 1 : 0.5 }}
                        />
                        <button onClick={() => setVisibleKeys(prev => ({ ...prev, [p.name]: !prev[p.name] }))}
                          style={{ position: 'absolute', right: '4px', top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', padding: '4px', display: 'flex', color: 'var(--text-muted)' }}
                          title={visibleKeys[p.name] ? 'Hide' : 'Show'}>
                          {visibleKeys[p.name] ? <EyeOff size={14} /> : <Eye size={14} />}
                        </button>
                      </div>
                    </div>
                  </div>

                  {/* Test result */}
                  {testResult[p.name] && (
                    <div style={{ fontSize: '0.78rem', padding: '6px 10px', borderRadius: 'var(--radius-sm)', color: testResult[p.name].ok ? 'var(--ok)' : 'var(--danger)', backgroundColor: `color-mix(in srgb, var(${testResult[p.name].ok ? '--ok' : '--danger'}) 10%, transparent)`, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span>{testResult[p.name].ok ? '✓' : '✗'}</span> {testResult[p.name].message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Per-Task Assignment */}
        <Card title="Per-Task LLM Assignment" action={<span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '6px' }}><Zap size={14} style={{ color: 'var(--accent)' }} /> Select which provider handles each task</span>}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '12px' }}>
            {[
              { key: 'demand_forecasting', label: 'Demand Forecasting' },
              { key: 'supplier_scoring', label: 'Supplier Scoring' },
              { key: 'anomaly_explanation', label: 'Anomaly Explanation' },
              { key: 'document_ingestion', label: 'Document Ingestion' },
              { key: 'procurement_recommendations', label: 'Procurement Recommendations' },
              { key: 'dashboard_insights', label: 'Dashboard Insights' },
            ].map(task => (
              <div key={task.key} style={{ padding: '12px', borderRadius: 'var(--radius-md)', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text)', marginBottom: '6px' }}>{task.label}</label>
                <select defaultValue="" style={selectStyle}>
                  <option value="">-- Default (auto) --</option>
                  {providers.filter(p => p.enabled).map(p => (
                    <option key={p.name} value={p.name}>{p.name}{p.is_default ? ' (default)' : ''}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </Card>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button onClick={handleSave} disabled={isSaving} style={saveBtn}><Save size={16} /> {isSaving ? 'Saving...' : 'Save All Changes'}</button>
        </div>
      </div>
    </ErrorBoundary>
  )
}

function Field({ label, value, onChange, type = 'text', placeholder, disabled }: { label: string; value: string; onChange: (v: string) => void; type?: string; placeholder?: string; disabled?: boolean }) {
  return (
    <div>
      <label style={fieldLabel}>{label}</label>
      <input type={type} value={value} onChange={e => onChange(e.target.value)} placeholder={placeholder} disabled={disabled} style={{ ...fieldInput, opacity: disabled ? 0.5 : 1 }} />
    </div>
  )
}

const fieldLabel: React.CSSProperties = { display: 'block', fontSize: '0.72rem', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '3px' }
const fieldInput: React.CSSProperties = { width: '100%', padding: '6px 8px', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text)', fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box' }
const cardStyle: React.CSSProperties = { backgroundColor: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--radius-lg)', padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px' }
const saveBtn: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '8px', padding: '10px 24px', backgroundColor: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', fontSize: '0.9rem', fontWeight: 600, cursor: 'pointer', whiteSpace: 'nowrap' }
const secBtn: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '4px', padding: '4px 10px', backgroundColor: 'transparent', color: 'var(--accent)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', fontWeight: 500, cursor: 'pointer' }
const selectStyle: React.CSSProperties = { width: '100%', padding: '6px 8px', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', color: 'var(--text)', fontSize: '0.8rem', outline: 'none', boxSizing: 'border-box' }
const bannerStyle = (color: string): React.CSSProperties => ({ backgroundColor: `color-mix(in srgb, var(--${color}) 12%, transparent)`, color: `var(--${color})`, padding: '10px 16px', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', border: `1px solid color-mix(in srgb, var(--${color}) 25%, transparent)` })
