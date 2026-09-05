# Visual overhaul design (Astra, 2026-09-05)

Design review + complete rewrite of the elsehow renderer, produced by Astra
(gpt-6-astra via OpenRouter). Supersedes the previous "Worlds and Thread" atlas
as the current visual approach.

**Verdict:** the old renderer compresses the information that needs space and
gives crossings no visual discipline. This is a replacement, not a restyle.

## Why this works

- Full-size, untruncated event cards; the canvas grows instead of shrinking
  typography.
- Connections occupy reserved routing gutters — not label space. Separate
  tracks, arrowheads, white crossing bridges, and keyed badges preserve
  attribution.
- The 2.5D view uses shallow **cabinet-axonometric decks**, not overlapping
  sheared plates. Text remains screen-facing.

## How to read it

- Read story order downward; equal-order cards share a band, not necessarily
  physical time.
- Slate rails identify worlds. Amber connections are split outcomes; blue
  connections are transfers; emerald tracks are explicitly recorded visits and
  links.
- Connector keys resolve to a relationship ledger. Numbered citations resolve to
  a complete evidence appendix.
- `time_travel` stays `time_travel`; it is **not** silently relabelled body
  transport.

## Exact layout

- World order follows the input array. Card width: **304 px**; text: **14 px /
  20 px leading**.
- Each ordinal band contains measured, vertically stacked cards, followed by
  **26 px per connector endpoint** of routing space.
- Each world reserves separate vertical tracks for connection trunks, endpoint
  stems, and overlapping visits.
- 2D: `P(x,y,z)=(x,y)`. 2.5D: `P(x,y,z)=(x+0.5z, y−0.3z)`; decks use `z=24`,
  cables `z=40`. Depth is decorative separation only.
- Both commands write **SVG and a self-contained HTML companion**:

```
python3 render.py tenet.json -o tenet.svg
python3 render.py tenet.json -o tenet-25d.svg --view 2.5d
```

## Hard rules the rewrite keeps (never invented)

- No inferred route links, transfers, worlds, resets or world-time values.
- `time_travel` / `body` / `memory` / `consciousness` / `signal` mechanisms are
  reported as declared, never relabelled.
- A "nonexistent" fate stays `∅`, never restyled as another kind of death.

## Provenance

Design and implementation authored by Astra (gpt-6-astra) via OpenRouter,
2026-09-05. The previous design (visual-representation-design.md) and the 2.5D
guide (2.5d-guide.md) remain as historical the source design it supersedes.
