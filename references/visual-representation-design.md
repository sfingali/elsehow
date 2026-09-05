## 1. Recommendation: “Worlds and Thread”

**Primary: a 2D vertical timeline atlas.** Thin world rails describe the universe structure; a thicker traveller thread describes the experienced story. Event cards, fate badges, and evidence marks sit beside—not inside—the topology.

**Companion: a 2.5D layered atlas.** The same chart becomes shallow, separated world strips viewed obliquely. Depth separates identities; it never means “more real,” “later,” or “more probable.”

Both representations must answer three questions independently:
- **What world exists?** World rails and origin markers.
- **What moves between worlds?** Transfer connectors and traveller threads.
- **What happens to each instance?** Local fate badges.

The renderer owns layout, colour, camera, folding, and selection. None belongs in the abstract document.

## 2. Shared semantic rules

- Render the **expanded profile parameters**, not assumptions attached to film names.
- `+` and `-` identify split outcomes. They do **not** universally mean survivor/death, good/bad, or selected/unselected.
- Select the followed tine using `route.links` and visit `passes`; show death only where an instance outcome or fate asserts it.
- Arrival is not creation. Departure is not destruction. Character death is not universe death.
- A line crossing is not a relationship: only a marked endpoint or junction establishes connectivity.
- Explicit records determine topology; profile parameters constrain interpretation but do not manufacture missing events.
- Keep graph namespaces separate. Identical local IDs or character names do not justify shared lanes.

**“Never draw a reset” means never erase a modeled branch or mistake travel for world replacement.**
For `branching=branch`, all recorded branches remain represented after departure or death.
For explicit overwrite/revision/iteration profiles, show the declared replacement or repetition—but preserve its recorded history as an archive. Do not disguise these ontologies as coexisting branches.

## 3. 2D layout: the timeline atlas

- **Vertical axis:** story order, progressing downward.
- **Horizontal axis:** categorical world identity; distance has no temporal meaning.
- Use ordinal event bands, not proportional spacing: `order=80` is not eighty minutes.
- Equal orders share a band without implying physical simultaneity; `order=null` goes in an “Order unspecified” shelf.
- Place frequently connected worlds near each other; use a stable ID-based tie-breaker.
- Offer a WAIF-focused arrangement with U1 rightmost and the main route migrating left, but never force adjacency by duplicating worlds.
- Keep unvisited outcome worlds as narrow rails or expandable side branches, rather than omitting them.
- Repeat visits occupy the same world rail at different story positions.
- Place transfer elbows in inter-band gutters; reserve side gutters for labels and evidence.
- Add a fixed header with title, namespace, axis, interpretation summary, and evidence status.
- Add a bottom visit strip: `1 U1 → 2 J+ → 3 *2 → 4 J- → 5 *F`.
- Supply “Overview,” “Traveller focus,” and “Evidence” views without changing the underlying topology.

**World-time mode:** the current normalized event format provides story order, not usable world-time coordinates; the importer drops legacy `world_time`. Display “World-time data unavailable—showing story order” unless a documented semantic enrichment supplies those coordinates. Never derive dates from scene numbers.

## 4. 2D primitives: worlds and events

| Model element | Visual primitive |
|---|---|
| World | Thin neutral rail with persistent `id` and film-language label. |
| `origin=initial` | Square origin marker labelled “Initial in model,” not “Universe begins.” |
| `origin=born` | Rail starts at its declared birth junction; parent and tine remain traceable. No pre-birth rail. |
| `origin=preexisting` | Rail enters from the upper chart boundary through an open continuation mark; chip: “Already existed.” This is context, not a dated biography. |
| `origin=unknown` | Unattached origin marker containing `?`; first known event remains separate from origin. No invented parent. |
| `ancestry=off_chart` | Outward-facing ancestry tab labelled “Ancestry off-chart.” Preserve literal starred IDs, but do not use stars as the sole encoding. |
| `start` | Small filled square: start of represented action. |
| `split` | Amber circle with event ID or short label; scene number appears separately as evidence. |
| `outcome` | Small tine-labelled node with `universe_outcome` annotation. |
| `entry` / `exit` | Inward/outward arrow-notch at the exact endpoint. |
| `anchor` | Diamond pin for a referenced story anchor, not a fork. |
| `cutoff` | Transverse bracket and “Chart stops here” card; does not assert world termination. |
| `gate_entry` / `gate_exit` | Portal-shaped brackets with entry/exit labels; connect only when a relationship is supplied. |
| Segment | Labelled bracket alongside its world rail between referenced endpoints. |
| Beat | Compact annotation card attached to its segment, placed by supplied order. |

`born.parent`, `born.event`, and split outcomes should agree. If they do not, mark a conflict rather than silently choosing one.

## 5. 2D primitives: splits, transfers, route, fates

**Splits**
- Draw thin structural edges from the split node to every supplied outcome; mark each edge `+` or `-`.
- A same-world outcome continues the existing rail. A born-world outcome begins a distinct rail.
- Annotate `cause`, `automatic`, `traveller`, and `source_disposition` in the split card.
- `source_disposition=ancestry_prefix` ends the parent’s identity prefix at the fork; label it “Ancestry,” not “Dead.”
- Attach `outcomes.instances` as instance-specific cards; retain free-text outcome/fate descriptions without guessing enum equivalents.
- A compact death branch ends its **displayed detail**, with an explicit continuation/unknown-state tab; it is not a terminated universe.

**Transfers**
- Use directed, elbowed connectors between `from.exit` and `to.entry`, labelled with transfer ID and traveller.
- Mechanism badges: **B / Body**, **M / Memory**, **C / Consciousness**, **S / Signal**; always include a text key.
- Body transfer shows a solid capsule token; memory and consciousness show distinct lettered tokens, not moving bodies.
- Signal uses a pulse marker and a labelled signal edge; it does not imply bodily occupancy at the receiver.
- Recognize documented mechanism strings such as `consciousness_transfer`; preserve unfamiliar strings verbatim.
- Display `relation` in the connector inspector. Same-world transfers return to the same rail; transfers never merge rails.

**Route / thread**
- Overlay a strong coloured stroke along each visit and its explicitly linked transitions; number visits in array order.
- Keep the thin structural split visible beneath the selected route: **the world forks; the selected thread need not.**
- Use `passes` to highlight traversed tines without inventing additional transfers.
- Missing links produce labelled gaps, not guessed continuity; same-entry/exit visits become numbered point stops.
- If the model supplies only a signal connection, do not extend a body thread over it.
- Multiple travellers receive distinct colour-plus-label identities; no colour-only distinction.

**Fates**
- Attach badges to the named instance, world, and referenced event: `× Dead`, `● Alive`, `? Unknown`, `∅ Nonexistent`.
- “Alive” means alive at that record—not immortal thereafter. “Nonexistent” is not another style of death.
- If a fate references an event in another world, attach the badge to the fate’s world with an explicit event-reference leader.
- Missing instance metadata remains a literal instance ID; do not infer native bodies or counterpart identity from its spelling.

## 6. Evidence and remaining document elements

- Citations use small numbered evidence tabs; expanded cards show source title, page, scene, locator, and status.
- Keep story order, scene number, and page number typographically distinct: `Order 10 · Scene 10 · p.4`.
- `resolved` receives a plain evidence mark; unavailable/pending status gets an outlined mark and its actual status text.
- Missing citation means “No citation supplied,” not “False.” Citation resolution is not proof of interpretation.
- Show source kinds prominently: **test fixture** is not screenplay evidence.
- Deduplicate `evidence` entries that repeat event/beat/fate citations while retaining all record references.
- Put `assumptions` in a persistent “Interpretive assumptions” panel; do not draw them as additional topology.
- `characters` and `travellers` populate the identity key and filters; `namespaces` label graph tabs or small multiples.
- `title`, `subtitle`, and `footer` become the heading, context line, and chart note.
- `merges` is only a count in this model: show the count, never fabricated merge locations or edges.
- `segments`, `beats`, route records, and evidence arrays have loose schemas. Render recognized documented fields; expose unsupported content in the inspector.
- The importer drops legacy instance definitions and graph links. The renderer must not reconstruct those relationships from film knowledge.

## 7. How profile parameters change both views

| Parameter | Visible consequence |
|---|---|
| `history_model=universes` | Distinct identity rails/strips; coexistence separately labelled. |
| `history_model=revisions` | Revision ledger within the modeled world identity; supplied superseded states remain labelled archive sections, not parallel universes. |
| `history_model=iterations` | One world rail with sequential repeat bands where repetition is explicitly recorded; never one universe per loop. |
| `branching=branch` | Preserve structural forks and their outcomes. |
| `branching=overwrite` | Use “Supersedes” transitions where supported; retain prior recorded states in the archive. |
| `branching=undeclared` | Neutral relationship labels; no branch or overwrite symbolism without explicit records. |
| `coexistence=coexisting` | Equal-status world rails; no “active universe” implied by traveller focus. |
| `coexistence=single_active` | Active/archive indicators where activation is known. If it is not known, state that instead of choosing. |
| `coexistence=undeclared` | Header says “Coexistence unspecified”; layout separation alone makes no claim. |
| `joined_worlds` | Interpretation chip governing arrival reading; explicit origin records determine individual origin marks. Flag conflicts. |
| `time_mechanics` | Allowed-mechanism legend; each actual transfer still uses its own mechanism. |
| `turnstiles` | Enable gate vocabulary and declared sign labels. “Both signs” does not create missing gate pairs or inverted strands. |
| `protagonist_scope` | Singular focus or multi-traveller key/small multiples; render only routes actually supplied. |
| `genealogy=bootstrap_cycles` | Enable a separate causal/genealogical inset for explicit relationships; a profile flag alone yields a note, not a self-loop. |
| `axis` | Explicit story-order/world-time axis treatment; disclose unavailable world-time data. |
| `validation` | Interpretation-status banner, independent of individual citation badges. |
| `merges` | Forbidden: flag contradictions. Apparent reset: label appearance without fusion. Siblings: permit explicit supported relationships, not inferred ones. |

Preset name and `rules` appear as metadata beside these resolved semantics, not as hidden rendering switches.

## 8. 2.5D variant: the layered atlas

Use a shallow orthographic/isometric camera: approximately 25–35° tilt, restrained shadows, no vanishing-point distortion.

- **Long axis:** story order, from the labelled far edge toward the near edge.
- **Across axis:** categorical world positions inherited from the 2D layout.
- **Depth/height:** layout separation only; explicitly labelled “Exploded view—not another time axis.”
- Each world rail becomes a narrow matte strip with its ID on the leading edge.
- Initial origins are square strip headers; born strips start at fork seams; preexisting strips enter from beyond the scene boundary; unknown origins have freestanding `?` tabs.
- Structural split edges become flat bridges labelled `+` and `-`; a bridge is a relationship, not a shared slab of universe.
- Transfers become elevated cables with arrowheads and B/M/C/S tokens. Cable endpoints visibly touch the relevant event anchors.
- The traveller thread becomes a raised ribbon, flush with occupied strips and following the corresponding transfer cable.
- Fate badges remain small upright flags attached to instances; death never breaks the world platform.
- Event nodes become shallow pins; segment labels run along strip margins; beat cards use screen-facing callouts.
- Citation tabs remain screen-facing and readable, not embossed into perspective surfaces.
- Keep all profile effects from Section 7. Revisions use labelled archive leaves; iterations use repeat bands on one strip.
- Archive leaves must say “Superseded record—not coexisting world”; depth cannot supply that meaning by itself.
- Separate graph namespaces into distinct scene trays, with no connecting cables unless explicit cross-graph semantics become available.

Allow bounded orbit, strip separation, isolation, and a one-click return to the exact 2D atlas.
Use cutaways or separation to reveal hidden connectors; never let occlusion hide a tine, fate, or destination.
Animation moves tokens through visits, not worlds backward through time. Existing branches remain present.

## 9. Concrete scene: THE WAIF

- BEN opens with eight world identities: five route worlds and three compact, expandable outcome worlds.
- At J, U1’s ancestry prefix forks into J+ and J−. **J− remains available for Ben’s later arrival.**
- The local `ben-jm-native` death badge does not terminate J− or identify the later visitor as that dead instance.
- T, M, and C show same-world `+` continuations and separate born `−` outcomes.
- The green Ben thread follows `U1 → J+ → *2 → J− → *F`; three transfers carry Consciousness badges.
- *2 and *F enter from the chart boundary as preexisting; neither begins at Ben’s arrival.
- Source-world rails remain visible after departure, with recorded continuation distinguished from unspecified future detail.
- *F ends the displayed route at `e-end`, with `Scene 277 · p.117`; implied abuse stays an assumption, not a new event.
- W occupies a separate panel/tray with its two transfers and unknown local fate. Its final zero-length visit is a point stop.

In 2.5D, this becomes five prominent strips, three narrow outcome strips, and a green ribbon crossing between them—not a branching ribbon of multiple Bens.

## 10. Hard-case behaviour

- **Verse-jumping / many protagonists:** share world identities, separate traveller threads, filter by traveller, and offer synchronized small multiples. Do not create worlds per visit.
- **Bootstrap self-cycles:** retain forward story-order reading; show explicitly supplied causal cycles in a labelled inset. Causal closure is not world fusion.
- **Revisions:** one-world corpus entries stay one world. Named revision states appear only when supported by records; profile metadata alone cannot supply their sequence.
- **Iteration loops:** show recorded repetitions as stacked story bands, with reset-trigger and memory-carryover annotations only when supplied. Compress counts only when known.
- **Sparse fixtures:** Interstellar or Predestination may have no explicit transfer/cycle edges. Show recorded events plus ontology notes—not familiar movie diagrams invented by the renderer.

## 11. Exports and interaction

- **SVG:** primary master for the 2D atlas; searchable text, semantic groups, stable record IDs.
- **PNG:** print/poster/deck output with a complete legend and evidence appendix when needed.
- **HTML:** zoom, filters, folded branches, synchronized 2D/2.5D selection, and keyboard-accessible inspectors.
- **Graphviz:** topology-first fallback with namespace clusters and distinct structural/transfer edges.
- **Mermaid:** simplified relationship or flowchart export; disclose that precise lane positioning and layered overlays are reduced.
- **Video:** narrated traveller traversal with persistent worlds and readable stop-frame citations.
- **2.5D stills:** PNG or projected SVG; interactive depth through an HTML graphics consumer.
- Every visual export includes an accessible event/route ledger. Selection and camera state live in renderer-side settings.

## 12. Five pitfalls to avoid

1. **Conflating world, traveller, and instance:** a dead counterpart must not erase a world or stop a different traveller.
2. **Treating `−` as death or `+` as the route:** outcomes, fates, and selected traversal are separate facts.
3. **Inventing chronology or topology:** no guessed world-time axis, revision sequence, gate pair, merge, or bootstrap edge.
4. **Making depth or fading semantic by accident:** distance is not time; dimming is not nonexistence; overlap is not merging.
5. **Applying WAIF conventions universally:** preserve its clear thread-and-world distinction, but let explicit profile parameters govern branches, revisions, iterations, and signals.