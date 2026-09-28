import type { ReactNode } from 'react'

interface CardProps {
  title?: string
  action?: ReactNode
  children: ReactNode
  footer?: ReactNode
  className?: string
  padding?: string
}

export default function Card({ title, action, children, footer, className, padding }: CardProps) {
  return (
    <div
      className={className}
      style={{
        backgroundColor: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {(title || action) && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: padding || '16px 20px',
            borderBottom: '1px solid var(--border)',
          }}
        >
          {title && (
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text)' }}>
              {title}
            </h3>
          )}
          {action && <div>{action}</div>}
        </div>
      )}

      <div style={{ padding: padding || '20px', flex: 1 }}>
        {children}
      </div>

      {footer && (
        <div
          style={{
            padding: padding || '12px 20px',
            borderTop: '1px solid var(--border)',
          }}
        >
          {footer}
        </div>
      )}
    </div>
  )
}
