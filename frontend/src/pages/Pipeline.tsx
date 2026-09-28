import { useState, useEffect, useCallback } from 'react'
import { DollarSign, ChevronDown, ChevronUp, User, Plus } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { formatCurrency, formatDate, getInitials } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import Modal from '../components/ui/Modal'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface Opportunity {
  id: number
  name: string
  account_name: string
  amount: string
  stage: string
  probability: number
  close_date: string
  owner_name: string
  owner_id: number
}

const STAGES = ['QUALIFICATION', 'PROPOSAL', 'NEGOTIATION', 'WON', 'LOST']

const STAGE_LABELS: Record<string, string> = {
  QUALIFICATION: 'Qualification',
  PROPOSAL: 'Proposal',
  NEGOTIATION: 'Negotiation',
  WON: 'Won',
  LOST: 'Lost',
}

const STAGE_COLORS: Record<string, string> = {
  QUALIFICATION: 'var(--info, #6B8AFF)',
  PROPOSAL: 'var(--accent)',
  NEGOTIATION: 'var(--warn)',
  WON: 'var(--ok)',
  LOST: 'var(--danger)',
}

const emptyOpp = () => ({
  name: '',
  account_id: '',
  amount: '',
  stage: 'QUALIFICATION',
  probability: 20,
  close_date: '',
})

export default function Pipeline() {
  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [collapsedStages, setCollapsedStages] = useState<string[]>(['LOST', 'WON'])
  const [dragOverStage, setDragOverStage] = useState<string | null>(null)
  const [addOpen, setAddOpen] = useState(false)
  const [newOpp, setNewOpp] = useState(emptyOpp())
  const [saving, setSaving] = useState(false)

  const fetchOpps = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const data = await api.get<Opportunity[]>('/crm/opportunities/')
      setOpportunities(extractResults(data))
    } catch {
      setError('Failed to load pipeline.')
      setOpportunities([])
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => { fetchOpps() }, [fetchOpps])

  const grouped = STAGES.reduce((acc, stage) => {
    acc[stage] = opportunities.filter((o) => o.stage === stage)
    return acc
  }, {} as Record<string, Opportunity[]>)

  const totalPipelineValue = opportunities
    .filter((o) => o.stage !== 'LOST')
    .reduce((sum, o) => sum + parseFloat(o.amount || '0'), 0)

  const handleDragStart = (e: React.DragEvent, opp: Opportunity) => {
    e.dataTransfer.setData('application/json', JSON.stringify({ id: opp.id, currentStage: opp.stage }))
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDragOver = (e: React.DragEvent, stage: string) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    setDragOverStage(stage)
  }

  const handleDragLeave = () => {
    setDragOverStage(null)
  }

  const handleDrop = async (e: React.DragEvent, targetStage: string) => {
    e.preventDefault()
    setDragOverStage(null)
    try {
      const raw = e.dataTransfer.getData('application/json')
      const { id, currentStage } = JSON.parse(raw)
      if (currentStage === targetStage) return

      // Optimistic update
      setOpportunities((prev) =>
        prev.map((o) => (o.id === id ? { ...o, stage: targetStage } : o))
      )

      await api.patch(`/crm/opportunities/${id}/stage/`, {
        stage: targetStage,
        lost_reason: targetStage === 'LOST' ? '' : undefined,
      })
    } catch {
      setError('Failed to update stage. Refreshing...')
      fetchOpps()
    }
  }

  const toggleCollapse = (stage: string) => {
    setCollapsedStages((prev) =>
      prev.includes(stage) ? prev.filter((s) => s !== stage) : [...prev, stage]
    )
  }

  const handleAdd = async () => {
    if (!newOpp.name.trim() || !newOpp.account_id) return
    setSaving(true)
    try {
      await api.post('/crm/opportunities/', newOpp)
      setAddOpen(false)
      setNewOpp(emptyOpp())
      fetchOpps()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create opportunity.')
    } finally { setSaving(false) }
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Pipeline</h1>
            <div style={{ display: 'flex', gap: '12px', marginTop: '4px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Total value: <strong style={{ color: 'var(--accent)' }}>{formatCurrency(totalPipelineValue)}</strong>
              </span>
              {STAGES.map((stage) => {
                const stageTotal = (grouped[stage] || []).reduce((s, o) => s + parseFloat(o.amount || '0'), 0)
                const count = (grouped[stage] || []).length
                return (
                  <span key={stage} style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                    <span style={{ color: STAGE_COLORS[stage], fontWeight: 600 }}>{STAGE_LABELS[stage]}</span>: {formatCurrency(stageTotal)} ({count})
                  </span>
                )
              })}
            </div>
          </div>
          <button onClick={() => setAddOpen(true)} style={priBtnStyle}>
            <Plus size={16} /> Add Opportunity
          </button>
        </div>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message="Loading pipeline..." />
        ) : (
          <div style={{
            display: 'flex',
            gap: '16px',
            overflowX: 'auto',
            paddingBottom: '8px',
            minHeight: '400px',
          }}>
            {STAGES.map((stage) => {
              const items = grouped[stage] || []
              const isCollapsed = collapsedStages.includes(stage)
              const stageTotal = items.reduce((s, o) => s + parseFloat(o.amount || '0'), 0)

              return (
                <div
                  key={stage}
                  onDragOver={(e) => handleDragOver(e, stage)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, stage)}
                  style={{
                    flex: '0 0 280px',
                    minHeight: '300px',
                    backgroundColor: dragOverStage === stage
                      ? 'color-mix(in srgb, var(--accent) 6%, var(--surface))'
                      : 'var(--surface)',
                    border: dragOverStage === stage
                      ? `2px dashed var(--accent)`
                      : '1px solid var(--border)',
                    borderRadius: 'var(--radius-lg)',
                    padding: '12px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                    transition: 'background-color 150ms ease, border 150ms ease',
                  }}
                >
                  {/* Column header */}
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    paddingBottom: '8px',
                    borderBottom: `2px solid ${STAGE_COLORS[stage]}`,
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{
                        width: '8px', height: '8px', borderRadius: '50%',
                        backgroundColor: STAGE_COLORS[stage],
                      }} />
                      <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                        {STAGE_LABELS[stage]}
                      </span>
                      <Badge variant="info" size="sm">{items.length}</Badge>
                    </div>
                    <button
                      onClick={() => toggleCollapse(stage)}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        color: 'var(--text-muted)', padding: '2px',
                      }}
                    >
                      {isCollapsed ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                  </div>

                  {!isCollapsed && (
                    <>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 500 }}>
                        {formatCurrency(stageTotal)}
                      </div>

                      {/* Cards */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', flex: 1 }}>
                        {items.length === 0 && (
                          <div style={{
                            padding: '20px 12px',
                            textAlign: 'center',
                            color: 'var(--text-muted)',
                            fontSize: '0.78rem',
                            border: '1px dashed var(--border)',
                            borderRadius: 'var(--radius-md)',
                          }}>
                            Drop here
                          </div>
                        )}
                        {items.map((opp) => (
                          <div
                            key={opp.id}
                            draggable
                            onDragStart={(e) => handleDragStart(e, opp)}
                            style={{
                              backgroundColor: 'var(--surface-2)',
                              border: '1px solid var(--border)',
                              borderRadius: 'var(--radius-md)',
                              padding: '12px',
                              cursor: 'grab',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '8px',
                              transition: 'box-shadow 150ms ease',
                            }}
                            onMouseEnter={(e) => {
                              (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-md)'
                            }}
                            onMouseLeave={(e) => {
                              (e.currentTarget as HTMLElement).style.boxShadow = 'none'
                            }}
                          >
                            <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                              {opp.name}
                            </div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              {opp.account_name}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--accent)' }}>
                                {formatCurrency(parseFloat(opp.amount || '0'))}
                              </span>
                              <Badge variant="info" size="sm">{opp.probability}%</Badge>
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.72rem' }}>
                              <span style={{ color: 'var(--text-muted)' }}>
                                {opp.close_date ? formatDate(opp.close_date) : '—'}
                              </span>
                              <span style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                color: 'var(--text-muted)',
                              }}>
                                <span style={{
                                  width: '20px',
                                  height: '20px',
                                  borderRadius: '50%',
                                  backgroundColor: 'color-mix(in srgb, var(--accent) 20%, transparent)',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  fontSize: '0.6rem',
                                  fontWeight: 700,
                                  color: 'var(--accent)',
                                }}>
                                  {getInitials(opp.owner_name?.split(' ')[0], opp.owner_name?.split(' ')[1])}
                                </span>
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Add Opportunity Modal */}
        <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add Opportunity" maxWidth="500px">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <Field label="Name" value={newOpp.name} onChange={(v) => setNewOpp((p) => ({ ...p, name: v }))} />
            <Field label="Account ID" value={newOpp.account_id} onChange={(v) => setNewOpp((p) => ({ ...p, account_id: v }))} type="number" />
            <Field label="Amount" value={newOpp.amount} onChange={(v) => setNewOpp((p) => ({ ...p, amount: v }))} type="number" />
            <div>
              <label style={labelStyle}>Stage</label>
              <select
                value={newOpp.stage}
                onChange={(e) => setNewOpp((p) => ({ ...p, stage: e.target.value }))}
                style={selectStyle}
              >
                {STAGES.filter((s) => s !== 'WON' && s !== 'LOST').map((s) => (
                  <option key={s} value={s}>{STAGE_LABELS[s]}</option>
                ))}
              </select>
            </div>
            <Field label="Probability (%)" value={String(newOpp.probability)} onChange={(v) => setNewOpp((p) => ({ ...p, probability: Number(v) }))} type="number" />
            <Field label="Close Date" value={newOpp.close_date} onChange={(v) => setNewOpp((p) => ({ ...p, close_date: v }))} type="date" />
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '8px' }}>
              <button onClick={() => setAddOpen(false)} style={secBtnStyle}>Cancel</button>
              <button onClick={handleAdd} disabled={saving || !newOpp.name.trim()} style={priBtnStyle}>
                {saving ? 'Saving...' : 'Save'}
              </button>
            </div>
          </div>
        </Modal>
      </div>
    </ErrorBoundary>
  )
}

function Field({ label, value, onChange, type = 'text' }: { label: string; value: string; onChange: (v: string) => void; type?: string }) {
  return (
    <div>
      <label style={labelStyle}>{label}</label>
      <input type={type} value={value} onChange={(e) => onChange(e.target.value)} style={inputStyle}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
        onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
      />
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: '0.8rem', fontWeight: 500, color: 'var(--text)', marginBottom: '4px' }
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', backgroundColor: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', color: 'var(--text)', fontSize: '0.85rem', outline: 'none', boxSizing: 'border-box' }
const selectStyle: React.CSSProperties = { ...inputStyle }
const priBtnStyle: React.CSSProperties = { display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '8px 16px', backgroundColor: 'var(--accent)', color: '#fff', border: 'none', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }
const secBtnStyle: React.CSSProperties = { padding: '8px 16px', backgroundColor: 'transparent', color: 'var(--text-muted)', border: '1px solid var(--border)', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', cursor: 'pointer' }
const errorBannerStyle: React.CSSProperties = { backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)', color: 'var(--danger)', padding: '10px 16px', borderRadius: 'var(--radius-md)', fontSize: '0.85rem', border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)' }
