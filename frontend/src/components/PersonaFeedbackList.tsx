import type { CustomerReaction } from '../api/dashboard'

const INTENT_CLASS: Record<CustomerReaction['buying_intent'], string> = {
  'Likely to buy': 'positive',
  Undecided: 'warning',
  'Unlikely to buy': 'negative',
}

const TONE_CLASS: Record<CustomerReaction['reaction'], string> = {
  Positive: 'positive',
  Neutral: 'neutral',
  Critical: 'negative',
  'Not classified': 'neutral',
}

/** The line listing: one row per simulated customer profile, each carrying
 * its own recorded figures. A profile whose reaction could not be
 * classified says "not classified" rather than being folded into neutral. */
export default function PersonaFeedbackList({ reactions }: { reactions: CustomerReaction[] }) {
  if (reactions.length === 0) {
    return <p className="muted">No customer reactions recorded.</p>
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {reactions.map((r, i) => (
        <li key={r.profile} className="reaction">
          <div className="reaction-head">
            <strong>
              <span className="code muted">{String(i + 1).padStart(2, '0')}</span> {r.profile}
            </strong>
            <span className="reaction-marks">
              <span className={`badge ${INTENT_CLASS[r.buying_intent]}`}>
                {r.buying_intent} <span className="quantity">{r.likelihood_pct}%</span>
              </span>
              <span className={`badge ${TONE_CLASS[r.reaction]}`}>{r.reaction} tone</span>
            </span>
          </div>
          <p style={{ margin: '0.25rem 0 0', maxWidth: 'var(--measure)' }}>{r.comment}</p>
        </li>
      ))}
    </ul>
  )
}
