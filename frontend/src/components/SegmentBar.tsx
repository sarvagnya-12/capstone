/** One horizontal bar split into labelled parts, with the counts written out
 * underneath ("2 likely to buy · 1 undecided · 2 unlikely"). Replaces the
 * sentiment pie chart: the reader gets the numbers in words, not slice sizes
 * to estimate. */
export interface Segment {
  label: string
  value: number
  color: string
}

export default function SegmentBar({ segments, ariaLabel }: { segments: Segment[]; ariaLabel: string }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  if (total === 0) return <p className="muted">No responses recorded.</p>

  return (
    <div>
      <div className="segment-bar" role="img" aria-label={ariaLabel}>
        {segments
          .filter((s) => s.value > 0)
          .map((s) => (
            <div key={s.label} style={{ flex: s.value, background: s.color }} title={`${s.value} ${s.label}`} />
          ))}
      </div>
      <div className="segment-legend">
        {segments.map((s) => (
          <span key={s.label}>
            <i style={{ background: s.color }} />
            <strong>{s.value}</strong> {s.label}
          </span>
        ))}
      </div>
    </div>
  )
}
