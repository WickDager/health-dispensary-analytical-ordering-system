import { describe, it, expect } from 'vitest'
import { cn, formatCurrency, formatDate, formatDateTime, getInitials } from '../utils'

describe('cn', () => {
  it('joins class names with a space', () => {
    expect(cn('a', 'b', 'c')).toBe('a b c')
  })

  it('filters out falsy values', () => {
    expect(cn('a', false, undefined, null, 'b')).toBe('a b')
  })

  it('returns empty string for no truthy args', () => {
    expect(cn(false, undefined, null)).toBe('')
  })

  it('handles a single class', () => {
    expect(cn('flex')).toBe('flex')
  })
})

describe('formatCurrency', () => {
  it('formats whole dollars', () => {
    expect(formatCurrency(100)).toBe('$100.00')
  })

  it('formats cents', () => {
    expect(formatCurrency(99.5)).toBe('$99.50')
  })

  it('formats zero', () => {
    expect(formatCurrency(0)).toBe('$0.00')
  })

  it('formats large numbers with commas', () => {
    expect(formatCurrency(1234567.89)).toBe('$1,234,567.89')
  })
})

describe('formatDate', () => {
  it('formats an ISO date string', () => {
    const result = formatDate('2026-07-16T00:00:00Z')
    expect(result).toContain('Jul')
    expect(result).toContain('16')
    expect(result).toContain('2026')
  })

  it('handles a date-only string', () => {
    const result = formatDate('2026-12-25')
    expect(result).toContain('Dec')
    expect(result).toContain('25')
  })
})

describe('formatDateTime', () => {
  it('includes time in the output', () => {
    const result = formatDateTime('2026-07-16T14:30:00Z')
    expect(result).toContain('Jul')
    expect(result).toContain('16')
    // Should contain hour info (2:30 PM or 14:30 depending on locale)
    expect(result).toMatch(/30/)
  })
})

describe('getInitials', () => {
  it('returns initials from first and last name', () => {
    expect(getInitials('John', 'Doe')).toBe('JD')
  })

  it('handles missing first name', () => {
    expect(getInitials(undefined, 'Smith')).toBe('S')
  })

  it('handles missing last name', () => {
    expect(getInitials('Jane')).toBe('J')
  })

  it('handles missing both names', () => {
    expect(getInitials()).toBe('?')
  })

  it('uppercases lowercase input', () => {
    expect(getInitials('alice', 'jones')).toBe('AJ')
  })
})
