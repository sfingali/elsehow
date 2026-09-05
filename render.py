#!/usr/bin/env python3
"""
Universe Timeline Atlas — Python 3, standard library only.

Usage:
    python3 render.py input.json -o output.svg
    python3 render.py input.json -o output.svg --view 2.5d
    python3 render.py input.json -o output.html --format html

Both <output-stem>.svg and <output-stem>.html are always written.
--format selects the primary output reported by the CLI.

Design:
  • Worlds are containment rails, not inferred histories.
  • Horizontal positions rank declared numeric orders; gaps are not durations.
  • Null orders occupy a separately labelled, explicitly unordered area.
  • Only declared relationships produce connectors.
  • In 2.5d, the same diagram is projected onto a receding plane. Depth has
    no narrative or temporal meaning.
  • Every input value is retained in a visible, linked record appendix and
    in the SVG metadata. Unresolvable relationships are reported, not guessed.

The schema leaves segments, beats, visits, and route links structurally open.
This renderer recognizes the sample conventions:
  segment: {id, universe, from: event_id, to: event_id}
  beat:    {segment: segment_id, order: number, text}
  visit:   {id, universe, entry: event_id, exit: event_id,
            passes: [event_id, ...]}
  link:    {from: visit_id, to: visit_id, kind, via: transfer_id}
Other structures remain fully visible in the record appendix.
"""
import argparse
import html
import json
import math
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path


PAPER = "#f5f3ed"
INK = "#172c3c"
MUTED = "#637482"
LINE = "#d6dfdf"
WHITE = "#ffffff"
GOLD = "#a76908"
PLUS = "#178469"
MINUS = "#c05a55"
WORLD_COLORS = [
    "#287f8b", "#8064a2", "#ac7051", "#537da9",
    "#628247", "#a3577b", "#607e86", "#927936"
]
MECHANISMS = {
    "body": ("B", "#b67524"),
    "memory": ("M", "#16877e"),
    "consciousness": ("C", "#8460a4"),
    "signal": ("S", "#3e79b1"),
}
UNKNOWN_MECHANISM = ("?", "#657684")
STATUS = {
    "alive": ("●", "#178469"),
    "dead": ("×", "#bc5054"),
    "unknown": ("?", "#727e88"),
    "nonexistent": ("∅", "#727e88"),
}
KINDS = {
    "start", "split", "outcome", "entry", "exit", "anchor",
    "cutoff", "gate_entry", "gate_exit"
}


def xml(value):
    """Escape input as XML text/attributes; replace XML-illegal characters."""
    s = str(value)
    s = "".join(
        c if (
            c in "\t\n\r" or
            0x20 <= ord(c) <= 0xD7FF or
            0xE000 <= ord(c) <= 0xFFFD or
            0x10000 <= ord(c) <= 0x10FFFF
        ) else "\ufffd" for c in s
    )
    return html.escape(s, quote=True)


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(", ", ": "))


def pretty(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def arr(value):
    return value if isinstance(value, list) else []


def obj(value):
    return value if isinstance(value, dict) else {}


def numeric(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )


def wrap(value, width):
    result = []
    for line in str(value).splitlines() or [""]:
        result.extend(textwrap.wrap(
            line, width=max(8, int(width)),
            replace_whitespace=False, drop_whitespace=True,
            break_long_words=True, break_on_hyphens=False
        ) or [""])
    return result


def snippet(value, width=23, limit=2):
    lines = wrap(value, width)
    if len(lines) > limit:
        lines = lines[:limit]
        lines[-1] = lines[-1].rstrip(" .") + "…"
    return lines


def unique_index(items, key="id"):
    counts = Counter(
        item.get(key) for item in items
        if isinstance(item, dict) and isinstance(item.get(key), str)
    )
    return {
        item[key]: item for item in items
        if isinstance(item, dict)
        and isinstance(item.get(key), str)
        and counts[item[key]] == 1
    }, [k for k, n in counts.items() if n > 1]


def attrs(values):
    return "".join(
        ' {}="{}"'.format(k.replace("_", "-"), xml(v))
        for k, v in values.items() if v is not None
    )


class SVG:
    def __init__(self):
        self.parts = []

    def raw(self, value):
        self.parts.append(value)

    def start(self, tag, **kw):
        self.raw("<" + tag + attrs(kw) + ">")

    def end(self, tag="g"):
        self.raw("</" + tag + ">")

    def element(self, tag, **kw):
        self.raw("<" + tag + attrs(kw) + "/>")

    def text(self, x, y, value, size=12, fill=INK, **kw):
        self.raw(
            "<text" + attrs(dict(x=round(x, 2), y=round(y, 2),
                                font_size=size, fill=fill, **kw)) +
            ">" + xml(value) + "</text>"
        )

    def lines(self, x, y, lines, size=12, leading=17, **kw):
        for i, line in enumerate(lines):
            self.text(x, y + i * leading, line, size, **kw)

    def rect(self, x, y, width, height, fill=WHITE, rx=0, **kw):
        self.element("rect", x=x, y=y, width=width, height=height,
                     fill=fill, rx=rx, **kw)

    def line(self, x1, y1, x2, y2, stroke=LINE, width=1, **kw):
        self.element("line", x1=x1, y1=y1, x2=x2, y2=y2,
                     stroke=stroke, stroke_width=width, **kw)

    def title(self, value):
        self.raw("<title>" + xml(value) + "</title>")

    def link(self, target, title=None):
        self.start("a", href="#" + target)
        if title:
            self.title(title)

    def __str__(self):
        return "".join(self.parts)


class Record:
    def __init__(self, number, category, label, value, path):
        self.anchor = "record-{}".format(number)
        self.code = "{:03d}".format(number)
        self.category = category
        self.label = str(label)
        self.value = value
        self.path = path


class Atlas:
    def __init__(self, model, view):
        self.model = model
        self.view = view
        self.records = []
        self.lookup = {}
        self.source_records = {}
        self.add_records()

    def add(self, category, label, value, path, lookup=None):
        r = Record(len(self.records) + 1, category, label, value, path)
        self.records.append(r)
        if lookup is not None:
            self.lookup[lookup] = r
        return r

    def add_records(self):
        # Partition the document without dropping fields or empty containers.
        top_meta = {}
        for key, value in self.model.items():
            if key == "graphs":
                continue
            if isinstance(value, list) and value:
                for i, item in enumerate(value):
                    d = obj(item)
                    label = d.get("title", d.get("label", d.get("id", key)))
                    r = self.add(key, label, item, "$.{}[{}]".format(key, i))
                    if key == "sources" and isinstance(d.get("id"), str):
                        self.source_records.setdefault(d["id"], []).append(r)
            elif isinstance(value, dict) and value:
                self.add(key, value.get("name", key), value, "$." + key)
            else:
                top_meta[key] = value
        self.add("document", self.model["title"], top_meta, "$")

        for gi, graph in enumerate(self.model["graphs"]):
            meta = {}
            for key, value in graph.items():
                if isinstance(value, list) and value:
                    for i, item in enumerate(value):
                        d = obj(item)
                        label = d.get(
                            "label", d.get("text", d.get(
                                "id", d.get("event", "{} {}".format(key, i + 1))
                            ))
                        )
                        self.add(
                            key, label, item,
                            "$.graphs[{}].{}[{}]".format(gi, key, i),
                            (gi, key, i)
                        )
                elif isinstance(value, dict) and value:
                    self.add(
                        key, value.get("traveller", key), value,
                        "$.graphs[{}].{}".format(gi, key), (gi, key)
                    )
                else:
                    meta[key] = value
            self.add("graph", graph.get("title", graph["namespace"]), meta,
                     "$.graphs[{}]".format(gi), (gi, "meta"))

    def record(self, gi, key, i=None):
        return self.lookup.get((gi, key) if i is None else (gi, key, i))

    def source(self, source_id):
        found = self.source_records.get(source_id, [])
        return found[0] if len(found) == 1 else None

    def render(self):
        scenes = [GraphScene(self, i, g) for i, g in enumerate(self.model["graphs"])]
        width = max([1240] + [s.width for s in scenes])
        out = SVG()
        y = self.header(out, width)

        for scene in scenes:
            out.start("g", transform="translate(0,{})".format(y))
            out.raw(scene.render())
            out.end()
            y += scene.height + 34

        y = self.record_appendix(out, y, width)
        footer = self.model.get("footer", "")
        if footer:
            lines = wrap(footer, min(150, (width - 96) / 7))
            out.lines(48, y + 25, lines, 12, 18, fill=MUTED)
            y += 45 + len(lines) * 18
        out.text(48, y + 22,
                 "UNIVERSE ATLAS  /  Explicit structure · complete records · no inferred topology",
                 10, MUTED, letter_spacing="1")
        height = math.ceil(y + 54)

        defs = SVG()
        for color in sorted(set(
                [PLUS, MINUS, GOLD, UNKNOWN_MECHANISM[1]] +
                [v[1] for v in MECHANISMS.values()])):
            mid = marker_id(color)
            defs.raw(
                '<marker id="{}" viewBox="0 0 10 10" refX="9" refY="5" '
                'markerWidth="8" markerHeight="8" markerUnits="userSpaceOnUse" '
                'orient="auto-start-reverse">'
                '<path d="M 1 1 L 9 5 L 1 9 Z" fill="{}"/></marker>'.format(mid, color)
            )

        style = """
        text { font-family: Inter, ui-sans-serif, system-ui, -apple-system,
               "Segoe UI", sans-serif; }
        .serif { font-family: Georgia, "Times New Roman", serif; }
        .mono { font-family: ui-monospace, SFMono-Regular, Consolas,
                "Liberation Mono", monospace; }
        a { cursor: pointer; }
        a:hover .event-hit { stroke: #172c3c; stroke-width: 3; }
        .record:target > .record-bg, .record.search-hit > .record-bg {
            stroke: #a76908; stroke-width: 3;
        }
        .record { scroll-margin: 80px; }
        .hide-splits .layer-splits,
        .hide-transfers .layer-transfers,
        .hide-route .layer-route,
        .hide-annotations .layer-annotations { display: none; }
        """
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" '
            'width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            'role="img" aria-labelledby="atlas-title atlas-desc">'
            '<title id="atlas-title">{title}</title>'
            '<desc id="atlas-desc">Universe timeline atlas. Event positions use '
            'declared ordinal values, not elapsed time. Diagram references link '
            'to complete records below. Projection depth has no semantic meaning.'
            '</desc><metadata id="input-model">{metadata}</metadata>'
            '<defs>{defs}</defs><style>{style}</style>'
            '<rect width="100%" height="100%" fill="{paper}"/>'
            '{body}</svg>'
        ).format(
            w=math.ceil(width), h=height, title=xml(self.model["title"]),
            metadata=xml(json.dumps(self.model, ensure_ascii=True)),
            defs=str(defs), style=style, paper=PAPER, body=str(out)
        )

    def header(self, s, width):
        s.rect(0, 0, width, 9, INK)
        s.text(48, 49, "U N I V E R S E   A T L A S", 11, MUTED)
        title_lines = wrap(self.model["title"], 42)
        s.lines(46, 101, title_lines, 43, 49, class_="serif")
        y = 112 + (len(title_lines) - 1) * 49
        subtitle = self.model.get("subtitle", "")
        if subtitle:
            lines = wrap(subtitle, 126)
            s.lines(49, y + 19, lines, 14, 21, fill=MUTED)
            y += len(lines) * 21 + 12

        graphs = self.model["graphs"]
        nw = sum(len(g.get("worlds", [])) for g in graphs)
        ne = sum(len(arr(g.get("events"))) for g in graphs)
        nt = sum(len(arr(g.get("transfers"))) for g in graphs)
        profile = obj(self.model.get("profile"))
        info = "{} graphs  /  {} declared worlds  /  {} events  /  {} transfers".format(
            len(graphs), nw, ne, nt
        )
        s.text(49, y + 25, info, 12, INK, class_="mono")
        y += 44
        view_label = (
            "2.5D · receding display plane; depth is not data"
            if self.view == "2.5d" else "2D · flat world rails"
        )
        profile_label = "Profile: " + str(profile.get("name", "unspecified"))
        for line in wrap(view_label + "  /  " + profile_label, 145):
            s.text(49, y, line, 11, MUTED)
            y += 16
        y += 12

        s.rect(48, y, min(width - 96, 1144), 128, "#eaf0ee", 12)
        s.text(66, y + 24, "READING KEY", 10, MUTED, letter_spacing="1.5")
        entries = [
            ("B", "body", MECHANISMS["body"][1]),
            ("M", "memory", MECHANISMS["memory"][1]),
            ("C", "consciousness", MECHANISMS["consciousness"][1]),
            ("S", "signal", MECHANISMS["signal"][1]),
            ("?", "other / unspecified — literal name retained", MUTED),
        ]
        x = 66
        for badge, label, color in entries:
            pill(s, x, y + 36, badge, color, width=25)
            s.text(x + 33, y + 50, label, 11, MUTED)
            x += 39 + len(label) * 6.3
        s.text(66, y + 80,
               "+ / −  declared split outcomes     →  transfer direction"
               "     R  traveller route     §  source reference", 12, INK)
        s.text(66, y + 105,
               "Rails are containment guides. Order spacing is ordinal, not duration."
               " Click any numbered item for its full record.", 11, MUTED)
        return y + 151

    def record_appendix(self, s, y, width):
        s.line(48, y, width - 48, y, INK)
        s.text(48, y + 39, "The record index", 29, INK, class_="serif")
        s.text(48, y + 64,
               "Complete declared values, including evidence, assumptions, profile parameters,"
               " opaque extensions and unresolved references.", 12, MUTED)
        y += 91

        # A wide chart need not force unreadably wide record text.
        columns = max(2, min(4, int((width - 72) // 540)))
        card_width = min(600, (width - 96 - (columns - 1) * 20) / columns)
        total_width = columns * card_width + (columns - 1) * 20
        left = 48
        if total_width > width - 96:
            card_width = (width - 96 - (columns - 1) * 20) / columns

        row = []
        for r in self.records:
            row.append(r)
            if len(row) == columns:
                heights = [
                    self.record_card(s, r, left + i * (card_width + 20), y, card_width)
                    for i, r in enumerate(row)
                ]
                y += max(heights) + 20
                row = []
        if row:
            heights = [
                self.record_card(s, r, left + i * (card_width + 20), y, card_width)
                for i, r in enumerate(row)
            ]
            y += max(heights) + 20
        return y

    def record_card(self, s, record, x, y, width):
        label = wrap(record.label, (width - 38) / 7.0)
        code_lines = []
        code_width = max(20, int((width - 38) / 6.6))
        for line in pretty(record.value).splitlines():
            indent = min(len(line) - len(line.lstrip()), 20)
            chunks = textwrap.wrap(
                line, width=code_width, subsequent_indent=" " * indent + "↳ ",
                replace_whitespace=False, drop_whitespace=False,
                break_long_words=True, break_on_hyphens=False
            )
            code_lines.extend(chunks or [""])
        path_lines = wrap(record.path, (width - 38) / 6.2)
        height = (
            48 + len(label) * 17 + len(path_lines) * 14 +
            18 + len(code_lines) * 15 + 18
        )
        s.start("g", id=record.anchor, **{"class": "record"})
        s.rect(x, y, width, height, WHITE, 10, stroke=LINE,
               **{"class": "record-bg"})
        s.rect(x, y + 14, 3, 25, "#39828b", 1)
        s.text(x + 18, y + 27,
               record.code + "  /  " + record.category.upper(), 10, MUTED,
               letter_spacing="1")
        yy = y + 49
        s.lines(x + 18, yy, label, 13, 17, font_weight="600")
        yy += len(label) * 17 + 2
        s.lines(x + 18, yy, path_lines, 10, 14, fill=MUTED, class_="mono")
        yy += len(path_lines) * 14 + 9
        s.line(x + 18, yy - 2, x + width - 18, yy - 2, LINE)
        yy += 15
        s.lines(x + 18, yy, code_lines, 11, 15, fill="#415767", class_="mono")
        s.end()
        return height


def marker_id(color):
    return "arrow-" + color.lstrip("#")


def pill(s, x, y, label, color, width=None, height=21, background=WHITE):
    width = width or max(27, len(str(label)) * 6.6 + 16)
    s.rect(x, y, width, height, background, height / 2,
           stroke=color, stroke_width=1)
    s.text(x + width / 2, y + height * 0.70, label, 10, color,
           text_anchor="middle", font_weight="650")
    return width


def path_line(points):
    if not points:
        return ""
    return "M " + " L ".join("{:.2f},{:.2f}".format(*p) for p in points)


def curve(a, b, index=0):
    """A directional connector, including backwards and self references."""
    ax, ay = a
    bx, by = b
    if abs(ay - by) < 25:
        lift = 66 + (index % 5) * 17
        if abs(ax - bx) < 3:
            c1, c2 = (ax + 80, ay - lift), (bx - 80, by - lift)
        else:
            c1 = (ax + (bx - ax) * .22, min(ay, by) - lift)
            c2 = (ax + (bx - ax) * .78, min(ay, by) - lift)
    else:
        direction = 1 if bx >= ax else -1
        bend = max(56, min(155, abs(bx - ax) * .48))
        shift = ((index % 5) - 2) * 12
        c1 = (ax + direction * bend, ay + shift)
        c2 = (bx - direction * bend, by + shift)

    def trim(p, towards, amount):
        dx, dy = towards[0] - p[0], towards[1] - p[1]
        length = math.hypot(dx, dy) or 1
        return p[0] + amount * dx / length, p[1] + amount * dy / length

    start = trim(a, c1, 10)
    end = trim(b, c2, 12)
    middle = (
        (start[0] + 3 * c1[0] + 3 * c2[0] + end[0]) / 8,
        (start[1] + 3 * c1[1] + 3 * c2[1] + end[1]) / 8,
    )
    d = "M {:.2f},{:.2f} C {:.2f},{:.2f} {:.2f},{:.2f} {:.2f},{:.2f}".format(
        *start, *c1, *c2, *end
    )
    return d, middle


class GraphScene:
    def __init__(self, atlas, gi, graph):
        self.a, self.gi, self.g = atlas, gi, graph
        self.worlds = arr(graph.get("worlds"))
        self.events = arr(graph.get("events"))
        self.segments = arr(graph.get("segments"))
        self.beats = arr(graph.get("beats"))
        self.transfers = arr(graph.get("transfers"))
        self.splits = arr(graph.get("splits"))
        self.fates = arr(graph.get("fates"))
        self.route = obj(graph.get("route"))
        self.notes = []
        self.note_set = set()
        self.wmap, wd = unique_index(self.worlds)
        self.emap, ed = unique_index(self.events)
        self.smap, sd = unique_index(self.segments)
        self.tmap, td = unique_index(self.transfers)
        for kind, duplicates in [
            ("world", wd), ("event", ed), ("segment", sd), ("transfer", td)
        ]:
            for value in duplicates:
                self.note("Duplicate {} ID {!r}; references to it are ambiguous.".format(kind, value))

        self.wrow = {
            w["id"]: i for i, w in enumerate(self.worlds)
            if self.wmap.get(w.get("id")) is w
        }
        orders = set()
        counts = defaultdict(Counter)
        for e in self.events:
            if numeric(e.get("order")):
                orders.add(e["order"])
                counts[e["order"]][e["universe"]] += 1
        for b in self.beats:
            if isinstance(b, dict) and numeric(b.get("order")):
                orders.add(b["order"])
        self.orders = sorted(orders)

        self.columns = {}
        self.spans = {}
        x = 65
        for order in self.orders:
            slots = max([1] + list(counts[order].values()))
            width = 144 * slots
            self.columns[order] = x + width / 2
            self.spans[order] = (x, width)
            x += width
        self.ordered_end = x + 12

        null_counts = Counter(e["universe"] for e in self.events if e.get("order") is None)
        self.has_unordered = bool(null_counts)
        self.unordered_start = self.ordered_end + 42
        self.local_width = max(
            640, self.ordered_end + (
                max(null_counts.values()) * 144 + 84 if null_counts else 40
            )
        )

        max_visits = Counter(
            obj(v).get("universe") for v in arr(self.route.get("visits"))
            if isinstance(obj(v).get("universe"), str)
        )
        max_fates = Counter(
            f.get("event") for f in self.fates if isinstance(f, dict)
            and isinstance(f.get("event"), str)
        )
        self.row_height = max(
            210,
            148 + 14 * max([0] + list(max_visits.values())) +
            23 * max([0] + list(max_fates.values()))
        )
        self.plane_height = max(1, len(self.worlds)) * self.row_height
        self.depth = atlas.view == "2.5d"
        self.width = math.ceil(345 + self.local_width + (175 if self.depth else 0) + 50)
        self.title_lines = wrap(graph.get("title", graph["namespace"]), 75)
        self.chart_top = 104 + 29 * (len(self.title_lines) - 1)
        self.positions = {}
        self.event_positions = {}
        lane_slots = defaultdict(Counter)
        null_slots = Counter()
        for i, e in enumerate(self.events):
            world = e["universe"]
            if world not in self.wrow:
                self.note("Event {!r}: universe {!r} is missing or ambiguous; node is in the index only."
                          .format(e["id"], world))
                continue
            order = e.get("order")
            if numeric(order):
                start, width = self.spans[order]
                slot = lane_slots[order][world]
                lane_slots[order][world] += 1
                ex = start + 72 + slot * 144
            else:
                ex = self.unordered_start + 72 + null_slots[world] * 144
                null_slots[world] += 1
            ey = self.row_height * (self.wrow[world] + .5)
            point = self.project(ex, ey)
            self.event_positions[i] = point
            if self.emap.get(e["id"]) is e:
                self.positions[e["id"]] = point

        self.transfer_geometry = {}
        self.visit_geometry = {}
        self.edge_counter = 0
        # Render once to establish warning count and exact scene height.
        self.body = self.draw()
        self.height = self.computed_height

    def note(self, message):
        if message not in self.note_set:
            self.notes.append(message)
            self.note_set.add(message)

    def project(self, x, y):
        if not self.depth:
            return 345 + x, self.chart_top + y
        depth = (self.plane_height - y) / self.plane_height
        scale = 1 - .15 * depth
        return (
            345 + 170 * depth + x * scale,
            self.chart_top + .82 * y + .10 * (self.local_width - x) * scale
        )

    def rec(self, kind, i=None):
        return self.a.record(self.gi, kind, i)

    def resolve(self, event_id, universe=None, context="Reference"):
        if not isinstance(event_id, str):
            self.note(context + ": no explicit event endpoint; no temporal position inferred.")
            return None
        event = self.emap.get(event_id)
        if event is None or event_id not in self.positions:
            self.note("{}: event {!r} is missing, ambiguous or unplaceable.".format(context, event_id))
            return None
        if universe is not None and universe != event["universe"]:
            self.note("{}: universe {!r} conflicts with event {!r}; connector not drawn."
                      .format(context, universe, event_id))
            return None
        return self.positions[event_id]

    def connector(self, s, a, b, label, color, record, layer,
                  dashed=False, width=2, tooltip="", geometry=None):
        if a is None or b is None:
            return None
        if geometry is None:
            geometry = curve(a, b, self.edge_counter)
            self.edge_counter += 1
        d, mid = geometry
        s.start("g", **{"class": "layer-" + layer})
        if record:
            s.link(record.anchor, tooltip or pretty(record.value))
        elif tooltip:
            s.title(tooltip)
        s.element("path", d=d, fill="none", stroke=PAPER,
                  stroke_width=width + 5, stroke_linecap="round", opacity=".94")
        s.element(
            "path", d=d, fill="none", stroke=color, stroke_width=width,
            stroke_dasharray="6 5" if dashed else None,
            marker_end="url(#{})".format(marker_id(color)),
            stroke_linecap="round"
        )
        if label:
            bw = max(30, len(label) * 6.5 + 16)
            pill(s, mid[0] - bw / 2, mid[1] - 11, label, color, bw)
        if record:
            s.end("a")
        s.end()
        return geometry

    def draw(self):
        s = SVG()
        s.text(48, 21, "{:02d}  /  {}".format(self.gi + 1, self.g["namespace"]),
               10, MUTED, letter_spacing="1.3")
        s.lines(48, 55, self.title_lines, 25, 29, class_="serif")
        subtitle_y = 77 + 29 * (len(self.title_lines) - 1)
        s.text(48, subtitle_y,
               "Declared event.order · ordinal spacing"
               "  |  equal-order slots are presentation only", 11, MUTED)
        if numeric(self.g.get("merges")):
            self.note("Declared merges: {}. No merge endpoints are supplied by this field."
                      .format(self.g["merges"]))

        corners = [
            self.project(0, 0), self.project(self.local_width, 0),
            self.project(self.local_width, self.plane_height),
            self.project(0, self.plane_height)
        ]
        if self.depth:
            shadow = [(x + 2, y + 12) for x, y in corners]
            s.element("path", d=path_line(shadow) + " Z", fill="#d7dfdc")
        s.element("path", d=path_line(corners) + " Z",
                  fill="#eef2ef", stroke=LINE)

        if not self.worlds:
            s.text(370, self.chart_top + 90,
                   "No worlds declared. All supplied records remain below.", 15, MUTED)

        for order in self.orders:
            x = self.columns[order]
            a, b = self.project(x, 0), self.project(x, self.plane_height)
            s.line(*a, *b, "#d8e1df", 1, stroke_dasharray="2 7")
            # Values shown here are exclusively input order values.
            s.text(a[0], a[1] - 13, str(order), 11, MUTED,
                   text_anchor="middle", class_="mono")
        if self.has_unordered:
            a = self.project(self.unordered_start, 0)
            b = self.project(self.unordered_start, self.plane_height)
            s.line(*a, *b, "#a4afae", 1.2, stroke_dasharray="4 6")
            s.text(a[0] + 13, a[1] - 13, "UNORDERED", 10, MUTED,
                   letter_spacing="1")

        for i, w in enumerate(self.worlds):
            color = WORLD_COLORS[i % len(WORLD_COLORS)]
            y = self.row_height * (i + .5)
            a, b = self.project(0, y), self.project(self.local_width, y)
            s.line(*a, *b, color, 19, opacity=".075")
            s.line(*a, *b, color, 1.7, opacity=".55")
            record = self.rec("worlds", i)
            if record:
                s.link(record.anchor, pretty(w))
            lx = a[0] - 289
            s.rect(lx, a[1] - 41, 4, 50, color, 2)
            s.text(lx + 15, a[1] - 23,
                   "{}  /  {}".format(record.code if record else "", w["id"]),
                   10, color, class_="mono")
            lines = snippet(w["label"], 31, 2)
            s.lines(lx + 15, a[1] - 3, lines, 14, 18, font_weight="600")
            yy = a[1] + 18 * (len(lines) - 1) + 19
            s.text(lx + 15, yy, "origin · " + w["origin"], 11, MUTED)
            detail = []
            born = obj(w.get("born"))
            for key in ("parent", "event", "tine"):
                if key in born:
                    detail.append(key + ": " + str(born[key]))
            if "ancestry" in w:
                detail.append("ancestry: " + str(w["ancestry"]))
            s.lines(lx + 15, yy + 17,
                    snippet(" · ".join(detail), 37, 3) if detail else [],
                    10, 14, fill=MUTED)
            if record:
                s.end("a")
            if w["origin"] == "born":
                for key, mapping in (("parent", self.wmap), ("event", self.emap)):
                    ref = born.get(key)
                    if isinstance(ref, str) and ref not in mapping:
                        self.note("World {!r}: born.{} reference {!r} is unresolved."
                                  .format(w["id"], key, ref))
            # Origins are declarations, not automatically inferred split edges.

        self.draw_segments(s)
        self.draw_splits(s)
        self.draw_transfers(s)
        self.draw_route(s)
        self.draw_events(s)
        self.draw_beats(s)
        self.draw_fates(s)

        bottom = max(y for x, y in corners) + 45
        s.text(48, bottom,
               "Node labels are excerpts. Numbered links open complete records."
               " Unavailable citations remain explicitly unavailable.", 11, MUTED)
        bottom += 26

        if self.notes:
            lines = []
            for note in self.notes:
                wrapped = wrap(note, 145)
                lines.extend(["• " + wrapped[0]] + ["  " + v for v in wrapped[1:]])
            height = 48 + len(lines) * 17
            s.rect(48, bottom, min(self.width - 96, 1144), height,
                   "#f0eade", 9, stroke="#e1d5bf")
            s.text(65, bottom + 24, "PLACEMENT NOTES / NO GUESSED ENDPOINTS",
                   10, GOLD, letter_spacing="1")
            s.lines(65, bottom + 47, lines, 11, 17, fill="#76603f")
            bottom += height + 8
        self.computed_height = bottom + 8
        return str(s)

    def draw_segments(self, s):
        for i, value in enumerate(self.segments):
            seg = obj(value)
            record = self.rec("segments", i)
            context = "Segment {}".format(seg.get("id", i + 1))
            if not seg:
                self.note(context + ": opaque structure retained in the index.")
                continue
            a = self.resolve(seg.get("from"), seg.get("universe"), context)
            b = self.resolve(seg.get("to"), seg.get("universe"), context)
            if a is None or b is None:
                continue
            # A segment is an extent, not an invented directional transfer.
            s.start("g", **{"class": "layer-annotations"})
            s.link(record.anchor, pretty(value))
            s.line(a[0], a[1] - 17, b[0], b[1] - 17, "#80989b", 5, opacity=".35")
            pill(s, (a[0] + b[0]) / 2 - 26, (a[1] + b[1]) / 2 - 29,
                 "Sg " + record.code, "#60787d", 58)
            s.end("a")
            s.end()

    def draw_splits(self, s):
        for i, split in enumerate(self.splits):
            record = self.rec("splits", i)
            context = "Split " + str(split.get("event", i + 1))
            a = self.resolve(split.get("event"), split.get("source_universe"), context)
            outcomes = obj(split.get("outcomes"))
            if not outcomes:
                self.note(context + ": no outcome endpoints declared.")
            for sign, outcome in outcomes.items():
                if not isinstance(outcome, dict):
                    self.note(context + ": opaque outcome {!r} retained in the index.".format(sign))
                    continue
                b = self.resolve(
                    outcome.get("entry"), outcome.get("universe"),
                    context + " / outcome " + str(sign)
                )
                label = str(sign) + " · " + record.code
                color = PLUS if sign == "+" else MINUS if sign == "-" else MUTED
                self.connector(s, a, b, label, color, record, "splits",
                               dashed=True, tooltip=pretty(split))

    def draw_transfers(self, s):
        for i, transfer in enumerate(self.transfers):
            record = self.rec("transfers", i)
            fr, to = obj(transfer.get("from")), obj(transfer.get("to"))
            context = "Transfer " + str(transfer.get("id", i + 1))
            a = self.resolve(fr.get("exit"), fr.get("universe"), context + " / from")
            b = self.resolve(to.get("entry"), to.get("universe"), context + " / to")
            mechanism = transfer.get("mechanism")
            badge, color = MECHANISMS.get(mechanism, UNKNOWN_MECHANISM)
            literal = mechanism if mechanism is not None else "unspecified"
            # No aliasing: time_travel is not silently mapped to body.
            label = badge + " · " + str(literal)
            geometry = self.connector(s, a, b, label, color, record, "transfers",
                                      width=2.5, tooltip=pretty(transfer))
            if geometry and self.tmap.get(transfer.get("id")) is transfer:
                self.transfer_geometry[transfer["id"]] = (a, b, geometry)

    def draw_route(self, s):
        if not self.route:
            return
        record = self.rec("route")
        visits = arr(self.route.get("visits"))
        visit_map, duplicates = unique_index(visits)
        for duplicate in duplicates:
            self.note("Route: duplicate visit ID {!r}; links to it are ambiguous.".format(duplicate))
        slots = Counter()
        for i, value in enumerate(visits):
            v = obj(value)
            context = "Route visit " + str(v.get("id", i + 1))
            world = v.get("universe")
            passed = v.get("passes", [])
            if not isinstance(passed, list):
                self.note(context + ": passes is opaque; retained in the index.")
                passed = []
            # Unknown pass shapes break, rather than silently bypass, the path.
            refs = [v.get("entry")] + passed + [v.get("exit")]
            pts = [self.resolve(ref, world, context) for ref in refs]
            slot_key = world if isinstance(world, str) else ""
            offset = 26 + slots[slot_key] * 14
            slots[slot_key] += 1

            s.start("g", **{"class": "layer-route"})
            s.link(record.anchor, pretty(value))
            for a, b in zip(pts, pts[1:]):
                if a is None or b is None:
                    continue
                shifted_a = (a[0], a[1] + offset)
                shifted_b = (b[0], b[1] + offset)
                s.line(*shifted_a, *shifted_b, WHITE, 7)
                s.line(*shifted_a, *shifted_b, GOLD, 3,
                       marker_end="url(#{})".format(marker_id(GOLD)))
            for p in (pts[0], pts[-1]):
                if p:
                    s.line(p[0], p[1] + 11, p[0], p[1] + offset, GOLD, 1.1,
                           stroke_dasharray="2 3")
            first = next((p for p in pts if p is not None), None)
            if first:
                pill(s, first[0] - 21, first[1] + offset - 10,
                     "R" + str(i + 1), GOLD, 40, background="#fff8e8")
            s.end("a")
            s.end()
            if visit_map.get(v.get("id")) is v:
                self.visit_geometry[v["id"]] = (pts[0], pts[-1])

        for i, value in enumerate(arr(self.route.get("links"))):
            link = obj(value)
            context = "Route link {}".format(i + 1)
            fr, to = link.get("from"), link.get("to")
            if not isinstance(fr, str) or not isinstance(to, str):
                self.note(context + ": unsupported visit reference shape; retained in the index.")
                continue
            source = self.visit_geometry.get(fr)
            target = self.visit_geometry.get(to)
            if source is None or target is None:
                self.note(context + ": missing or ambiguous visit reference.")
                continue
            a, b = source[1], target[0]
            if "via" in link:
                via = link["via"]
                declared = self.transfer_geometry.get(via) if isinstance(via, str) else None
                if declared is None:
                    self.note(context + ": via transfer is missing, ambiguous or unplaceable.")
                    continue
                ta, tb, geometry = declared
                if a != ta or b != tb:
                    self.note(context + ": via transfer endpoints disagree with visit endpoints; "
                              "no replacement connection inferred.")
                    continue
                # Follow only the explicitly referenced transfer, as a separate
                # dashed overlay. The transfer's literal mechanism stays visible.
                d, mid = geometry
                s.start("g", **{"class": "layer-route"})
                s.link(record.anchor, pretty(link))
                s.element("path", d=d, fill="none", stroke=GOLD,
                          stroke_width=5.5, stroke_dasharray="2 9", opacity=".9")
                pill(s, mid[0] - 15, mid[1] + 16, "R", GOLD, 30,
                     background="#fff8e8")
                s.end("a")
                s.end()
            else:
                self.connector(
                    s, a, b, "R · " + str(link.get("kind", "link")),
                    GOLD, record, "route", dashed=True, width=2.5,
                    tooltip=pretty(link)
                )

    def draw_events(self, s):
        for i, event in enumerate(self.events):
            p = self.event_positions.get(i)
            if p is None:
                continue
            x, y = p
            record = self.rec("events", i)
            color = WORLD_COLORS[self.wrow[event["universe"]] % len(WORLD_COLORS)]
            kind = event["kind"]
            s.link(record.anchor, pretty(event))
            # Label plates preserve readability where relations cross labels.
            lines = snippet(event["label"], 22, 2)
            box_y = y - 76
            s.rect(x - 68, box_y, 136, 62, PAPER, 7, opacity=".96")
            s.text(x, box_y + 16, record.code + " · " + kind, 10, color,
                   text_anchor="middle", font_weight="700")
            s.lines(x, box_y + 33, lines, 10, 14,
                    fill=INK, text_anchor="middle")
            s.element("circle", cx=x, cy=y, r=12, fill=WHITE,
                      stroke=color, stroke_width=2, **{"class": "event-hit"})
            if kind == "split":
                s.element("path", d="M {},{} l 6,6 -6,6 -6,-6 Z".format(x, y - 6),
                          fill=color)
            elif kind in ("entry", "gate_entry"):
                s.element("path", d="M {},{} l 8,5 -8,5 Z".format(x - 4, y - 5),
                          fill=color)
            elif kind in ("exit", "gate_exit"):
                s.element("path", d="M {},{} l -8,5 8,5".format(x + 4, y - 5),
                          fill="none", stroke=color, stroke_width=2)
            elif kind == "cutoff":
                s.line(x - 4, y - 5, x - 4, y + 5, color, 2)
                s.line(x + 4, y - 5, x + 4, y + 5, color, 2)
            elif kind == "anchor":
                s.element("path", d="M {},{} l 6,6 -6,6 -6,-6 Z".format(x, y - 6),
                          fill="none", stroke=color, stroke_width=1.5)
            else:
                s.element("circle", cx=x, cy=y, r=4, fill=color)
            s.end("a")

            cite = obj(event.get("cite"))
            if cite:
                source = self.a.source(cite.get("source"))
                target = source.anchor if source else record.anchor
                s.link(target, "Citation as declared:\n" + pretty(cite))
                s.text(x + 18, y + 4, "§", 16,
                       GOLD if cite.get("status") == "unavailable" else MUTED)
                s.end("a")
                if "source" in cite and source is None:
                    self.note("Event {!r}: citation source {!r} is missing or ambiguous."
                              .format(event["id"], cite["source"]))

    def draw_beats(self, s):
        occupied = Counter()
        for i, value in enumerate(self.beats):
            beat = obj(value)
            segment_id = beat.get("segment")
            segment = self.smap.get(segment_id) if isinstance(segment_id, str) else None
            world = obj(segment).get("universe", beat.get("universe"))
            order = beat.get("order")
            record = self.rec("beats", i)
            if world not in self.wrow or not numeric(order):
                self.note("Beat {}: no supported world/order placement; retained in the index."
                          .format(beat.get("id", i + 1)))
                continue
            offset = occupied[(world, order)] * 23
            occupied[(world, order)] += 1
            y = self.row_height * (self.wrow[world] + .5)
            x, yy = self.project(self.columns[order], y)
            yy += 79 + offset
            s.start("g", **{"class": "layer-annotations"})
            s.link(record.anchor, pretty(value))
            pill(s, x - 32, yy - 12, "◇ " + record.code, "#60787d", 64)
            s.end("a")
            s.end()

    def draw_fates(self, s):
        slots = Counter()
        for i, fate in enumerate(self.fates):
            record = self.rec("fates", i)
            context = "Fate " + str(fate.get("id", i + 1))
            p = self.resolve(fate.get("event"), fate.get("universe"), context)
            if p is None:
                continue
            symbol, color = STATUS[fate["status"]]
            offset = slots[fate.get("event")] * 24
            slots[fate.get("event")] += 1
            label = "{} {} · {}".format(symbol, fate["status"], record.code)
            width = len(label) * 6.5 + 16
            s.start("g", **{"class": "layer-annotations"})
            s.link(record.anchor, pretty(fate))
            pill(s, p[0] - width / 2, p[1] + 104 + offset,
                 label, color, width)
            s.end("a")
            s.end()

    def render(self):
        return self.body


def validate(model):
    """Structural guardrails, deliberately not a full JSON Schema validator."""
    if not isinstance(model, dict):
        raise ValueError("The JSON root must be an object.")
    if model.get("abstract_model") != "universe-timeline/1.0":
        raise ValueError("abstract_model must be 'universe-timeline/1.0'.")
    if not isinstance(model.get("title"), str):
        raise ValueError("title must be a string.")
    graphs = model.get("graphs")
    if not isinstance(graphs, list) or not graphs:
        raise ValueError("graphs must be a nonempty array.")

    def string_fields(value, fields, context):
        if not isinstance(value, dict):
            raise ValueError(context + " must be an object.")
        for field in fields:
            if not isinstance(value.get(field), str):
                raise ValueError(context + "." + field + " must be a string.")

    for gi, graph in enumerate(graphs):
        context = "graphs[{}]".format(gi)
        string_fields(graph, ["namespace"], context)
        if not isinstance(graph.get("worlds"), list):
            raise ValueError(context + ".worlds must be an array.")
        for name in ("events", "segments", "beats", "splits", "transfers",
                     "fates", "assumptions", "evidence"):
            if name in graph and not isinstance(graph[name], list):
                raise ValueError(context + "." + name + " must be an array.")
        if "route" in graph and not isinstance(graph["route"], dict):
            raise ValueError(context + ".route must be an object.")
        for wi, world in enumerate(graph["worlds"]):
            wc = context + ".worlds[{}]".format(wi)
            string_fields(world, ["id", "label", "origin"], wc)
            if world["origin"] not in ("initial", "born", "preexisting", "unknown"):
                raise ValueError(wc + ": unsupported origin.")
        for ei, event in enumerate(graph.get("events", [])):
            ec = context + ".events[{}]".format(ei)
            string_fields(event, ["id", "kind", "universe", "label"], ec)
            if event["kind"] not in KINDS:
                raise ValueError(ec + ": unsupported event kind.")
            if "order" not in event or not (
                event["order"] is None or
                isinstance(event["order"], int) and not isinstance(event["order"], bool)
            ):
                raise ValueError(ec + ".order must be an integer or null.")
        for si, split in enumerate(graph.get("splits", [])):
            sc = context + ".splits[{}]".format(si)
            string_fields(split, ["event"], sc)
            if not isinstance(split.get("outcomes"), dict):
                raise ValueError(sc + ".outcomes must be an object.")
        for ti, transfer in enumerate(graph.get("transfers", [])):
            tc = context + ".transfers[{}]".format(ti)
            string_fields(transfer, ["id", "traveller"], tc)
            if "mechanism" in transfer and not isinstance(transfer["mechanism"], str):
                raise ValueError(tc + ".mechanism must be a string.")
        for fi, fate in enumerate(graph.get("fates", [])):
            fc = context + ".fates[{}]".format(fi)
            string_fields(fate, ["id", "status"], fc)
            if fate["status"] not in STATUS:
                raise ValueError(fc + ": unsupported fate status.")


def make_html(svg, title):
    # Inline SVG: the companion has no network or file dependencies.
    svg = svg.split("\n", 1)[1] if svg.startswith("<?xml") else svg
    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Universe Atlas</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body { margin:0; color:#172c3c; background:#e6ebe7;
       font:13px system-ui,-apple-system,"Segoe UI",sans-serif; }
header { position:sticky; top:0; z-index:10; display:flex; flex-wrap:wrap;
         align-items:center; gap:10px; padding:12px 18px;
         color:#f6f5ef; background:#172c3cf5; box-shadow:0 3px 14px #172c3c25; }
header strong { margin-right:12px; letter-spacing:2px; font-size:11px; }
button, input[type=search] { border:1px solid #6d808b; border-radius:6px;
         background:#fff; color:#172c3c; padding:7px 10px; font:inherit; }
button { cursor:pointer; }
button:hover { background:#f3e9d1; }
button:focus-visible, input:focus-visible { outline:3px solid #eac87f; }
label { display:inline-flex; gap:4px; align-items:center; font-size:12px; }
.controls { display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
.divider { width:1px; height:24px; background:#536773; margin:0 4px; }
#viewport { overflow:auto; padding:20px; }
#art { margin:0 auto; width:max-content; }
#art svg { display:block; box-shadow:0 12px 45px #172c3c18; }
#zoom-label { min-width:43px; text-align:center; font-variant-numeric:tabular-nums; }
#status { color:#d3dedf; font-size:12px; }
.hint { margin:0; padding:10px 20px; color:#566c77; }
@media print {
  header, .hint { display:none; }
  #viewport { padding:0; overflow:visible; }
  #art { width:100%; }
  #art svg { width:100% !important; height:auto !important; box-shadow:none; }
}
</style>
</head>
<body>
<header>
<strong>UNIVERSE ATLAS</strong>
<div class="controls">
<button id="out" aria-label="Zoom out">−</button>
<span id="zoom-label">100%</span>
<button id="in" aria-label="Zoom in">+</button>
<button id="fit">Fit width</button>
<button id="actual">100%</button>
</div>
<span class="divider"></span>
<label><input type="checkbox" data-layer="splits" checked> Splits</label>
<label><input type="checkbox" data-layer="transfers" checked> Transfers</label>
<label><input type="checkbox" data-layer="route" checked> Route</label>
<label><input type="checkbox" data-layer="annotations" checked> Annotations</label>
<span class="divider"></span>
<form id="search-form" class="controls">
<input id="search" type="search" placeholder="Search complete records"
       aria-label="Search complete records">
<button>Find next</button>
</form>
<button id="download">Download SVG</button>
<span id="status" role="status" aria-live="polite"></span>
</header>
<p class="hint">Scroll to explore. Hover for original values; click numbered items for full records.
The SVG is embedded here and works offline. Search finds values in the record index.</p>
<main id="viewport"><div id="art">__SVG__</div></main>
<script>
(() => {
  "use strict";
  const svg = document.querySelector("#art svg");
  const viewport = document.getElementById("viewport");
  const box = svg.viewBox.baseVal;
  const naturalWidth = box.width, naturalHeight = box.height;
  const status = document.getElementById("status");
  let zoom = 1, lastQuery = "", matchIndex = -1;
  function setZoom(value) {
    zoom = Math.max(.015, Math.min(3, value));
    svg.style.width = (naturalWidth * zoom) + "px";
    svg.style.height = (naturalHeight * zoom) + "px";
    document.getElementById("zoom-label").textContent = Math.round(zoom * 100) + "%";
  }
  function fit() { setZoom((viewport.clientWidth - 42) / naturalWidth); }
  document.getElementById("in").onclick = () => setZoom(zoom * 1.25);
  document.getElementById("out").onclick = () => setZoom(zoom / 1.25);
  document.getElementById("fit").onclick = fit;
  document.getElementById("actual").onclick = () => setZoom(1);
  document.querySelectorAll("[data-layer]").forEach(input => {
    input.addEventListener("change", () => {
      svg.classList.toggle("hide-" + input.dataset.layer, !input.checked);
    });
  });
  document.getElementById("search-form").addEventListener("submit", event => {
    event.preventDefault();
    const query = document.getElementById("search").value.trim().toLowerCase();
    document.querySelectorAll(".search-hit").forEach(n => n.classList.remove("search-hit"));
    if (!query) { status.textContent = ""; return; }
    const matches = Array.from(svg.querySelectorAll(".record"))
      .filter(n => n.textContent.toLowerCase().includes(query));
    if (query !== lastQuery) matchIndex = -1;
    lastQuery = query;
    if (!matches.length) { status.textContent = "No matching records"; return; }
    matchIndex = (matchIndex + 1) % matches.length;
    const target = matches[matchIndex];
    target.classList.add("search-hit");
    target.scrollIntoView({block:"center", inline:"center", behavior:"smooth"});
    status.textContent = (matchIndex + 1) + " / " + matches.length + " matching records";
  });
  svg.addEventListener("click", event => {
    const a = event.target.closest("a");
    if (!a) return;
    const href = a.getAttribute("href");
    if (!href || !href.startsWith("#")) return;
    const target = document.getElementById(href.slice(1));
    if (!target) return;
    event.preventDefault();
    svg.querySelectorAll(".search-hit").forEach(n => n.classList.remove("search-hit"));
    target.classList.add("search-hit");
    target.scrollIntoView({block:"center", inline:"center", behavior:"smooth"});
  });
  document.getElementById("download").onclick = () => {
    const clone = svg.cloneNode(true);
    clone.removeAttribute("style");
    clone.removeAttribute("class");
    clone.querySelectorAll(".search-hit").forEach(n => n.classList.remove("search-hit"));
    const text = '<?xml version="1.0" encoding="UTF-8"?>\\n' +
      new XMLSerializer().serializeToString(clone);
    const url = URL.createObjectURL(new Blob([text], {type:"image/svg+xml;charset=utf-8"}));
    const a = document.createElement("a");
    a.href = url; a.download = "universe-atlas.svg"; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  fit();
})();
</script>
</body>
</html>
"""
    # Replace SVG last so model text cannot act as a template placeholder.
    return template.replace("__TITLE__", html.escape(title)).replace("__SVG__", svg)


def reject_constant(value):
    raise ValueError("Non-finite JSON constant is not supported: " + value)


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key: " + repr(key))
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Render an abstract universe timeline as an offline SVG/HTML atlas.",
        epilog="Both companion files are written. --format selects the primary output."
    )
    parser.add_argument("input", type=Path, help="Input JSON model")
    parser.add_argument("-o", "--output", type=Path, default=Path("output.svg"),
                        help="Output basename or filename (default: output.svg)")
    parser.add_argument("--view", choices=("2d", "2.5d"), default="2d")
    parser.add_argument("--format", choices=("svg", "html"), default="svg")
    args = parser.parse_args()

    try:
        with args.input.open("r", encoding="utf-8-sig") as f:
            model = json.load(
                f, parse_constant=reject_constant,
                object_pairs_hook=reject_duplicate_keys
            )
        validate(model)
        atlas = Atlas(model, args.view)
        svg = atlas.render()
        companion = make_html(svg, model["title"])

        base = args.output
        if base.suffix.lower() in (".svg", ".html", ".htm"):
            base = base.with_suffix("")
        svg_path = Path(str(base) + ".svg")
        html_path = Path(str(base) + ".html")
        for path in (svg_path, html_path):
            if path.resolve() == args.input.resolve():
                raise ValueError("Output must not overwrite the input JSON.")
            path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg, encoding="utf-8")
        html_path.write_text(companion, encoding="utf-8")
        primary, secondary = (
            (svg_path, html_path) if args.format == "svg" else (html_path, svg_path)
        )
        print("Primary:   {}".format(primary))
        print("Companion: {}".format(secondary))
        print("View: {} | Complete records: {}".format(args.view, len(atlas.records)))
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        parser.exit(1, "render.py: error: {}\n".format(exc))


if __name__ == "__main__":
    main()