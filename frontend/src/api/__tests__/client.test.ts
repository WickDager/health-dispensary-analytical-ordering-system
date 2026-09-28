import { describe, it, expect, vi, beforeEach } from 'vitest'
import api, { ApiError } from '../client'

const mockFetch = vi.fn()
globalThis.fetch = mockFetch as unknown as typeof fetch

beforeEach(() => {
  vi.resetAllMocks()
})

describe('ApiError', () => {
  it('uses the detail message', () => {
    const err = new ApiError(400, { detail: 'Bad input' })
    expect(err.message).toBe('Bad input')
    expect(err.status).toBe(400)
  })

  it('falls back to message field', () => {
    const err = new ApiError(500, { message: 'Server error' })
    expect(err.message).toBe('Server error')
  })

  it('falls back to generic message', () => {
    const err = new ApiError(403, {})
    expect(err.message).toBe('Request failed with status 403')
  })
})

describe('api.get', () => {
  it('makes a GET request and returns JSON', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ data: 'ok' }),
    })

    const result = await api.get('/test')
    expect(result).toEqual({ data: 'ok' })
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/test',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    )
  })

  it('throws ApiError on non-ok response', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ detail: 'Bad request' }),
    })

    await expect(api.get('/fail')).rejects.toThrow(ApiError)
  })

  it('handles 204 No Content', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: () => Promise.resolve({}),
    })

    const result = await api.delete('/resource/1')
    expect(result).toBeUndefined()
  })

  it('retries once on 401 if refresh succeeds', async () => {
    // First call: 401
    mockFetch
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: () => Promise.resolve({ detail: 'Unauthorized' }),
      })
      // Refresh call
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({}),
      })
      // Retry succeeds
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ data: 'retried' }),
      })

    const result = await api.get('/protected')
    expect(result).toEqual({ data: 'retried' })
    expect(mockFetch).toHaveBeenCalledTimes(3)
  })
})

describe('api.post', () => {
  it('sends JSON body with Content-Type header', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve({ id: '123' }),
    })

    const body = { name: 'test' }
    const result = await api.post('/items', body)

    expect(result).toEqual({ id: '123' })
    const call = mockFetch.mock.calls[0]
    expect(call[1].headers['Content-Type']).toBe('application/json')
    expect(call[1].body).toBe(JSON.stringify(body))
  })

  it('does not set Content-Type for FormData', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: () => Promise.resolve({}),
    })

    const formData = new FormData()
    await api.post('/upload', formData)

    const call = mockFetch.mock.calls[0]
    expect(call[1].headers['Content-Type']).toBeUndefined()
  })
})

describe('api.patch', () => {
  it('sends a PATCH request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ updated: true }),
    })

    const result = await api.patch('/item/1', { name: 'new' })
    expect(result).toEqual({ updated: true })
    expect(mockFetch.mock.calls[0][1].method).toBe('PATCH')
  })
})

describe('api.delete', () => {
  it('sends a DELETE request', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      status: 204,
      json: () => Promise.resolve({}),
    })

    await api.delete('/item/1')
    expect(mockFetch.mock.calls[0][1].method).toBe('DELETE')
  })
})
