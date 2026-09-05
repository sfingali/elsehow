# Visual design (Astra, 2026-09-05)

The renderer's visual language, from a blank brief (data contract only — no
prescribed style, no template to mirror). Authored by Astra (gpt-6-astra via
OpenRouter). This supersedes the earlier atlas and the rejected text-card
overhaul as the current approach.

## Design principles

- **Worlds are containment rails, not inferred histories.** Each world is a rail;
  nothing about a world's past is guessed.
- **Horizontal positions rank declared numeric orders; gaps are not durations.**
  Spatial separation is ordinal, never a time scale.
- **Null orders occupy a separately labelled, explicitly unordered area.**
- **Only declared relationships produce connectors.** No inferred links,
  transfers, worlds, resets, or world-time values.
- **2.5D: the same diagram is projected onto a receding plane. Depth has no
  narrative or temporal meaning** — it is purely a clearer view.
- **Every input value is retained** in a visible, linked record appendix and in
  the SVG metadata. **Unresolvable relationships are reported, not guessed.**

## Data conventions recognised

The schema leaves `segments`, `beats`, `visits`, and `route links` structurally
open. This renderer recognises the sample conventions:

- `segment: {id, universe, from: event_id, to: event_id}`
- `beat:    {segment: segment_id, order: number, text}`
- `visit:   {id, universe, entry: event_id, exit: event_id, passes: [event_id, ...]}`
- `link:    {from: visit_id, to: visit_id, kind, via: transfer_id}`

Other structures remain fully visible in the record appendix.

## Provenance

Implementation authored by Astra (gpt-6-astra) via OpenRouter, 2026-09-05, from a
blank brief (data contract only). Prior designs — visual-representation-design.md,
2.5d-guide.md, and the earlier text-card overhaul — are retained as history and
are superseded by this document.
