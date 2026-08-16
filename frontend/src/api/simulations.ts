import { apiFetch } from './client'

export type SimulationStatus =
  | 'pending'
  | 'generating'
  | 'simulating'
  | 'evaluating'
  | 'optimizing'
  | 'completed'
  | 'failed'

export interface Simulation {
  id: string
  product_id: string
  user_id: string
  pricing_strategy: { tiers: { tier_name: string; price: number }[] }
  target_demographic: Record<string, unknown>
  promotional_messaging: string | null
  status: SimulationStatus
  iteration_count: number
  max_iterations: number
  created_at: string
  completed_at: string | null
}

export interface PricingTierInput {
  tier_name: string
  price: number
}

export interface TargetDemographicInput {
  age_min?: number
  age_max?: number
  gender?: string
  income_segment?: string
  region?: string
  lifestyle?: string
}

export interface CreateSimulationInput {
  product_id: string
  pricing_strategy: PricingTierInput[]
  target_demographic: TargetDemographicInput
  promotional_messaging?: string
  variant_count: number
  max_iterations?: number
}

export function createSimulation(input: CreateSimulationInput): Promise<Simulation> {
  return apiFetch<Simulation>('/api/v1/simulations', { method: 'POST', body: JSON.stringify(input) })
}

export function listSimulations(): Promise<Simulation[]> {
  return apiFetch<Simulation[]>('/api/v1/simulations')
}

export function getSimulationStatus(simulationId: string): Promise<Simulation> {
  return apiFetch<Simulation>(`/api/v1/simulations/${simulationId}/status`)
}

export function variantImagePath(simulationId: string, variantId: string): string {
  return `/api/v1/simulations/${simulationId}/variants/${variantId}/image`
}

export const SIMULATION_STAGE_LABELS: Record<SimulationStatus, string> = {
  pending: 'Queued',
  generating: 'Generating product variants',
  simulating: 'Simulating persona reactions',
  evaluating: 'Evaluating sentiment & risk',
  optimizing: 'Optimizing for next round',
  completed: 'Completed',
  failed: 'Failed',
}
