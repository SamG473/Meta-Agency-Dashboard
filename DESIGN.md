---
name: The Ward Board
description: A clinical enamel board where saturation is spent only on an account past its own target.
colors:
  ground: "#e9eeec"
  ground-sunk: "#dfe6e3"
  ground-raised: "#f2f5f3"
  ink: "#16191a"
  ink-soft: "#59635e"
  rule: "#c6d0cb"
  rule-strong: "#a4b2aa"
  alarm: "#b81f27"
  alarm-wash: "#f0d9da"
typography:
  monument:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "clamp(4.25rem, 7.5vw, 5.5rem)"
    fontWeight: 700
    lineHeight: 0.82
    letterSpacing: "-0.04em"
    fontVariantNumeric: "tabular-nums"
  statement:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "clamp(1.375rem, 2.6vw, 1.75rem)"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.02em"
  strip-value:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "1.375rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.02em"
    fontVariantNumeric: "tabular-nums"
  heading:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "1.1875rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "0.06em"
  title:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "1.0625rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  figure:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "normal"
    fontVariantNumeric: "tabular-nums"
    fontFeature: "'tnum' 1"
  body:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "0.9375rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
    fontVariantNumeric: "tabular-nums"
  label:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.14em"
  micro:
    fontFamily: "'Archivo Variable', 'Archivo', system-ui, sans-serif"
    fontSize: "0.625rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.16em"
rounded:
  none: "0px"
spacing:
  hair: "0.25rem"
  tight: "0.5rem"
  cell: "0.75rem"
  block: "1.25rem"
  band: "2.5rem"
  major: "3.5rem"
  gutter: "clamp(1.25rem, 3.5vw, 3rem)"
components:
  window-btn:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.4rem 0.7rem"
  window-btn-hover:
    backgroundColor: "{colors.ground-sunk}"
    textColor: "{colors.ink}"
  window-btn-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
  expand-btn:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.35rem 0.6rem"
  expand-btn-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
  chip-in-range:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.25rem 0.5rem"
  chip-watch:
    backgroundColor: "{colors.ground}"
    textColor: "{colors.ink}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.25rem 0.5rem"
  chip-out-of-range:
    backgroundColor: "transparent"
    textColor: "{colors.alarm}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.25rem 0.5rem"
  chip-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.25rem 0.5rem"
  target-btn:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.figure}"
    rounded: "{rounded.none}"
    padding: "0 0 1px"
  target-input:
    backgroundColor: "{colors.ground-raised}"
    textColor: "{colors.ink}"
    typography: "{typography.figure}"
    rounded: "{rounded.none}"
    padding: "0.2rem 0.35rem"
    width: "5.5rem"
  target-save:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.3rem 0.45rem"
  target-cancel:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    typography: "{typography.micro}"
    rounded: "{rounded.none}"
    padding: "0.3rem 0.45rem"
  notice:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "1.25rem 1.5rem"
  chart-readout:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground-raised}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "0.65rem 0.8rem"
---

# Design System: The Ward Board

## Overview

**Creative North Star: "The Ward Board"**

A clinical enamel board read at a glance from across a room. The ground is a pale cool grey-green enamel, the ink is graphite, and everything that separates one thing from another is a hairline rule — never a filled card, never a shadow, never a tint panel. The board carries exceptions, not summary: a healthy or quiet portfolio renders almost entirely in ink and reads as calm on purpose, because the only thing the ground gives up saturation for is an account that has gone past its own target.

Density is high and even. The page opens on a monumental numeral rather than on a nameplate or a title bar, drops immediately into a ruled portfolio strip, then into the board itself — one row per client, each judged against its own goal and never ranked against another client. There is no sidebar, no chrome, no orientation copy; the board is the page. Every figure is set in tabular figures so columns of money align down the rule.

Confirmed rejections, held in the build: no filled or shadowed card shells (unfilled hairline panels, added at the user's request, are the only outlined containers), no rounded corners anywhere, no gradient used as shading, no sidebar, no looping animation. Where the direction contract and the build diverge, the build is the record: the shipped alarm is `#b81f27` (not the `#C1272D` first proposed), and Archivo works through **weight only** — the width axis named in the direction was never used.

**Key Characteristics:**
- One accent, spent only on a real breach against a client's own target
- Hairline rules as the only separation device; zero radius, zero shadow
- One type family, self-hosted Archivo Variable, tabular figures throughout
- State encoded three ways at once — word, authored SVG glyph shape, border treatment
- Exactly two authored motion moments, both non-looping
- Print vocabulary for texture: hatches, knocked-out legends, bracketed blocks

## Colors

An enamel-and-graphite palette in a single cool grey-green family, with one saturated red held in reserve.

### Primary
- **Alarm Red** (`{colors.alarm}`): The only saturated hue in the system. It appears on the monument numeral when the out-of-range count is above zero, on the breached row's actual figure, on the deviation rail fill and readout when an account is over its own target, on the out-of-range chip's border and text, on the target reference line in both charts, on the top rule of an alarm notice, on validation error text, and on the caret. Nowhere else.
- **Alarm Wash** (`{colors.alarm-wash}`): A single-pass background wash used only by the `breach-arrive` animation as a breached row lands. It is a motion value, never a resting fill.

### Neutral
- **Enamel Ground** (`{colors.ground}`): The page. Also the knock-out colour behind rail legends set into a broken rule, and the text colour of anything reversed out on ink.
- **Sunk Ground** (`{colors.ground-sunk}`): Recessed tint for inline code, chart hover cursors, and the hatch pattern's base. Never used to build a card.
- **Raised Ground** (`{colors.ground-raised}`): The expanded history panel and the target input field — the only two surfaces that lift off the ground, and both are still bracketed by hairlines rather than shadow.
- **Graphite Ink** (`{colors.ink}`): Body text, headings, figures, the rail's zero mark and under-target fill, section-opening rules, filled controls, chart lines, and the focus ring.
- **Soft Ink** (`{colors.ink-soft}`): The only secondary ink. Labels, micro captions, absent figures, quiet-state chips, axis ticks, and every "nothing to measure" legend.
- **Hairline Rule** (`{colors.rule}`): Standard row and cell separation, and the hatch stroke in the watch chip.
- **Strong Rule** (`{colors.rule-strong}`): Heavier hairline for control borders, the broken rail track, chart axis lines, spend bars, and the scrollbar thumb.

### Named Rules
**The One Alarm Rule.** Saturation is spent on exactly one thing: an account past its own target. Quiet, stale, untargeted, watch and healthy states are all rendered in ink. Any new token that introduces a second hue breaks the world.

**The Retired Grey Rule.** `{colors.ink-soft}` is the only secondary ink. A lighter `#7d8882` was measured at 3.13:1 on this ground, failed the 4.5:1 floor, and was retired. Do not reintroduce it or any grey lighter than it for text; the quiet vocabulary is this board's common case, not its edge.

**The Greyscale Survival Rule.** State is always encoded redundantly — the state word, an authored SVG glyph shape, and a border treatment. Never hue alone. Print the board in greyscale and every state must still be readable.

## Typography

**Display Font:** Archivo Variable (self-hosted via `@fontsource-variable/archivo`, falling back to Archivo, system-ui, sans-serif)
**Body Font:** the same family. There is no second face.
**Label/Mono Font:** none authored; inline `<code>` falls back to a system monospace stack (see Do's and Don'ts).

**Character:** Grotesque, tightly tracked at large sizes and widely tracked at small ones — the two registers of a printed instrument panel. Numerals are tabular everywhere, so a column of money reads as a stack rather than as a ragged edge.

### Hierarchy
- **Monument** (`{typography.monument}`): The out-of-range count in the attention band. One per page, tabular, turning alarm red only above zero.
- **Statement** (`{typography.statement}`): The sentence beside the monument, capped at 24ch on wide screens so it stays a headline and not a paragraph. It shares the monument's `<h1>` so the whole sentence reads as one heading.
- **Strip Value** (`{typography.strip-value}`): Portfolio totals in the ruled strip.
- **Heading** (`{typography.heading}`): Uppercase, ink, `--t-lead`. Panel names only — "Portfolio totals" and "Clients" on Overview; "Period-over-period comparison", "CPA trend", "CTR trend" and "Campaign / ad set breakdown" on Analytics — each an `<h2>` set close above the thing it names (a strip's ink rule, a table's column headers, a chart).
- **Title** (`{typography.title}`): Client names and notice titles.
- **Figure** (`{typography.figure}`): Per-row money — target and actual — with `font-feature-settings: 'tnum' 1` in addition to `tabular-nums`. The absent variant drops to weight 500 in soft ink and prints an em dash.
- **Body** (`{typography.body}`): Prose, reasons, notice bodies, chart readouts. Long prose is capped between 66ch and 74ch.
- **Label** (`{typography.label}`): Uppercase, soft ink. Column headers and minor section captions such as "Retained portfolio history".
- **Micro** (`{typography.micro}`): Uppercase, soft ink. Chips, controls, captions, rail legends, chart footnotes.

### Named Rules
**The One Family Rule.** Archivo Variable, weight axis only (400/500/600/700). No second face, no italic, no width-axis variation — the width axis was named in the direction but never shipped, and the record follows the build.

**The Tabular Figures Rule.** Every numeral on the board carries `font-variant-numeric: tabular-nums`, set on `body` and reasserted on every figure class. Money that can be compared down a column must never reflow.

**The Three Uppercase Registers Rule.** Uppercase belongs to Heading (0.06em, ink, panel names only), Label (0.14em) and Micro (0.16em); the last two always in soft ink, always as a column header, minor section caption, control, or caption. Uppercase is never used decoratively above a heading.

## Layout

One centred column, `1360px` maximum, with a fluid `{spacing.gutter}` and `3rem` of bottom padding. There is no sidebar. An app bar opens every page: a `{colors.rule}` hairline across the full window width, its contents on the board's column and left-aligned — the agency name, a short hairline divider, then the page tabs — with `{spacing.band}` between that hairline and the first panel so the bar never reads as part of it. On the Overview page the content is two panels, `{spacing.band}` apart. The first is **Portfolio totals**: its top row carries the heading (Heading register) on the left, bottom-aligned so it sits on the strip's rule, with the window selector pinned right against it (wrapping above the heading when the two cannot share a line); beneath come the portfolio strip and then the retained history chart, with no rule between them, so the totals and their history read as one unit. The second is **Clients**: its heading over the ward table. The Analytics page is read-only and four panels, `{spacing.band}` apart: **Period-over-period comparison** (heading, with a client picker and the reporting window on the right, then a strip of Spend, Results, CPA and CTR, each with its change on the equal-length period before), **CPA trend**, **CTR trend**, and **Campaign / ad set breakdown**, whose table reuses the ward table's header and row styling.

The portfolio strip is an auto-fit grid of `minmax(min(140px, 100%), 1fr)` cells, opened by an ink rule with no closing rule (the retained history carries on beneath it inside the same panel), each cell divided by a hairline on its right except the last. The ward is a real `<table>` with `border-collapse: collapse`, header cells underlined in ink, rows underlined in hairline, and right-aligned money columns. Layout is fixed: every column has a set width sized to its widest real content (`10rem` client name, `6.5rem` goal, `5.75rem` target and actual, the `132px` trace, `6.625rem` state), and one `1.5rem` gap — `{spacing.cell}` on each side of every cell, outer edges flush — separates every pair of columns, so headers sit exactly over their cells. Nothing stretches to fill the row: History has no width of its own and is left-aligned, starting one gap after State with the spare width trailing after its control, so the header rule and row hairlines still run the full width of the board. The columns need `942px` in all. Cells pad `0.9rem` vertically.

Vertical rhythm runs on a small set of reused steps: `{spacing.hair}` and `{spacing.tight}` inside controls, `{spacing.cell}` in table cells, `{spacing.block}` for panel padding and between the strip and the retained history, and `{spacing.band}` between the two panels and to space notices.

**Responsive:** none, by decision (2026-09-11). The board is a desktop tool with a single layout and no breakpoint. `index.html` carries no viewport meta tag, so a phone renders the desktop page zoomed out rather than a reflowed mobile version.

### Named Rules
**The No-Sidebar Rule.** No sidebar and no chrome beyond one app bar — the agency's name set as plain text, then the page tabs (Overview, Analytics) — added at the user's request on 2026-09-11. Beyond it, the only persistent control is the reporting-window selector.

**The Enclosed Band Rule.** Every major band is enclosed: every panel is a hairline box, so the page never simply stops, and nothing inside a panel needs a rule of its own to close it.

## Elevation & Depth

There are **no shadows anywhere in this system** and there is no blur, glow, or overlay scrim. Depth is entirely a matter of rules and tone: hairlines separate, an ink rule opens a section, and two surfaces (`{colors.ground-raised}` for the expanded history panel and the target input) sit a half-step above the ground by tone alone, still fenced by hairlines on three or four sides. Recession uses `{colors.ground-sunk}`, again with a hairline rather than a shading gradient.

The only true layering is inside the deviation rail, and it is a z-index order, not an elevation ramp.

### Named Rules
**The Hairline-Only Rule.** Separation is a rule, never a shadow and never a filled card. If two things must be distinguished, draw a line.

**The Marks Above The Breach Rule.** In the deviation rail, `rail__zero` and `rail__threshold` sit at `z-index: 3` above the fill at `z-index: 1`. The marks that explain why a row is red must never be covered by the red. The legend layer sits between them at `z-index: 2`.

## Shapes

Zero radius, everywhere, on every element — chips, buttons, inputs, panels, notices, the rail. There is no rounded corner in the build and adding one would read as a foreign object.

Strokes are hairlines: `1px` for rules, borders, rail track, rail zero and threshold marks; `2px` reserved for the ink rule that opens a notice, the current page tab's underline, and the focus ring. Rail fills are `9px` deep bars, the rail itself `30px` tall with a `150px` minimum on wide screens; vitals traces are `132×30` SVGs at `1.35` stroke weight; chart lines run `1.75`.

Glyphs are authored SVG on a `9×9` box at `1.4` stroke, `square` linecap, `currentColor`, one geometry per state: in-range a single horizontal bar, watch a chevron, out-of-range a doubled chevron, stale a broken bar, everything else a ring.

Texture is `repeating-linear-gradient` and SVG `<pattern>` used as **print hatch**, never as shading — a 45° hatch behind the watch chip, a dashed track under a broken rail, and a cross-hatch area fill under the portfolio history area chart.

### Named Rules
**The Square Corner Rule.** Border radius is `0` on every surface in this system. There is no `sm`/`md`/`lg` radius scale to reach for.

**The Hatch-Not-Gradient Rule.** Gradients exist in this build only as repeating hard-stop hatches standing in for print texture. A soft gradient used as shading, a tint ramp, or a glow is out of world.

## Components

### Buttons
- **Shape:** square (`{rounded.none}`), hairline border in strong rule, uppercase micro type.
- **Window selector:** three segments in a single strong-rule box, divided by internal borders, last divider removed. Resting segments are transparent with soft ink; the pressed segment (`aria-pressed="true"`) inverts to ink ground with enamel text.
- **App bar:** the agency name in ink at `--t-lead`, weight 700, mixed case, `-0.01em`, parted from the tabs by a short `{colors.rule}` hairline with `1.75rem` either side. No logo — none exists, and none is to be invented.
- **Page tabs:** unboxed and unfilled, `2rem` apart, `1.5rem` of padding above and below. Uppercase at `--t-body`, weight 700, `0.08em` tracking. Resting tabs are soft ink; hover darkens to ink with a strong-rule underline; the current page (`aria-current="page"`) is ink with a `2px` ink underline landing on the bar's hairline. Weight is identical in every state, so switching tabs moves nothing.
- **Row history button:** transparent with a strong-rule border; on hover it inverts fully — ink background, ink border, enamel text.
- **Hover / Focus:** all controls transition `background`, `color` and `border-color` over `0.15s` on the system easing. Focus is a `2px` ink outline at `2px` offset, never a coloured glow.
- **Save (filled):** ink ground, enamel text, ink border. Disabled drops to `opacity: 0.45` with `not-allowed`.

### Chips
- **Style:** inline-flex, square, `1px` border, uppercase micro at weight 700, an authored SVG glyph and the state word side by side with a `0.4rem` gap.
- **In range:** ink border and ink text.
- **Watch:** ink border and text over a 45° hairline hatch.
- **Out of range:** alarm border and alarm text, **outlined and never filled** — a solid block here would become the second-largest red mass on the page and compete with the monument and the rail.
- **Quiet / stale / no data:** strong-rule border, soft ink text, the state carried by its glyph.
- **Change indicator (Analytics):** chip type without the box — micro, weight 700, uppercase — with a `9×9` arrow glyph for direction and a signed whole percentage on the previous period. Soft ink by default; `--ok` green only when the change is an improvement (results or CTR up, CPA down). A decline stays soft ink, never alarm red, and spend is never coloured because it has no better direction. With no earlier figure it reads "No prior data".

### Cards / Containers
There are no filled cards. The container surfaces are panels (`.panel`: transparent, a `1px` `{colors.rule}` hairline on all four sides, square, `1.25rem 1.5rem` padding, `{spacing.band}` apart): on Overview, Portfolio totals with its retained history and the client list, which adds a `20rem` minimum height (room for about three rows) so one client reads as the start of a list; on Analytics, one panel per section; the expanded history panel (raised ground, hairline on left, right and bottom, `1.25rem 1.25rem 0.5rem` padding) and the notice block (transparent, hairline border, `2px` ink top rule that becomes alarm on an error notice, capped at 70ch).

### Inputs / Fields
- **Target editor:** at rest, an inline button in figure type with a dashed strong-rule underline; hovering turns that underline solid ink. Empty targets read "Set target" in soft ink at weight 500.
- **Editing:** a `5.5rem` numeric input on raised ground with a `1px` ink border, followed by a filled Save and an outlined Cancel.
- **Focus:** the global `2px` ink outline; no border-colour change, no glow.
- **Error:** alarm-red micro text on a full-width flex basis under the field, capped at 28ch, announced via `role="alert"`.

### Navigation
A single top nav bar with two routed pages: **Overview** (`/`, the default) and **Analytics** (`/analytics`, a read-only view of one client, chosen by `?account=`). Unknown paths redirect to Overview. The URL carries the chosen reporting window as `?window=`, and the tabs carry it between pages, so any view is bookmarkable and a trip to Analytics does not reset it.

### Deviation Rail (signature)
Every row's zero is that account's **own** target, so bars grow from each client's own centre and no client is ever ranked against another. A hairline track spans the cell, an ink zero mark stands at 50%, and two soft-ink threshold ticks mark the ±15% band inside a ±50% full travel. The fill is `9px` deep, ink when under target and alarm when over, anchored with `transform-origin` at its own side, with the signed percentage set just outside its end in micro type — soft ink under, alarm over. Absent conditions never draw a fake bar: the track breaks into a dashed rule and a legend ("No target set", "Quiet N days", "No data in window") is knocked out of it with a ground-coloured background, the way a legend is set into a printed line.

### Vitals Trace
A `132×30` inline SVG on every row at rest, never behind a click. The account's own target is a dashed alarm line at 75% opacity; the cost-per-result path is an ink polyline at `1.35`, with a `2r` ink dot on the last known day. Days with spend but no results **break the line** rather than inventing a point, and a single isolated day is drawn as a dot. With nothing measurable, the trace degrades to a dashed strong-rule baseline.

### Charts
Recharts styled entirely from the tokens: soft-ink `10px` axis ticks at `0.08em` tracking, hairline horizontal grid only, strong-rule axis lines, spend bars in strong rule capped at `26px`, cost-per-result lines in ink at `1.75` with `connectNulls={false}`, and the target as a dashed alarm reference line. The portfolio area chart fills with the `ward-hatch` SVG pattern. Chart animation is disabled (`isAnimationActive={false}`) everywhere.

### Chart Readout (tooltip)
An ink block with enamel-raised text, square, minimum `12rem` wide: an uppercase micro date in rule grey over a two-column definition list, labels in rule grey and right-aligned tabular values in enamel.

### Named Rules
**The No Invented Point Rule.** A missing measurement is drawn as a break, a dash, or a knocked-out legend — never interpolated, never bridged, never given a zero.

## Do's and Don'ts

### Do:
- **Do** spend `{colors.alarm}` only on an account past its own target — monument, actual figure, rail fill and readout, out-of-range chip, target reference line, error text.
- **Do** encode every state three ways at once: the word, an authored `9×9` SVG glyph shape at `1.4` stroke, and a border treatment.
- **Do** set every numeral in tabular figures, adding `font-feature-settings: 'tnum' 1` on comparison figures.
- **Do** separate with hairlines, and open *and* close each major block with a rule.
- **Do** keep the rail's explanatory marks (`z-index: 3`) above its fill (`z-index: 1`).
- **Do** keep motion to the two authored moments: `rack-in` row entrance staggered by `--i` at `55ms` with `rail-draw` at a `200ms` offset, and `breach-arrive`, a single `1.3s` wash. Honour `prefers-reduced-motion`.
- **Do** use `cubic-bezier(0.16, 1, 0.3, 1)` for every transition and animation, at `0.15s` for control state changes.
- **Do** style browser surfaces — selection, caret, scrollbar, focus ring — from the same tokens.
- **Do** keep the board a single desktop layout. There is no mobile version, so no breakpoint rebuilds the table.

### Don't:
- **Don't** introduce a second hue. Green for good, amber for warning, or a blue accent all break the One Alarm Rule.
- **Don't** reintroduce `#7d8882` or any secondary grey lighter than `{colors.ink-soft}` for text.
- **Don't** add border radius, box-shadow, blur, or a filled card shell to any surface. Unfilled hairline panels are the only outlined bands.
- **Don't** use a gradient as shading; gradients here are hard-stop print hatches only.
- **Don't** fill the out-of-range chip solid — outlined only, so the red mass stays with the monument and the rail.
- **Don't** ship a looping animation, a spinner, a pulse that repeats, or chart entrance animation.
- **Don't** add a sidebar, a logo or invented brand mark, or a provenance colophon. The app bar's agency name, set as plain text, is the only nameplate.
- **Don't** rank accounts against one another in any new visualisation; every scale centres on the account's own target.
- **Don't** bridge or interpolate a missing day of data.
- **Don't** add a second type family or reach for an italic or width axis; Archivo's weight axis is the whole ramp.
