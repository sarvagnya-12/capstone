import type { OptionInsight } from '../api/dashboard'
import { INTEREST_COLOR } from './interest'

/** The sheet's signature: every generated option as a colour chip read
 * across in one row, the way a developer lays colour-ups side by side.
 *
 * Each chip is painted with `colourway_hex` -- the dominant colour measured
 * from the render itself (backend `_measure_dominant`), never a colour
 * inferred from the colourway's name. When the render could not be measured
 * the chip is hatched and says so: a guessed swatch would be a fabricated
 * figure in a surface whose whole claim is that its figures are real.
 *
 * Selecting a chip scopes the detail below it. */
export default function ColourwayChips({
  options,
  selectedId,
  onSelect,
}: {
  options: OptionInsight[]
  selectedId: string | null
  onSelect: (variantId: string | null) => void
}) {
  return (
    <ul className="chiprow">
      {options.map((o) => {
        const selected = o.variant_id === selectedId
        const measured = o.colourway_hex !== null
        return (
          <li key={o.variant_id}>
            <button
              type="button"
              className={`swatch-button${o.is_recommended ? ' swatch-recommended' : ''}`}
              aria-pressed={selected}
              onClick={() => onSelect(selected ? null : o.variant_id)}
            >
              <span
                className={`swatch${measured ? '' : ' unmeasured'}`}
                style={measured ? { background: o.colourway_hex as string } : undefined}
              />
              <span className="swatch-body">
                <span className="code">
                  {o.label}
                  {o.is_recommended ? ' · recommended' : ''}
                </span>
                <span className="swatch-name">
                  {measured ? o.colourway : `${o.colourway} — colour not measured`}
                </span>
                <span className="swatch-figure">
                  <span className="quantity" style={{ color: INTEREST_COLOR[o.interest_level] }}>
                    {o.purchase_intent_pct}%
                  </span>
                  <span className="legend">would buy</span>
                </span>
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
