import { apiFetch } from './client'
import type { User } from './auth'
import type { Simulation } from './simulations'

export function listAllUsers(): Promise<User[]> {
  return apiFetch<User[]>('/api/v1/admin/users')
}

export function listAllSimulations(): Promise<Simulation[]> {
  return apiFetch<Simulation[]>('/api/v1/admin/simulations')
}
