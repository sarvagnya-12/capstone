import { apiFetch } from './client'

export type UserRole = 'user' | 'admin'

export interface User {
  id: string
  org_name: string
  email: string
  role: UserRole
}

interface TokenResponse {
  access_token: string
  token_type: string
}

export function register(orgName: string, email: string, password: string): Promise<User> {
  return apiFetch<User>('/api/v1/auth/register', {
    method: 'POST',
    body: JSON.stringify({ org_name: orgName, email, password }),
  })
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const body = new URLSearchParams()
  body.set('username', email)
  body.set('password', password)
  return apiFetch<TokenResponse>('/api/v1/auth/login', { method: 'POST', body })
}

export function getCurrentUser(): Promise<User> {
  return apiFetch<User>('/api/v1/auth/me')
}
