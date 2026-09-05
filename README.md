# elsehow

A **renderer** for the `elsewhen` abstract timeline model. It reads a
presentation-agnostic abstract story (worlds, origins, events, splits,
transfers, route, fates, citations, profile parameters) and produces a
**"Worlds and Thread" 2D vertical timeline atlas** as SVG (primary) or a
self-contained HTML.

This is the *consumer* side of the split: `elsewhen` describes *what* a film's
universe structure is; `elsehow` decides *how to see it*. It has no opinion on
the model — it reads the abstract JSON contract and renders it.

Design source: [`references/visual-representation-design.md`](references/visual-representation-design.md)
(Astra, 2026-09-05).

## The atlas

- **World rails** — one thin vertical rail per universe; the opening universe is
  placed rightmost and the thread migrates leftward.
- **Origin markers** — initial (square), born (rail starts at its birth fork),
  preexisting (enters from the top, "already existed"), unknown (`?`).
- **Event nodes** — start (green square), split (amber circle), entry/exit
  (dot/anchor diamond), cutoff (grey square); story order printed downward.
- **Splits** — structural edges from the split node to every outcome, marked
  `+` and `−`. Both are *outcome signs*, not follow/death: the followed tine
  comes from the route links, never from the sign. Never a "reset".
- **Transfers** — elbowed connectors with a mechanism badge **B/M/C/S**
  (body / memory / consciousness / signal).
- **Route/thread** — a thick green stroke along the protagonist's visits.
- **Fates** — badges `× dead · ● alive · ? unknown · ∅ nonexistent`.
- **Citations** — numbered evidence tabs (scene/page) beside events.

Profile parameters (history_model, branching, coexistence, turnstiles,
genealogy, …) drive what is drawn — e.g. `iterations` packs repeat bands on one
world, `revisions` keeps an archive, `branching=undeclared` stays neutral. The
renderer never invents topology.

## Usage

```bash
# Produce an abstract model from an elsewhen fixture (or author one)
python3 <elsewhen>/to_abstract.py <fixture>.json -o story.json     # elsewhen
python3 <elsewhen>/author.py ...                                     # elsewhen

# Render it here
python3 render.py story.json -o story.svg                  # 2D atlas (SVG)
python3 render.py story.json -o story.html --format html   # 2D (HTML)
python3 render.py story.json -o story-25d.svg --view 2.5d   # 2.5D orthographic
```

The renderer is intentionally decoupled: it reads the abstract JSON directly and
does not import `elsewhen`'s Python. Regenerate the model on the engine side;
render here, any time.

## Layout

```
render.py                     the "Worlds and Thread" renderer (abstract JSON -> SVG/HTML, 2D + 2.5D)
references/visual-representation-design.md   the Astra design it implements
references/2.5d-guide.md      the Astra guide for the 2.5D projection
samples/                      sample renders (published films only, 2D + 2.5D as SVG + PNG)
```

Review-drive corrections applied: ordinal order bands (not proportional spacing),
link-driven route thread (missing links are gaps, not guessed continuity),
unknown-world diagnostic cards, birth-aware rails, corrected `+`/`−` legend, and
world+order collision grouping.

## Provenance

Design by Astra (gpt-6-astra) via Experiential Labs. Rendered with the `elsewhen`
abstract model. Committed on `sfingali`.

The `samples/` gallery publishes **published films only** — sensitive or
unpublished screenplays (e.g. THE WAIF) are deliberately excluded and never
used as public reference/sample diagrams.
