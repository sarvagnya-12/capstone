---
version: 1
slug: "frontend-src-pages-dashboardpage-tsx"
primary_target: "frontend/src/pages/DashboardPage.tsx"
related_targets: ["frontend/src/index.css","frontend/src/components/VariantCard.tsx","frontend/src/components/SegmentBar.tsx"]
---

## Scope

The results surface (`DashboardPage.tsx`, `VariantCard.tsx`, `SegmentBar.tsx`, `interest.ts`) as the lead expression of a replacement visual world, with `index.css` carrying the world's tokens for the whole app. Visitor mode: **Operate**.

Audience: a capstone evaluator driving the app live on a 1280–1536px laptop during a viva (see PRODUCT.md). Job: read which design option won, and verify the figure behind that claim without leaving the screen. Proof on hand: real analytics from `GET /simulations/{id}/analytics`, including the business-terms `insights` payload, per-variant FID, and 20 persona reactions. Constraints: no fabricated numbers anywhere including empty and loading states; footwear-only scope stated honestly; GAN-centric framing preserved.

## Direction contract

**THESIS:** The sheet a footwear developer marks up, not a dashboard. It refuses the KPI-tile grid the category ships: the comparison is a row of the options' real colourways, read across, not a stack of metric cards.

**OWN-WORLD:** Cool bond ground (#f1f3f1) under white sheets, near-black cool ink (#15191a), hairline rules (#c9cfcb). A deep sample-room slate (#2c3836) owns the header band as a real field, not an accent. Three marking colours only, at full saturation and only where they carry meaning: spec-pencil red (#c0211c) unverified or critical, stamp green (#1a6b41) confirmed or recommended, amber (#96681a) undecided. Every other bit of chroma on screen is a generated variant's own colourway — the data supplies the colour, the brand does not. Archivo Narrow in tracked caps for part codes and legends, Archivo for prose, tabular figures for every quantity. Zero radius on rules and fields; chips are the only rounded objects. Carried invariants: bars are dimensionally honest (length is the real percentage, never normalised); every run, option and persona carries a short printed identifier citable out loud; conflict and unverified data render as hatch texture rather than colour.

**STORY:** The evaluator sees a recorded comparison of real options, can cite any figure on screen by its printed code, and leaves knowing which option won, how far ahead it was, and exactly what the system could not verify.

**FIRST VIEWPORT:** Slate header band, left to right: product name, run identity (RUN 014 · DRY-SNK-0231), and the standard nav. Beneath it the sheet opens on the finding — verdict set large in ink, bottom line in prose under it, the two report-download actions sitting right of that block on the same baseline. Directly below, the signature: the option chip row, each chip painted in that variant's actual generated colourway, carrying its code and its purchase-likelihood figure in tabular numerals, the recommended chip marked with a stamp-green rule; selecting a chip scopes the whole sheet beneath it. Then the hairline-ruled line listing, one row per option with part-callout labels for what varied, persona rows nested under it.

**FORM:** The Colourway Spec Sheet (footwear tech packs and colour-up sheets), candidate 1 of 7 on my ordered list, taken as IMPECCABLE'S PICK over the assigned Case Report Form. seed:ab081961d4f5079d

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Unresolved

- Dark rendition: light is canonical (the scene is a lit bench at 10am). The incumbent app ships a `prefers-color-scheme` dark block; whether the new world keeps a dark inversion is undecided.
- Favicon: the violet bolt (`frontend/public/favicon.svg`) is off-palette and was called AI slop by the user. Needs redrawing in the new world; not yet done.
- Academic attribution in-interface: offered and not selected; neither required nor forbidden.
- Recharts is an installed dependency with zero imports. Removal is a judgement call for the build, not a design decision.
