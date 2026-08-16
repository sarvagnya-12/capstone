import type { RiskFlag } from '../api/dashboard'

export default function RiskAlertList({ flags }: { flags: RiskFlag[] }) {
  if (flags.length === 0) {
    return <p className="success-text">No risk flags triggered.</p>
  }

  return (
    <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
      {flags.map((flag, i) => (
        <li key={i} style={{ marginBottom: '0.4rem' }}>
          <span className={`badge ${flag.severity === 'high' ? 'negative' : 'neutral'}`}>{flag.severity}</span>{' '}
          <strong>{flag.rule.replaceAll('_', ' ')}</strong>
          <div className="muted" style={{ fontSize: '0.85rem' }}>
            {flag.detail}
          </div>
        </li>
      ))}
    </ul>
  )
}
