# elsehow

A **renderer** for the `elsewhen` abstract timeline model. It reads a
presentation-agnostic abstract story (worlds, origins, events, splits,
transfers, route, fates, citations, profile parameters) and produces an
**offline SVG + HTML "Universe Timeline Atlas"**.

This is the *consumer* side of the split: `elsewhen` describes *what* a film's
universe structure is; `elsehow` decides *how to see it*. It has no opinion on
the model — it reads the abstract JSON contract and renders it.

Design source:
[`references/visual-overhaul-design.md`](references/visual-overhaul-design.md)
(Astra, 2026-09-05) — produced from a blank brief (data contract only, no
prescribed style or template). Supersedes the earlier atlas and the interim
text-card overhaul.

## Gallery

Full-resolution renders of published films, in both views — see
**[the gallery](samples/GALLERY.md)**. The default image is the **atlas chart**;
the **record index** is a separate image; SVG vector masters are linked per film.

## How it draws

- **Worlds are containment rails** — one rail per universe; nothing about a
  world's past is inferred.
- **Ordinal ordering** — horizontal positions rank declared numeric event orders;
  gaps are not durations. Null orders sit in a separately labelled unordered area.
- **Only declared relationships produce connectors** — splits (amber), transfers
  (with B/M/C/S mechanism badges), and the declared route/thread. Never invents a
  link, transfer, world, reset, or world-time.
- **Fates** — `● alive · × dead · ? unknown · ∅ nonexistent`.
- **Retained input** — every input value is kept in a visible, linked record
  appendix and in the SVG metadata; unresolvable relationships are reported, not
  guessed.
- **2D & 2.5D** — the flat layout and a receding-planed projection; depth has no
  narrative or temporal meaning.
- Every invocation writes **both** an SVG primary and an HTML companion.

## Usage

```bash
# Produce an abstract model from an elsewhen fixture (or author one)
python3 <elsewhen>/to_abstract.py <fixture>.json -o story.json     # elsewhen
python3 <elsewhen>/author.py ...                                     # elsewhen

# Render it here — writes both the SVG and the HTML companion
python3 render.py story.json -o story.svg                  # 2D atlas
python3 render.py story.json -o story-25d.svg --view 2.5d   # 2.5D receding-plane
python3 render.py story.json -o story.html --format html    # HTML primary
```

The renderer is intentionally decoupled: it reads the abstract JSON directly and
does not import `elsewhen`'s Python. Regenerate the model on the engine side;
render here, any time.

## Layout

```
render.py                     the atlas renderer (abstract JSON -> SVG + HTML, 2D + 2.5D)
references/visual-overhaul-design.md   the Astra design it implements (current)
references/visual-representation-design.md  the prior design (superseded)
references/2.5d-guide.md      the prior 2.5D guide (superseded)
samples/                      full-resolution gallery (published films only, 2D + 2.5D as SVG + PNG + GALLERY.md)
```

## Provenance

Design and implementation by Astra (gpt-6-astra) via OpenRouter, 2026-09-05, from
a blank brief. Committed on `sfingali`.

The `samples/` gallery publishes **published films only** — sensitive or
unpublished screenplays (e.g. THE WAIF) are deliberately excluded and never
used as public reference/sample diagrams.
