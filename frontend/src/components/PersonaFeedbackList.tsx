import type { PersonaFeedbackEntry } from '../api/dashboard'

export default function PersonaFeedbackList({ feedback }: { feedback: PersonaFeedbackEntry[] }) {
  if (feedback.length === 0) {
    return <p className="muted">No persona feedback recorded.</p>
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {feedback.map((entry) => (
        <li key={entry.persona_id} style={{ marginBottom: '0.6rem', borderBottom: '1px solid var(--color-border)', paddingBottom: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <strong>{entry.persona_name}</strong>
            {entry.sentiment_label && <span className={`badge ${entry.sentiment_label}`}>{entry.sentiment_label}</span>}
          </div>
          <p style={{ margin: '0.25rem 0' }}>{entry.qualitative_text}</p>
          <span className="muted" style={{ fontSize: '0.8rem' }}>
            Purchase likelihood: {(entry.purchase_likelihood * 100).toFixed(0)}%
          </span>
        </li>
      ))}
    </ul>
  )
}
