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

export default function PersonaFeedbackList({ reactions }: { reactions: CustomerReaction[] }) {
  if (reactions.length === 0) {
    return <p className="muted">No customer reactions recorded.</p>
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {reactions.map((r) => (
        <li key={r.profile} className="reaction">
          <div className="reaction-head">
            <strong>{r.profile}</strong>
            <span>
              <span className={`badge ${INTENT_CLASS[r.buying_intent]}`}>
                {r.buying_intent} ({r.likelihood_pct}%)
              </span>{' '}
              <span className={`badge ${TONE_CLASS[r.reaction]}`}>{r.reaction} tone</span>
            </span>
          </div>
          <p style={{ margin: '0.25rem 0' }}>{r.comment}</p>
        </li>
      ))}
    </ul>
  )
}
