#!/usr/bin/env python3
"""Elsehow — clarity-first Worlds and Thread atlas.

Python 3.8+, standard library only.

Usage:
    python3 render.py tenet.json -o tenet.svg
    python3 render.py tenet.json -o tenet-25d.svg --view 2.5d
    python3 render.py tenet.json -o tenet.html --format html
    python3 render.py --self-test

Every normal invocation writes an SVG master and an HTML companion.
SVG includes legends, relationship records, citations, assumptions and sources.
HTML adds zoom, layer controls and a complete, escaped model inspector.

Layout:
    - Input world order; ordinal event/beat bands; explicit unspecified shelf.
    - Measured cards, no truncation and no collision-placement fallback.
    - Per-world trunk, endpoint-stem and visit corridors.
    - Every relationship endpoint gets a dedicated horizontal routing bus.
    - No inferred route links, transfers, worlds, resets or world-time values.
    - 2.5D is a shallow cabinet-axonometric extrusion, not a sheared chart.
"""

import argparse
import collections
import copy
import html
import json
import math
from pathlib import Path
import sys
import unicodedata
import xml.etree.ElementTree as ET


FONT = "DejaVu Sans, Arial, Helvetica, sans-serif"
C = {
    "paper": "#f5f6f8",
    "white": "#ffffff",
    "ink": "#172a3a",
    "muted": "#526575",
    "rule": "#d3dde5",
    "rail": "#667b8a",
    "split": "#ad6200",
    "transfer": "#285ac7",
    "route": "#087d60",
    "reference": "#7a637c",
    "dead": "#b82f46",
    "alive": "#087d60",
    "unknown": "#64717d",
    "nonexistent": "#343a47",
    "warning": "#a33732",
}
WORLD_COLORS = [
    "#416f99", "#78639a", "#397f78", "#997144",
    "#93637c", "#5a768f", "#778449",
]
ORIGINS = {
    "initial": "INITIAL IN MODEL",
    "preexisting": "ALREADY EXISTED",
    "born": "BORN AT DECLARED EVENT",
    "unknown": "ORIGIN UNKNOWN",
}
MECHANISMS = {
    "body": "B", "body_transport": "B",
    "memory": "M", "memory_transfer": "M",
    "consciousness": "C", "consciousness_transfer": "C",
    "signal": "S", "signal_transfer": "S",
}
FATES = {
    "dead": ("×", C["dead"]),
    "alive": ("●", C["alive"]),
    "unknown": ("?", C["unknown"]),
    "nonexistent": ("∅", C["nonexistent"]),
}

CARD_W = 304
PAD = 16
LINE_H = 20
ROW_GAP = 18
BUS_STEP = 26
LEFT = 142
RIGHT = 42
DECK_Z = 24
CABLE_Z = 40


def clean(value):
    """Remove XML 1.0-invalid controls, retaining normal Unicode."""
    s = str("" if value is None else value)
    return "".join(
        ch for ch in s
        if ch in "\t\n\r"
        or 0x20 <= ord(ch) <= 0xD7FF
        or 0xE000 <= ord(ch) <= 0xFFFD
        or 0x10000 <= ord(ch) <= 0x10FFFF
    )


def esc(value):
    return html.escape(clean(value), quote=True)


def compact(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(", ", ": "))


def width_estimate(s, size=14):
    """Conservative advance estimates; all cards also retain inner padding."""
    total = 0.0
    for ch in clean(s):
        if unicodedata.combining(ch):
            continue
        if unicodedata.east_asian_width(ch) in ("W", "F"):
            em = 1.04
        elif ch in "MW@%&":
            em = 1.00
        elif ch in "ilI.,:;!'|` ":
            em = 0.38
        elif ch.isupper():
            em = 0.80
        else:
            em = 0.69
        total += em * size
    return total


def wrap_text(value, width, size=14):
    """Pixel-budget wrapping; split long tokens; never ellipsize."""
    result = []
    for paragraph in clean(value).split("\n"):
        if not paragraph:
            result.append("")
            continue
        line = ""
        for word in paragraph.split():
            candidate = (line + " " + word).strip()
            if width_estimate(candidate, size) <= width:
                line = candidate
                continue
            if line:
                result.append(line)
                line = ""
            chunk = ""
            for ch in word:
                if chunk and width_estimate(chunk + ch, size) > width:
                    result.append(chunk)
                    chunk = ""
                chunk += ch
            line = chunk
        result.append(line)
    return result or [""]


def attrs(values):
    return " ".join(
        '%s="%s"' % (k.rstrip("_").replace("_", "-"), esc(v))
        for k, v in values.items() if v is not None
    )


class SVG:
    def __init__(self):
        self.parts = []

    def raw(self, value):
        self.parts.append(value)

    def start(self, tag, **kw):
        self.raw("<%s %s>" % (tag, attrs(kw)))

    def end(self, tag):
        self.raw("</%s>" % tag)

    def element(self, tag, **kw):
        self.raw("<%s %s/>" % (tag, attrs(kw)))

    def text(self, x, y, value, size=14, color=None, weight=None, **kw):
        kw.update(x=round(x, 2), y=round(y, 2), font_size=size,
                  fill=color or C["ink"], font_weight=weight)
        self.raw("<text %s>%s</text>" % (attrs(kw), esc(value)))

    def title(self, value):
        self.raw("<title>%s</title>" % esc(value))

    def rect(self, x, y, w, h, fill, stroke=None, rx=0, **kw):
        self.element("rect", x=x, y=y, width=w, height=h, fill=fill,
                     stroke=stroke, rx=rx, **kw)

    def line(self, x1, y1, x2, y2, color, width=1, **kw):
        self.element("line", x1=x1, y1=y1, x2=x2, y2=y2,
                     stroke=color, stroke_width=width, **kw)

    def circle(self, x, y, r, fill, stroke=None, **kw):
        self.element("circle", cx=x, cy=y, r=r, fill=fill,
                     stroke=stroke, **kw)

    def poly(self, points, fill, stroke=None, **kw):
        self.element("polygon",
                     points=" ".join("%.2f,%.2f" % p for p in points),
                     fill=fill, stroke=stroke, **kw)

    def paragraph(self, x, y, value, width, size=14, color=None,
                  leading=None, weight=None):
        leading = leading or size * 1.45
        for line in wrap_text(value, width, size):
            self.text(x, y + size, line, size, color, weight)
            y += leading
        return y

    def output(self):
        return "\n".join(self.parts)


class Evidence:
    """Document-wide deduplication, retaining every citation owner."""
    def __init__(self):
        self.rows = []
        self.index = {}

    def add(self, cite, owner):
        if not isinstance(cite, dict) or not cite:
            return None
        key = json.dumps(cite, sort_keys=True, ensure_ascii=False)
        if key not in self.index:
            self.index[key] = len(self.rows) + 1
            self.rows.append({"cite": copy.deepcopy(cite), "owners": []})
        number = self.index[key]
        owners = self.rows[number - 1]["owners"]
        if owner not in owners:
            owners.append(owner)
        return number

    def scan(self, obj, owner="document"):
        if isinstance(obj, dict):
            name = obj.get("id") or obj.get("where") or owner
            here = owner if str(name) == owner else owner + " / " + str(name)
            if isinstance(obj.get("cite"), dict):
                self.add(obj["cite"], here)
            for key, value in obj.items():
                if key != "cite":
                    self.scan(value, here)
        elif isinstance(obj, list):
            for value in obj:
                self.scan(value, owner)

    def number(self, cite):
        if not isinstance(cite, dict) or not cite:
            return None
        key = json.dumps(cite, sort_keys=True, ensure_ascii=False)
        return self.index.get(key)


def rich_row(value, size=12, color=None, weight=None, href=None):
    return {
        "text": clean(value), "size": size, "color": color or C["muted"],
        "weight": weight, "href": href,
    }


def citation_row(evidence, cite):
    number = evidence.number(cite)
    if number is None:
        return rich_row("No citation supplied", 11)
    fields = ["[%d]" % number]
    for key, label in (("scene", "Scene"), ("page", "p."),
                       ("locator", "Locator")):
        if cite.get(key) is not None:
            fields.append("%s %s" % (label, cite[key]))
    fields.append(str(cite.get("status", "status unspecified")))
    return rich_row(" · ".join(fields), 11, C["transfer"],
                    href="#evidence-%d" % number)


def measure_card(item):
    laid = []
    y = PAD
    for row in item["rows"]:
        leading = LINE_H if row["size"] >= 14 else 17
        lines = wrap_text(row["text"], CARD_W - 2 * PAD, row["size"])
        laid.append((y, lines, leading, row))
        y += len(lines) * leading + 6
    item["laid"] = laid
    item["height"] = max(76, y + PAD - 6)


class Graph:
    def __init__(self, graph, index, evidence, view):
        self.g = graph
        self.index = index
        self.prefix = "g%d" % index
        self.ev = evidence
        self.view = view
        self.worlds = copy.deepcopy(graph.get("worlds", []))
        self.world_map = {}
        self.items = []
        self.events = {}
        self.edges = []
        self.visits = []
        self.warnings = []
        self.edge_records = []
        self.route_records = []
        self.passed = set()
        self._prepare()

    def warn(self, message):
        if message not in self.warnings:
            self.warnings.append(message)

    def owner(self, wid):
        if wid in self.world_map:
            return self.world_map[wid]
        literal = "(missing universe)" if wid is None else str(wid)
        # This is explicitly a diagnostics column, not a modeled world.
        world = {
            "id": wid,
            "label": "Undeclared reference: " + literal,
            "origin": "unknown",
            "_diagnostic": True,
        }
        self.worlds.append(world)
        self.world_map[wid] = world
        self.warn("Undeclared world reference: %s. Its column is diagnostic, "
                  "not an inferred world." % literal)
        return world

    def item(self, record, wid, order, category, rows, kind=None):
        self.owner(wid)
        item = {
            "key": "%s-item-%d" % (self.prefix, len(self.items) + 1),
            "record": record, "world": wid, "order": order,
            "category": category, "kind": kind, "rows": rows,
        }
        self.items.append(item)
        return item

    def endpoint(self, eid, context):
        item = self.events.get(eid)
        if item is None:
            self.warn("%s: missing event %r; no endpoint invented." %
                      (context, eid))
        return item

    def check_world(self, declared, item, context):
        if declared is not None and item and declared != item["world"]:
            self.warn("%s: declared world %r disagrees with event world %r; "
                      "the event is the connection anchor." %
                      (context, declared, item["world"]))

    def edge(self, code, kind, a, b, badge, detail, record,
             sign=None, selected=False):
        self.edge_records.append((code, detail, record))
        if a is None or b is None:
            return None
        edge = {
            "code": code, "kind": kind, "a": a, "b": b,
            "badge": badge, "detail": detail, "record": record,
            "sign": sign, "selected": selected,
        }
        self.edges.append(edge)
        return edge

    def _prepare(self):
        seen = set()
        kept = []
        for world in self.worlds:
            wid = world.get("id")
            if wid in seen:
                self.warn("Duplicate world ID %r; first declaration used." % wid)
                continue
            seen.add(wid)
            kept.append(world)
            self.world_map[wid] = world
        self.worlds = kept

        for event in self.g.get("events", []):
            eid = event.get("id")
            if eid in self.events:
                self.warn("Duplicate event ID %r; first event is the reference "
                          "target; both records remain visible." % eid)
            rows = [
                rich_row("%s  ·  %s" %
                         (str(event.get("kind", "event")).upper(), eid),
                         11, C["muted"], "bold"),
                rich_row(event.get("label") or eid, 14, C["ink"]),
                citation_row(self.ev, event.get("cite")),
            ]
            item = self.item(event, event.get("universe"), event.get("order"),
                             "event", rows, event.get("kind"))
            self.events.setdefault(eid, item)

        segments = {s.get("id"): s for s in self.g.get("segments", [])
                    if isinstance(s, dict)}
        for beat in self.g.get("beats", []):
            if not isinstance(beat, dict):
                self.warn("Unstructured beat retained in the document inspector.")
                continue
            segment = segments.get(beat.get("segment"), {})
            wid = beat.get("universe", segment.get("universe"))
            rows = [
                rich_row("BEAT  ·  %s" % beat.get("id", "unnamed"), 11,
                         C["muted"], "bold"),
                rich_row(beat.get("text") or beat.get("label") or compact(beat),
                         14, C["ink"]),
                rich_row("Segment: %s" % beat.get("segment", "unspecified"), 11),
                citation_row(self.ev, beat.get("cite")),
            ]
            self.item(beat, wid, beat.get("order"), "beat", rows)

        for fate in self.g.get("fates", []):
            at = self.events.get(fate.get("event"))
            wid = fate.get("universe", at["world"] if at else None)
            status = fate.get("status", "unknown")
            symbol, color = FATES.get(status, FATES["unknown"])
            rows = [
                rich_row("%s %s  ·  %s" %
                         (symbol, str(status).upper(),
                          fate.get("instance", "instance unspecified")),
                         12, color, "bold"),
                rich_row("Fate %s · at %s" %
                         (fate.get("id", "?"),
                          fate.get("event", "event unspecified")), 11),
                citation_row(self.ev, fate.get("cite")),
            ]
            if at and wid == at["world"]:
                at["rows"].extend(rows)
            else:
                item = self.item(
                    fate, wid, at["order"] if at else None, "fate", rows
                )
                if at:
                    self.edge(
                        "F%d" % (len(self.edge_records) + 1), "reference",
                        at, item, "ref", "Fate reference, not a transfer: " +
                        compact(fate), fate
                    )
                else:
                    self.warn("Fate %s has no resolved event; shown on the "
                              "unspecified-order shelf." % fate.get("id", "?"))

        split_lookup = {}
        for number, split in enumerate(self.g.get("splits", []), 1):
            source = self.endpoint(split.get("event"), "Split S%d" % number)
            self.check_world(split.get("source_universe"), source,
                             "Split S%d" % number)
            if source:
                facts = []
                for key in ("cause", "automatic", "traveller",
                            "source_disposition"):
                    if key in split:
                        facts.append("%s: %s" % (key.replace("_", " "),
                                                compact(split[key])))
                source["rows"].append(rich_row(
                    "S%d · %s" % (number, " · ".join(facts)), 11, C["split"]
                ))
            for sign, outcome in (split.get("outcomes") or {}).items():
                target = self.endpoint(outcome.get("entry"), "Split S%d" % number)
                self.check_world(outcome.get("universe"), target,
                                 "Split S%d outcome %s" % (number, sign))
                display_sign = "−" if sign == "-" else str(sign)
                code = "S%d%s" % (number, display_sign)
                detail = "%s → %s · outcome %s · %s" % (
                    split.get("event"), outcome.get("entry"), display_sign,
                    compact(outcome)
                )
                edge = self.edge(code, "split", source, target, code,
                                 detail, {"split": split, "outcome": outcome},
                                 sign=sign)
                split_lookup[(split.get("event"), sign)] = edge

        transfer_lookup = {}
        for number, transfer in enumerate(self.g.get("transfers", []), 1):
            code = "T%d" % number
            a_ref = transfer.get("from") or {}
            b_ref = transfer.get("to") or {}
            a = self.endpoint(a_ref.get("exit"), code)
            b = self.endpoint(b_ref.get("entry"), code)
            self.check_world(a_ref.get("universe"), a, code + " source")
            self.check_world(b_ref.get("universe"), b, code + " destination")
            mechanism = str(transfer.get("mechanism") or "unspecified")
            letter = MECHANISMS.get(mechanism.lower(), "?")
            detail = "%s · %s · %s → %s · mechanism: %s" % (
                transfer.get("id", code),
                transfer.get("traveller", "traveller unspecified"),
                a_ref.get("exit"), b_ref.get("entry"), mechanism
            )
            if transfer.get("relation"):
                detail += " · relation: " + compact(transfer["relation"])
            edge = self.edge(code, "transfer", a, b, code + " " + letter,
                             detail, transfer)
            transfer_lookup[transfer.get("id")] = edge

        route = self.g.get("route") or {}
        visits_by_id = {}
        for number, visit in enumerate(route.get("visits", []), 1):
            code = "V%d" % number
            a = self.endpoint(visit.get("entry"), code)
            b = self.endpoint(visit.get("exit"), code)
            detail = "%s · %s · %s → %s · %s" % (
                code, visit.get("id", "?"), visit.get("entry"),
                visit.get("exit"), compact(visit)
            )
            self.route_records.append(detail)
            visits_by_id[visit.get("id")] = (visit, a, b, code)
            for item, role in ((a, "entry"), (b, "exit")):
                if item:
                    item["rows"].append(rich_row(
                        "%s %s · %s" %
                        (code, role, route.get("traveller", "route")),
                        11, C["route"], "bold"
                    ))
            if a and b:
                self.check_world(visit.get("universe"), a, code)
                self.check_world(visit.get("universe"), b, code)
                if a["world"] == b["world"]:
                    self.visits.append({
                        "code": code, "a": a, "b": b, "record": visit
                    })
                else:
                    self.warn("%s spans worlds. Its explicit endpoints are "
                              "shown as a route connection, not a world rail." %
                              code)
                    self.edge(code, "route", a, b, code, detail, visit)

            # Loose pass records: only explicit event + sign pairs are applied.
            for passed in visit.get("passes", []) or []:
                if not isinstance(passed, dict):
                    continue
                event_id = passed.get("event", passed.get("split"))
                sign = passed.get("tine", passed.get("sign"))
                match = split_lookup.get((event_id, sign))
                if match:
                    match["selected"] = True
                    self.passed.add(match["code"])

        linked_pairs = set()
        for number, link in enumerate(route.get("links", []), 1):
            code = "L%d" % number
            av = visits_by_id.get(link.get("from"))
            bv = visits_by_id.get(link.get("to"))
            detail = "%s · %s → %s · %s" % (
                code, link.get("from"), link.get("to"), compact(link)
            )
            self.route_records.append(detail)
            if not av or not bv:
                self.warn("%s references a missing visit; no link invented." %
                          code)
                continue
            a, b = av[2], bv[1]
            linked_pairs.add((link.get("from"), link.get("to")))
            via = link.get("via")
            transfer = transfer_lookup.get(via) if isinstance(via, str) else None
            if transfer and transfer["a"] is a and transfer["b"] is b:
                transfer["selected"] = True
                transfer["detail"] += " · followed by " + code
                continue

            matched = None
            if link.get("kind") == "split":
                for edge in self.edges:
                    if (edge["kind"] == "split" and edge["a"] is a
                            and edge["b"] is b):
                        matched = edge
                        break
            if matched:
                matched["selected"] = True
                matched["detail"] += " · followed by " + code
            else:
                if transfer:
                    self.warn("%s via %r disagrees with visit endpoints; "
                              "explicit route endpoints are drawn separately." %
                              (code, via))
                self.edge(code, "route", a, b, code, detail, link)

        ordered_visits = route.get("visits", [])
        for a, b in zip(ordered_visits, ordered_visits[1:]):
            if (a.get("id"), b.get("id")) not in linked_pairs:
                self.route_records.append(
                    "GAP · No explicit link from %s to %s; no continuity drawn."
                    % (a.get("id"), b.get("id"))
                )

        for item in self.items:
            measure_card(item)
        self._layout()

    def _layout(self):
        orders = sorted({i["order"] for i in self.items
                         if i["order"] is not None})
        if any(i["order"] is None for i in self.items) or not orders:
            orders.append(None)
        self.orders = orders
        self.by_band = collections.defaultdict(list)
        for item in self.items:
            self.by_band[item["order"]].append(item)

        # Dedicated trunks belong to the source world.
        trunk_counts = collections.Counter()
        endpoint_counts = collections.Counter()
        for edge in self.edges:
            world = edge["a"]["world"]
            edge["trunk_slot"] = trunk_counts[world]
            trunk_counts[world] += 1
            for end in ("a", "b"):
                item = edge[end]
                key = (item["world"], item["order"])
                edge[end + "_port"] = endpoint_counts[key]
                endpoint_counts[key] += 1

        visit_counts = collections.Counter()
        for visit in self.visits:
            wid = visit["a"]["world"]
            visit["slot"] = visit_counts[wid]
            visit_counts[wid] += 1

        x = LEFT
        header_heights = []
        for number, world in enumerate(self.worlds):
            wid = world.get("id")
            ports = max([count for (w, _), count in endpoint_counts.items()
                         if w == wid] or [0])
            visits = visit_counts[wid]
            trunks = trunk_counts[wid]
            # Left-to-right: trunks, endpoint stems, visits, rail, card.
            trunk_w = 96 + 12 * trunks
            port_w = 12 + 9 * ports
            visit_w = 20 + 10 * visits
            rail_x = x + trunk_w + port_w + visit_w
            world.update({
                "_x": x, "_rail": rail_x, "_card": rail_x + 24,
                "_width": rail_x + 24 + CARD_W + 24 - x,
                "_trunk_w": trunk_w, "_ports": ports,
                "_visits": visits,
                "_color": (C["warning"] if world.get("_diagnostic")
                           else WORLD_COLORS[number % len(WORLD_COLORS)]),
            })
            header_rows = [
                rich_row(str(wid) if wid is not None else "UNRESOLVED", 15,
                         world["_color"], "bold"),
                rich_row(world.get("label", ""), 14, C["ink"], "bold"),
                rich_row("UNDECLARED WORLD — DIAGNOSTIC ONLY"
                         if world.get("_diagnostic") else
                         ORIGINS.get(world.get("origin"), "ORIGIN UNKNOWN"),
                         11),
            ]
            if world.get("born"):
                header_rows.append(rich_row(
                    "Birth declaration: " + compact(world["born"]), 11
                ))
            if world.get("ancestry"):
                header_rows.append(rich_row(
                    "Ancestry: " + str(world["ancestry"]).replace("_", " "), 11
                ))
            header = {"rows": header_rows}
            measure_card(header)
            world["_header"] = header
            header_heights.append(header["height"])
            x += world["_width"] + 28
        self.width = max(1040, x + RIGHT)

        self.header_h = max(header_heights or [100])
        y = self.header_h + 54
        self.chart_top = y
        self.bands = []
        for rank, order in enumerate(self.orders):
            items = self.by_band[order]
            per_world = collections.defaultdict(list)
            for item in items:
                per_world[item["world"]].append(item)
            body_h = max(
                [sum(i["height"] + ROW_GAP for i in values)
                 for values in per_world.values()] or [70]
            )
            for wid, values in per_world.items():
                iy = y + 20
                for item in values:
                    item["x"] = self.world_map[wid]["_card"]
                    item["y"] = iy
                    item["node_y"] = iy + 25
                    iy += item["height"] + ROW_GAP
            buses = []
            for edge in self.edges:
                for end in ("a", "b"):
                    if edge[end]["order"] == order:
                        buses.append((edge, end))
            bus_top = y + 20 + body_h + 10
            for slot, (edge, end) in enumerate(buses):
                edge[end + "_bus"] = bus_top + 16 + BUS_STEP * slot
            height = 20 + body_h + 30 + BUS_STEP * len(buses)
            self.bands.append({
                "order": order, "rank": rank, "top": y,
                "body_bottom": bus_top - 6, "height": height,
            })
            y += height
        self.chart_bottom = y + 26
        self.height = self.chart_bottom + 65

        for world in self.worlds:
            wid = world.get("id")
            origin = world.get("origin")
            owned = [i for i in self.items if i["world"] == wid]
            first = min([i["node_y"] for i in owned] or [self.chart_top + 20])
            start = self.chart_top
            if origin == "born":
                birth = world.get("born") or {}
                event = self.events.get(birth.get("event"))
                if event:
                    start = event["node_y"]
                    parent = birth.get("parent")
                    if parent is not None and event["world"] != parent:
                        self.warn("World %s: born.parent differs from the "
                                  "declared birth event's world." % wid)
                    if any(i["node_y"] < start for i in owned):
                        self.warn("World %s has records before its declared "
                                  "birth. Records remain visible; the rail "
                                  "does not extend before birth." % wid)
                else:
                    start = first
                    self.warn("World %s has an unresolved birth event; rail "
                              "starts at its first displayed record, with "
                              "origin unresolved." % wid)
            elif origin == "unknown":
                start = first

            end = self.chart_bottom
            for split in self.g.get("splits", []):
                if split.get("source_disposition") != "ancestry_prefix":
                    continue
                event = self.events.get(split.get("event"))
                source = split.get("source_universe",
                                   event["world"] if event else None)
                if source == wid and event:
                    end = min(end, event["node_y"])
            world["_start"], world["_end"] = start, max(start, end)

    def project(self, x, y, z=DECK_Z):
        if self.view == "2.5d":
            return x + 0.5 * z, y - 0.3 * z
        return x, y

    def path_data(self, points, z=DECK_Z):
        projected = [self.project(x, y, z) for x, y in points]
        return "M " + " L ".join("%.2f %.2f" % p for p in projected)

    def stroke(self, svg, points, color, width, marker=None, dash=None,
               z=DECK_Z, halo=True):
        d = self.path_data(points, z)
        if halo:
            svg.element("path", d=d, fill="none", stroke=C["white"],
                        stroke_width=width + 4, stroke_linejoin="round",
                        stroke_linecap="round")
        svg.element("path", d=d, fill="none", stroke=color,
                    stroke_width=width, stroke_linejoin="round",
                    stroke_linecap="round", stroke_dasharray=dash,
                    marker_end=("url(#arrow-%s)" % marker) if marker else None)

    def card(self, svg, item, x=None, y=None, header=False):
        x = item.get("x") if x is None else x
        y = item.get("y") if y is None else y
        px, py = self.project(x, y)
        world = self.world_map.get(item.get("world"))
        accent = world["_color"] if world else C["rail"]
        if item.get("category") == "beat":
            fill = "#f9fafc"
        elif item.get("category") == "fate":
            fill = "#fff9fa"
        else:
            fill = C["white"]
        svg.start("g", id=item.get("key"), class_="card",
                  role="group", aria_label=compact(item.get("record", {})))
        if item.get("record"):
            svg.title(compact(item["record"]))
        svg.rect(px, py + 2, CARD_W, item["height"], "#e7edf2", rx=9)
        svg.rect(px, py, CARD_W, item["height"], fill, C["rule"], rx=9)
        if not header:
            svg.rect(px, py + 12, 3, item["height"] - 24, accent, rx=1.5)
        for offset, lines, leading, row in item["laid"]:
            if row.get("href"):
                svg.start("a", href=row["href"], class_="citation",
                          aria_label=row["text"])
            for number, line in enumerate(lines):
                svg.text(px + PAD, py + offset + row["size"] +
                         number * leading, line, row["size"],
                         row["color"], row["weight"])
            if row.get("href"):
                svg.end("a")
        svg.end("g")

    def node(self, svg, item):
        world = self.world_map[item["world"]]
        x, y = self.project(world["_rail"], item["node_y"])
        kind = item.get("kind")
        color = world["_color"]
        svg.start("g", class_="event-node")
        svg.title("%s · %s" % (item["record"].get("id", ""),
                               item["record"].get("label", "")))
        svg.circle(x, y, 11, C["white"])
        if item["category"] != "event":
            svg.circle(x, y, 4, C["white"], color, stroke_width=2)
        elif kind == "split":
            svg.circle(x, y, 8, "#fff1d7", C["split"], stroke_width=2.5)
            svg.text(x, y + 4, "Y", 11, C["split"], "bold",
                     text_anchor="middle")
        elif kind == "anchor":
            svg.poly([(x, y - 8), (x + 8, y), (x, y + 8), (x - 8, y)],
                     C["white"], color, stroke_width=2.5)
        elif kind == "start":
            svg.rect(x - 7, y - 7, 14, 14, C["route"],
                     C["white"], rx=2, stroke_width=2)
        elif kind == "cutoff":
            svg.line(x - 9, y - 4, x + 9, y - 4, color, 3)
            svg.line(x - 9, y + 4, x + 9, y + 4, color, 3)
        elif kind in ("entry", "exit", "gate_entry", "gate_exit"):
            svg.circle(x, y, 8, C["white"], color, stroke_width=2.5)
            if kind in ("entry", "gate_entry"):
                points = [(x - 3, y - 4), (x + 3, y), (x - 3, y + 4)]
            else:
                points = [(x + 3, y - 4), (x - 3, y), (x + 3, y + 4)]
            svg.poly(points, color)
            if kind.startswith("gate"):
                svg.line(x - 11, y - 10, x - 11, y + 10, color, 2)
                svg.line(x + 11, y - 10, x + 11, y + 10, color, 2)
        else:
            svg.circle(x, y, 6, color, C["white"], stroke_width=2)
        svg.end("g")

    def edge_points(self, edge):
        a, b = edge["a"], edge["b"]
        wa, wb = self.world_map[a["world"]], self.world_map[b["world"]]
        ax, bx = wa["_rail"], wb["_rail"]
        # Stems stay left of all visit tracks; trunks stay farther left.
        pa = (ax - 30 - 10 * wa["_visits"] - 9 * edge["a_port"])
        pb = (bx - 30 - 10 * wb["_visits"] - 9 * edge["b_port"])
        tx = wa["_x"] + 20 + 12 * edge["trunk_slot"]
        ay, by = a["node_y"], b["node_y"]
        ya, yb = edge["a_bus"], edge["b_bus"]
        points = [
            (ax - 9, ay), (pa, ay), (pa, ya), (tx, ya),
            (tx, yb), (pb, yb), (pb, by), (bx - 10, by)
        ]
        return points, ((tx + pa) / 2, ya)

    def draw_edge(self, svg, edge):
        kind = edge["kind"]
        color = C[kind]
        marker = kind
        points, badge = self.edge_points(edge)
        z = CABLE_Z if self.view == "2.5d" else DECK_Z
        svg.start("g", class_="layer-" + kind,
                  id=self.prefix + "-edge-" + str(self.edges.index(edge) + 1))
        svg.title(edge["detail"] + "\n" + compact(edge["record"]))
        # Cables are raised, but risers visibly join the deck endpoints.
        if self.view == "2.5d":
            for endpoint in (points[0], points[-1]):
                low = self.project(*endpoint, DECK_Z)
                high = self.project(*endpoint, z)
                svg.line(*low, *high, C["white"], 8)
                svg.line(*low, *high, color, 3)
        dash = "8 5" if (kind == "split" and edge.get("sign") == "-") else None
        if kind == "reference":
            dash = "3 5"
        width = 6 if edge["selected"] else (4 if kind != "reference" else 2)
        self.stroke(svg, points, color, width, marker, dash, z)
        if edge["selected"]:
            svg.start("g", class_="layer-route")
            self.stroke(svg, points, C["route"], 2.6,
                        z=z, halo=False)
            svg.end("g")
        px, py = self.project(*badge, z)
        badge_w = max(48, width_estimate(edge["badge"], 11) + 18)
        svg.start("a", href="#%s-relationships" % self.prefix,
                  aria_label=edge["detail"])
        svg.rect(px - badge_w / 2, py - 10, badge_w, 20,
                 C["white"], color, rx=6, stroke_width=1.6)
        svg.text(px, py + 4, edge["badge"], 11, color, "bold",
                 text_anchor="middle")
        svg.end("a")
        svg.end("g")

    def draw_visit(self, svg, visit):
        a, b = visit["a"], visit["b"]
        world = self.world_map[a["world"]]
        rail = world["_rail"]
        x = rail - 17 - 10 * visit["slot"]
        ay, by = a["node_y"], b["node_y"]
        svg.start("g", class_="layer-route")
        svg.title("%s · %s" % (visit["code"], compact(visit["record"])))
        if a is b:
            points = [(rail - 8, ay), (x, ay), (x, ay + 16),
                      (rail - 8, ay + 16), (rail - 8, ay + 9)]
        else:
            points = [(rail - 8, ay), (x, ay), (x, by), (rail - 10, by)]
        self.stroke(svg, points, C["route"], 4.5, "route")
        # Mid-track chevron supplies an unambiguous direction along the visit.
        if abs(by - ay) > 42:
            direction = 1 if by > ay else -1
            mid = (ay + by) / 2
            self.stroke(svg, [(x, mid - direction * 9),
                              (x, mid + direction * 9)],
                        C["route"], 4.5, "route", halo=False)
        svg.end("g")

    def draw(self):
        svg = SVG()
        svg.text(24, 20, "STORY", 11, C["muted"], "bold")
        svg.text(24, 37, "ORDER ↓", 11, C["muted"], "bold")

        for world in self.worlds:
            x = world["_x"]
            width = world["_width"]
            top, bottom = self.chart_top - 12, self.chart_bottom + 8
            if self.view == "2.5d":
                front = [
                    self.project(x, top), self.project(x + width, top),
                    self.project(x + width, bottom), self.project(x, bottom)
                ]
                base_right = self.project(x + width, bottom, 0)
                base_top_right = self.project(x + width, top, 0)
                base_left = self.project(x, bottom, 0)
                svg.poly([front[1], base_top_right, base_right, front[2]],
                         "#d9e2ea", "#becbd6", stroke_width=1)
                svg.poly([front[3], front[2], base_right, base_left],
                         "#cbd7e1", "#b7c6d2", stroke_width=1)
                svg.poly(front, "#eef3f7", "#c7d3dd", stroke_width=1)
            else:
                svg.rect(x, top, width, bottom - top, "#eef3f7",
                         "#d6e0e8", rx=10)

            self.card(svg, world["_header"], world["_card"], 4, header=True)
            hx, hy = self.project(world["_x"] + 14, 12)
            svg.rect(hx, hy, 5, self.header_h - 14,
                     world["_color"], rx=2)

        # Band rules cross only empty space, never card interiors.
        for band in self.bands:
            y = band["top"]
            py = self.project(0, y)[1]
            svg.line(20, py, self.width - RIGHT, py, C["rule"], 1)
            label = "Unspecified" if band["order"] is None else str(band["order"])
            for n, line in enumerate(wrap_text(label, 106, 12)):
                svg.text(24, py + 28 + n * 17, line, 12, C["ink"], "bold")
            svg.text(24, py + 53 + 17 * max(0, len(wrap_text(label, 106, 12)) - 1),
                     "rank %02d" % (band["rank"] + 1), 10, C["muted"])

        # Rails never end at a character death or ordinary cutoff event.
        for world in self.worlds:
            if world.get("_diagnostic"):
                continue
            x, start, end = world["_rail"], world["_start"], world["_end"]
            self.stroke(svg, [(x, start), (x, end)], C["rail"], 3,
                        halo=False)
            px, py = self.project(x, start)
            origin = world.get("origin")
            if origin == "initial":
                svg.rect(px - 6, py - 6, 12, 12, C["white"],
                         world["_color"], rx=1, stroke_width=2)
            elif origin == "preexisting":
                svg.element("path",
                            d="M %.2f %.2f l -5 -7 m 5 7 l 5 -7" % (px, py),
                            fill="none", stroke=world["_color"], stroke_width=2)
            elif origin == "born":
                svg.poly([(px, py - 7), (px + 7, py), (px, py + 7),
                          (px - 7, py)], "#fff1d7", C["split"], stroke_width=2)
            else:
                svg.circle(px, py, 9, C["white"], C["rail"], stroke_width=2)
                svg.text(px, py + 4, "?", 12, C["rail"], "bold",
                         text_anchor="middle")
            ex, ey = self.project(x, end)
            svg.line(ex - 7, ey, ex + 7, ey, C["rail"], 2)
            if end < self.chart_bottom:
                text = "Ancestry prefix ends"
            else:
                text = "End of displayed extent"
            svg.text(ex + 15, ey + 5, text, 10, C["muted"])

        for visit in self.visits:
            self.draw_visit(svg, visit)
        # Crossing order is deterministic. White casings mean bridges, not joins.
        for edge in self.edges:
            self.draw_edge(svg, edge)

        # Cards and short attachment leaders occupy exclusive body rectangles.
        for item in self.items:
            world = self.world_map[item["world"]]
            y = item["node_y"]
            a = self.project(world["_rail"] + 10, y)
            b = self.project(item["x"], y)
            svg.line(*a, *b, world["_color"], 1.8)
            self.card(svg, item)
        for item in self.items:
            self.node(svg, item)

        return svg.output()


def validate(story):
    """Small contract check, deliberately not a pretend JSON-Schema engine."""
    if not isinstance(story, dict):
        raise ValueError("The document root must be an object.")
    if story.get("abstract_model") != "universe-timeline/1.0":
        raise ValueError("abstract_model must be 'universe-timeline/1.0'.")
    if not isinstance(story.get("title"), str):
        raise ValueError("title must be a string.")
    graphs = story.get("graphs")
    if not isinstance(graphs, list) or not graphs:
        raise ValueError("graphs must be a nonempty array.")
    for index, graph in enumerate(graphs):
        if not isinstance(graph, dict):
            raise ValueError("graphs[%d] must be an object." % index)
        if not isinstance(graph.get("worlds"), list):
            raise ValueError("graphs[%d].worlds must be an array." % index)
        for key in ("events", "beats", "segments", "splits", "transfers",
                    "fates", "evidence", "assumptions"):
            if key in graph and not isinstance(graph[key], list):
                raise ValueError("graphs[%d].%s must be an array." % (index, key))
        for event in graph.get("events", []):
            if not isinstance(event, dict):
                raise ValueError("Every event must be an object.")
            order = event.get("order")
            if order is not None and (isinstance(order, bool)
                                      or not isinstance(order, int)):
                raise ValueError("Event %r has a non-integer order." %
                                 event.get("id"))
        for beat in graph.get("beats", []):
            if isinstance(beat, dict):
                order = beat.get("order")
                if order is not None and (isinstance(order, bool)
                                          or not isinstance(order, int)):
                    raise ValueError("Beat %r has a non-integer order." %
                                     beat.get("id"))


def definitions(svg):
    svg.start("defs")
    for kind in ("split", "transfer", "route", "reference"):
        svg.start("marker", id="arrow-" + kind, viewBox="0 0 10 10",
                  refX=8, refY=5, markerWidth=7, markerHeight=7,
                  markerUnits="userSpaceOnUse", orient="auto",
                  overflow="visible")
        svg.element("path", d="M 1 1 L 9 5 L 1 9 Z", fill=C[kind])
        svg.end("marker")
    svg.end("defs")
    svg.raw("""
<style>
text { font-kerning: normal; }
a { cursor: pointer; }
a:hover text { text-decoration: underline; }
.card:hover > rect { stroke: #879ead; }
:target > rect { stroke: #285ac7; stroke-width: 2; }
.hide-split .layer-split,
.hide-transfer .layer-transfer,
.hide-route .layer-route,
.hide-evidence .citation { display: none; }
</style>""")


def section(svg, y, title, width, ident=None):
    svg.start("g", id=ident)
    svg.line(32, y, width - 32, y, C["rule"], 1.5)
    svg.text(40, y + 29, title, 18, C["ink"], "bold")
    svg.end("g")
    return y + 48


def ledger_record(svg, y, key, text, width, color=None, ident=None):
    available = min(width - 190, 1160)
    lines = wrap_text(text, available, 12)
    h = max(42, 22 + len(lines) * 18)
    svg.start("g", id=ident)
    svg.rect(32, y, width - 64, h, C["white"], C["rule"], rx=7)
    label_lines = wrap_text(key, 112, 11)
    # Long keys are allowed to increase row height rather than overlap.
    needed = 22 + 17 * len(label_lines)
    if needed > h:
        h = needed
        svg.rect(32, y, width - 64, h, C["white"], C["rule"], rx=7)
    for n, line in enumerate(label_lines):
        svg.text(46, y + 23 + n * 17, line, 11, color or C["muted"], "bold")
    for n, line in enumerate(lines):
        svg.text(174, y + 23 + n * 18, line, 12, C["ink"])
    svg.end("g")
    return y + h + 8


def graph_appendix(svg, graph, y, width):
    g = graph.g
    y = section(svg, y, "Relationship ledger", width,
                graph.prefix + "-relationships")
    if not graph.edge_records:
        y = svg.paragraph(40, y, "No split or transfer edges supplied.",
                          min(width - 80, 1150), 12) + 12
    selected = {e["code"]: e for e in graph.edges}
    for code, detail, record in graph.edge_records:
        edge = selected.get(code)
        if edge:
            detail = edge["detail"]
            color = C[edge["kind"]]
        else:
            detail += " · UNRESOLVED ENDPOINT — no geometry fabricated"
            color = C["warning"]
        y = ledger_record(svg, y, code, detail, width, color)

    if graph.route_records:
        route = g.get("route") or {}
        y = section(svg, y + 18,
                    "Thread / " + str(route.get("traveller", "unspecified")),
                    width)
        for number, text in enumerate(graph.route_records, 1):
            y = ledger_record(svg, y, "ROUTE %02d" % number, text,
                              width, C["route"])

    if g.get("segments"):
        y = section(svg, y + 18, "Declared segments", width)
        for number, segment in enumerate(g["segments"], 1):
            if isinstance(segment, dict):
                key = segment.get("id", "SEG %d" % number)
                text = "%s · %s · %s → %s" % (
                    segment.get("label", ""),
                    segment.get("universe", "world unspecified"),
                    segment.get("from", "?"), segment.get("to", "?")
                )
                extra = {k: v for k, v in segment.items()
                         if k not in ("id", "label", "universe", "from", "to")}
                if extra:
                    text += " · " + compact(extra)
            else:
                key, text = "SEG %d" % number, compact(segment)
            y = ledger_record(svg, y, key, text, width)

    notes = list(g.get("assumptions", []))
    if "merges" in g:
        notes.append("Declared merge count: %s. A count supplies no merge "
                     "locations; none are invented." % g["merges"])
    if notes:
        y = section(svg, y + 18, "Interpretive assumptions / model notes", width)
        for number, note in enumerate(notes, 1):
            y = ledger_record(svg, y, "NOTE %02d" % number,
                              str(note), width)
    if graph.warnings:
        y = section(svg, y + 18, "Diagnostics — records retained, nothing guessed",
                    width)
        for number, warning in enumerate(graph.warnings, 1):
            y = ledger_record(svg, y, "CHECK %02d" % number, warning,
                              width, C["warning"])
    return y + 24


def render_document(story, view="2d"):
    validate(story)
    evidence = Evidence()
    evidence.scan(story)
    graphs = [Graph(g, i + 1, evidence, view)
              for i, g in enumerate(story["graphs"])]
    width = math.ceil(max([g.width for g in graphs] + [1100]) + 24)
    svg = SVG()
    definitions(svg)

    y = 34
    svg.text(40, y + 13, "ELSEHOW  /  WORLDS & THREAD",
             11, C["route"], "bold", letter_spacing=1.5)
    y += 35
    y = svg.paragraph(40, y, story["title"], min(width - 80, 1400),
                      34, C["ink"], 43, "bold") + 8
    if story.get("subtitle"):
        y = svg.paragraph(40, y, story["subtitle"], min(width - 80, 1300),
                          15, C["muted"], 23) + 14
    mode = ("2.5D · cabinet axonometric · depth separates surfaces only"
            if view == "2.5d" else "2D · categorical world columns")
    y = svg.paragraph(
        40, y, mode + " · Story-order ranks, not elapsed time. "
        "Equal ranks do not assert physical simultaneity.",
        min(width - 80, 1350), 12, C["muted"], 18
    ) + 18

    legend_lines = [
        ("split", "Amber S±", "Split outcomes. + and − are signs, not fates."),
        ("transfer", "Blue T", "Directed transfers. B body · M memory · "
         "C consciousness · S signal · ? literal/unspecified mechanism."),
        ("route", "Emerald V / L", "Numbered visits and explicit links only. "
         "Emerald centre on a cable means the route follows that connection."),
        ("rail", "Slate rail", "World identity. Cutoff means chart boundary, "
         "not destruction. Crossings are bridges; only markers are joins."),
        ("reference", "Evidence / fate", "[n] opens the evidence record. "
         "× dead · ● alive · ? unknown · ∅ nonexistent. "
         "Purple dotted connections are annotation references."),
    ]
    for kind, label, detail in legend_lines:
        sx = 45
        svg.line(sx, y + 10, sx + 31, y + 10, C[kind], 4)
        y = svg.paragraph(90, y, label + " — " + detail,
                          min(width - 140, 1260), 12, C["ink"], 18) + 9
    y += 12

    profile = story.get("profile") or {}
    if profile:
        y = section(svg, y, "Declared interpretation", width)
        profile_text = "Profile: %s · rules: %s" % (
            profile.get("name", "unspecified"),
            profile.get("rules", "unspecified")
        )
        y = ledger_record(svg, y, "PROFILE", profile_text, width)
        params = profile.get("params") or {}
        if params:
            y = ledger_record(
                svg, y, "PARAMETERS",
                " · ".join("%s: %s" % (k, compact(v))
                           for k, v in params.items()), width
            )
        y = ledger_record(
            svg, y, "POLICY",
            "Explicit records determine geometry. Profile declarations do not "
            "manufacture branches, activation intervals, genealogy, repeated "
            "worlds or replacement links. No reset is drawn. World-time "
            "coordinates are unavailable in this contract.", width
        )
        y += 16

    for graph in graphs:
        g = graph.g
        y = section(svg, y, "%s  /  %s" %
                    (g.get("namespace", "?"), g.get("title") or story["title"]),
                    width, graph.prefix)
        count = "%d declared worlds · %d events · %d transfers · %d split records" % (
            len(g.get("worlds", [])), len(g.get("events", [])),
            len(g.get("transfers", [])), len(g.get("splits", []))
        )
        y = svg.paragraph(40, y, count, width - 80, 12, C["muted"], 18) + 26
        svg.start("g", transform="translate(0 %.2f)" % y,
                  role="group",
                  aria_label="Atlas for " + str(g.get("namespace", "")))
        svg.raw(graph.draw())
        svg.end("g")
        y += graph.height
        y = graph_appendix(svg, graph, y, width)

    if evidence.rows:
        y = section(svg, y + 8, "Evidence / complete citation register", width,
                    "evidence")
        y = svg.paragraph(
            40, y,
            "Status is the supplied evidence status, not a truth rating. "
            "Repeated citations are deduplicated; all owners remain listed.",
            min(width - 80, 1280), 12, C["muted"], 18
        ) + 15
        for number, row in enumerate(evidence.rows, 1):
            cite = row["cite"]
            fields = ["%s: %s" % (k, compact(v))
                      for k, v in cite.items() if v is not None]
            text = " · ".join(fields)
            text += " · Referenced by: " + "; ".join(row["owners"])
            y = ledger_record(svg, y, "[%d]" % number, text,
                              width, C["transfer"],
                              ident="evidence-%d" % number)

    if story.get("sources"):
        y = section(svg, y + 18, "Sources — including fixture provenance", width)
        for number, source in enumerate(story["sources"], 1):
            y = ledger_record(svg, y, source.get("id", "SOURCE %d" % number),
                              compact(source), width)

    for field, heading in (("characters", "Characters"),
                           ("travellers", "Travellers"),
                           ("namespaces", "Namespaces")):
        if story.get(field):
            y = section(svg, y + 18, heading, width)
            for record in story[field]:
                y = ledger_record(svg, y, record.get("id", field),
                                  compact(record), width)

    if story.get("footer"):
        y = section(svg, y + 18, "Chart note", width)
        y = svg.paragraph(40, y, story["footer"], min(width - 80, 1280),
                          13, C["muted"], 20) + 20
    y += 32
    height = math.ceil(y)
    description = (
        "Worlds and Thread atlas. Story order progresses downward. "
        "Connections use reserved routing space. Full relationship and "
        "citation ledgers follow the chart. The HTML companion contains "
        "the complete accessible model."
    )
    result = (
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="%d" height="%d" viewBox="0 0 %d %d" '
        'font-family="%s" role="img" aria-labelledby="atlas-title atlas-desc">\n'
        '<title id="atlas-title">%s</title>\n'
        '<desc id="atlas-desc">%s</desc>\n'
        '<rect width="%d" height="%d" fill="%s"/>\n%s\n</svg>\n'
    ) % (
        width, height, width, height, FONT, esc(story["title"]),
        esc(description), width, height, C["paper"], svg.output()
    )
    warnings = [warning for graph in graphs for warning in graph.warnings]
    return result, width, height, warnings


def accessible_ledger(story):
    parts = []
    for graph in story["graphs"]:
        parts.append("<h3>%s — %s</h3>" % (
            esc(graph.get("namespace", "")), esc(graph.get("title", ""))
        ))
        parts.append("<table><thead><tr><th>World</th><th>Order</th>"
                     "<th>Event</th><th>Description</th><th>Citation</th>"
                     "</tr></thead><tbody>")
        for event in graph.get("events", []):
            parts.append("<tr>%s</tr>" % "".join(
                "<td>%s</td>" % esc(value) for value in (
                    event.get("universe"),
                    "unspecified" if event.get("order") is None
                    else event["order"],
                    str(event.get("id")) + " / " + str(event.get("kind")),
                    event.get("label"),
                    compact(event.get("cite") or "No citation supplied"),
                )
            ))
        parts.append("</tbody></table>")
        for field in ("worlds", "splits", "transfers", "route", "fates",
                      "segments", "beats", "assumptions", "evidence"):
            if graph.get(field):
                parts.append("<details><summary>%s</summary><pre>%s</pre>"
                             "</details>" %
                             (esc(field), esc(json.dumps(
                                 graph[field], ensure_ascii=False, indent=2))))
    return "\n".join(parts)


def render_html(story, svg, width, height, view):
    raw_model = esc(json.dumps(story, ensure_ascii=False, indent=2))
    title = esc(story["title"])
    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>@@TITLE@@ — Elsehow</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin:0; color:#172a3a; background:#f5f6f8;
       font:14px/1.5 system-ui,Arial,sans-serif; }
header { position:sticky; top:0; z-index:10; display:flex; flex-wrap:wrap;
         align-items:center; gap:10px 18px; padding:12px 20px;
         background:#fff; border-bottom:1px solid #cbd7e1; }
header strong { margin-right:auto; }
button, input { font:inherit; }
button { border:1px solid #bbcbd6; background:#fff; color:#172a3a;
         border-radius:6px; padding:5px 12px; cursor:pointer; }
button:hover { background:#edf3f7; }
button:focus-visible, a:focus-visible, summary:focus-visible {
    outline:3px solid #285ac7; outline-offset:3px;
}
label { white-space:nowrap; font-size:12px; }
#viewport { height:78vh; overflow:auto; overscroll-behavior:contain;
            border-bottom:1px solid #cbd7e1; }
#surface { position:relative; }
#surface > svg { display:block; position:absolute; left:0; top:0;
                 transform-origin:top left; max-width:none; }
main > p, main > details { margin:18px 24px; }
details { background:#fff; padding:12px 16px; border:1px solid #d3dde5;
          border-radius:8px; }
details details { margin:10px 0; }
summary { cursor:pointer; font-weight:600; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; }
table { border-collapse:collapse; width:100%; font-size:12px; }
th,td { padding:9px; text-align:left; vertical-align:top;
        border-bottom:1px solid #d3dde5; overflow-wrap:anywhere; }
th { background:#eef3f7; }
@media print {
    header,.screen-note { display:none; }
    #viewport { height:auto; overflow:visible; border:0; }
    #surface { width:auto!important; height:auto!important; }
    #surface > svg { position:static; transform:none!important;
                     width:100%; height:auto; }
    main > details { display:none; }
}
</style>
</head>
<body>
<header>
<strong>@@TITLE@@ <small> / @@VIEW@@</small></strong>
<button type="button" id="minus" aria-label="Zoom out">−</button>
<output id="zoom-label" aria-live="polite">100%</output>
<button type="button" id="plus" aria-label="Zoom in">+</button>
<button type="button" id="actual">100%</button>
<button type="button" id="fit">Fit width</button>
<label><input type="checkbox" data-layer="split" checked> Splits</label>
<label><input type="checkbox" data-layer="transfer" checked> Transfers</label>
<label><input type="checkbox" data-layer="route" checked> Thread</label>
<label><input type="checkbox" data-layer="evidence" checked> Citation tabs</label>
</header>
<main>
<div id="viewport" tabindex="0" aria-label="Scrollable timeline atlas">
<div id="surface">@@SVG@@</div>
</div>
<p class="screen-note">Native-size text is the default. Pan with the scrollbars;
zoom with the controls. Hiding a layer changes presentation only.
Citation tabs navigate to the evidence appendix. Hover cards or cables for
their exact records. No external scripts, fonts or assets are required.</p>
<details><summary>Accessible event and relationship ledger</summary>
@@LEDGER@@
</details>
<details><summary>Complete input model — including loose-schema fields</summary>
<pre>@@MODEL@@</pre></details>
</main>
<script>
"use strict";
(() => {
    const viewport = document.getElementById("viewport");
    const surface = document.getElementById("surface");
    const svg = surface.querySelector("svg");
    const label = document.getElementById("zoom-label");
    const W = @@WIDTH@@, H = @@HEIGHT@@;
    let zoom = 1;
    function setZoom(value) {
        const old = zoom;
        zoom = Math.max(0.08, Math.min(3, value));
        const cx = (viewport.scrollLeft + viewport.clientWidth / 2) / old;
        const cy = (viewport.scrollTop + viewport.clientHeight / 2) / old;
        surface.style.width = (W * zoom) + "px";
        surface.style.height = (H * zoom) + "px";
        svg.style.transform = "scale(" + zoom + ")";
        label.textContent = Math.round(zoom * 100) + "%";
        viewport.scrollLeft = Math.max(0, cx * zoom - viewport.clientWidth / 2);
        viewport.scrollTop = Math.max(0, cy * zoom - viewport.clientHeight / 2);
    }
    document.getElementById("minus").onclick = () => setZoom(zoom / 1.2);
    document.getElementById("plus").onclick = () => setZoom(zoom * 1.2);
    document.getElementById("actual").onclick = () => setZoom(1);
    document.getElementById("fit").onclick = () =>
        setZoom((viewport.clientWidth - 20) / W);
    document.querySelectorAll("[data-layer]").forEach(input => {
        input.addEventListener("change", () =>
            svg.classList.toggle("hide-" + input.dataset.layer, !input.checked));
    });
    svg.addEventListener("click", event => {
        const anchor = event.target.closest("a");
        if (!anchor) return;
        const href = anchor.getAttribute("href");
        if (!href || !href.startsWith("#")) return;
        const target = document.getElementById(href.slice(1));
        if (!target) return;
        event.preventDefault();
        const box = target.getBBox();
        viewport.scrollTop = Math.max(0, box.y * zoom - 24);
        viewport.scrollLeft = Math.max(0, box.x * zoom - 24);
        target.setAttribute("tabindex", "-1");
        target.focus({preventScroll:true});
    });
    setZoom(1);
    viewport.scrollLeft = 0;
    viewport.scrollTop = 0;
})();
</script>
</body>
</html>
"""
    replacements = {
        "@@TITLE@@": title,
        "@@VIEW@@": esc(view),
        "@@SVG@@": svg,
        "@@LEDGER@@": accessible_ledger(story),
        "@@MODEL@@": raw_model,
        "@@WIDTH@@": str(width),
        "@@HEIGHT@@": str(height),
    }
    # Single-pass replacement: input text cannot introduce new substitutions.
    import re
    return re.sub(r"@@(?:TITLE|VIEW|SVG|LEDGER|MODEL|WIDTH|HEIGHT)@@",
                  lambda match: replacements[match.group(0)], template)


# Backward-compatible public helpers.
def render_js(story, view="2d"):
    return render_document(story, view)[0]


def self_test():
    """Geometry/XML regression smoke tests, not a substitute for visual review."""
    story = {
        "abstract_model": "universe-timeline/1.0",
        "title": 'Atlas test < & " Unicode − ∅',
        "graphs": [{
            "namespace": "TEST",
            "worlds": [
                {"id": "A", "label": "Opening world", "origin": "initial"},
                {"id": "B", "label": "Born world", "origin": "born",
                 "born": {"event": "fork", "parent": "A", "tine": "-"}},
                {"id": "C", "label": "Empty preexisting world",
                 "origin": "preexisting"},
            ],
            "events": [
                {"id": "start", "kind": "start", "universe": "A", "order": 0,
                 "label": "A deliberately long event label " * 8,
                 "cite": {"source": "fixture", "locator": "<opening>",
                          "status": "pending"}},
                {"id": "fork", "kind": "split", "universe": "A", "order": 1,
                 "label": "Fork"},
                {"id": "same", "kind": "outcome", "universe": "A", "order": 1,
                 "label": "Same rank; separate card"},
                {"id": "entry", "kind": "entry", "universe": "B", "order": 1,
                 "label": "Born-world entry"},
                {"id": "end", "kind": "cutoff", "universe": "B", "order": None,
                 "label": "Order unspecified"},
            ],
            "splits": [{
                "event": "fork", "outcomes": {
                    "+": {"universe": "A", "entry": "same"},
                    "-": {"universe": "B", "entry": "entry"},
                }
            }],
            "transfers": [
                {"id": "t1", "traveller": "p", "mechanism": "consciousness",
                 "from": {"exit": "fork"}, "to": {"entry": "entry"}},
                {"id": "loop", "traveller": "p", "mechanism": "time_travel",
                 "from": {"exit": "same"}, "to": {"entry": "same"}},
            ],
            "route": {
                "traveller": "p",
                "visits": [
                    {"id": "v1", "universe": "A", "entry": "start",
                     "exit": "fork"},
                    {"id": "v2", "universe": "B", "entry": "entry",
                     "exit": "end"},
                    {"id": "v3", "universe": "B", "entry": "entry",
                     "exit": "entry"},
                ],
                "links": [{"from": "v1", "to": "v2", "via": "t1",
                           "kind": "transfer"}],
            },
            "fates": [
                {"id": "f1", "universe": "B", "event": "end",
                 "instance": "p", "status": "alive"},
                {"id": "f2", "universe": "A", "event": "end",
                 "instance": "other", "status": "nonexistent"},
            ],
        }],
    }
    for view in ("2d", "2.5d"):
        result, width, height, warnings = render_document(story, view)
        ET.fromstring(result)
        assert width > 1000 and height > 500
        assert "time_travel" in result and "T1 C" in result
        assert "Same rank; separate card" in result
        assert "Order unspecified" in result
        assert render_document(story, view)[0] == result
        wrapper = render_html(story, result, width, height, view)
        assert "<!doctype html>" in wrapper
        evidence = Evidence()
        evidence.scan(story)
        graph = Graph(story["graphs"][0], 1, evidence, view)
        for world in graph.worlds:
            cards = [item for item in graph.items
                     if item["world"] == world["id"]]
            for i, a in enumerate(cards):
                for b in cards[i + 1:]:
                    assert (a["y"] + a["height"] <= b["y"]
                            or b["y"] + b["height"] <= a["y"])
        for edge in graph.edges:
            assert "a_bus" in edge and "b_bus" in edge
        assert graph.world_map["B"]["_start"] == graph.events["fork"]["node_y"]
    print("self-test: deterministic SVG/XML, both views, card separation, "
          "birth start, ties, null order, self-transfer and citation escaping OK")


def main():
    parser = argparse.ArgumentParser(
        description="Render a readable Worlds and Thread atlas; writes SVG + HTML."
    )
    parser.add_argument("input", nargs="?", help="Abstract model JSON file")
    parser.add_argument("-o", "--out", help="Primary output path (.svg or .html)")
    parser.add_argument("--view", choices=("2d", "2.5d"), default="2d")
    parser.add_argument("--format", choices=("svg", "html"),
                        help="Primary format; companion is always written")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.input or not args.out:
        parser.error("input and -o/--out are required unless --self-test is used")
    try:
        input_path = Path(args.input)
        out = Path(args.out)
        fmt = args.format or (
            "html" if out.suffix.lower() in (".html", ".htm") else "svg"
        )
        other_suffix = ".html" if fmt == "svg" else ".svg"
        companion = out.with_suffix(other_suffix)
        if companion == out:
            companion = out.with_name(out.name + other_suffix)
        if input_path.resolve() in (out.resolve(), companion.resolve()):
            raise ValueError("An output path would overwrite the input JSON.")
        with input_path.open("r", encoding="utf-8") as handle:
            story = json.load(handle)
        svg, width, height, warnings = render_document(story, args.view)
        wrapper = render_html(story, svg, width, height, args.view)
        # Parse the generated SVG before committing either output.
        ET.fromstring(svg)
        primary = svg if fmt == "svg" else wrapper
        secondary = wrapper if fmt == "svg" else svg
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(primary, encoding="utf-8")
        companion.write_text(secondary, encoding="utf-8")
        print("wrote %s" % out)
        print("wrote %s" % companion)
        print("%s · %d × %d px · %d diagnostic(s)" %
              (args.view, width, height, len(warnings)))
        for warning in warnings:
            print("warning: " + warning, file=sys.stderr)
    except (OSError, ValueError, TypeError, KeyError, ET.ParseError) as exc:
        parser.exit(2, "render.py: %s\n" % exc)


if __name__ == "__main__":
    main()