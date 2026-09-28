import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Bell, Check, Clock, Pill, ShoppingCart,
  ClipboardList, CheckCheck, DollarSign, ExternalLink,
} from 'lucide-react'
import api, { extractResults, type PaginatedResponse } from '../api/client'
import { useNotifications, type Notification } from '../hooks/useNotifications'
import { formatDateTime } from '../lib/utils'
import Card from '../components/ui/Card'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import EmptyState from '../components/ui/EmptyState'
import ErrorBoundary from '../components/ui/ErrorBoundary'

// Severity color derived from the backend Notification.level field.
type Severity = 'info' | 'warn' | 'danger'
const LEVEL_COLORS: Record<string, Severity> = {
  INFO: 'info',
  WARN: 'warn',
  CRITICAL: 'danger',
}

// UI filter keys -> backend Notification.notif_type values.
type FilterType = 'all' | 'expiry' | 'refills' | 'reorders' | 'tasks' | 'approvals' | 'deals'

const FILTER_NOTIF_TYPE: Record<Exclude<FilterType, 'all'>, string> = {
  expiry: 'EXPIRY_WARNING',
  refills: 'REFILL_DUE',
  reorders: 'REORDER',
  tasks: 'TASK_DUE',
  approvals: 'APPROVAL_PENDING',
  deals: 'DEAL_UPDATE',
}

const FILTERS: { key: FilterType; label: string; icon: React.ReactNode }[] = [
  { key: 'all', label: 'All', icon: <Bell size={14} /> },
  { key: 'expiry', label: 'Expiry', icon: <Clock size={14} /> },
  { key: 'refills', label: 'Refills', icon: <Pill size={14} /> },
  { key: 'reorders', label: 'Reorders', icon: <ShoppingCart size={14} /> },
  { key: 'tasks', label: 'Tasks', icon: <ClipboardList size={14} /> },
  { key: 'approvals', label: 'Approvals', icon: <CheckCheck size={14} /> },
  { key: 'deals', label: 'Deals', icon: <DollarSign size={14} /> },
]

const SEVERITY_COLORS: Record<Severity, string> = {
  info: 'var(--accent)',
  warn: 'var(--warn)',
  danger: 'var(--danger)',
}

const TYPE_ICONS: Record<string, React.ReactNode> = {
  expiry: <Clock size={16} />,
  refills: <Pill size={16} />,
  reorders: <ShoppingCart size={16} />,
  tasks: <ClipboardList size={16} />,
  approvals: <CheckCheck size={16} />,
  deals: <DollarSign size={16} />,
}

export default function NotificationCenter() {
  const navigate = useNavigate()
  const { markAllRead, markRead } = useNotifications()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeFilter, setActiveFilter] = useState<FilterType>('all')
  const [markingAll, setMarkingAll] = useState(false)

  const fetchAll = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ page_size: '200' })
      // Backend filter param is `type` and expects the notif_type value (e.g. EXPIRY_WARNING).
      if (activeFilter !== 'all') params.set('type', FILTER_NOTIF_TYPE[activeFilter])
      const data = await api.get<Notification[] | PaginatedResponse<Notification>>(`/notifications/?${params.toString()}`)
      setNotifications(extractResults(data))
    } catch {
      setError('Failed to load notifications.')
    } finally { setIsLoading(false) }
  }, [activeFilter])

  useEffect(() => { fetchAll() }, [fetchAll])

  const handleMarkAllRead = async () => {
    setMarkingAll(true)
    await markAllRead()
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })))
    setMarkingAll(false)
  }

  const handleMarkRead = async (n: Notification) => {
    if (n.read) return
    await markRead(n.id)
    setNotifications((prev) => prev.map((nn) => (nn.id === n.id ? { ...nn, read: true } : nn)))
  }

  const unreadCount = notifications.filter((n) => !n.read).length

  const filtered = activeFilter === 'all'
    ? notifications
    : notifications.filter((n) => n.notif_type === FILTER_NOTIF_TYPE[activeFilter])

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Notifications</h1>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
              {unreadCount} unread of {notifications.length} total
            </p>
          </div>
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              disabled={markingAll}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '8px 16px',
                backgroundColor: 'color-mix(in srgb, var(--accent) 10%, transparent)',
                color: 'var(--accent)',
                border: '1px solid var(--border)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.85rem', fontWeight: 500,
                cursor: markingAll ? 'wait' : 'pointer',
                opacity: markingAll ? 0.7 : 1,
              }}
            >
              <Check size={16} />
              {markingAll ? 'Marking...' : 'Mark All Read'}
            </button>
          )}
        </div>

        {/* Filter chips */}
        <Card padding="12px 16px">
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setActiveFilter(f.key)}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: '5px',
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: '0.78rem',
                  fontWeight: activeFilter === f.key ? 600 : 400,
                  border: activeFilter === f.key ? '1px solid var(--accent)' : '1px solid var(--border)',
                  backgroundColor: activeFilter === f.key
                    ? 'color-mix(in srgb, var(--accent) 12%, transparent)'
                    : 'var(--surface-2)',
                  color: activeFilter === f.key ? 'var(--accent)' : 'var(--text-muted)',
                  cursor: 'pointer',
                  transition: 'all 150ms ease',
                }}
              >
                {f.icon}
                {f.label}
              </button>
            ))}
          </div>
        </Card>

        {error && <div style={errorBannerStyle}>{error}</div>}

        {isLoading ? (
          <LoadingSpinner message="Loading notifications..." />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Bell size={48} />}
            title="No notifications"
            description={activeFilter !== 'all'
              ? `No "${FILTERS.find((f) => f.key === activeFilter)?.label}" notifications.`
              : "You're all caught up."}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {filtered.map((n) => {
              const severity = LEVEL_COLORS[n.level] ?? 'info'
              const color = SEVERITY_COLORS[severity]
              return (
                <div
                  key={n.id}
                  onClick={() => { handleMarkRead(n); if (n.link) navigate(n.link) }}
                  style={{
                    position: 'relative',
                    display: 'flex',
                    gap: '14px',
                    padding: '14px 18px',
                    backgroundColor: n.read ? 'var(--surface)' : 'var(--surface-2)',
                    border: '1px solid var(--border)',
                    borderLeft: `4px solid ${color}`,
                    borderRadius: 'var(--radius-md)',
                    cursor: n.link ? 'pointer' : 'default',
                    opacity: n.read ? 0.75 : 1,
                    transition: 'all 150ms ease',
                  }}
                  onMouseEnter={(e) => {
                    (e.currentTarget as HTMLElement).style.boxShadow = 'var(--shadow-sm)'
                  }}
                  onMouseLeave={(e) => {
                    (e.currentTarget as HTMLElement).style.boxShadow = 'none'
                  }}
                >
                  {/* Icon */}
                  <div style={{
                    width: '32px',
                    height: '32px',
                    minWidth: '32px',
                    borderRadius: '50%',
                    backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)`,
                    color,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}>
                    {TYPE_ICONS[Object.entries(FILTER_NOTIF_TYPE).find(([, nt]) => nt === n.notif_type)?.[0] ?? ''] || <Bell size={16} />}
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                        {n.title}
                      </span>
                      {!n.read && (
                        <span style={{
                          width: '8px',
                          height: '8px',
                          borderRadius: '50%',
                          backgroundColor: 'var(--accent)',
                          flexShrink: 0,
                        }} />
                      )}
                    </div>
                    <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px', lineHeight: 1.4 }}>
                      {n.body}
                    </p>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                      {formatDateTime(n.created_at)}
                    </div>
                  </div>

                  {/* Link indicator */}
                  {n.link && (
                    <div style={{ display: 'flex', alignItems: 'center', color: 'var(--text-muted)' }}>
                      <ExternalLink size={14} />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </ErrorBoundary>
  )
}

const errorBannerStyle: React.CSSProperties = {
  backgroundColor: 'color-mix(in srgb, var(--danger) 12%, transparent)',
  color: 'var(--danger)', padding: '10px 16px', borderRadius: 'var(--radius-md)',
  fontSize: '0.85rem', border: '1px solid color-mix(in srgb, var(--danger) 25%, transparent)',
}
