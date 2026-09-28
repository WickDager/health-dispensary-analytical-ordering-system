import { useState, useEffect, useCallback } from 'react'
import {
  Brain,
  ToggleLeft,
  ToggleRight,
  BarChart3,
  Zap,
  ExternalLink,
} from 'lucide-react'
import api, { extractResults } from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface AIModule {
  key: string
  label: string
  description: string
  enabled: boolean
  confidence_threshold: number
}

interface ModelPerformance {
  id: number
  name: string
  model_type: string
  accuracy: number
  precision_score: number
  recall_score: number
  f1_score: number
  last_trained: string | null
}

interface AIConfig {
  modules: AIModule[]
  retraining_schedule: string
}

const DEFAULT_MODULES: AIModule[] = [
  { key: 'demand_forecasting', label: 'Demand Forecasting', description: 'Predict future inventory needs based on historical dispense data', enabled: true, confidence_threshold: 0.7 },
  { key: 'supplier_scoring', label: 'Supplier Scoring', description: 'Rate suppliers on delivery performance, reliability, and pricing', enabled: true, confidence_threshold: 0.65 },
  { key: 'expiry_risk', label: 'Expiry Risk', description: 'Identify inventory items at risk of expiring before use', enabled: true, confidence_threshold: 0.6 },
  { key: 'adherence_prediction', label: 'Adherence Prediction', description: 'Predict patient medication adherence patterns', enabled: false, confidence_threshold: 0.7 },
  { key: 'anomaly_detection', label: 'Anomaly Detection', description: 'Detect unusual patterns in orders, dispense, and inventory', enabled: true, confidence_threshold: 0.75 },
  { key: 'llm_insights', label: 'LLM Insights', description: 'AI-generated analysis and natural language explanations', enabled: true, confidence_threshold: 0.5 },
  { key: 'document_ingestion', label: 'Document Ingestion', description: 'Extract structured data from PDFs, images, and scanned documents', enabled: true, confidence_threshold: 0.55 },
]

const RETRAINING_OPTIONS = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'manual', label: 'Manual Only' },
]

export default function SettingsAI() {
  const { isAdmin } = useRoleAccess()
  const [modules, setModules] = useState<AIModule[]>(DEFAULT_MODULES)
  const [retrainingSchedule, setRetrainingSchedule] = useState('weekly')
  const [performance, setPerformance] = useState<ModelPerformance[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [perfLoading, setPerfLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isRunningAll, setIsRunningAll] = useState(false)
  const [runResult, setRunResult] = useState('')

  const fetchConfig = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<AIConfig>('/settings/ai/')
      if (data) {
        if (data.modules) setModules(data.modules)
        if (data.retraining_schedule) setRetrainingSchedule(data.retraining_schedule)
      }
    } catch {
      // Use defaults if API not available
    } finally {
      setIsLoading(false)
    }
  }, [])

  const fetchPerformance = useCallback(async () => {
    setPerfLoading(true)
    try {
      const data = await api.get<ModelPerformance[]>('/intelligence/performance/')
      setPerformance(extractResults(data))
    } catch {
      // Performance endpoint may not be available yet
    } finally {
      setPerfLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchConfig()
    fetchPerformance()
  }, [fetchConfig, fetchPerformance])

  const toggleModule = (key: string) => {
    setModules((prev) =>
      prev.map((m) => (m.key === key ? { ...m, enabled: !m.enabled } : m)),
    )
  }

  const updateThreshold = (key: string, value: number) => {
    setModules((prev) =>
      prev.map((m) => (m.key === key ? { ...m, confidence_threshold: value } : m)),
    )
  }

  const handleSave = async () => {
    setError('')
    setSuccess('')
    try {
      await api.patch('/settings/ai/', {
        modules,
        retraining_schedule: retrainingSchedule,
      })
      setSuccess('AI configuration saved successfully.')
    } catch {
      setError('Failed to save AI configuration.')
    }
  }

  const handleRunAll = async () => {
    setIsRunningAll(true)
    setRunResult('')
    try {
      const result = await api.post<{ message: string }>('/intelligence/run-all/')
      setRunResult(result.message || 'All models executed successfully.')
    } catch {
      setRunResult('Failed to run models.')
    } finally {
      setIsRunningAll(false)
    }
  }

  if (!isAdmin) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>Access Denied</h2>
        <p style={{ fontSize: '0.85rem', marginTop: '4px' }}>Only administrators can manage AI settings.</p>
      </div>
    )
  }

  if (isLoading) {
    return <LoadingSpinner message="Loading AI configuration..." />
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {error && <div style={errorBannerStyle}>{error}</div>}
        {success && <div style={successBannerStyle}>{success}</div>}
        {runResult && (
          <div
            style={{
              ...(runResult.toLowerCase().includes('fail')
                ? errorBannerStyle
                : successBannerStyle),
            }}
          >
            {runResult}
          </div>
        )}

        {/* Module Toggles */}
        <Card title="AI Modules">
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '16px' }}>
            Enable or disable AI intelligence modules and set confidence thresholds for each.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {modules.map((mod) => (
              <div
                key={mod.key}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '16px',
                  padding: '14px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--surface-2)',
                  border: '1px solid var(--border)',
                  flexWrap: 'wrap',
                }}
              >
                {/* Toggle */}
                <button
                  onClick={() => toggleModule(mod.key)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: 0,
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  {mod.enabled ? (
                    <ToggleRight size={22} style={{ color: 'var(--ok)' }} />
                  ) : (
                    <ToggleLeft size={22} style={{ color: 'var(--text-muted)' }} />
                  )}
                </button>

                {/* Info & Slider */}
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span
                      style={{
                        fontWeight: 600,
                        fontSize: '0.9rem',
                        color: mod.enabled ? 'var(--text)' : 'var(--text-muted)',
                      }}
                    >
                      {mod.label}
                    </span>
                    <Badge variant={mod.enabled ? 'ok' : 'info'} size="sm" dot>
                      {mod.enabled ? 'Active' : 'Disabled'}
                    </Badge>
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {mod.description}
                  </p>

                  {/* Confidence Threshold Slider */}
                  <div
                    style={{
                      marginTop: '10px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      opacity: mod.enabled ? 1 : 0.4,
                      pointerEvents: mod.enabled ? 'auto' : 'none',
                    }}
                  >
                    <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', minWidth: '100px' }}>
                      Threshold: {mod.confidence_threshold.toFixed(2)}
                    </span>
                    <input
                      type="range"
                      min="0.5"
                      max="0.95"
                      step="0.05"
                      value={mod.confidence_threshold}
                      onChange={(e) => updateThreshold(mod.key, parseFloat(e.target.value))}
                      style={{
                        flex: 1,
                        maxWidth: '200px',
                        accentColor: 'var(--accent)',
                        cursor: 'pointer',
                      }}
                    />
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>0.5</span>
                    <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>0.95</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Retraining Schedule */}
        <Card title="Retraining Schedule">
          <div style={{ maxWidth: '400px' }}>
            <label style={labelStyle}>Auto-retrain Models</label>
            <select
              value={retrainingSchedule}
              onChange={(e) => setRetrainingSchedule(e.target.value)}
              style={selectStyle}
            >
              {RETRAINING_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '6px' }}>
              {retrainingSchedule === 'daily'
                ? 'Models will retrain automatically every 24 hours with new data.'
                : retrainingSchedule === 'weekly'
                  ? 'Models will retrain every Sunday at midnight.'
                  : 'Models only retrain when manually triggered.'}
            </p>
          </div>
        </Card>

        {/* Model Performance */}
        <Card
          title="Model Performance"
          action={
            <button onClick={handleRunAll} disabled={isRunningAll} style={runBtnStyle}>
              <Zap size={14} />
              {isRunningAll ? 'Running...' : 'Run All Models Now'}
            </button>
          }
        >
          {perfLoading ? (
            <LoadingSpinner size={24} message="Loading performance data..." />
          ) : performance.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '30px',
                color: 'var(--text-muted)',
                fontSize: '0.85rem',
              }}
            >
              <Brain size={36} style={{ marginBottom: '8px', opacity: 0.4 }} />
              <p>No performance data available yet.</p>
              <p style={{ fontSize: '0.75rem', marginTop: '4px' }}>
                Run the models to generate performance metrics.
              </p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '12px' }}>
              {performance.map((p) => (
                <div
                  key={p.id}
                  style={{
                    padding: '14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'var(--surface-2)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                      {p.name}
                    </span>
                    <Badge
                      variant={
                        p.accuracy >= 0.9 ? 'ok' : p.accuracy >= 0.75 ? 'warn' : 'danger'
                      }
                      size="sm"
                    >
                      {p.model_type}
                    </Badge>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                    <PerfItem label="Accuracy" value={p.accuracy} />
                    <PerfItem label="Precision" value={p.precision_score} />
                    <PerfItem label="Recall" value={p.recall_score} />
                    <PerfItem label="F1 Score" value={p.f1_score} />
                  </div>
                  <div
                    style={{
                      marginTop: '8px',
                      fontSize: '0.7rem',
                      color: 'var(--text-muted)',
                    }}
                  >
                    Last trained:{' '}
                    {p.last_trained
                      ? new Date(p.last_trained).toLocaleDateString()
                      : 'Never'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* View Prediction Log Link */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <a
            href="/intelligence/log"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.85rem',
              color: 'var(--accent)',
              fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            <ExternalLink size={14} />
            View Prediction Log
          </a>

          <button onClick={handleSave} style={saveBtnStyle}>
            Save AI Configuration
          </button>
        </div>
      </div>
    </ErrorBoundary>
  )
}

function PerfItem({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100)
  return (
    <div>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: '0.7rem',
          color: 'var(--text-muted)',
          marginBottom: '2px',
        }}
      >
        <span>{label}</span>
        <span style={{ fontWeight: 600, color: pct >= 90 ? 'var(--ok)' : pct >= 75 ? 'var(--warn)' : 'var(--danger)' }}>
          {pct}%
        </span>
      </div>
      <div
        style={{
          height: '4px',
          borderRadius: '2px',
          backgroundColor: 'var(--border)',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            borderRadius: '2px',
            backgroundColor:
              pct >= 90 ? 'var(--ok)' : pct >= 75 ? 'var(--warn)' : 'var(--danger)',
            transition: 'width 300ms ease',
          }}
        />
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.8rem',
  fontWeight: 500,
  color: 'var(--text)',
  marginBottom: '4px',
}

const selectStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  backgroundColor: 'var(--surface-2)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  color: 'var(--text)',
  fontSize: '0.85rem',
  outline: 'none',
  boxSizing: 'border-box',
}

const runBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '6px',
  padding: '6px 14px',
  backgroundColor: 'var(--surface-2)',
  color: 'var(--accent)',
  border: '1px solid var(--border)',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.8rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const saveBtnStyle: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: '8px',
  padding: '10px 24px',
  backgroundColor: 'var(--accent)',
  color: '#fff',
  border: 'none',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.9rem',
  fontWeight: 600,
  cursor: 'pointer',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)',
  padding: '10px 16px',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}

const successBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--ok) 12%, transparent)',
  color: 'var(--ok)',
  padding: '10px 16px',
  borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem',
  border: '1px solid color-mix(in srgb, var(--ok) 25%, transparent)',
}
