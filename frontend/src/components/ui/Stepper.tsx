import { cn } from '../../lib/utils'

interface Step {
  label: string
  description?: string
}

interface StepperProps {
  steps: Step[]
  activeStep: number
  orientation?: 'horizontal' | 'vertical'
}

export default function Stepper({ steps, activeStep, orientation = 'horizontal' }: StepperProps) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: orientation === 'vertical' ? 'column' : 'row',
        alignItems: orientation === 'vertical' ? 'flex-start' : 'center',
        gap: orientation === 'vertical' ? '0' : '0',
      }}
    >
      {steps.map((step, idx) => {
        const isCompleted = idx < activeStep
        const isActive = idx === activeStep
        const isLast = idx === steps.length - 1

        return (
          <div
            key={idx}
            style={{
              display: 'flex',
              alignItems: orientation === 'vertical' ? 'flex-start' : 'center',
              flex: orientation === 'horizontal' ? 1 : undefined,
              gap: '8px',
            }}
          >
            {/* Step indicator + label */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                flexDirection: orientation === 'horizontal' ? 'column' : 'row',
              }}
            >
              {/* Circle */}
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  minWidth: '32px',
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.8rem',
                  fontWeight: 700,
                  backgroundColor: isCompleted
                    ? 'var(--ok)'
                    : isActive
                      ? 'var(--accent)'
                      : 'var(--surface-2)',
                  color: isCompleted || isActive ? '#fff' : 'var(--text-muted)',
                  border: isCompleted || isActive ? 'none' : '2px solid var(--border)',
                  transition: 'all 200ms ease',
                }}
              >
                {isCompleted ? '✓' : idx + 1}
              </div>

              {/* Label */}
              <div
                style={{
                  textAlign: orientation === 'horizontal' ? 'center' : 'left',
                  whiteSpace: 'nowrap',
                }}
              >
                <div
                  style={{
                    fontSize: '0.8rem',
                    fontWeight: isActive ? 600 : 400,
                    color: isActive ? 'var(--accent)' : 'var(--text)',
                  }}
                >
                  {step.label}
                </div>
                {step.description && (
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {step.description}
                  </div>
                )}
              </div>
            </div>

            {/* Connecting line */}
            {!isLast && (
              <div
                style={{
                  flex: orientation === 'horizontal' ? 1 : undefined,
                  height: orientation === 'horizontal' ? '2px' : '28px',
                  width: orientation === 'vertical' ? '2px' : undefined,
                  backgroundColor: isCompleted ? 'var(--ok)' : 'var(--border)',
                  marginTop: orientation === 'vertical' ? '4px' : undefined,
                  marginLeft: orientation === 'vertical' ? '15px' : undefined,
                  marginRight: orientation === 'horizontal' ? '8px' : undefined,
                  marginBottom: orientation === 'horizontal' ? '20px' : undefined,
                  transition: 'background-color 200ms ease',
                }}
              />
            )}
          </div>
        )
      })}
    </div>
  )
}
