import { apiFetch, apiFetchBlob } from './client'

export interface SentimentBreakdown {
  positive: number
  negative: number
  neutral: number
  unclassified: number
}

export interface PersonaFeedbackEntry {
  persona_id: string
  persona_name: string
  qualitative_text: string
  purchase_likelihood: number
  sentiment_label: 'positive' | 'negative' | 'neutral' | null
}

export interface RiskFlag {
  rule: string
  severity: string
  detail: string
}

export interface VariantAnalytics {
  variant_id: string
  rank: number
  pmf_score: number
  is_recommended: boolean
  sentiment: SentimentBreakdown
  avg_purchase_likelihood: number | null
  avg_engagement_score: number | null
  risk_flags: RiskFlag[]
  fid_score: number | null
  feedback: PersonaFeedbackEntry[]
}

export interface SimulationAnalytics {
  simulation_id: string
  status: string
  final_iteration: number
  recommended_variant_id: string
  pmf_score: number
  summary_text: string
  scenario: Record<string, unknown>
  variants: VariantAnalytics[]
}

export function getSimulationAnalytics(simulationId: string): Promise<SimulationAnalytics> {
  return apiFetch<SimulationAnalytics>(`/api/v1/simulations/${simulationId}/analytics`)
}

/** Triggers a browser-native file save via the standard anchor-download
 * pattern (Step 37's own spec) -- the blob must be fetched with an auth
 * header first since the report endpoint is ownership-scoped, not a plain
 * downloadable link. */
export async function downloadReport(simulationId: string, format: 'csv' | 'pdf'): Promise<void> {
  const blob = await apiFetchBlob(`/api/v1/simulations/${simulationId}/report?format=${format}`)
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `simulation_${simulationId}.${format}`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
