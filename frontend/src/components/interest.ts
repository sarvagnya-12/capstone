import type { OptionInsight } from '../api/dashboard'

/** The sheet has three marking inks and no others. Interest level takes one
 * each, at full strength: a tint of a marking ink reads as a different,
 * weaker claim than the one the data supports. Shared by the results sheet,
 * the line listing and the option detail so one figure never changes colour
 * between two places on the same screen. */
export const INTEREST_COLOR: Record<OptionInsight['interest_level'], string> = {
  Strong: 'var(--mark-green)',
  Moderate: 'var(--mark-amber)',
  Low: 'var(--mark-red)',
}

/** Badge class carrying the same three inks through the printed-mark styles. */
export const INTEREST_CLASS: Record<OptionInsight['interest_level'], string> = {
  Strong: 'positive',
  Moderate: 'warning',
  Low: 'negative',
}
