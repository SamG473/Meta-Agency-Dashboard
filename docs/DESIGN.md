# Design System: The Ward Board

The visual system behind the dashboard, described from the shipped code. Tokens written as `--name` are CSS custom properties on `:root` in `frontend/src/styles.css`.

## Overview

The board is styled like a clinical ward board: a pale grey-green enamel ground, graphite ink, and hairline rules as the only way of separating one thing from another. There are no filled cards, no shadows, no rounded corners and no gradients.

Colour carries meaning and nothing else. A healthy or quiet portfolio renders almost entirely in ink and reads as calm on purpose. Red is reserved for a client that is past its own target; green and amber appear only in status chips and change indicators. Every client is judged against its own goal and never ranked against another.

Density is high and even. There is no sidebar and no orientation copy: an app bar, then the data. Every figure is set in tabular figures so columns of money align.

**Key characteristics:**
- Red only for a client past its own target; green and amber only for status
- Hairline rules as the only separation device; zero radius, zero shadow
- One type family, self-hosted Archivo Variable, tabular figures throughout
- State encoded three ways at once: the word, an SVG glyph shape, and a border colour
- Two motion moments, both one-off: rows sliding in, and a single red wash on a breached row

## Colors

A single cool grey-green family for the ground and ink, with three status colours.

### Status
- **Alarm Red** (`--alarm`, `#b81f27`): a client past its own target. It appears on a Behind or Missed row's actual figure, on the Behind and Missed chips, on the dashed target line in a client's expanded history chart, on the top rule of an error notice, on validation error text, and on the text caret. Nowhere else.
- **Alarm Wash** (`--alarm-wash`, `#f0d9da`): used only by the `breach-arrive` animation as a breached row lands. A motion value, never a resting fill.
- **Ok Green** (`--ok`, `#1a6b43`): the On track and Met chips, and a change indicator showing an improvement. 4.9:1 as text on the ground.
- **Warn Amber** (`--warn`, `#8a5a00`): the At risk chip only. A three-state badge needs a middle, and grey there would read as "no information" rather than "slipping". 5.9:1 as text on the ground.

### Neutral
- **Enamel Ground** (`--ground`, `#e9eeec`): the page, and the text colour of anything reversed out of ink (the pressed window segment, a hovered History button, the Save button, selected text).
- **Sunk Ground** (`--ground-sunk`, `#dfe6e3`): inline code, hover states on the window selector and the expanded history chart, and the base of the chart hatch. Never used to build a card.
- **Raised Ground** (`--ground-raised`, `#f2f5f3`): the expanded history panel, the target input and the goal/client select, the only surfaces that sit above the ground, still bounded by hairlines. Also the text colour of chart tooltips.
- **Graphite Ink** (`--ink`, `#16191a`): body text, headings, figures, the rules that open the strip and the table header, filled controls, chart lines, tooltip backgrounds and the focus ring.
- **Soft Ink** (`--ink-soft`, `#59635e`): the only secondary ink. Labels, captions, absent figures, neutral chips, axis ticks, and change indicators that are not improvements.
- **Hairline Rule** (`--rule`, `#c6d0cb`): panel borders, row separators, the app bar's hairline, chart grid lines, and tooltip labels.
- **Strong Rule** (`--rule-strong`, `#a4b2aa`): control borders, neutral chip borders, chart axis lines, spend bars, the chart hatch stroke, the empty-trace baseline and the scrollbar thumb.

### Rules
**Red means past target.** Red is spent on one thing: a client past its own target. Green and amber are status colours confined to chips and change indicators. Clients whose standing cannot be judged (no target, no end date, no data, not started) stay in grey, because neither green nor red would be honest.

**No lighter grey.** `--ink-soft` is the only secondary ink. A lighter `#7d8882` measured 3.13:1 on this ground, failed the 4.5:1 contrast floor, and was retired. Don't reintroduce it or anything lighter for text.

**Readable in greyscale.** State is always encoded redundantly: the state word, a glyph shape, and a border colour. Never colour alone.

## Typography

**Font:** Archivo Variable, self-hosted via `@fontsource-variable/archivo`, falling back to Archivo, system-ui, sans-serif. One family for everything, including inline `<code>`, which is set in the same face at weight 500 on sunk ground with a hairline border.

**Character:** a grotesque, tightly tracked at large sizes and widely tracked at small ones. Numerals are tabular everywhere (`font-variant-numeric: tabular-nums` on `body`), so a column of money reads as a stack.

Size tokens: `--t-lead` (1.1875rem), `--t-body` (0.9375rem), `--t-label` (0.6875rem), `--t-micro` (0.625rem).

### Hierarchy
- **Strip value:** the totals in a strip, `clamp(1.75rem, 2.8vw, 2.375rem)`, weight 600, `-0.03em`, with `font-feature-settings: 'tnum' 1` via `.num`.
- **Heading:** uppercase, ink, `--t-lead`, weight 700, `0.06em`. Panel names only, each an `<h2>`: "Portfolio totals" and "Clients" on Overview; "Period-over-period comparison", "CPA trend", "Cost per 1,000 reached trend", "CTR trend", "Frequency trend" and "Campaign / ad set breakdown" on Analytics.
- **Title:** `1.0625rem`, weight 600. Client names, ad set names and notice titles.
- **Figure:** `1rem`, weight 600, tabular. Target, actual and breakdown figures. When absent it drops to weight 500 in soft ink and prints an em dash.
- **Body:** `--t-body`. Prose, notice bodies, tooltips. Prose is capped by context: 28ch for errors, 52ch for the loading explanation, 66ch for empty states, 70ch for notices.
- **Label:** `--t-label`, weight 600, uppercase, `0.14em`, soft ink. Column headers, stat labels and captions such as "Portfolio history".
- **Micro:** `--t-micro`, weight 600, uppercase, `0.16em`, soft ink. Controls, captions and chart footnotes. Chips use the same size at weight 700 and `0.14em`.

### Rules
**One family.** Archivo Variable on its weight axis only (400 to 700). No second face, no italic.

**Uppercase has three registers.** Heading (ink, panel names), Label and Micro (soft ink, headers, captions and controls). Uppercase is never decorative.

## Layout

One centred column, `1360px` maximum (`--board-max`), with a fluid `--gutter`, `2.5rem` above the first panel and `3rem` of bottom padding.

**App bar.** A `--rule` hairline across the full window width, with its contents on the board's column: the agency name, a short hairline divider, then the page tabs. On a demo instance a "Demo data — not real client accounts" chip is pinned to the right, so it is on screen on every page and cannot be scrolled past.

**Panels.** Every section is a panel: a `1px` `--rule` box, `1.25rem 1.5rem` padding, `2.5rem` apart.

**Overview** has two panels:
1. **Portfolio totals.** The heading on the left with the window selector pinned right (the selector wraps above the heading when they cannot share a line). Beneath it the strip (Spend, Accounts, CPM, On pace), then the portfolio history chart, with no rule between them so the totals and their history read as one unit.
2. **Clients.** The heading over the client table, with a `20rem` minimum height so a single client reads as the start of a list.

**Analytics** is read-only panels for one client:
1. **Period-over-period comparison.** The heading, with a client picker and the window selector on the right. Then a strip of Spend, Results, CPA (unless only awareness ad sets spent), Cost / 1,000 reached (when awareness ad sets spent) and CTR, each with its change on the equal-length period before, and captions saying what was compared and what "results" counts.
2. **CPA trend**, **Cost per 1,000 reached trend** (only when awareness ad sets spent), **CTR trend** and **Frequency trend.** One line chart each, or a plain-language empty state.
3. **Campaign / ad set breakdown.** A five-column table (name, goal, spend, results, cost; widths 34/14/14/19/19%) reusing the client table's styling, with a unit caption under results and cost so a reach cost is never read as a cost per conversion.

**The strip** is an auto-fit grid of `minmax(min(140px, 100%), 1fr)` cells under an ink rule, divided by hairlines. The first cell is flush with the panel edge; the others are indented `1.75rem` off their divider.

**The client table** is a real `<table>`: `table-layout: fixed`, `border-collapse: collapse`, header underlined in ink, rows in hairline, cells padded `0.9rem` vertically. Its seven columns (Client, Goal, Target, Actual, Trend, State, History) have percentage widths of 18/12/12/12/18/16/12, summing to 100% so no column absorbs slack. Everything is left-aligned, with a `0.75rem` gap on each side of every cell and the outer edges flush; individual header labels are nudged with `padding-left` without moving their column. The trade-off, noted in the stylesheet: figures no longer line up on their last digit, which is invisible with a handful of clients but would argue for right-aligned Target and Actual columns at thirty.

**Responsive:** none, by design. The board is a desktop tool with a single layout and no breakpoint; `index.html` has no viewport meta tag.

## Elevation & Depth

There are no shadows, blur, glow or overlay scrims. Depth is rules and tone: hairlines separate, an ink rule opens the strip and the table header, and the raised-ground surfaces (expanded history, target input, selects) sit a half-step above the ground by tone alone, still bounded by hairlines.

## Shapes

Zero radius on every element: chips, buttons, inputs, panels and notices. There is no radius scale.

Strokes are hairlines: `1px` for rules and borders; `2px` only for the top rule of a notice, the current tab's underline, and the focus ring. Row traces are `132×30` SVGs at `1.35` stroke; chart lines are `1.75`; spend bars are capped at `26px` wide.

**Glyphs** are SVG on a `9×9` box at `1.4` stroke, `square` linecap, `currentColor`, one shape per state: a bar (On track), a chevron (At risk), a double chevron (Behind), a tick (Met), a cross (Missed), an arrow (No end date), a broken bar (No data), and a ring for the rest (Not started, No target). Change indicators use an up arrow, a down arrow, or a bar for no change.

**Texture.** One SVG pattern, `ward-hatch`: a 5px tile of sunk ground with a single diagonal stroke in strong rule, filling the portfolio history area. Dashed strokes mark things that are a reference or an absence rather than data: the target line (`4 4`), the empty-trace baseline (`4 5`), and the underline on the editable goal and target.

## Components

### Buttons and controls
- **Window selector:** three segments (30 days, 90 days, All) in one strong-rule box. Resting segments are transparent with soft ink; hover is sunk ground; the pressed segment (`aria-pressed="true"`) inverts to ink with ground text.
- **App bar name:** ink, `--t-lead`, weight 700, mixed case, `-0.01em`, parted from the tabs by a hairline with `1.75rem` either side. Plain text, not a logo.
- **Page tabs:** unboxed, `2rem` apart, `1.5rem` padding above and below, uppercase `--t-body`, weight 700, `0.08em`. Resting tabs are soft ink; hover darkens to ink with a strong-rule underline; the current page (`aria-current="page"`) is ink with a `2px` ink underline sitting on the bar's hairline. Weight never changes, so switching tabs moves nothing.
- **History button:** transparent with a strong-rule border and soft-ink micro type; on hover it inverts to ink.
- **Save / Cancel:** Save is filled ink with ground text (disabled: `opacity: 0.45`, `not-allowed`); Cancel is outlined.
- **Transitions and focus:** controls transition colour, background and border over `0.15s` on `--ease-out`. Focus is a `2px` ink outline at `2px` offset, never a coloured glow.

### Chips
- **Style:** inline-flex, square, `1px` border, micro type at weight 700, glyph and state word side by side with a `0.4rem` gap.
- **On track / Met:** `--ok` border and text.
- **At risk:** `--warn` border and text.
- **Behind / Missed:** `--alarm` border and text, outlined and never filled, so the red stays with the figures it describes.
- **No end date / Not started / No target / No data:** strong-rule border, soft ink, the state carried by its glyph.
- **Pace line:** under the chip, micro uppercase in soft ink: "Day 5 of 15 · 10 left", "Period ended · 15 days" or "Starts in 3 days". A state judged on pace is unreadable without it.
- **Change indicator (Analytics):** chip type without the box, with an arrow glyph and a signed whole percentage on the previous period. Soft ink by default; `--ok` only for an improvement (results or CTR up, a cost down). A decline stays soft ink, never red, and spend is never coloured because it has no better direction. With no earlier figure it reads "No prior data".

### Containers
- **Panel:** described under Layout.
- **Expanded history:** raised ground, hairline on left, right and bottom, `1.25rem 1.25rem 0.5rem` padding, opening beneath a client's row.
- **Notice:** strong-rule border with a `2px` ink top rule (red on an error notice), `1.25rem 1.5rem` padding, capped at 70ch. Used for errors, empty boards and stale links.
- **Loading:** a label while data loads. On the deployed demo only, after 2.5 seconds, a soft-ink line explains that the free-tier server may be waking up.

### Inputs
- **Goal picker:** at rest, the goal's name as a button with a dashed strong-rule underline that turns solid ink on hover. Clicked, it becomes a select on raised ground with an ink border. Changing the goal clears the target, since the old number was in the old metric's units. The Analytics client picker reuses the same select style.
- **Target editor:** at rest, the target in figure type with the same dashed underline; an empty target reads "Set target" in soft ink at weight 500. Editing shows a `5.5rem` numeric input on raised ground with an ink border, then Save and Cancel.
- **Error:** red micro text on its own line under the field, capped at 28ch, announced with `role="alert"`.

### Navigation
Two routed pages: **Overview** (`/`) and **Analytics** (`/analytics`, one client, chosen by `?account=`). Unknown paths redirect to Overview. The reporting window lives in the URL as `?window=`, and the tabs carry it between pages, so any view can be bookmarked and switching pages doesn't reset it.

### Row trace
A `132×30` inline SVG on every client row: that client's own goal metric over the window, as an ink polyline at `1.35`, with a `2`-radius dot on the last known day. Days the metric can't be computed for break the line, and an isolated day is drawn as a small dot. With nothing measurable, the trace is a dashed strong-rule baseline. It has no target line; the expanded history chart carries that.

### Charts
Recharts, styled from the tokens: soft-ink `10px` axis ticks at `0.08em`, horizontal grid lines only in `--rule`, axis lines in `--rule-strong`, and no animation (`isAnimationActive={false}`). There are three kinds:
- **Portfolio history** (Overview): daily spend as an ink area line filled with `ward-hatch`, on a real time axis. Any skipped day breaks the area, so two runs of delivery months apart never read as one trend.
- **Expanded history** (a client row): daily spend as strong-rule bars on the left axis, the client's goal metric as an ink line on the right axis, and, when a target is set, a dashed red target line. The axis lists only days on record, one slot each; a day on record whose metric can't be computed breaks the line.
- **Analytics trends:** one metric per chart as an ink line on a real time axis, with y-axis ticks from zero in steps of 1, 2, 2.5 or 5. Days with no value are left out and the line joins across them for gaps of up to 7 days, so a quiet day inside a run still reads as one trend; a longer gap breaks the line.

### Chart tooltip
An ink block with raised-ground text, square, at least `12rem` wide: the date in uppercase micro type in `--rule`, over a two-column list of labels in `--rule` and right-aligned tabular values.

### Missing data
A missing value is never drawn as zero. It shows as an em dash, a break in a line, a dashed baseline or a plain-language empty state. The one deliberate join is in the Analytics trends, which bridge gaps of up to 7 days as described above.

## Motion

Two moments, neither of which repeats:
- **`rack-in`:** client rows fade and slide up `6px` over `0.5s`, staggered `55ms` apart.
- **`breach-arrive`:** a Behind or Missed row also gets a single `1.3s` `--alarm-wash` background that fades out, starting `420ms` after its entrance.

Every transition and animation uses `--ease-out` (`cubic-bezier(0.16, 1, 0.3, 1)`), at `0.15s` for control state changes. `prefers-reduced-motion` collapses all of it to an instant.

## Do's and Don'ts

### Do
- **Do** keep `--alarm` for a client past its own target: the actual figure, the Behind/Missed chip, the target line, plus error states and the caret.
- **Do** encode every state three ways: the word, a `9×9` glyph shape, and a border colour.
- **Do** set every numeral in tabular figures.
- **Do** separate with hairlines; every section is a hairline panel.
- **Do** use `--ease-out` for all motion, and honour `prefers-reduced-motion`.
- **Do** style browser surfaces (selection, caret, scrollbar, focus ring) from the same tokens.
- **Do** keep the board a single desktop layout.

### Don't
- **Don't** use green or amber outside status chips and change indicators, or add another hue.
- **Don't** reintroduce `#7d8882` or any grey lighter than `--ink-soft` for text.
- **Don't** add border radius, box-shadow, blur, gradients or a filled card.
- **Don't** fill the Behind/Missed chip solid.
- **Don't** add a looping animation, a spinner, or chart entrance animation.
- **Don't** add a sidebar or an invented logo; the agency's name in plain text is the only nameplate.
- **Don't** rank clients against one another; each is judged against its own target.
- **Don't** draw a missing value as zero.
- **Don't** add a second type family or an italic.
