import { useState, useCallback, useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import Navbar from './Navbar'
import { useNotifications } from '../../hooks/useNotifications'
import type { Notification } from '../../hooks/useNotifications'

const SIDEBAR_COLLAPSED_KEY = 'hdaos_sidebar_collapsed'

function getStoredCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === 'true'
  } catch {
    return false
  }
}

export default function AppLayout() {
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(getStoredCollapsed)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications()

  // Keyboard shortcut: Alt+B to go back, Alt+N for notifications
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.altKey && e.key === 'b') {
        e.preventDefault()
        navigate(-1)
      }
      if (e.altKey && e.key === 'n') {
        e.preventDefault()
        setNotificationsOpen(prev => !prev)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate])

  const toggleSidebar = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next))
      } catch {
        // ignore
      }
      return next
    })
  }, [])

  const toggleNotifications = useCallback(() => {
    setNotificationsOpen((prev) => !prev)
  }, [])

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        backgroundColor: 'var(--bg)',
      }}
    >
      <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />

      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          marginLeft: collapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)',
          transition: 'margin-left 200ms ease',
          minWidth: 0,
        }}
      >
        <Navbar
          onToggleNotifications={toggleNotifications}
          unreadCount={unreadCount}
        />

        <main
          style={{
            flex: 1,
            padding: '24px',
            overflowY: 'auto',
          }}
        >
          <Outlet />
        </main>
      </div>

      {/* Notification Center Overlay */}
      {notificationsOpen && (
        <>
          <div
            onClick={() => setNotificationsOpen(false)}
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 40,
              backgroundColor: 'rgba(0,0,0,0.3)',
            }}
          />
          <div
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: '380px',
              maxWidth: '100vw',
              zIndex: 50,
              backgroundColor: 'var(--surface)',
              borderLeft: '1px solid var(--border)',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: 'var(--shadow-lg)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '16px 20px',
                borderBottom: '1px solid var(--border)',
              }}
            >
              <h2 style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text)' }}>
                Notifications
              </h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                {unreadCount > 0 && (
                  <button
                    onClick={markAllRead}
                    style={{
                      fontSize: '0.8rem',
                      color: 'var(--accent)',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    Mark all read
                  </button>
                )}
                <button
                  onClick={() => setNotificationsOpen(false)}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    fontSize: '1.2rem',
                    cursor: 'pointer',
                    lineHeight: 1,
                  }}
                  aria-label="Close notifications"
                >
                  &times;
                </button>
              </div>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
              {notifications.length === 0 ? (
                <p style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No new notifications
                </p>
              ) : (
                notifications.map((n: Notification) => (
                  <div
                    key={n.id}
                    style={{
                      padding: '12px 20px',
                      borderBottom: '1px solid var(--border)',
                      cursor: 'pointer',
                      transition: 'background 150ms',
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.backgroundColor = 'var(--surface-2)'
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent'
                    }}
                    onClick={() => markRead(n.id)}
                  >
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text)' }}>
                      {n.title}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {n.body}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '4px', opacity: 0.7 }}>
                      {new Date(n.created_at).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
