import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import type { SentimentBreakdown } from '../api/dashboard'

const COLORS: Record<string, string> = {
  Positive: '#1f7a4d',
  Negative: '#c1352d',
  Neutral: '#8a8a94',
  Unclassified: '#c9c9d1',
}

export default function SentimentChart({ sentiment }: { sentiment: SentimentBreakdown }) {
  const data = [
    { name: 'Positive', value: sentiment.positive },
    { name: 'Negative', value: sentiment.negative },
    { name: 'Neutral', value: sentiment.neutral },
    { name: 'Unclassified', value: sentiment.unclassified },
  ].filter((d) => d.value > 0)

  if (data.length === 0) {
    return <p className="muted">No sentiment data yet.</p>
  }

  return (
    <div style={{ width: '100%', height: 140 }}>
      <ResponsiveContainer>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={55} label>
            {data.map((entry) => (
              <Cell key={entry.name} fill={COLORS[entry.name]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}
