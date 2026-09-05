# elsehow

A **renderer** for the `elsewhen` abstract timeline model. It reads a
presentation-agnostic abstract story (worlds, origins, events, splits,
transfers, route, fates, citations, profile parameters) and produces a
**clarity-first "Worlds and Thread" atlas** as SVG (primary) plus a self-contained
HTML companion.

This is the *consumer* side of the split: `elsewhen` describes *what* a film's
universe structure is; `elsehow` decides *how to see it*. It has no opinion on
the model — it reads the abstract JSON contract and renders it.

Design source:
[`references/visual-overhaul-design.md`](references/visual-overhaul-design.md)
(Astra, 2026-09-05) — a complete visual overhaul replacing the earlier atlas
([`references/visual-representation-design.md`](references/visual-representation-design.md)
and [`references/2.5d-guide.md`](references/2.5d-guide.md)).

## The design

- **Untruncated event cards** — every event gets a full-size card (name, story
  order, description, attributes, fate badge, citation chips). The canvas grows
  instead of shrinking typography.
- **Reserved routing gutters** — connections occupy dedicated tracks, not label
  space. Separate tracks plus arrowheads, white crossing bridges and keyed
  badges preserve attribution.
- **Colour = meaning** — slate rails identify worlds; **amber** = split
  outcomes; **blue** = transfers (with B/M/C/S mechanism badges); **emerald** =
  explicitly recorded route visits and links.
- **Legends + ledger + appendix** — a legend explains every element; a
  relationship ledger lists every connection; numbered citations resolve to a
  complete evidence appendix; sources and notes are included.
- **2D vs 2.5D** — the flat layout and the **cabinet-axonometric** variant share
  a Projection: 2D `(x, y)`, 2.5D `(x+0.5z, y−0.3z)` with decks at `z=24` and
  cables at `z=40`. Depth is *decorative separation only*, never time,
  probability or "more real"; text stays screen-facing.
- **No invention** — never draws a reset, never infers an unmodelled link,
  world, transfer or world-time value; `time_travel`/`body`/`memory`/
  `consciousness`/`signal` are reported as declared; `∅ nonexistent` stays
  `∅`.

## Usage

```bash
# Produce an abstract model from an elsewhen fixture (or author one)
python3 <elsewhen>/to_abstract.py <fixture>.json -o story.json     # elsewhen
python3 <elsewhen>/author.py ...                                     # elsewhen

# Render it here — every invocation writes an SVG master + an HTML companion
python3 render.py story.json -o story.svg                  # 2D atlas
python3 render.py story.json -o story-25d.svg --view 2.5d   # 2.5D cabinet-axonometric
python3 render.py story.json -o story.html --format html    # HTML primary
python3 render.py --self-test                                # run the self-test
```

The renderer is intentionally decoupled: it reads the abstract JSON directly and
does not import `elsewhen`'s Python. Regenerate the model on the engine side;
render here, any time.

## Layout

```
render.py                     the clarity-first atlas renderer (abstract JSON -> SVG + HTML, 2D + 2.5D)
references/visual-overhaul-design.md   the Astra redesign it implements (current)
references/visual-representation-design.md  the prior design (superseded)
references/2.5d-guide.md      the Astra 2.5D guide (superseded)
samples/                      sample renders (published films only, 2D + 2.5D as SVG + PNG)
```

## Self-test

`python3 render.py --self-test` validates the renderer against a built-in model
and reports diagnostics.

## Provenance

Design and implementation by Astra (gpt-6-astra) via OpenRouter, 2026-09-05.
Committed on `sfingali`.

The `samples/` gallery publishes **published films only** — sensitive or
unpublished screenplays (e.g. THE WAIF) are deliberately excluded and never
used as public reference/sample diagrams.
