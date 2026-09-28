import { NavLink, Outlet } from 'react-router-dom'
import ErrorBoundary from '../components/ui/ErrorBoundary'

const TABS = [
  { to: '/settings/providers', label: 'Providers', icon: 'Zap' },
  { to: '/settings/theme', label: 'Theme', icon: 'Palette' },
  { to: '/settings/ai', label: 'AI Intelligence', icon: 'Brain' },
  { to: '/settings/notifications', label: 'Notifications', icon: 'Bell' },
  { to: '/settings/users', label: 'Users', icon: 'Users' },
]

const iconMap: Record<string, string> = {
  Zap: '⚡',
  Palette: '🎨',
  Brain: '🧠',
  Bell: '🔔',
  Users: '👥',
}

export default function SettingsLayout() {
  return (
    <ErrorBoundary>
      <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
        {/* Settings Header */}
        <div style={{ padding: '0 0 16px 0' }}>
          <h1 style={{ fontSize: '1.5rem', fontWeight: 700, color: 'var(--text)' }}>Settings</h1>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '2px' }}>
            Configure system preferences, AI providers, notifications, and user access
          </p>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: 'flex',
            gap: '2px',
            borderBottom: '1px solid var(--border)',
            marginBottom: '24px',
            overflowX: 'auto',
          }}
        >
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '10px 16px',
                fontSize: '0.85rem',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--accent)' : 'var(--text-muted)',
                borderBottom: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                textDecoration: 'none',
                whiteSpace: 'nowrap',
                transition: 'all 150ms ease',
                marginBottom: '-1px',
              })}
            >
              <span style={{ fontSize: '0.9rem' }}>{iconMap[tab.icon] || ''}</span>
              {tab.label}
            </NavLink>
          ))}
        </div>

        {/* Page Content */}
        <div style={{ flex: 1 }}>
          <Outlet />
        </div>
      </div>
    </ErrorBoundary>
  )
}
