#!/usr/bin/env python3
"""Elsehow — a renderer for the elsewhen abstract timeline model.

Takes a presentation-agnostic abstract story JSON (worlds, origins, events,
splits, transfers, route, fates, citations, profile parameters) and produces a
'Worlds and Thread' 2D vertical timeline atlas as SVG (primary) or a
self-contained HTML (SVG + legend). Honours the cardinal rule: never draw a
reset — branches persist, a 'rewind' is a surviving branch, and profile
parameters (revisions/iterations/signal/bootstrap) change what is drawn without
inventing topology.

Design source: references/visual-representation-design.md (Astra, 2026-09-05).

Usage:
    python3 render.py story.abstract.json -o out.svg                 # SVG
    python3 render.py story.abstract.json -o out.html --format html  # HTML
"""

import argparse
import json
import math
import sys
import xml.sax.saxutils as sx

# ---- palette / constants ---------------------------------------------
COL = {
    "bg": "#ffffff", "text": "#202124", "muted": "#5f6368", "rail": "#9aa0a6",
    "thread": "#2f7d4f", "split": "#e8a33d", "start": "#3d8f4f", "cutoff": "#5f6368",
    "death": "#c0392b", "alive": "#2f7d4f", "unknown": "#7f8c8d", "nonexit": "#000000",
    "init_fill": "#e8f0fe", "born_fill": "#fdf3d0", "pre_fill": "#e6f4ea", "unk_fill": "#f5f5f5",
}
MECH = {"body": "B", "memory": "M", "consciousness": "C", "signal": "S",
        "body_transport": "B", "consciousness_transfer": "C"}
FATE = {"dead": ("×", COL["death"]), "alive": ("●", COL["alive"]),
        "unknown": ("?", COL["unknown"]), "nonexistent": ("∅", COL["nonexit"])}
FONT = "Arial, Helvetica, sans-serif"
PAD_TOP, PAD_BOT = 96, 120
PAD_X, COL_W, COL_GAP, Y_STEP = 60, 210, 250, 54


def esc(s):
    return sx.escape(str(s if s is not None else ""))


def mstroke(x1, y1, x2, y2, color, width, dash=None, opacity=1.0):
    d = f' stroke-dasharray="{width*3},{width*2}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{color}" stroke-width="{width}"{d} stroke-opacity="{opacity}"/>')


# ---- geometry ---------------------------------------------------------
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


def event_map(g):
    return {e.get("id"): e for e in g.get("events", [])}


def order_span(g):
    orders = [e.get("order") for e in g.get("events", []) if e.get("order") is not None]
    if not orders:
        return 0, 1
    return min(orders), max(orders)


def step(omin, omax):
    """Vertical step that keeps the chart a viewable aspect ratio."""
    span = (omax - omin + 1) or 1
    target = 1500 - PAD_TOP - PAD_BOT
    return max(18, min(Y_STEP, target // span))


def render_graph(g):
    ev = event_map(g)
    worlds = ordered_worlds(g)
    n = len(worlds)
    widx = {w["id"]: i for i, w in enumerate(worlds)}
    omin, omax = order_span(g)
    st = step(omin, omax)
    # adaptive column gap so many-world charts stay legible
    gap = max(130, min(COL_GAP, (1500 - 2 * PAD_X) // max(1, n)))
    W = PAD_X * 2 + max(1, n) * gap + 80
    H = PAD_TOP + PAD_BOT + (omax - omin + 1) * st

    def xcol(i):
        return PAD_X + (n - 1 - i) * gap + 40  # earliest world rightmost

    def ypos(o):
        return PAD_TOP + (o - omin + 1) * st

    def xw(wid):
        return xcol(widx.get(wid, 0))

    def epos(eid):
        e = ev.get(eid)
        if not e:
            return None
        return (xw(e.get("universe")), ypos(e.get("order") if e.get("order") is not None else omin))

    S = []

    # world rails + origin markers + labels
    for i, w in enumerate(worlds):
        x = xcol(i)
        ws = [e for e in g.get("events", []) if e.get("universe") == w["id"] and e.get("order") is not None]
        if not ws:
            continue
        ys = [ypos(e["order"]) for e in ws]
        ybot = max(ys)
        kind = w.get("origin", "unknown")
        # rail start: born begins at birth; preexisting/initial begin at top; unknown at top with ?
        ytop = PAD_TOP - 6
        railstart = ytop if kind in ("initial", "preexisting", "unknown") else min(ys)
        S.append(mstroke(x, railstart, x, ybot, COL["rail"], 2))
        # origin marker
        if kind == "initial":
            S.append(f'<rect x="{x-7}" y="{PAD_TOP-26}" width="14" height="14" fill="{COL["init_fill"]}" stroke="{COL["text"]}"/>')
            S.append(f'<text x="{x}" y="{PAD_TOP-40}" text-anchor="middle" font-size="12" fill="{COL["text"]}">{esc(w["id"])}</text>')
        elif kind == "born":
            S.append(f'<rect x="{x-6}" y="{railstart-20}" width="12" height="12" fill="{COL["born_fill"]}" stroke="{COL["text"]}"/>')
        elif kind == "preexisting":
            S.append(f'<text x="{x}" y="{PAD_TOP-38}" text-anchor="middle" font-size="11" fill="{COL["muted"]}">* already existed</text>')
        elif kind == "unknown":
            S.append(f'<text x="{x}" y="{PAD_TOP-38}" text-anchor="middle" font-size="14" fill="{COL["muted"]}">?</text>')
        # world label
        S.append(f'<text x="{x}" y="{PAD_TOP-8}" text-anchor="middle" font-size="12" fill="{COL["text"]}">{esc(w["id"])}: {esc(w.get("label",""))[:28]}</text>')

    # split edges (structural, before nodes so they sit under)
    for sp in g.get("splits", []):
        src = epos(sp.get("event"))
        if not src:
            continue
        for sign, o in (sp.get("outcomes") or {}).items():
            tgt = epos(o.get("entry")) or (xw(o.get("universe")), src[1])
            S.append(mstroke(src[0], src[1], tgt[0], tgt[1], COL["split"], 2, dash=(sign == "-")))
            mx, my = (src[0] + tgt[0]) / 2, (src[1] + tgt[1]) / 2
            S.append(f'<text x="{mx:.1f}" y="{my-6:.1f}" text-anchor="middle" font-size="13" font-weight="bold" fill="{COL["split"]}">{sign}</text>')

    # transfers (elbows)
    for tr in g.get("transfers", []):
        f = epos(tr.get("from", {}).get("exit"))
        t = epos(tr.get("to", {}).get("entry"))
        if not f or not t:
            continue
        mx = (f[0] + t[0]) / 2
        path = f'M {f[0]:.1f} {f[1]:.1f} H {mx:.1f} V {t[1]:.1f} H {t[0]:.1f}'
        S.append(f'<path d="{path}" fill="none" stroke="{COL["thread"]}" stroke-width="2" stroke-opacity="0.6"/>')
        mech = MECH.get((tr.get("mechanism") or "").lower(), "·")
        mx, my = mx, (f[1] + t[1]) / 2
        S.append(f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="10" fill="{COL["bg"]}" stroke="{COL["thread"]}"/>')
        S.append(f'<text x="{mx:.1f}" y="{my+4:.1f}" text-anchor="middle" font-size="12" font-weight="bold" fill="{COL["thread"]}">{mech}</text>')

    # route thread (drawn over structure)
    vis = g.get("route", {}).get("visits", [])
    if vis:
        pts = []
        for v in vis:
            en = epos(v.get("entry"))
            ex = epos(v.get("exit"))
            if en and ex:
                pts.append((en[0], en[1]))
                pts.append((ex[0], ex[1]))
        if len(pts) >= 2:
            d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in pts)
            S.append(f'<path d="{d}" fill="none" stroke="{COL["thread"]}" stroke-width="6" stroke-opacity="0.35" stroke-linecap="round"/>')

    # event nodes
    by_order = {}
    for e in g.get("events", []):
        if e.get("order") is None:
            continue
        by_order.setdefault(e["order"], []).append(e)
    for o in sorted(by_order):
        for j, e in enumerate(by_order[o]):
            x = xw(e["universe"]) + (j - (len(by_order[o]) - 1) / 2) * 14
            y = ypos(o)
            kind, label = e.get("kind"), e.get("label", "")
            node = None
            if kind == "split":
                node = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="7" fill="{COL["split"]}" stroke="{COL["text"]}"/>'
            elif kind == "start":
                node = f'<rect x="{x-6:.1f}" y="{y-6:.1f}" width="12" height="12" fill="{COL["start"]}" stroke="{COL["text"]}"/>'
            elif kind == "cutoff":
                node = f'<rect x="{x-6:.1f}" y="{y-6:.1f}" width="12" height="12" fill="{COL["cutoff"]}" stroke="{COL["text"]}"/>'
            elif kind in ("entry", "exit"):
                node = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{COL["bg"]}" stroke="{COL["text"]}"/>'
            elif kind == "anchor":
                node = f'<path d="M {x:.1f} {y-6:.1f} L {x+6:.1f} {y:.1f} L {x:.1f} {y+6:.1f} L {x-6:.1f} {y:.1f} Z" fill="{COL["cutoff"]}" stroke="{COL["text"]}"/>'
            else:
                node = f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{COL["text"]}"/>'
            S.append(node)
            citetext = ""
            if e.get("cite") and (e["cite"].get("page") or e["cite"].get("scene") or e["cite"].get("locator")):
                citetext = f' · {e["cite"].get("scene") or e["cite"].get("page") or e["cite"].get("locator")}'
            S.append(f'<text x="{x:.1f}" y="{y+16:.1f}" text-anchor="middle" font-size="9" fill="{COL["muted"]}">{esc(str(o))}{esc(citetext)}</text>')
            if label:
                S.append(f'<text x="{x+9:.1f}" y="{y+3:.1f}" font-size="9" fill="{COL["muted"]}">{esc(label[:26])}</text>')

    # fates
    for fa in g.get("fates", []):
        ep = epos(fa.get("event"))
        if not ep:
            continue
        x, y = ep[0] + 14, ep[1]
        symbol, color = FATE.get(fa.get("status"), FATE["unknown"])
        S.append(f'<text x="{x:.1f}" y="{y+4:.1f}" font-size="14" font-weight="bold" fill="{color}">{symbol}</text>')
        S.append(f'<text x="{x+4:.1f}" y="{y+4:.1f}" font-size="8" fill="{COL["muted"]}">{esc(fa.get("instance",""))}</text>')

    return "\n".join(S), W, H


def render_js(story):
    """Compose ONE svg containing every graph, stacked vertically."""
    GAP = 48
    groups, total_h, max_w = [], 0, 0
    for g in story.get("graphs", []):
        inner, W, H = render_graph(g)
        header = (
            f'<text x="{W/2:.0f}" y="26" text-anchor="middle" font-size="18" font-weight="bold" fill="{COL["text"]}">{esc(story.get("title",""))}</text>'
            f'<text x="{W/2:.0f}" y="44" text-anchor="middle" font-size="11" fill="{COL["muted"]}">{esc(g.get("namespace",""))} — {esc(g.get("title",""))} · {esc(story.get("subtitle",""))}</text>')
        groups.append((header + inner, W, H))
        total_h += H + GAP
        max_w = max(max_w, W)
    max_w = max(max_w, 800)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{max_w}" height="{total_h}" '
             f'viewBox="0 0 {max_w} {total_h}" font-family="{FONT}">',
             f'<rect width="{max_w}" height="{total_h}" fill="{COL["bg"]}"/>']
    off = 0
    for inner, W, H in groups:
        parts.append(f'<g transform="translate(0,{off})">{inner}</g>')
        off += H + GAP
    parts.append('</svg>')
    return "\n".join(parts)


def render_html(story):
    svg = render_js(story)
    prof = story.get("profile", {})
    params = prof.get("params", {})
    p_s = " · ".join(f"{k} {v if not isinstance(v, list) else '/'.join(v)}" for k, v in params.items())
    legend = (f'<div class="box"><b>Legend</b> · mechanism badges: '
              f'<b>B</b>body <b>M</b>memory <b>C</b>consciousness <b>S</b>signal · '
              f'fates <span style="color:{COL["death"]}">× dead</span> '
              f'<span style="color:{COL["alive"]}">● alive</span> '
              f'<span style="color:{COL["unknown"]}">? unknown</span> ∅ nonexistent · '
              f'split tines <b>+</b> follow / <b>−</b> death · rails: initial/born/preexisting/unknown</div>')
    html = (f'<!doctype html><html><head><meta charset="utf-8"><title>{esc(story.get("title",""))}</title>'
            f'<style>body{{font-family:{FONT};margin:24px;background:#fff;color:{COL["text"]}}}'
            f'.box{{font-size:12px;color:{COL["muted"]};margin:6px 0 14px;padding:6px 8px;border:1px solid #ddd;border-radius:6px}}'
            f'.header{{font-size:11px;color:{COL["muted"]};margin-bottom:10px}}'
            f'.note{{font-size:11px;color:{COL["muted"]};margin-top:10px}}</style></head><body>'
            f'<div class="header">profile: {esc(prof.get("name",""))} · {esc(prof.get("rules",""))} · {esc(p_s)}</div>'
            f'{legend}<div style="overflow-x:auto">{svg}</div>'
            f'<div class="note">{esc(story.get("footer",""))} · assumptions: {len(sum((g.get("assumptions",[]) for g in story.get("graphs",[])), []))}</div>'
            f'</body></html>')
    return html


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--format", choices=["svg", "html"], default=None)
    a = ap.parse_args()
    with open(a.input) as fh:
        story = json.load(fh)
    fmt = a.format or ("html" if a.out.endswith(".html") else "svg")
    if fmt == "html":
        out = render_html(story)
    else:
        out = render_js(story) + "\n"
    with open(a.out, "w") as fh:
        fh.write(out)
    print(f"wrote {a.out} ({len(out)} chars, {fmt})")


if __name__ == "__main__":
    main()
