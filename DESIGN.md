---
name: DryRunAI
description: Pre-launch product simulation, reported as a footwear developer's colour-up sheet.
colors:
  bond: "#f1f3f1"
  sheet: "#fafbf8"
  field: "#e8ebe8"
  rule: "#c9cfcb"
  rule-strong: "#9ba39f"
  ink: "#15191a"
  ink-2: "#4a5250"
  slate: "#2c3836"
  slate-2: "#3b4a47"
  slate-ink: "#eef1ee"
  slate-ink-2: "#a9b6b2"
  mark-green: "#1a6b41"
  mark-amber: "#8a5f17"
  mark-red: "#c0211c"
typography:
  display:
    fontFamily: "Archivo, 'Segoe UI', system-ui, sans-serif"
    fontSize: "clamp(1.625rem, 2.6vw, 2.125rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Archivo, 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Archivo, 'Segoe UI', system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Archivo, 'Segoe UI', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Archivo, 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.1em"
    fontStretch: "70%"
  code:
    fontFamily: "Archivo, 'Segoe UI', system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.09em"
    fontStretch: "62%"
  quantity:
    fontFamily: "Archivo, 'Segoe UI', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    letterSpacing: "-0.01em"
    fontFeature: "tnum"
rounded:
  none: "0"
  chip: "2px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "0.75rem"
  lg: "1rem"
  xl: "1.5rem"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.none}"
    padding: "0.4375rem 0.875rem"
    typography: "{typography.label}"
  button-primary-hover:
    backgroundColor: "{colors.slate}"
    textColor: "{colors.sheet}"
  button-primary-disabled:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink-2}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.4375rem 0.875rem"
  button-secondary-hover:
    backgroundColor: "{colors.field}"
    textColor: "{colors.ink}"
  input:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.4375rem 0.5rem"
  input-invalid:
    textColor: "{colors.ink}"
    backgroundColor: "{colors.sheet}"
  card:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "1.25rem 1.375rem"
  chip:
    backgroundColor: "transparent"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.chip}"
    padding: "0.125rem 0.4375rem"
  badge-recommended:
    backgroundColor: "{colors.mark-green}"
    textColor: "{colors.sheet}"
    rounded: "{rounded.none}"
    padding: "0.0625rem 0.375rem"
  swatch:
    rounded: "{rounded.none}"
    height: "4.5rem"
    width: "100%"
  app-header:
    backgroundColor: "{colors.slate}"
    textColor: "{colors.slate-ink}"
    rounded: "{rounded.none}"
    padding: "0.625rem 1.5rem"
---

# Design System: DryRunAI

## Overview

**Creative North Star: "The Colourway Spec Sheet"**

This is the sheet a footwear developer marks up, not a dashboard. Everything on screen behaves like a working document: cool bond stock, hairline rules, tracked condensed codes in the margins, and quantities set in tabular figures so a column of numbers lines up and can be compared down the page rather than read one at a time. The reader is an examiner driving the app live while questioning the team, so the sheet is built to be cited out loud — every run, option and customer profile carries a short printed identifier, and every figure sits next to the thing it describes.

Colour on this surface belongs to the data. Besides three marking inks, the only saturated colour anywhere is a generated variant's **own measured colourway**, sampled from the render by the backend and painted into its chip. That rule is what makes the system honest at a glance: when the pipeline could not read an image, its chip is hatched rather than filled with a plausible guess. The shell takes a deep sample-room slate that owns a real region of the screen, so the page is never a grey screen with one accent colour.

The system is deliberately flat — no shadows anywhere. Depth comes from a one-pixel rule and the tonal step between bond and sheet. Light is canonical and there is no dark inversion: the use scene is a lit desk, read against physical chips, and a second theme nobody verifies is a second theme that drifts. Confirmed anti-references: the AI-product aesthetic (violet-to-cyan gradients, glow, glass) and the enterprise BI dashboard (wall-to-wall KPI tiles and donut charts). The second matters most, because this system looks superficially like a data product and must never become one: a control room reads **one live run**; a BI dashboard tiles many metrics for scanning.

**Key Characteristics:**

- Measured and plain — nothing shouts; the figures do the talking.
- Precise and instrumented — tabular numerals, exact percentages, dimensionally honest bars.
- Warm in language, exact in presentation — plain business sentences, never softened numbers.
- Flat, ruled, zero-radius; chips are the only rounded objects.
- Chroma is data; the interface itself is near-monochrome.

## Colors

A near-monochrome cool-grey sheet, a single deep slate field for the shell, and three saturated marking inks that appear only where they carry meaning.

### Primary

- **Sample-Room Slate** (#2c3836): the header band. A real field, not an accent — it owns the top of every screen and is the only large area of committed colour the interface itself supplies. **Slate Shade** (#3b4a47) is its pressed/hover state.

### Secondary

The three marking inks. Each is used at full strength; a tint of a marking ink reads as a weaker claim than the data supports.

- **Stamp Green** (#1a6b41): confirmed, recommended, strong interest, a completed stage. Also the rule stamped under the recommended option's chip.
- **Record Amber** (#8a5f17): undecided, moderate interest, a caution worth reading.
- **Spec-Pencil Red** (#c0211c): low interest, critical tone, errors, anything unverified. Also the caret colour.

### Neutral

- **Cool Bond** (#f1f3f1): the page ground, the stock the sheets sit on. The bond is *printed*: a tiled scatter of outline shoe doodles (sneaker, sole, boot, lace knot, shoebox, sandal, heel, barefoot print, high-top, shoe from above) across a 240px tile rendered at 165px, in two tonal depths (#e3e7e2 far, #d0d6d0 near). Tonal, never chromatic, and only ever visible in the margins because every sheet is opaque.
- **Sheet Off-White** (#fafbf8): every card, table and field block. Off-white rather than paper-white — a sheet of real stock laid on the bond, not a lit panel.
- **Field Grey** (#e8ebe8): disabled controls, bar troughs, hover rows.
- **Rule** (#c9cfcb): the hairline between rows and around sheets.
- **Rule Strong** (#9ba39f): control borders, scrollbar thumb, hatch strokes.
- **Iron Ink** (#15191a): body text and the primary button fill.
- **Ink Secondary** (#4a5250): legends, codes, secondary prose — tinted from the ground's hue, never a neutral grey.
- **Slate Ink** (#eef1ee) / **Slate Ink Secondary** (#a9b6b2): text on the header band, tinted from the slate's own hue.

### Named Rules

**The Measured Colour Rule.** The only saturated colour on a results screen besides the three marking inks is a variant's own colourway, and it comes from `colourway_hex` — measured from the render. If that value is null the chip is hatched and labelled "colour not measured." Never infer a swatch from a colour's name.

**The Printed Ground Rule.** The doodle ground is tonal and stays within one step of the bond. It is never tinted toward a hue, never placed behind a sheet, and never built from the hatch — hatch means *unmeasured*, and borrowing it for ornament would make a real state unreadable. Motifs never overlap each other: placement is collision-checked on a torus so the tile repeats seamlessly.

**The Three Inks Rule.** Green, amber and red mean confirmed, undecided and critical. They are never used decoratively, never tinted down to soften a result, and no fourth accent is added.

## Typography

**Display / Body / Label Font:** Archivo (variable, `wght` 400–700 and `wdth` 62%–125%), self-hosted at `/fonts/archivo-latin.woff2` and `/fonts/archivo-latin-ext.woff2`, falling back to Segoe UI and system-ui.

**Character:** One industrial grotesk supplying three voices from its width axis — condensed for codes and legends, normal for prose, and the same face at 600 for quantities. A spec sheet needs a label voice, a prose voice and a number voice that visibly differ without introducing unrelated typefaces, and the width axis gives exactly that from one family.

### Hierarchy

- **Display** (600, clamp 1.625–2.125rem, 1.15, -0.02em): the finding — the verdict line at the top of a results sheet. One per screen, capped at 24ch and balanced.
- **Headline** (600, 1.375rem): page titles.
- **Title** (600, 1.0625rem): an option's colourway name, an empty state's heading.
- **Body** (400, 1rem, 1.55): all prose, capped at a 68ch measure.
- **Label** (600, 0.6875rem, 70% width, uppercase, 0.1em): section headings, field labels, table headers, state words. Section headings are set in this voice and ruled underneath.
- **Code** (600, 0.75rem, 62% width, uppercase, 0.09em): run identifiers, option codes, subject numbers.
- **Quantity** (600, tabular figures): every number.

### Named Rules

**The Tabular Rule.** Every figure renders with `tabular-nums`, inherited from `body` and reasserted on numeric cells. Numbers in a column must align digit for digit; a reader comparing options should never re-find the decimal.

**The No-Eyebrow Rule.** A heading carries its own weight. No small label sits above a heading to introduce it — context goes into a ruled field block underneath, where it is a fact with a name rather than decoration.

## Layout

A centred sheet, `1160px` maximum, on a bond ground, with `1.5rem` padding. Prose inside caps at a 68ch measure regardless of sheet width, so a wide laptop widens the apparatus, never the reading line. Narrow forms (login, register) take a `26rem` sheet centred with `2rem` of air.

The real design target is a 1280–1536px laptop driven live; there is no layout breakpoint inside that band. Below `900px` the two-column field blocks collapse to one and stage rows drop their trailing state word to a second column; below `600px` padding tightens and tables scroll inside their own container rather than widening the page.

Spacing runs on a small set of steps — `0.25 / 0.5 / 0.75 / 1 / 1.5rem` — with tight grouping inside a field block and a full `1rem` between sheets. Section headings carry more space above than below, and sit on a rule.

Option detail uses `repeat(auto-fill, minmax(19rem, 1fr))`; the colourway chip row uses flexible `8.5rem`–`13rem` columns so a row of options reads across at any count.

## Elevation & Depth

**There are no shadows in this system, anywhere.** Depth is carried by exactly two devices: the tonal step from bond ground to sheet white, and a one-pixel rule. A sheet is distinguished from the page because it is lighter and bounded, not because it floats.

Two heavier rules carry meaning rather than elevation: a `3px` ink rule above the finding, and a `3px` marking-ink rule to stamp a recommended option or flag an alert.

The current state of depth was recorded as **open rather than doctrine** — flatness is where the implementation stands and what this document describes, not a prohibition the user has committed to. A future direction may introduce a depth system; it should do so deliberately and record it here rather than letting soft shadows arrive one component at a time.

### Named Rules

**The Hatch Rule.** Anything unmeasured, unavailable or in conflict renders as a 45° hairline hatch (`repeating-linear-gradient`, `rule-strong` at 1.5px on 5px), never as a colour. Hatch survives greyscale, a projector and colour blindness, which a grey fill does not.

## Shapes

Zero radius everywhere — rules, fields, buttons, badges, swatches, bars. The one exception is the theme chip at `2px`, which is the system's only rounded object and marks it as a loose tag rather than a field.

Form is rectangular and ruled: field blocks are two-column grids separated by hairlines, bars are flat-ended rectangles, and the colour swatch is a plain rectangle with its data printed beneath it on the sheet.

## Components

### Buttons

- **Shape:** square (0 radius), `0.4375rem 0.875rem`, label voice at 80% width.
- **Primary:** iron ink fill, sheet-white text. **Hover:** fills slate. **Active:** slate shade.
- **Secondary:** transparent on an ink hairline. **Hover:** field grey.
- **Quiet:** transparent on a `rule-strong` hairline in secondary ink, tighter padding — for row-level actions like removing a pricing tier.
- **Disabled:** field-grey fill, `rule-strong` border, secondary ink, `not-allowed`.
- On the header band, secondary buttons invert to slate-ink borders and fill with slate shade on hover.
- Buttons are `inline-flex` with a `0.375rem` gap so a drawn mark sits on the label's line.

### Inputs / Fields

- **Style:** sheet-white on a `rule-strong` hairline, square, `0.4375rem 0.5rem`.
- **Hover:** border darkens to secondary ink.
- **Focus:** `2px` ink outline at `1px` offset, border to ink.
- **Invalid:** `aria-invalid="true"` thickens the left edge to `3px` spec-pencil red, always alongside an error line naming the problem and the recovery.
- **Disabled:** field grey, secondary ink.
- Labels are the label voice; hints sit under the control in secondary ink at `0.8125rem`.

### Tables (the line listing)

Full-width, collapsed borders, hairline under every row and a `rule-strong` rule under the header. Headers are the label voice. Numeric columns right-align with tabular figures. Row hover tints field grey; the recommended row carries a 6%-alpha stamp-green wash. Wide tables scroll inside `.table-scroll`.

### Badges

Printed marks, not filled pills: square, `1px` of `currentColor`, label voice at `0.6875rem`. Positive, warning, negative and neutral take the three inks plus secondary ink. Only `badge.recommended` fills — stamp green with sheet-white text.

### Colourway Chip Row (signature component)

The system's signature. Every generated option reads across one row as a rectangular swatch painted in its **measured** colourway, over a sheet-white body carrying the option code, the colourway name and the would-buy figure in the interest level's ink. Figures align on a common baseline via `margin-top: auto`, so they compare even when a name wraps to two lines.

- **Recommended:** a `3px` stamp-green rule along the swatch's bottom edge.
- **Selected** (`aria-pressed="true"`): a `2px` inset ink ring; selecting scopes the detail below the row.
- **Unmeasured:** hatch fill and the name suffixed "— colour not measured".

### Bars and Segment Bars

A bar is a measurement: its filled width is the real percentage, and a segment's flex basis is its real count. Bars are `4px`, troughed in field grey on a hairline, capped at `9rem`. Segment bars are `0.875rem` tall on a `rule-strong` border with sheet-white hairlines between parts, and always carry written counts underneath.

### Stage List (signature component)

The run record: a hairline-ruled list where each stage carries a drawn mark (check / arrow / empty box), its label, an active-stage detail line, and a state word in the label voice.

This is where the system's motion lives. A **finished** stage carries a static stamp-green rule. A stage that finishes **while the reader is watching** draws that rule once, left to right (420ms, `cubic-bezier(0.16, 1, 0.3, 1)`); stages already complete when the page opened are simply ruled, because replaying their history on mount would claim four things finished just now when none of them did. The **active** stage keeps a short segment passing back and forth along its rule (1600ms, alternating), so a run that takes minutes reads as working rather than stalled. The loop pauses when the tab is hidden.

### Motion

The sheet has one motion material: **the rule**. Nothing on this surface moves spatially except a rule being drawn or a rule being traversed, and no element ever changes size, lifts, or slides. Everything else is a colour transition at 120ms — the time it takes to notice a control responded.

Scoping the results sheet to a single option is the one content change that is acknowledged, and only on opacity (160ms), because it changes what is being read rather than where anything is.

Under `prefers-reduced-motion`, travel and drawing stop; the active rule fills its row and breathes on opacity instead, and colour feedback is untouched. Reduced motion removes movement, not the signal that the system is alive.

### Named Rules

**The One Material Rule.** Motion is the rule being drawn, traversed, or held. A new animation that moves, scales, or lifts anything else is outside the system — reach for a rule, a colour, or nothing.

**The No Entrance Rule.** Nothing animates on arrival. A sheet that choreographs its own load makes the reader wait to read it, and on a record it also asserts that something just happened. Motion fires on a state change the reader caused or is waiting for, never on first paint.

### Navigation

Brand in 70%-width tracked caps on the slate band, followed by the live run identifier in the code voice. Links are slate-ink at `0.875rem` with a transparent `2px` bottom border; hover shows the secondary slate ink, and `aria-current="page"` shows full slate ink. Focus rings invert to slate ink inside the header.

### Empty States

A hatched field with a cleared sheet-white panel floated on it carrying the heading, plain-language prose about what is missing and why, and the action that resolves it. The panel is unbordered — a bordered panel inside a bordered card would read as nested cards, which this system never uses.

### Browser Surfaces

Selection is slate on slate-ink. The caret is spec-pencil red. Scrollbars are thin, `rule-strong` on bond. Focus rings are `2px` ink at `2px` offset. Links are ink with a `1px` underline at `0.18em` offset, reddening on hover. `accent-color` is slate.

## Do's and Don'ts

### Do:

- **Do** paint a colourway swatch only from `colourway_hex`; hatch it when that value is null.
- **Do** set every figure in tabular numerals, and put the number next to the thing it measures.
- **Do** size every bar and segment to its real value, with the written count beside it.
- **Do** print a citable identifier — run, option, subject — wherever a figure can be asked about.
- **Do** keep colour on the data: slate for the shell, three inks for meaning, variant colour for variants.
- **Do** state what the system does not know, in the place the reader would otherwise assume it does.
- **Do** give every control its hover, focus-visible, disabled, loading, error and empty state.

### Don't:

- **Don't** add a shadow. Depth is the tonal step and the hairline.
- **Don't** put a small label above a heading. The heading speaks for itself.
- **Don't** introduce a fourth accent colour, or tint a marking ink to soften a result.
- **Don't** render a figure that did not come from an API response — including in empty and loading states.
- **Don't** nest a bordered box inside a bordered box.
- **Don't** reach for a chart library. The written numbers and the ruled bar are the chart; Recharts remains an unused dependency by choice.
- **Don't** use a Unicode glyph as an icon. Marks are drawn SVG at 1.5 stroke in a 16px box.
- **Don't** imply the system covers categories beyond footwear.
