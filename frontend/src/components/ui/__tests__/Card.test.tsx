import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import Card from '../Card'

describe('Card', () => {
  it('renders children', () => {
    render(<Card><p>content</p></Card>)
    expect(screen.getByText('content')).toBeInTheDocument()
  })

  it('renders title when provided', () => {
    render(<Card title="My Card"><p>body</p></Card>)
    expect(screen.getByText('My Card')).toBeInTheDocument()
  })

  it('renders action when provided', () => {
    render(<Card title="Card" action={<button>Click</button>}><p>body</p></Card>)
    expect(screen.getByRole('button', { name: 'Click' })).toBeInTheDocument()
  })

  it('renders footer when provided', () => {
    render(<Card footer={<span>Footer text</span>}><p>body</p></Card>)
    expect(screen.getByText('Footer text')).toBeInTheDocument()
  })

  it('renders without title or action', () => {
    const { container } = render(<Card><p>just body</p></Card>)
    expect(container.querySelector('h3')).toBeNull()
  })
})
