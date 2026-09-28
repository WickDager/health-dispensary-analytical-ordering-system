import { Link } from 'react-router-dom'
import { ChevronRight, Home } from 'lucide-react'

interface Crumb {
  label: string
  to?: string
}

interface BreadcrumbsProps {
  items: Crumb[]
  backTo?: { to: string; label: string }
}

export default function Breadcrumbs({ items, backTo }: BreadcrumbsProps) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
      {/* Back button */}
      {backTo && (
        <Link
          to={backTo.to}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            padding: '6px 12px',
            borderRadius: 'var(--radius-md)',
            backgroundColor: 'var(--surface-2)',
            border: '1px solid var(--border)',
            color: 'var(--text)',
            fontSize: '0.82rem',
            fontWeight: 500,
            textDecoration: 'none',
            cursor: 'pointer',
            transition: 'all 150ms ease',
            minHeight: '36px',
            minWidth: '36px',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--surface)'
            e.currentTarget.style.borderColor = 'var(--accent)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--surface-2)'
            e.currentTarget.style.borderColor = 'var(--border)'
          }}
          title={`Back to ${backTo.label}`}
        >
          ← Back
        </Link>
      )}

      {/* Breadcrumb trail */}
      <nav aria-label="Breadcrumb" style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
        <Link
          to="/dashboard"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '6px 8px',
            color: 'var(--text-muted)',
            textDecoration: 'none',
            fontSize: '0.82rem',
            borderRadius: 'var(--radius-sm)',
            minHeight: '32px',
            minWidth: '32px',
          }}
          title="Dashboard"
        >
          <Home size={16} />
        </Link>

        {items.map((crumb, i) => (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <ChevronRight size={14} style={{ color: 'var(--text-muted)', opacity: 0.5 }} />
            {crumb.to ? (
              <Link
                to={crumb.to}
                style={{
                  padding: '6px 8px',
                  color: 'var(--text-muted)',
                  textDecoration: 'none',
                  fontSize: '0.82rem',
                  borderRadius: 'var(--radius-sm)',
                  minHeight: '32px',
                  display: 'inline-flex',
                  alignItems: 'center',
                }}
              >
                {crumb.label}
              </Link>
            ) : (
              <span
                style={{
                  padding: '6px 8px',
                  color: 'var(--text)',
                  fontWeight: 600,
                  fontSize: '0.82rem',
                }}
              >
                {crumb.label}
              </span>
            )}
          </div>
        ))}
      </nav>
    </div>
  )
}
