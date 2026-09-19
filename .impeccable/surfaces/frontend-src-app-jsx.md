---
version: 1
slug: "frontend-src-app-jsx"
primary_target: "frontend/src/App.jsx"
related_targets: []
---

Scope: the single dashboard surface at `frontend/src/App.jsx` and its components. Visitor mode: Operate.

Audience: the solo agency operator at a laptop at a desk, daylight, short sessions. **One user only** — corrected by the user on 2026-09-10: *"this is something for only me to use and then im just going to do a video demo."* The September 2026 demo is a recording, not a live walkthrough, so nobody else ever drives the interface and the surface owes no self-introduction: no nameplate, no title bar, no provenance colophon, no orientation copy for a stranger. Job: learn in one glance how many clients are off their own target, then go to the one that is.

Constraints: reads only from Postgres, never Meta at render time; alert-only, never acts on a campaign; one real account and eight days of July data, so quiet and empty states are the common case, not the edge.

## Direction contract

THESIS: The board owns exception, not summary. Every client is measured against its own target and healthy accounts go quiet. It refuses the category-default grid of equal KPI cards, where every account shouts at the same volume and nothing reads as a problem.

OWN-WORLD: A clinical enamel ward board. Pale cool grey-green ground (#E9EEEC), graphite ink (#16191A), hairline rules (#C6D0CB), and one alarm red (#C1272D) spent exclusively on a real breach — a healthy portfolio renders almost entirely in ink. One type family, Archivo, working through width and weight only, tabular figures throughout. Ruled columns, printed threshold bands, vitals traces. No card shells, no rounded containers, no gradients, no sidebar.

STORY: The operator opens it, reads one number — how many clients are out of range — and either closes the tab or goes straight to the red row. A video viewer watching over their shoulder sees, without narration, that many accounts live in one view, each judged against its own goal.

FIRST VIEWPORT: A full-width top band carrying the out-of-range count as a single monumental numeral, alarm red above zero, plain ink reading ALL ACCOUNTS IN RANGE at zero. Beneath it a hairline-ruled strip: portfolio spend, results, accounts tracked, last updated. Below that the ward board itself — one row per client with name, its own target, current cost per result, a deviation rail whose zero is that client's own goal, a retained trend trace, and a state chip. The board is the page.

FORM: The Ward Board. Candidate 7 of the grounded list; seed key 58c0f930. Code-led — no image generation on this machine.

SIGNATURE INTERACTION: The deviation rail. Every row's zero is its own target, so bars grow from each client's own centre and never rank clients against one another — the product's core rule made visible. Focusing a row expands it into its retained history, the trend Meta's own interface discards. Motion grammar: rows rack into the board once on load in a short stagger, rails draw outward from their own centre, a breach pulses once on arrival and never loops.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

Unresolved: the conversions figure is inflated upstream (all Meta action types summed), so cost per result reads roughly twice as favourable as reality; the board must not present it as trustworthy until ingest is fixed.
