import type { OptionInsight } from '../api/dashboard'

/** Colour for each interest level, shared by the results page and option cards. */
export const INTEREST_COLOR: Record<OptionInsight['interest_level'], string> = {
  Strong: 'var(--color-success)',
  Moderate: 'var(--color-warning)',
  Low: 'var(--color-danger)',
}
