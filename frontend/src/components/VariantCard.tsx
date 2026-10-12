import type { CustomerReaction, OptionInsight } from '../api/dashboard'
import { variantImagePath } from '../api/simulations'
import AuthenticatedImage from './AuthenticatedImage'
import { INTEREST_COLOR } from './interest'
import PersonaFeedbackList from './PersonaFeedbackList'
import SegmentBar from './SegmentBar'

function Quote({ label, quote }: { label: string; quote: CustomerReaction }) {
  return (
    <blockquote className="quote">
      <span className="muted">
        {label}: {quote.profile} · {quote.buying_intent.toLowerCase()}
      </span>
      <p>“{quote.comment}”</p>
    </blockquote>
  )
}

/** One design option, described in business terms: how many customer
 * profiles would buy it, who it appeals to, what they objected to. */
export default function VariantCard({ simulationId, option }: { simulationId: string; option: OptionInsight }) {
  return (
    <div className={`card option-card${option.is_recommended ? ' recommended' : ''}`}>
      <div className="option-head">
        <div>
          <h3>
            {option.label}: {option.colourway}
          </h3>
          <span className="badge" style={{ background: INTEREST_COLOR[option.interest_level], color: '#fff' }}>
            {option.interest_level} interest
          </span>{' '}
          {option.is_recommended && <span className="badge recommended">Recommended</span>}
        </div>
      </div>

      <AuthenticatedImage
        path={variantImagePath(simulationId, option.variant_id)}
        alt={`${option.label}, ${option.colourway}`}
        className="thumb"
      />

      <div className="metric">
        <span className="metric-value" style={{ color: INTEREST_COLOR[option.interest_level] }}>
          {option.purchase_intent_pct}%
        </span>
        <span className="muted">average purchase likelihood across {option.profiles} customer profiles</span>
      </div>

      <h4>Would they buy it?</h4>
      <SegmentBar
        ariaLabel="Buying intent"
        segments={[
          { label: 'likely to buy', value: option.likely_buyers, color: 'var(--color-success)' },
          { label: 'undecided', value: option.undecided, color: 'var(--color-warning)' },
          { label: 'unlikely to buy', value: option.unlikely_buyers, color: 'var(--color-danger)' },
        ]}
      />

      <h4>Tone of their comments: {option.reception.toLowerCase()}</h4>
      <SegmentBar
        ariaLabel="Tone of customer comments"
        segments={[
          { label: 'positive', value: option.liked, color: 'var(--color-success)' },
          { label: 'neutral', value: option.neutral, color: 'var(--color-neutral)' },
          { label: 'critical', value: option.disliked, color: 'var(--color-danger)' },
        ]}
      />

      {option.appeals_most_to.length > 0 && (
        <>
          <h4>Appeals most to</h4>
          <p>{option.appeals_most_to.join(', ')}</p>
        </>
      )}
      {option.least_interested.length > 0 && (
        <>
          <h4>Least interested</h4>
          <p>{option.least_interested.join(', ')}</p>
        </>
      )}

      {option.themes.length > 0 && (
        <>
          <h4>What customers talked about</h4>
          <div className="chips">
            {option.themes.map((t) => (
              <span key={t.topic} className="chip">
                {t.topic} · {t.mentions} of {option.profiles}
              </span>
            ))}
          </div>
        </>
      )}

      <h4>Concerns</h4>
      {option.concerns.length === 0 ? (
        <p className="success-text">No major concerns raised.</p>
      ) : (
        <ul className="concerns">
          {option.concerns.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </ul>
      )}

      {option.best_quote && <Quote label="Most positive" quote={option.best_quote} />}
      {option.worst_quote && <Quote label="Most critical" quote={option.worst_quote} />}

      <details style={{ marginTop: '0.75rem' }}>
        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
          All customer reactions ({option.reactions.length})
        </summary>
        <div style={{ marginTop: '0.5rem' }}>
          <PersonaFeedbackList reactions={option.reactions} />
        </div>
      </details>
    </div>
  )
}
