import { Link } from 'react-router-dom'
import { Home } from 'lucide-react'

export default function NotFound() {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '80px 20px',
        textAlign: 'center',
      }}
    >
      <div
        style={{
          fontSize: '6rem',
          fontWeight: 800,
          color: 'var(--text)',
          opacity: 0.1,
          lineHeight: 1,
          marginBottom: '8px',
          userSelect: 'none',
        }}
      >
        404
      </div>
      <h1 style={{ fontSize: '1.4rem', fontWeight: 600, color: 'var(--text)', marginBottom: '8px' }}>
        Page not found
      </h1>
      <p style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginBottom: '28px', maxWidth: '400px' }}>
        The page you are looking for does not exist or has been moved. Check the URL or navigate back to the dashboard.
      </p>
      <Link
        to="/dashboard"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '8px',
          padding: '10px 24px',
          backgroundColor: 'var(--accent)',
          color: '#fff',
          borderRadius: 'var(--radius-md)',
          fontSize: '0.9rem',
          fontWeight: 600,
          textDecoration: 'none',
        }}
      >
        <Home size={18} />
        Back to Dashboard
      </Link>
    </div>
  )
}
