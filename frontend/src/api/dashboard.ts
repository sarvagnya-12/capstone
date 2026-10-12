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

/** Business-facing summary (backend app/services/insights_service.py) --
 * what the dashboard shows to non-technical readers. */
export interface CustomerReaction {
  profile: string
  buying_intent: 'Likely to buy' | 'Undecided' | 'Unlikely to buy'
  likelihood_pct: number
  reaction: 'Positive' | 'Neutral' | 'Critical' | 'Not classified'
  comment: string
}

export interface OptionInsight {
  variant_id: string
  label: string
  colourway: string
  rank: number
  is_recommended: boolean
  purchase_intent_pct: number
  interest_level: 'Strong' | 'Moderate' | 'Low'
  likely_buyers: number
  undecided: number
  unlikely_buyers: number
  profiles: number
  liked: number
  neutral: number
  disliked: number
  reception: string
  appeals_most_to: string[]
  least_interested: string[]
  best_quote: CustomerReaction | null
  worst_quote: CustomerReaction | null
  concerns: string[]
  themes: { topic: string; mentions: number }[]
  reactions: CustomerReaction[]
}

export interface SimulationInsights {
  product_name: string
  product_brand: string | null
  product_category: string | null
  price_text: string
  audience_text: string
  messaging: string | null
  profiles_tested: number
  options_tested: number
  rounds_run: number
  verdict: string
  bottom_line: string
  recommended_label: string
  options: OptionInsight[]
  next_steps: string[]
  disclaimer: string
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
  insights: SimulationInsights
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
  anchor.download = `launch_report_${simulationId.slice(0, 8)}.${format}`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}
