import { cn } from '../../lib/utils'

type BadgeVariant = 'ok' | 'warn' | 'danger' | 'info' | 'accent'
type BadgeSize = 'sm' | 'md'

interface BadgeProps {
  variant?: BadgeVariant
  size?: BadgeSize
  dot?: boolean
  children: React.ReactNode
  className?: string
}

const variantStyles: Record<BadgeVariant, { bg: string; color: string }> = {
  ok: { bg: 'color-mix(in srgb, var(--ok) 15%, transparent)', color: 'var(--ok)' },
  warn: { bg: 'color-mix(in srgb, var(--warn) 15%, transparent)', color: 'var(--warn)' },
  danger: { bg: 'color-mix(in srgb, var(--danger) 15%, transparent)', color: 'var(--danger)' },
  info: { bg: 'color-mix(in srgb, var(--text-muted) 12%, transparent)', color: 'var(--text-muted)' },
  accent: { bg: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' },
}

export default function Badge({
  variant = 'info',
  size = 'md',
  dot = false,
  children,
  className,
}: BadgeProps) {
  const style = variantStyles[variant]

  return (
    <span
      className={cn(className)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: dot ? '5px' : '0',
        backgroundColor: style.bg,
        color: style.color,
        padding: size === 'sm' ? '1px 6px' : '3px 10px',
        fontSize: size === 'sm' ? '0.7rem' : '0.78rem',
        fontWeight: 600,
        borderRadius: 'var(--radius-sm)',
        lineHeight: 1.4,
        whiteSpace: 'nowrap',
      }}
    >
      {dot && (
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: style.color,
            flexShrink: 0,
          }}
        />
      )}
      {children}
    </span>
  )
}
