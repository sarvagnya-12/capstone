const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export const AUTH_TOKEN_STORAGE_KEY = 'dryrunai_token'

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, body: unknown, message: string) {
    super(message)
    this.status = status
    this.body = body
  }
}

/** Best-effort human-readable message from a FastAPI error body -- `detail`
 * is either a plain string or a Pydantic validation-error array. */
export function apiErrorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return 'Something went wrong. Please try again.'
  }
  const detail = (error.body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'object' && d && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join('; ')
  }
  return error.message
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  const isPreEncodedBody = options.body instanceof FormData || options.body instanceof URLSearchParams
  if (!headers.has('Content-Type') && options.body && !isPreEncodedBody) {
    headers.set('Content-Type', 'application/json')
  }

  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (response.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
    if (location.pathname !== '/login') {
      location.href = '/login'
    }
  }

  if (!response.ok) {
    let body: unknown = null
    try {
      body = await response.json()
    } catch {
      // response had no JSON body
    }
    throw new ApiError(response.status, body, `Request to ${path} failed with status ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

/** For endpoints returning a binary body (report export) rather than JSON. */
export async function apiFetchBlob(path: string, options: RequestInit = {}): Promise<Blob> {
  const headers = new Headers(options.headers)
  const token = localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers })

  if (response.status === 401) {
    localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
    if (location.pathname !== '/login') {
      location.href = '/login'
    }
  }

  if (!response.ok) {
    throw new ApiError(response.status, null, `Request to ${path} failed with status ${response.status}`)
  }

  return response.blob()
}

export { API_BASE_URL }
