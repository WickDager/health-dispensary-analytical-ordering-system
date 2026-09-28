const BASE_URL = '/api'

interface ApiErrorBody {
  detail?: string
  message?: string
  [key: string]: unknown
}

export class ApiError extends Error {
  status: number
  body: ApiErrorBody

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail || body.message || `Request failed with status ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

let isRefreshing = false
let refreshPromise: Promise<boolean> | null = null

async function refreshToken(): Promise<boolean> {
  if (isRefreshing && refreshPromise) {
    return refreshPromise
  }

  isRefreshing = true
  refreshPromise = fetch(`${BASE_URL}/auth/refresh/`, {
    method: 'POST',
    credentials: 'include',
  })
    .then((res) => {
      if (res.ok) {
        return true
      }
      return false
    })
    .catch(() => false)
    .finally(() => {
      isRefreshing = false
      refreshPromise = null
    })

  return refreshPromise
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  options?: RequestInit,
): Promise<T> {
  const url = `${BASE_URL}${path}`

  const headers: Record<string, string> = {}
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json'
  }

  const config: RequestInit = {
    method,
    headers,
    credentials: 'include',
    ...options,
  }

  if (body) {
    config.body = body instanceof FormData ? body : JSON.stringify(body)
  }

  let response = await fetch(url, config)

  // Auto-refresh on 401
  if (response.status === 401) {
    const refreshed = await refreshToken()
    if (refreshed) {
      // Retry the original request
      response = await fetch(url, config)
    }
  }

  if (!response.ok) {
    let errorBody: ApiErrorBody = {}
    try {
      errorBody = await response.json()
    } catch {
      // response may not be JSON
    }
    throw new ApiError(response.status, errorBody)
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T
  }

  return response.json()
}

// ---------------------------------------------------------------------------
// DRF pagination helpers
//
// DRF's global PageNumberPagination (PAGE_SIZE=50) wraps list endpoints in a
// {count, next, previous, results} envelope, while some endpoints (custom
// @action views, e.g. /crm/contacts/{id}/timeline/) return a bare array.
// Use extractResults() to normalize either shape into a plain array.
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export function isPaginated<T>(data: unknown): data is PaginatedResponse<T> {
  return (
    data !== null &&
    typeof data === 'object' &&
    'results' in (data as Record<string, unknown>) &&
    Array.isArray((data as Record<string, unknown>).results)
  )
}

/** Normalize a list endpoint response (paginated envelope or bare array) to an array. */
export function extractResults<T>(data: T[] | PaginatedResponse<T>): T[] {
  if (isPaginated<T>(data)) return data.results
  if (Array.isArray(data)) return data
  return []
}

/** Total item count of a list endpoint, accounting for pagination. */
export function extractCount<T>(data: T[] | PaginatedResponse<T>): number {
  if (isPaginated<T>(data)) return data.count
  if (Array.isArray(data)) return data.length
  return 0
}

const api = {
  get<T>(path: string, options?: RequestInit) {
    return request<T>('GET', path, undefined, options)
  },
  post<T>(path: string, body?: unknown, options?: RequestInit) {
    return request<T>('POST', path, body, options)
  },
  put<T>(path: string, body?: unknown, options?: RequestInit) {
    return request<T>('PUT', path, body, options)
  },
  patch<T>(path: string, body?: unknown, options?: RequestInit) {
    return request<T>('PATCH', path, body, options)
  },
  delete<T>(path: string, options?: RequestInit) {
    return request<T>('DELETE', path, undefined, options)
  },
}

export default api
