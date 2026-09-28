import { useState, useEffect, useCallback } from 'react'
import {
  Bell,
  BellOff,
  Mail,
  AlertTriangle,
  Info,
  ShieldAlert,
  Package,
  Truck,
  AlertCircle,
  FileText,
  Save,
} from 'lucide-react'
import api from '../api/client'
import { useRoleAccess } from '../hooks/useRoleAccess'
import Card from '../components/ui/Card'
import Badge from '../components/ui/Badge'
import LoadingSpinner from '../components/ui/LoadingSpinner'
import EmptyState from '../components/ui/EmptyState'
import ErrorBoundary from '../components/ui/ErrorBoundary'

type SeverityLevel = 'info' | 'warning' | 'critical'

interface NotificationTypeSetting {
  id: number
  notification_type: string
  type_label: string
  description: string
  icon_key: string
  is_muted: boolean
  force_email: boolean
  severity_filter: SeverityLevel[]
}

interface GlobalSettings {
  digest_mode: 'realtime' | 'daily' | 'weekly'
  quiet_hours_start: string
  quiet_hours_end: string
}

const SEVERITY_LEVELS: { key: SeverityLevel; label: string; color: string; icon: React.ReactNode }[] = [
  { key: 'info', label: 'Info', color: 'var(--text-muted)', icon: <Info size={14} /> },
  { key: 'warning', label: 'Warning', color: 'var(--warn)', icon: <AlertTriangle size={14} /> },
  { key: 'critical', label: 'Critical', color: 'var(--danger)', icon: <ShieldAlert size={14} /> },
]

const NOTIFICATION_ICONS: Record<string, React.ReactNode> = {
  expiry: <AlertCircle size={22} />,
  refill: <Package size={22} />,
  reorder: <Truck size={22} />,
  anomaly: <AlertTriangle size={22} />,
  approval: <ShieldAlert size={22} />,
  system: <Info size={22} />,
  document: <FileText size={22} />,
}

const DIGEST_MODES = [
  { value: 'realtime' as const, label: 'Real-time', description: 'Send notifications immediately' },
  { value: 'daily' as const, label: 'Daily Digest', description: 'Bundle into one daily summary' },
  { value: 'weekly' as const, label: 'Weekly Digest', description: 'Bundle into one weekly summary' },
]

const DEFAULT_NOTIFICATION_TYPES: NotificationTypeSetting[] = [
  {
    id: 1,
    notification_type: 'expiry',
    type_label: 'Expiry Alerts',
    description: 'Warnings when inventory items near expiration',
    icon_key: 'expiry',
    is_muted: false,
    force_email: false,
    severity_filter: ['warning', 'critical'],
  },
  {
    id: 2,
    notification_type: 'refill',
    type_label: 'Refill Reminders',
    description: 'Reminders for patient medication refills',
    icon_key: 'refill',
    is_muted: false,
    force_email: false,
    severity_filter: ['info', 'warning'],
  },
  {
    id: 3,
    notification_type: 'reorder',
    type_label: 'Reorder Alerts',
    description: 'Low stock and reorder point notifications',
    icon_key: 'reorder',
    is_muted: false,
    force_email: true,
    severity_filter: ['warning', 'critical'],
  },
  {
    id: 4,
    notification_type: 'anomaly',
    type_label: 'Anomaly Detection',
    description: 'Unusual patterns detected in dispense or orders',
    icon_key: 'anomaly',
    is_muted: false,
    force_email: false,
    severity_filter: ['warning', 'critical'],
  },
  {
    id: 5,
    notification_type: 'approval',
    type_label: 'Approval Requests',
    description: 'Maker-checker approval workflow notifications',
    icon_key: 'approval',
    is_muted: false,
    force_email: false,
    severity_filter: ['info'],
  },
  {
    id: 6,
    notification_type: 'system',
    type_label: 'System Notifications',
    description: 'Maintenance, updates, and system health alerts',
    icon_key: 'system',
    is_muted: false,
    force_email: false,
    severity_filter: ['info', 'warning', 'critical'],
  },
  {
    id: 7,
    notification_type: 'document',
    type_label: 'Document Processing',
    description: 'AI document ingestion completion and errors',
    icon_key: 'document',
    is_muted: false,
    force_email: false,
    severity_filter: ['info', 'warning'],
  },
]

export default function SettingsNotifications() {
  const { isAdmin } = useRoleAccess()
  const [typeSettings, setTypeSettings] = useState<NotificationTypeSetting[]>(DEFAULT_NOTIFICATION_TYPES)
  const [global, setGlobal] = useState<GlobalSettings>({
    digest_mode: 'realtime',
    quiet_hours_start: '',
    quiet_hours_end: '',
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [isSaving, setIsSaving] = useState(false)

  const fetchSettings = useCallback(async () => {
    setIsLoading(true)
    setError('')
    try {
      const [types, glob] = await Promise.all([
        api.get<NotificationTypeSetting[]>('/settings/notification-types/'),
        api.get<GlobalSettings>('/settings/notification-global/'),
      ])
      if (Array.isArray(types) && types.length > 0) setTypeSettings(types)
      if (glob) setGlobal(glob)
    } catch {
      // Use defaults if API unavailable
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSettings()
  }, [fetchSettings])

  const toggleMute = (n: NotificationTypeSetting) => {
    setTypeSettings((prev) =>
      prev.map((ts) => (ts.id === n.id ? { ...ts, is_muted: !ts.is_muted } : ts)),
    )
  }

  const toggleForceEmail = (n: NotificationTypeSetting) => {
    setTypeSettings((prev) =>
      prev.map((ts) => (ts.id === n.id ? { ...ts, force_email: !ts.force_email } : ts)),
    )
  }

  const toggleSeverity = (n: NotificationTypeSetting, level: SeverityLevel) => {
    setTypeSettings((prev) =>
      prev.map((ts) => {
        if (ts.id !== n.id) return ts
        const current = ts.severity_filter
        const updated = current.includes(level)
          ? current.filter((l) => l !== level)
          : [...current, level]
        return { ...ts, severity_filter: updated }
      }),
    )
  }

  const updateGlobal = (field: keyof GlobalSettings, value: string) => {
    setGlobal((prev) => ({ ...prev, [field]: value }))
  }

  const handleSave = async () => {
    setIsSaving(true)
    setError('')
    setSuccess('')
    try {
      await Promise.all([
        api.patch('/settings/notification-types/bulk/', { types: typeSettings }),
        api.patch('/settings/notification-global/', global),
      ])
      setSuccess('Notification preferences saved successfully.')
    } catch {
      setError('Failed to save notification preferences.')
    } finally {
      setIsSaving(false)
    }
  }

  if (!isAdmin) {
    return (
      <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>Access Denied</h2>
        <p style={{ fontSize: '0.85rem', marginTop: '4px' }}>Only administrators can manage notification settings.</p>
      </div>
    )
  }

  if (isLoading) {
    return <LoadingSpinner message="Loading notification settings..." />
  }

  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {error && <div style={errorBannerStyle}>{error}</div>}
        {success && <div style={successBannerStyle}>{success}</div>}

        {/* Global Settings */}
        <Card title="Global Settings">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '500px' }}>
            {/* Digest Mode */}
            <div>
              <label style={labelStyle}>Digest Mode</label>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                {DIGEST_MODES.map((mode) => (
                  <button
                    key={mode.value}
                    onClick={() => updateGlobal('digest_mode', mode.value)}
                    style={{
                      flex: '1 1 140px',
                      padding: '12px',
                      borderRadius: 'var(--radius-md)',
                      border: global.digest_mode === mode.value
                        ? '2px solid var(--accent)'
                        : '1px solid var(--border)',
                      backgroundColor: global.digest_mode === mode.value
                        ? 'color-mix(in srgb, var(--accent) 8%, var(--surface))'
                        : 'var(--surface)',
                      cursor: 'pointer',
                      textAlign: 'center',
                      transition: 'all 150ms ease',
                    }}
                  >
                    <div style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text)' }}>
                      {mode.label}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {mode.description}
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* Quiet Hours */}
            <div>
              <label style={labelStyle}>Quiet Hours</label>
              <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
                Notifications will be suppressed during this time range (except critical alerts).
              </p>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={subLabelStyle}>Start</label>
                  <input
                    type="time"
                    value={global.quiet_hours_start}
                    onChange={(e) => updateGlobal('quiet_hours_start', e.target.value)}
                    style={inputStyle}
                  />
                </div>
                <div>
                  <label style={subLabelStyle}>End</label>
                  <input
                    type="time"
                    value={global.quiet_hours_end}
                    onChange={(e) => updateGlobal('quiet_hours_end', e.target.value)}
                    style={inputStyle}
                  />
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* Notification Types */}
        <Card title="Notification Types">
          {typeSettings.length === 0 ? (
            <EmptyState
              icon={<Bell size={48} />}
              title="No notification types configured"
              description="Notification types will appear here once configured."
            />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {typeSettings.map((n) => (
                <div
                  key={n.id}
                  style={{
                    padding: '16px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: n.is_muted ? 'var(--surface-2)' : 'var(--surface)',
                    border: '1px solid var(--border)',
                    opacity: n.is_muted ? 0.65 : 1,
                    transition: 'all 200ms ease',
                  }}
                >
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '14px',
                      flexWrap: 'wrap',
                    }}
                  >
                    {/* Icon */}
                    <div
                      style={{
                        color: n.is_muted ? 'var(--text-muted)' : 'var(--accent)',
                        flexShrink: 0,
                        marginTop: '2px',
                      }}
                    >
                      {NOTIFICATION_ICONS[n.icon_key] || <Bell size={22} />}
                    </div>

                    {/* Info */}
                    <div style={{ flex: 1, minWidth: '180px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span
                          style={{
                            fontWeight: 600,
                            fontSize: '0.9rem',
                            color: n.is_muted ? 'var(--text-muted)' : 'var(--text)',
                          }}
                        >
                          {n.type_label}
                        </span>
                        {n.is_muted && <Badge variant="danger" size="sm">Muted</Badge>}
                        {n.force_email && <Badge variant="accent" size="sm">Email</Badge>}
                      </div>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {n.description}
                      </p>
                    </div>

                    {/* Controls */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        flexShrink: 0,
                      }}
                    >
                      {/* Mute Toggle */}
                      <button
                        onClick={() => toggleMute(n)}
                        style={iconBtnStyle}
                        title={n.is_muted ? 'Unmute' : 'Mute'}
                      >
                        {n.is_muted ? (
                          <BellOff size={20} style={{ color: 'var(--danger)' }} />
                        ) : (
                          <Bell size={20} style={{ color: 'var(--ok)' }} />
                        )}
                      </button>

                      {/* Force Email */}
                      <button
                        onClick={() => toggleForceEmail(n)}
                        style={iconBtnStyle}
                        title={n.force_email ? 'Disable email' : 'Force email'}
                      >
                        <Mail
                          size={20}
                          style={{
                            color: n.force_email ? 'var(--accent)' : 'var(--text-muted)',
                            opacity: n.force_email ? 1 : 0.4,
                          }}
                        />
                      </button>
                    </div>
                  </div>

                  {/* Severity Filter Checkboxes */}
                  <div
                    style={{
                      marginTop: '12px',
                      paddingTop: '12px',
                      borderTop: '1px solid var(--border)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      flexWrap: 'wrap',
                    }}
                  >
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 500,
                        color: 'var(--text-muted)',
                        marginRight: '4px',
                      }}
                    >
                      Trigger on:
                    </span>
                    {SEVERITY_LEVELS.map((sev) => {
                      const checked = n.severity_filter.includes(sev.key)
                      return (
                        <label
                          key={sev.key}
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '3px 8px',
                            borderRadius: 'var(--radius-sm)',
                            fontSize: '0.72rem',
                            fontWeight: 500,
                            cursor: n.is_muted ? 'default' : 'pointer',
                            color: checked ? sev.color : 'var(--text-muted)',
                            backgroundColor: checked
                              ? `color-mix(in srgb, ${sev.color} 12%, transparent)`
                              : 'var(--surface-2)',
                            border: `1px solid ${checked ? sev.color : 'var(--border)'}`,
                            opacity: n.is_muted ? 0.5 : 1,
                            transition: 'all 150ms ease',
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleSeverity(n, sev.key)}
                            disabled={n.is_muted}
                            style={{
                              accentColor: sev.color,
                              width: '13px',
                              height: '13px',
                              cursor: n.is_muted ? 'default' : 'pointer',
                            }}
                          />
                          {sev.icon}
                          {sev.label}
                        </label>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {/* Save Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button onClick={handleSave} disabled={isSaving} style={saveBtnStyle}>
            <Save size={16} />
            {isSaving ? 'Saving...' : 'Save Notification Preferences'}
          </button>
        </div>
      </div>
    </ErrorBoundary>
  )
}

const labelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.85rem',
  fontWeight: 600,
  color: 'var(--text)',
  marginBottom: '6px',
}

const subLabelStyle: React.CSSProperties = {
  display: 'block',
  fontSize: '0.75rem',
  fontWeight: 500,
  color: 'var(--text-muted)',
  marginBottom: '4px',
}

const inputStyle: React.CSSProperties = {
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

const iconBtnStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: '4px',
  borderRadius: 'var(--radius-sm)',
  display: 'flex',
  transition: 'background-color 150ms ease',
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
