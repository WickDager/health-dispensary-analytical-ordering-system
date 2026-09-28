import { Bell } from 'lucide-react'

interface NotificationBellProps {
  unreadCount: number
  onClick: () => void
}

export default function NotificationBell({ unreadCount, onClick }: NotificationBellProps) {
  return (
    <button
      onClick={onClick}
      title="Notifications"
      style={{
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: '6px',
        borderRadius: 'var(--radius-sm)',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
      }}
    >
      <Bell size={18} style={{ color: 'var(--text-muted)' }} />
      {unreadCount > 0 && (
        <span
          style={{
            position: 'absolute',
            top: '2px',
            right: '2px',
            minWidth: '16px',
            height: '16px',
            borderRadius: '8px',
            backgroundColor: 'var(--danger)',
            color: '#fff',
            fontSize: '0.6rem',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '0 4px',
            lineHeight: 1,
          }}
        >
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  )
}
