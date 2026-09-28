import { useState, useEffect, useCallback } from 'react'
import { CheckCheck, Check, X, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-react'
import api, { extractResults } from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import { formatDateTime, formatDate } from '../lib/utils'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import EmptyState from '../components/ui/EmptyState'
import ErrorBoundary from '../components/ui/ErrorBoundary'

interface Approval {
  id: number
  action_type: string
  requested_by_name: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  payload: Record<string, unknown>
  reason: string | null
  reviewed_by_name: string | null
  reviewed_at: string | null
}

const STATUS_VARIANT: Record<string, 'warn' | 'ok' | 'danger'> = {
  pending: 'warn',
  approved: 'ok',
  rejected: 'danger',
}

const STATUS_FILTERS = ['pending', 'approved', 'rejected'] as const

export default function Approvals() {
  const { isAdmin } = useRoleAccess()
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('pending')
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [rejectReason, setRejectReason] = useState('')
  const [actingId, setActingId] = useState<number | null>(null)
  const [acting, setActing] = useState(false)

  const fetchApprovals = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ status: statusFilter })
      const data = await api.get<Approval[]>(`/approvals/?${params}`)
      setApprovals(extractResults(data))
    } catch {
      setError('Failed to load approvals.')
      setApprovals([])
    } finally { setIsLoading(false) }
  }, [statusFilter])

  useEffect(() => { fetchApprovals() }, [fetchApprovals])

  const handleAction = async (id: number, action: 'approve' | 'reject') => {
    if (action === 'reject' && !rejectReason.trim()) {
      setError('Please provide a reason for rejection.')
      return
    }
    setActingId(id)
    setActing(true)
    setError('')
    try {
      await api.post(`/approvals/${id}/${action}/`, {
        reason: action === 'reject' ? rejectReason : '',
      })
      setRejectReason('')
      fetchApprovals()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Action failed.')
    } finally {
      setActing(false)
      setActingId(null)
    }
  }

  if (!isAdmin) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
        <AlertTriangle size={32} style={{ marginBottom: '12px', color: 'var(--warn)' }} />
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>Access Denied</h2>
        <p style={{ fontSize: '0.85rem', marginTop: '4px' }}>Only administrators can access the approvals inbox.</p>
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Approvals</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Admin approval inbox
          </p>
        </div>

        <Card padding="12px 16px">
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {STATUS_FILTERS.map((s) => (
              <button key={s} onClick={() => setStatusFilter(s)} style={{
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: '0.78rem',
                fontWeight: statusFilter === s ? 600 : 400,
                border: statusFilter === s ? '1px solid var(--accent)' : '1px solid var(--border)',
                backgroundColor: statusFilter === s ? 'color-mix(in srgb, var(--accent) 12%, transparent)' : 'var(--surface-2)',
                color: statusFilter === s ? 'var(--accent)' : 'var(--text-muted)',
                cursor: 'pointer',
                textTransform: 'capitalize',
              }}>
                {s}
              </button>
            ))}
          </div>
        </Card>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message="Loading approvals..." />
        ) : approvals.length === 0 ? (
          <EmptyState
            icon={<CheckCheck size={48} />}
            title={`No ${statusFilter} approvals`}
            description={`There are no ${statusFilter} requests at this time.`}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {approvals.map((a) => (
              <div
                key={a.id}
                style={{
                  backgroundColor: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-lg)',
                  overflow: 'hidden',
                }}
              >
                {/* Header */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '14px 18px',
                  cursor: 'pointer',
                  flexWrap: 'wrap',
                  gap: '8px',
                }}
                  onClick={() => setExpandedId(expandedId === a.id ? null : a.id)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1 }}>
                    <Badge variant={STATUS_VARIANT[a.status] || 'info'} dot>
                      <span style={{ textTransform: 'capitalize' }}>{a.status}</span>
                    </Badge>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                        {a.action_type}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        Requested by {a.requested_by_name} &middot; {formatDateTime(a.created_at)}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {a.status === 'pending' && (
                      <>
                        <button
                          onClick={(e) => { e.stopPropagation(); handleAction(a.id, 'approve') }}
                          disabled={acting}
                          style={approveBtnStyle}
                        >
                          <Check size={14} /> Approve
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setExpandedId(a.id); setRejectReason('') }}
                          disabled={acting}
                          style={rejectBtnStyle}
                        >
                          <X size={14} /> Reject
                        </button>
                      </>
                    )}
                    {expandedId === a.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                  </div>
                </div>

                {/* Expanded content */}
                {expandedId === a.id && (
                  <div style={{ padding: '0 18px 16px', borderTop: '1px solid var(--border)' }}>
                    <div style={{ paddingTop: '12px' }}>
                      <div style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', textTransform: 'uppercase' }}>
                        Payload
                      </div>
                      <pre style={{
                        backgroundColor: 'var(--surface-2)',
                        padding: '12px',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '0.75rem',
                        color: 'var(--text)',
                        overflowX: 'auto',
                        maxHeight: '200px',
                        overflow: 'auto',
                        lineHeight: 1.5,
                        fontFamily: 'monospace',
                        margin: 0,
                      }}>
                        {JSON.stringify(a.payload, null, 2)}
                      </pre>
                    </div>

                    {/* Reject reason input */}
                    {a.status === 'pending' && (
                      <div style={{ marginTop: '12px' }}>
                        <label style={{ fontSize: '0.78rem', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '6px' }}>
                          Rejection Reason
                        </label>
                        <textarea
                          value={rejectReason}
                          onChange={(e) => setRejectReason(e.target.value)}
                          placeholder="Provide a reason for rejection..."
                          rows={2}
                          style={{
                            width: '100%',
                            padding: '8px 10px',
                            backgroundColor: 'var(--surface-2)',
                            border: '1px solid var(--border)',
                            borderRadius: 'var(--radius-md)',
                            color: 'var(--text)',
                            fontSize: '0.85rem',
                            outline: 'none',
                            resize: 'vertical',
                            boxSizing: 'border-box',
                            fontFamily: 'inherit',
                          }}
                          onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--accent)' }}
                          onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--border)' }}
                        />
                        <button
                          onClick={() => handleAction(a.id, 'reject')}
                          disabled={acting || !rejectReason.trim()}
                          style={{
                            ...rejectBtnStyle,
                            marginTop: '8px',
                            opacity: acting || !rejectReason.trim() ? 0.5 : 1,
                          }}
                        >
                          <X size={14} /> Reject with Reason
                        </button>
                      </div>
                    )}

                    {a.reviewed_by_name && (
                      <div style={{ marginTop: '12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        Reviewed by {a.reviewed_by_name} on {formatDate(a.reviewed_at ?? '')}
                      </div>
                    )}

                    {a.reason && (
                      <div style={{ marginTop: '8px', padding: '10px', backgroundColor: 'var(--surface-2)', borderRadius: 'var(--radius-md)', fontSize: '0.8rem', color: 'var(--text)' }}>
                        <strong>Reason:</strong> {a.reason}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}

const approveBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '4px',
  padding: '5px 12px', backgroundColor: 'var(--ok)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
}

const rejectBtnStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '4px',
  padding: '5px 12px', backgroundColor: 'var(--danger)', color: '#fff',
  border: 'none', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem', fontWeight: 600, cursor: 'pointer',
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)', padding: '10px 16px', borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem', border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}
