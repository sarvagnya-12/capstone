import { PolarAngleAxis, RadialBar, RadialBarChart } from 'recharts'

function scoreColor(score: number): string {
  if (score >= 66) return '#1f7a4d'
  if (score >= 33) return '#c98a1f'
  return '#c1352d'
}

export default function PMFScoreGauge({ score }: { score: number }) {
  const data = [{ name: 'PMF', value: score, fill: scoreColor(score) }]

  return (
    <div style={{ width: '100%', height: 110, position: 'relative' }}>
      <RadialBarChart
        width={140}
        height={110}
        cx="50%"
        cy="100%"
        innerRadius={55}
        outerRadius={85}
        startAngle={180}
        endAngle={0}
        data={data}
      >
        <PolarAngleAxis type="number" domain={[0, 100]} angleAxisId={0} tick={false} />
        <RadialBar dataKey="value" background cornerRadius={6} />
      </RadialBarChart>
      <div style={{ position: 'absolute', top: '55%', left: '50%', transform: 'translate(-50%, -50%)', textAlign: 'center' }}>
        <strong style={{ fontSize: '1.3rem' }}>{score.toFixed(0)}</strong>
        <div className="muted" style={{ fontSize: '0.7rem' }}>
          PMF / 100
        </div>
      </div>
    </div>
  )
}
