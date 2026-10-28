/** The sheet's drawn marks. One stroke weight (1.5), one 16px box, all
 * inheriting currentColor so a mark takes the colour of the state it sits
 * in. Drawn rather than typed: a "✓" or "→" from the text stream is a
 * glyph standing in for an icon system, and it renders differently in
 * every font. */

type IconProps = { size?: number; className?: string }

function svg(path: React.ReactNode, { size = 16, className }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {path}
    </svg>
  )
}

/** A recorded, completed step. */
export const CheckMark = (p: IconProps) => svg(<path d="M3 8.5 6.25 11.75 13 5" />, p)

/** The step in progress. */
export const RuleArrow = (p: IconProps) =>
  svg(
    <>
      <path d="M2 8h10" />
      <path d="M8.75 4.75 12 8l-3.25 3.25" />
    </>,
    p,
  )

/** A step not yet reached: an unticked box. */
export const EmptyBox = (p: IconProps) => svg(<rect x="3.5" y="3.5" width="9" height="9" />, p)

/** Pull a copy off the sheet. */
export const SheetDown = (p: IconProps) =>
  svg(
    <>
      <path d="M8 2.5v7.5" />
      <path d="M4.75 6.75 8 10l3.25-3.25" />
      <path d="M2.5 13h11" />
    </>,
    p,
  )

/** Something the reader has to know about. */
export const FlagMark = (p: IconProps) =>
  svg(
    <>
      <path d="M8 2.5 14 13H2L8 2.5Z" />
      <path d="M8 6.75v2.5" />
      <path d="M8 11.25v.5" />
    </>,
    p,
  )

/** Add another row to a field block. */
export const PlusRule = (p: IconProps) =>
  svg(
    <>
      <path d="M8 3.5v9" />
      <path d="M3.5 8h9" />
    </>,
    p,
  )

/** Strike a row out. */
export const StrikeRule = (p: IconProps) =>
  svg(
    <>
      <path d="M4 4l8 8" />
      <path d="M12 4l-8 8" />
    </>,
    p,
  )
