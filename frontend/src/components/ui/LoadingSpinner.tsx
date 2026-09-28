interface LoadingSpinnerProps {
  size?: number
  fullPage?: boolean
  message?: string
}

export default function LoadingSpinner({ size = 32, fullPage = false, message }: LoadingSpinnerProps) {
  const spinner = (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        padding: fullPage ? '0' : '20px',
      }}
    >
      <div
        style={{
          width: `${size}px`,
          height: `${size}px`,
          border: '3px solid var(--border)',
          borderTopColor: 'var(--accent)',
          borderRadius: '50%',
          animation: 'hdaos-spin 0.7s linear infinite',
        }}
      />
      {message && (
        <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{message}</p>
      )}
      <style>{`
        @keyframes hdaos-spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )

  if (fullPage) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          backgroundColor: 'var(--bg)',
        }}
      >
        {spinner}
      </div>
    )
  }

  return spinner
}
