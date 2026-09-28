import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import LoadingSpinner from '../LoadingSpinner'

describe('LoadingSpinner', () => {
  it('renders a spinner element', () => {
    const { container } = render(<LoadingSpinner />)
    const spinnerDiv = container.querySelector('[style*="animation"]')
    expect(spinnerDiv).toBeInTheDocument()
  })

  it('renders message when provided', () => {
    render(<LoadingSpinner message="Loading data..." />)
    expect(screen.getByText('Loading data...')).toBeInTheDocument()
  })

  it('does not render message when omitted', () => {
    const { container } = render(<LoadingSpinner />)
    expect(container.querySelector('p')).toBeNull()
  })

  it('renders full-page variant', () => {
    const { container } = render(<LoadingSpinner fullPage />)
    const outerDiv = container.firstChild as HTMLElement
    expect(outerDiv.style.minHeight).toBe('100vh')
  })

  it('renders at custom size', () => {
    const { container } = render(<LoadingSpinner size={48} />)
    const spinnerDiv = container.querySelector('[style*="animation"]') as HTMLElement
    expect(spinnerDiv.style.width).toBe('48px')
    expect(spinnerDiv.style.height).toBe('48px')
  })
})
