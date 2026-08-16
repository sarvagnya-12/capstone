import { variantImagePath } from '../api/simulations'
import type { VariantAnalytics } from '../api/dashboard'
import AuthenticatedImage from './AuthenticatedImage'
import PersonaFeedbackList from './PersonaFeedbackList'
import PMFScoreGauge from './PMFScoreGauge'
import RiskAlertList from './RiskAlertList'
import SentimentChart from './SentimentChart'

export default function VariantCard({ simulationId, variant }: { simulationId: string; variant: VariantAnalytics }) {
  return (
    <div className="card" style={{ border: variant.is_recommended ? '2px solid var(--color-primary)' : undefined }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <h3>Rank #{variant.rank}</h3>
        {variant.is_recommended && <span className="badge recommended">Recommended</span>}
      </div>

      <AuthenticatedImage
        path={variantImagePath(simulationId, variant.variant_id)}
        alt={`Generated variant ranked ${variant.rank}`}
        className="thumb"
      />

      <PMFScoreGauge score={variant.pmf_score} />

      <dl style={{ fontSize: '0.85rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <dt className="muted">Avg. purchase likelihood</dt>
          <dd>{variant.avg_purchase_likelihood !== null ? `${(variant.avg_purchase_likelihood * 100).toFixed(0)}%` : '—'}</dd>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <dt className="muted">Avg. engagement</dt>
          <dd>{variant.avg_engagement_score !== null ? variant.avg_engagement_score.toFixed(2) : '—'}</dd>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between' }}>
          <dt className="muted">FID (realism)</dt>
          <dd>{variant.fid_score !== null ? variant.fid_score.toFixed(1) : '—'}</dd>
        </div>
      </dl>

      <h4>Sentiment</h4>
      <SentimentChart sentiment={variant.sentiment} />

      <h4>Risk indicators</h4>
      <RiskAlertList flags={variant.risk_flags} />

      <details style={{ marginTop: '0.75rem' }}>
        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
          Persona feedback ({variant.feedback.length})
        </summary>
        <div style={{ marginTop: '0.5rem' }}>
          <PersonaFeedbackList feedback={variant.feedback} />
        </div>
      </details>
    </div>
  )
}
