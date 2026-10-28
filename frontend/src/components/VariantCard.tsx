import type { CustomerReaction, OptionInsight } from '../api/dashboard'
import { variantImagePath } from '../api/simulations'
import AuthenticatedImage from './AuthenticatedImage'
import { INTEREST_CLASS } from './interest'
import PersonaFeedbackList from './PersonaFeedbackList'
import SegmentBar from './SegmentBar'

function Quote({ label, quote }: { label: string; quote: CustomerReaction }) {
  return (
    <blockquote className="quote">
      <span className="legend">
        {label} · {quote.profile} · {quote.buying_intent.toLowerCase()}
      </span>
      <p>“{quote.comment}”</p>
    </blockquote>
  )
}

/** One design option in full: the render, the figures that decided its
 * rank, who it appealed to, and what they objected to. The headline figure
 * lives in the chip row above this card, so it is stated here as a ruled
 * field entry rather than repeated as a second hero number. */
export default function VariantCard({ simulationId, option }: { simulationId: string; option: OptionInsight }) {
  return (
    <section className={`card option-card${option.is_recommended ? ' recommended' : ''}`}>
      <div className="option-head">
        <div>
          <span className="code muted">{option.label}</span>
          <h3>{option.colourway}</h3>
        </div>
        <div className="reaction-marks">
          <span className={`badge ${INTEREST_CLASS[option.interest_level]}`}>{option.interest_level} interest</span>
          {option.is_recommended && <span className="badge recommended">Recommended</span>}
        </div>
      </div>

      <AuthenticatedImage
        path={variantImagePath(simulationId, option.variant_id)}
        alt={`${option.label}, ${option.colourway}`}
        className="thumb"
      />

      <dl className="facts" style={{ marginTop: '0.75rem' }}>
        <dt>Avg. would buy</dt>
        <dd>
          <span className="quantity">{option.purchase_intent_pct}%</span>{' '}
          <span className="muted">across {option.profiles} customer profiles</span>
        </dd>
      </dl>

      <h4>Would they buy it?</h4>
      <SegmentBar
        ariaLabel="Buying intent"
        segments={[
          { label: 'likely to buy', value: option.likely_buyers, color: 'var(--mark-green)' },
          { label: 'undecided', value: option.undecided, color: 'var(--mark-amber)' },
          { label: 'unlikely to buy', value: option.unlikely_buyers, color: 'var(--mark-red)' },
        ]}
      />

      <h4>Tone of their comments: {option.reception.toLowerCase()}</h4>
      <SegmentBar
        ariaLabel="Tone of customer comments"
        segments={[
          { label: 'positive', value: option.liked, color: 'var(--mark-green)' },
          { label: 'neutral', value: option.neutral, color: 'var(--ink-2)' },
          { label: 'critical', value: option.disliked, color: 'var(--mark-red)' },
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
                {t.topic} · <span className="quantity">{t.mentions}</span> of {option.profiles}
              </span>
            ))}
          </div>
        </>
      )}

      <h4>Concerns</h4>
      {option.concerns.length === 0 ? (
        <p className="muted">No major concerns raised.</p>
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
        <summary>All {option.reactions.length} customer reactions</summary>
        <PersonaFeedbackList reactions={option.reactions} />
      </details>
    </section>
  )
}
