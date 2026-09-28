import { type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface KpiCardProps {
  icon: ReactNode
  label: string
  value: string | number
  trend?: {
    direction: 'up' | 'down'
    value: string
    label?: string
  }
  linkTo?: string
}

export default function KpiCard({ icon, label, value, trend, linkTo }: KpiCardProps) {
  const content = (
    <div
      style={{
        backgroundColor: 'var(--surface)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        transition: 'box-shadow 200ms ease, border-color 200ms ease',
      }}
      onMouseEnter={(e) => {
        const el = e.currentTarget as HTMLElement
        el.style.boxShadow = 'var(--shadow-md)'
        el.style.borderColor = 'var(--accent)'
      }}
      onMouseLeave={(e) => {
        const el = e.currentTarget as HTMLElement
        el.style.boxShadow = 'var(--shadow-sm)'
        el.style.borderColor = 'var(--border)'
      }}
    >
      {/* Top row: icon + trend */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'color-mix(in srgb, var(--accent) 12%, transparent)',
            color: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </div>

        {trend && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
              fontSize: '0.8rem',
              fontWeight: 600,
              color: trend.direction === 'up' ? 'var(--ok)' : 'var(--danger)',
            }}
          >
            {trend.direction === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
            {trend.value}
          </div>
        )}
      </div>

      {/* Value */}
      <div>
        <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text)', lineHeight: 1.1 }}>
          {value}
        </div>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
          {label}
        </div>
      </div>

      {trend?.label && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {trend.label}
        </div>
      )}
    </div>
  )

  if (linkTo) {
    return (
      <Link to={linkTo} style={{ textDecoration: 'none' }}>
        {content}
      </Link>
    )
  }

  return content
}
