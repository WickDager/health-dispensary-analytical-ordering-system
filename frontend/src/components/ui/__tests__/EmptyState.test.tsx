import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import EmptyState from '../EmptyState'

describe('EmptyState', () => {
  it('renders title', () => {
    render(<EmptyState title="No items found" />)
    expect(screen.getByText('No items found')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<EmptyState title="Empty" description="There is nothing here yet." />)
    expect(screen.getByText('There is nothing here yet.')).toBeInTheDocument()
  })

  it('does not render description when omitted', () => {
    const { container } = render(<EmptyState title="Empty" />)
    expect(container.querySelector('p')).toBeNull()
  })

  it('renders action when provided', () => {
    render(<EmptyState title="Empty" action={<button>Add</button>} />)
    expect(screen.getByRole('button', { name: 'Add' })).toBeInTheDocument()
  })

  it('renders default inbox icon when no icon provided', () => {
    const { container } = render(<EmptyState title="Empty" />)
    const svg = container.querySelector('svg')
    expect(svg).toBeInTheDocument()
  })
})
