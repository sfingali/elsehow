#!/usr/bin/env python3
"""Elsehow — a renderer for the elsewhen abstract timeline model.

Reads a presentation-agnostic abstract story JSON (worlds, origins, events,
splits, transfers, route, fates, citations, profile parameters) and produces a
'Worlds and Thread' timeline atlas as SVG (primary) or a self-contained HTML.

Two views:
  --view 2d    flat vertical timeline atlas (default)
  --view 2.5d  the same layout projected orthographically (isometric tilt);
               depth is exploded separation only, never time/probability.

Honours 'never draw a reset'; profile parameters drive what is drawn without
inventing topology.

Review-derived corrections (see references/visual-representation-design.md and
references/2.5d-guide.md): ordinal order bands (not proportional), link-driven
route thread, unknown-world diagnostics, birth-aware rails, corrected legend,
and world+order collision grouping.

Usage:
    python3 render.py story.json -o out.svg                  # 2D
    python3 render.py story.json -o out.svg --view 2.5d      # 2.5D
    python3 render.py story.json -o out.html --format html --view 2.5d
"""

import argparse
import json
import math
import sys
import xml.sax.saxutils as sx

# ---- palette ---------------------------------------------------------
COL = {
    "bg": "#ffffff", "text": "#202124", "muted": "#5f6368", "rail": "#9aa0a6",
    "thread": "#2f7d4f", "split": "#e8a33d", "start": "#3d8f4f", "cutoff": "#5f6368",
    "death": "#c0392b", "alive": "#2f7d4f", "unknown": "#7f8c8d", "nonexit": "#000000",
    "warn": "#c0392b",
    "init_fill": "#e8f0fe", "born_fill": "#fdf3d0", "pre_fill": "#e6f4ea", "unk_fill": "#f5f5f5",
}
MECH = {"body": "B", "memory": "M", "consciousness": "C", "signal": "S",
        "body_transport": "B", "consciousness_transfer": "C"}
FATE = {"dead": ("×", COL["death"]), "alive": ("●", COL["alive"]),
        "unknown": ("?", COL["unknown"]), "nonexistent": ("∅", COL["nonexit"])}
FONT = "Arial, Helvetica, sans-serif"

# scene/plan units (not pixels)
TOP, BOT, LEFT = 96, 120, 60
BAND = 54            # story-order band spacing
SHELF = 40           # null-order shelf offset below the last band
MIN_GAP = 130        # min world column gap (many worlds compress)
GAP = 250            # default world column gap
STRIP_W = 28         # 2.5D world strip width


def esc(s):
    return sx.escape(str(s if s is not None else ""))


# ---- label layout helpers (collision avoidance + leader lines) ----
CHAR_W = 5.4        # avg glyph width at font-size 9 (Arial)
LINE_H = 11.0
LABEL_PAD = 3.0     # collision padding around each label box


def text_w(s, fs=9.0):
    return len(s) * CHAR_W * (fs / 9.0)


def wrap(s, width_chars=24):
    """Word-wrap to <=2 lines (ellipsis if longer). Returns list of lines."""
    words = str(s).split()
    lines, cur = [], []
    for w in words:
        if cur and len(" ".join(cur)) + 1 + len(w) > width_chars:
            lines.append(" ".join(cur)); cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(" ".join(cur))
    if len(lines) > 2:
        lines = lines[:2]
        if len(lines[1]) > 3:
            lines[1] = lines[1][:-3].rstrip() + "..."
    return lines or [""]


def _rects_overlap(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return not (ax + aw < bx or bx + bw < ax or ay + ah < by or by + bh < ay)


def layout_labels(pending, xmax, ymax, obstacles=None):
    """Greedy non-overlap layout for billboard labels.

    pending: list of dicts {ax, ay, text}. Placed top-left anchor is the node
    centre; each label is pushed right/above/below/left/stacked until free and
    its leader pulled back to the node. `obstacles` (node glyph boxes etc.) are
    pre-placed so labels don't sit on top of markers. Returns list of
    (ax, ay, lines, lead_from, lead_to) where lead_from is the node point.
    """
    pending = sorted(
        [{**p, "tex": wrap(p["text"])} for p in pending],
        key=lambda p: (p["ay"], p["ax"]),
    )
    placed = list(obstacles) if obstacles else []
    out = []
    for p in pending:
        lines = p["tex"]
        w = max((text_w(l, 9) for l in lines), default=0)
        h = LINE_H * len(lines)
        ax, ay = p["ax"], p["ay"]
        # candidate placements, priority order: right, above, right-stacked, left, below
        cands = [
            ("right", ax + 12, ay - h / 2.0, (ax, ay), (ax + 12, ay)),
            ("above", ax - w / 2.0, ay - 10 - h, (ax, ay), (ax - w / 2.0, ay - 10)),
        ]
        for k in range(1, 8):  # stacked right, sliding down one row each
            cands.append(("right_stack", ax + 12, ay - h / 2.0 + k * LINE_H, (ax, ay), (ax + 12, ay - h / 2.0 + k * LINE_H)))
        for k in range(1, 8):  # stacked above, sliding up
            cands.append(("above_stack", ax - w / 2.0, ay - 10 - h - k * LINE_H, (ax, ay), (ax - w / 2.0, ay - 10 - k * LINE_H)))
        cands += [
            ("left", ax - 12 - w, ay - h / 2.0, (ax + 12, ay), (ax - 12, ay)),
            ("below", ax - w / 2.0, ay + 12, (ax, ay), (ax - w / 2.0, ay + 12)),
        ]
        best = None
        for side, bx, by, lead_a, lead_b in cands:
            # keep on canvas
            if bx < LABEL_PAD or by < LABEL_PAD or bx + w > xmax - LABEL_PAD or by + h > ymax - LABEL_PAD:
                continue
            box = (bx - LABEL_PAD, by - LABEL_PAD, w + 2 * LABEL_PAD, h + 2 * LABEL_PAD)
            if not any(_rects_overlap(box, pl) for pl in placed):
                best = (bx, by, lead_a, lead_b)
                placed.append(box)
                break
        if best is None:  # fallback: right at node, ignore collision
            bx, by = ax + 12, ay - h / 2.0
            best = (bx, by, (ax, ay), (ax + 12, ay))
            placed.append((bx - LABEL_PAD, by - LABEL_PAD, w + 2 * LABEL_PAD, h + 2 * LABEL_PAD))
        out.append((best[0], best[1], lines, best[2], best[3]))
    return out


def order_bands(g):
    """Ordinal bands: rank distinct story orders (not proportional spacing)."""
    orders = sorted({e.get("order") for e in g.get("events", []) if e.get("order") is not None})
    band = {o: i for i, o in enumerate(orders)}
    nulls = [e for e in g.get("events", []) if e.get("order") is None]
    return orders, band, nulls


def ordered_worlds(g):
    """Worlds left-to-right by first story-order appearance (opening rightmost)."""
    first = {}
    for e in g.get("events", []):
        w, o = e.get("universe"), e.get("order")
        if w is None:
            continue
        if w not in first or (o is not None and (first[w] is None or o < first[w])):
            first[w] = o
    def key(w):
        o = first.get(w["id"])
        return (1 if o is None else 0, o if o is not None else 1e18, w["id"])
    return sorted(g.get("worlds", []), key=key)


def col_gap_for(n):
    return max(MIN_GAP, min(GAP, (1500 - 2 * LEFT) // max(1, n)))


def project(x, y, z, theta=math.radians(30), phi=math.radians(12), scale=1.0, ox=0.0, oy=0.0):
    """Orthographic projection (2.5d-guide.md). Returns (sx, sy, depth)."""
    u = math.cos(phi) * x - math.sin(phi) * y
    v = math.sin(phi) * x + math.cos(phi) * y
    sx = ox + scale * u
    sy = oy + scale * (math.cos(theta) * v - math.sin(theta) * z)
    depth = math.sin(theta) * v + math.cos(theta) * z   # larger = nearer
    return sx, sy, depth


# ---- a scene: list of drawable primitives in 3D plan coords ----
# Each primitive is (kind, data). Kinds: 'rail','plate','node','edge',
# 'cable','thread','fate','text','badge','diag','stripend'.
def build_scene(g):
    ev = event_map(g)
    worlds = ordered_worlds(g)
    n = len(worlds)
    widx = {w["id"]: i for i, w in enumerate(worlds)}
    orders, band, nulls = order_bands(g)
    nband = len(orders)
    gap = col_gap_for(n)

    def xw(wid):
        return LEFT + (n - 1 - widx.get(wid, 0)) * gap + 40

    def yband(o):
        return TOP + band[o] * BAND

    def epos(eid):
        e = ev.get(eid)
        if not e:
            return None, None
        y = yband(e["order"]) if e.get("order") is not None else TOP + nband * BAND + SHELF
        return xw(e.get("universe")), y

    scene = []
    bad_refs = []

    # world rails (birth-aware) + plates + headers
    for i, w in enumerate(worlds):
        ws = [e for e in g.get("events", []) if e.get("universe") == w["id"]]
        kind = w.get("origin", "unknown")
        # rail start: born begins at its declared birth event; others from the top
        ytop = TOP - 6
        railstart = ytop
        if kind == "born":
            born_ev = (w.get("born") or {}).get("event")
            be = ev.get(born_ev)
            railstart = yband(be["order"]) if be and be.get("order") is not None else TOP
        ys = [epos(e["id"])[1] for e in ws if e.get("order") is not None] or [TOP]
        ybot = max(ys)
        scene.append(("rail", (xw(w["id"]), railstart, ybot, kind, w["id"], w.get("label", ""))))
        scene.append(("plate", (xw(w["id"]), railstart, ybot, kind)))

    # diagnostics: unknown world references
    for e in g.get("events", []):
        if e.get("universe") and e["universe"] not in widx:
            bad_refs.append(f"event {e['id']} → unknown world {e['universe']!r}")
    for fa in g.get("fates", []):
        if fa.get("universe") and fa["universe"] not in widx:
            bad_refs.append(f"fate {fa['id']} → unknown world {fa['universe']!r}")

    # split edges (under nodes): split node -> outcome entry
    for sp in g.get("splits", []):
        sx_, sy_ = epos(sp.get("event"))
        if sx_ is None:
            continue
        for sign, o in (sp.get("outcomes") or {}).items():
            tx, ty = epos(o.get("entry"))
            if tx is None:
                continue
            scene.append(("edge", (sx_, sy_, tx, ty, sign, sp.get("event"))))

    # transfers: cable elbow in scene space (z = lift)
    for tr in g.get("transfers", []):
        f = epos(tr.get("from", {}).get("exit"))
        t = epos(tr.get("to", {}).get("entry"))
        if not f[0] or not t[0]:
            continue
        scene.append(("cable", (f[0], f[1], t[0], t[1], MECH.get((tr.get("mechanism") or "").lower(), "·"),
                              tr.get("traveller", ""), tr.get("id", ""))))

    # thread: occupation segments + link-driven connectors
    route = g.get("route") or {}
    vis = {v.get("id"): v for v in route.get("visits", [])}
    for v in route.get("visits", []):
        en = epos(v.get("entry"))
        ex = epos(v.get("exit"))
        if en[0] and ex[0]:
            scene.append(("thread_once", (en[0], en[1], ex[0], ex[1])))
    for lk in route.get("links", []):
        a = vis.get(lk.get("from"))
        b = vis.get(lk.get("to"))
        if not a or not b:
            continue
        ax, ay = epos(a.get("exit"))
        bx, by = epos(b.get("entry"))
        if ax is None or bx is None:
            continue
        scene.append(("thread_link", (ax, ay, bx, by)))

    # events as nodes (group collisions by world+order)
    by_world_order = {}
    for e in g.get("events", []):
        by_world_order.setdefault((e.get("universe"), e.get("order")), []).append(e)
    for (univ, order), evs in by_world_order.items():
        basex = xw(univ)
        y = yband(order) if order is not None else TOP + nband * BAND + SHELF
        off = (len(evs) - 1) / 2.0
        for j, e in enumerate(evs):
            x = basex + (j - off) * 16
            scene.append(("node", (x, y, e.get("kind"), e.get("id"), order, e.get("label", ""),
                                   (e.get("cite") or {}).get("scene") or (e.get("cite") or {}).get("page") or "")))

    # fates
    for fa in g.get("fates", []):
        x, y = epos(fa.get("event"))
        if x is None:
            continue
        scene.append(("fate", (x + 14, y, fa.get("status"), fa.get("instance", ""))))

    return scene, bad_refs, worlds, nband


def event_map(g):
    return {e.get("id"): e for e in g.get("events", [])}


# ---- project a scene to 2D or 2.5D and emit SVG ----
def emit(scene, view, W, H, bad_refs, story, g):
    is25 = view == "2.5d"

    def P(px, py, z=0.0):
        if not is25:
            return px, py
        sx, sy, _ = project(px, py, z)
        return sx, sy

    def m(x1, y1, x2, y2, color, width, dash=False, z=0.0, op=1.0):
        a = P(x1, y1, z); b = P(x2, y2, z)
        d = f' stroke-dasharray="{width*3},{width*2}"' if dash else ""
        return (f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" '
                f'stroke="{color}" stroke-width="{width}"{d} stroke-opacity="{op}"/>')

    out = []
    pending = []   # deferred event labels -> collision-avoided callouts
    node_boxes = []  # node glyph obstacles so labels push off markers
    # headers
    cx = W / 2.0
    out.append(f'<text x="{cx:.0f}" y="24" text-anchor="middle" font-size="18" font-weight="bold" fill="{COL["text"]}">{esc(story.get("title",""))}</text>')
    out.append(f'<text x="{cx:.0f}" y="42" text-anchor="middle" font-size="11" fill="{COL["muted"]}">{esc(g.get("namespace",""))} — {esc(g.get("title",""))} · {esc(story.get("subtitle",""))}</text>')

    # plates (2.5D) and rails (2D+2.5D)
    for item in scene:
        if item[0] == "plate":
            if not is25:
                continue
            x, y1, y2, kind = item[1]
            fill = {"initial": COL["init_fill"], "born": COL["born_fill"],
                    "preexisting": COL["pre_fill"], "unknown": COL["unk_fill"]}.get(kind, "#f5f5f5")
            half = STRIP_W / 2.0
            p1 = P(x - half, y1, 0); p2 = P(x + half, y1, 0)
            p3 = P(x + half, y2, 0); p4 = P(x - half, y2, 0)
            out.append(f'<polygon points="{p1[0]:.1f},{p1[1]:.1f} {p2[0]:.1f},{p2[1]:.1f} {p3[0]:.1f},{p3[1]:.1f} {p4[0]:.1f},{p4[1]:.1f}" fill="{fill}" stroke="{COL["rail"]}" stroke-width="1"/>')
        elif item[0] == "rail":
            x, y1, y2, kind, wid, label = item[1]
            out.append(m(x, y1, x, y2, COL["rail"], 2, z=0.0))
            # origin marker / header
            if kind == "initial":
                out.append(f'<rect x="{x-7:.1f}" y="{y1-18:.1f}" width="14" height="14" fill="{COL["init_fill"]}" stroke="{COL["text"]}"/>')
            elif kind == "preexisting":
                out.append(f'<text x="{x:.1f}" y="{y1-8:.1f}" text-anchor="middle" font-size="10" fill="{COL["muted"]}">* already existed</text>')
            elif kind == "unknown":
                out.append(f'<text x="{x:.1f}" y="{y1-8:.1f}" text-anchor="middle" font-size="14" fill="{COL["muted"]}">?</text>')
            text = f'<text x="{x:.1f}" y="{y1-32:.1f}" text-anchor="middle" font-size="11" fill="{COL["text"]}">{esc(wid)}: {esc(label[:26])}</text>'
            out.append(text if is25 else text)
        elif item[0] == "edge":
            x1, y1, x2, y2, sign, ev = item[1]
            out.append(m(x1, y1, x2, y2, COL["split"], 2, dash=(sign == "-")))
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            a = P(mx, my)
            out.append(f'<text x="{a[0]:.1f}" y="{a[1]-6:.1f}" text-anchor="middle" font-size="13" font-weight="bold" fill="{COL["split"]}">{sign}</text>')
        elif item[0] == "cable":
            x1, y1, x2, y2, mech, trav, tid = item[1]
            z = 16.0 if is25 else 0.0
            mx = (x1 + x2) / 2
            verts = [(x1, y1, z), (mx, y1, z), (mx, y2, z), (x2, y2, z)]
            pts = " ".join(f"{P(*vv)[0]:.1f},{P(*vv)[1]:.1f}" for vv in verts)
            out.append(f'<polyline points="{pts}" fill="none" stroke="{COL["thread"]}" stroke-width="2" stroke-opacity="0.6"/>')
            b = P(mx, (y1 + y2) / 2, z)
            out.append(f'<circle cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="10" fill="{COL["bg"]}" stroke="{COL["thread"]}"/>')
            out.append(f'<text x="{b[0]:.1f}" y="{b[1]+4:.1f}" text-anchor="middle" font-size="12" font-weight="bold" fill="{COL["thread"]}">{mech}</text>')
        elif item[0] in ("thread_once", "thread_link"):
            x1, y1, x2, y2 = item[1]
            a = P(x1, y1, 2.0 if is25 else 0.0); b = P(x2, y2, 2.0 if is25 else 0.0)
            out.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{COL["thread"]}" stroke-width="6" stroke-opacity="0.35" stroke-linecap="round"/>')
        elif item[0] == "node":
            x, y, kind, eid, order, label, cite = item[1]
            a = P(x, y)
            node_boxes.append((a[0] - 13, a[1] - 13, 26, 26))
            if kind == "split":
                out.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="7" fill="{COL["split"]}" stroke="{COL["text"]}"/>')
            elif kind == "start":
                out.append(f'<rect x="{a[0]-6:.1f}" y="{a[1]-6:.1f}" width="12" height="12" fill="{COL["start"]}" stroke="{COL["text"]}"/>')
            elif kind == "cutoff":
                out.append(f'<rect x="{a[0]-6:.1f}" y="{a[1]-6:.1f}" width="12" height="12" fill="{COL["cutoff"]}" stroke="{COL["text"]}"/>')
            elif kind in ("entry", "exit"):
                out.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="5" fill="{COL["bg"]}" stroke="{COL["text"]}"/>')
            elif kind == "anchor":
                out.append(f'<path d="M {a[0]:.1f} {a[1]-6:.1f} L {a[0]+6:.1f} {a[1]:.1f} L {a[0]:.1f} {a[1]+6:.1f} L {a[0]-6:.1f} {a[1]:.1f} Z" fill="{COL["cutoff"]}" stroke="{COL["text"]}"/>')
            else:
                out.append(f'<circle cx="{a[0]:.1f}" cy="{a[1]:.1f}" r="4" fill="{COL["text"]}"/>')
            out.append(f'<text x="{a[0]:.1f}" y="{a[1]+16:.1f}" text-anchor="middle" font-size="9" fill="{COL["muted"]}">{esc(str(order if order is not None else "∅"))}{esc(("·" + cite) if cite else "")}</text>')
            if label:
                pending.append({"ax": a[0], "ay": a[1], "text": label})
        elif item[0] == "fate":
            x, y, status, inst = item[1]
            a = P(x, y)
            symbol, color = FATE.get(status, FATE["unknown"])
            out.append(f'<text x="{a[0]:.1f}" y="{a[1]+4:.1f}" font-size="14" font-weight="bold" fill="{color}">{symbol}</text>')
            out.append(f'<text x="{a[0]+4:.1f}" y="{a[1]+4:.1f}" font-size="8" fill="{COL["muted"]}">{esc(inst)}</text>')

    # event labels: collision-avoided billboards with leader callouts
    if pending:
        for bx, by, lines, (lx1, ly1), (lx2, ly2) in layout_labels(pending, W, H, node_boxes):
            out.append(f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" x2="{lx2:.1f}" y2="{ly2:.1f}" stroke="{COL["muted"]}" stroke-width="1" stroke-opacity="0.5"/>')
            for i, line in enumerate(lines):
                out.append(f'<text x="{bx:.1f}" y="{by + (i+1)*LINE_H - 3:.1f}" font-size="9" fill="{COL["muted"]}">{esc(line)}</text>')

    # diagnostics (unknown world refs etc.)
    if bad_refs:
        out.append(f'<text x="10" y="{H-4:.0f}" font-size="10" fill="{COL["warn"]}">{esc("Broken references: " + "; ".join(bad_refs[:4]))}</text>')

    return "\n".join(out)


def render_graph(story, g, view):
    scene, bad_refs, worlds, nband = build_scene(g)
    gap = col_gap_for(len(worlds))
    W = LEFT * 2 + len(worlds) * gap + 80
    H = TOP + BOT + (nband + 1) * BAND + SHELF
    inner = emit(scene, view, W, H, bad_refs, story, g)
    return inner, W, H, bad_refs


def render_js(story, view="2d"):
    GAP = 48
    groups, total, maxw = [], 0, 0
    bad = []
    for g in story.get("graphs", []):
        inner, W, H, br = render_graph(story, g, view)
        groups.append((inner, W, H))
        bad += br
        total += H + GAP
        maxw = max(maxw, W)
    maxw = max(maxw, 900)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{maxw}" height="{total}" viewBox="0 0 {maxw} {total}" font-family="{FONT}">',
             f'<rect width="{maxw}" height="{total}" fill="{COL["bg"]}"/>']
    off = 0
    for inner, W, H in groups:
        parts.append(f'<g transform="translate(0,{off})">{inner}</g>')
        off += H + GAP
    parts.append('</svg>')
    return "\n".join(parts)


def render_html(story, view="2d"):
    svg = render_js(story, view)
    prof = story.get("profile", {})
    params = prof.get("params", {})
    p_s = " · ".join(f"{k} {v if not isinstance(v, list) else '/'.join(v)}" for k, v in params.items())
    vert = "2.5D (orthographic; depth = exploded separation only, never time)" if view == "2.5d" else "2D"
    legend = (f'<div class="box"><b>Legend</b> · {vert} · mechanism badges: '
              f'<b>B</b>body <b>M</b>memory <b>C</b>consciousness <b>S</b>signal · '
              f'fates <span style="color:{COL["death"]}">× dead</span> <span style="color:{COL["alive"]}">● alive</span> '
              f'<span style="color:{COL["unknown"]}">? unknown</span> ∅ nonexistent · '
              f'split tines <b>+</b>/<b>−</b> are outcome signs (the followed tine comes from route links)</div>')
    html = (f'<!doctype html><html><head><meta charset="utf-8"><title>{esc(story.get("title",""))}</title>'
            f'<style>body{{font-family:{FONT};margin:24px;background:#fff;color:{COL["text"]}}}'
            f'.box{{font-size:12px;color:{COL["muted"]};margin:6px 0 14px;padding:6px 8px;border:1px solid #ddd;border-radius:6px}}'
            f'.header{{font-size:11px;color:{COL["muted"]};margin-bottom:10px}}'
            f'.note{{font-size:11px;color:{COL["muted"]};margin-top:10px}}</style></head><body>'
            f'<div class="header">profile: {esc(prof.get("name",""))} · {esc(prof.get("rules",""))} · {esc(p_s)}</div>'
            f'{legend}<div style="overflow-x:auto">{svg}</div>'
            f'<div class="note">{esc(story.get("footer",""))}</div>'
            f'</body></html>')
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--format", choices=["svg", "html"], default=None)
    ap.add_argument("--view", choices=["2d", "2.5d"], default="2d")
    a = ap.parse_args()
    with open(a.input) as fh:
        story = json.load(fh)
    fmt = a.format or ("html" if a.out.endswith(".html") else "svg")
    out = render_html(story, a.view) if fmt == "html" else render_js(story, a.view) + "\n"
    with open(a.out, "w") as fh:
        fh.write(out)
    print(f"wrote {a.out} ({len(out)} chars, {fmt}, {a.view})")


if __name__ == "__main__":
    main()
