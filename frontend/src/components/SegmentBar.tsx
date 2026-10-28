/** One ruled bar split into labelled parts, with the counts written out
 * underneath ("2 likely to buy · 1 undecided · 2 unlikely"). Replaces the
 * sentiment pie chart: the reader gets the numbers in words, not slice
 * sizes to estimate.
 *
 * Each part's width is its real share of the total -- the bar is a
 * measurement, so nothing is padded to a minimum width for legibility. A
 * part too thin to see is a part with almost no responses in it, and the
 * written counts below carry the number regardless. */
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
            <span
              key={s.label}
              style={{ flex: s.value, background: s.color }}
              title={`${s.value} ${s.label}`}
            />
          ))}
      </div>
      <div className="segment-legend">
        {segments.map((s) => (
          <span key={s.label}>
            <i style={{ background: s.color }} />
            <strong className="quantity">{s.value}</strong> {s.label}
          </span>
        ))}
      </div>
    </div>
  )
}
