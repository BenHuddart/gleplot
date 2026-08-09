# G17 — guide emission: literal datasets vs engine-range awareness

**Status: IMPLEMENTED. Candidate 1a (§3) was approved and is what this branch
now ships** — `src/gleplot/guides.py` (the four `gleplot_*line`/`*span` subs
and the layer constants), the write-time routing in
`Axes.guide_needs_engine_range` / `Figure._write_axes_content`, the two
emission methods on `GLEWriter`, and the call-site recogniser at
`_try_guide_layer_block`. The measurements below stand as recorded; §1.1's
"before" numbers are re-measured against the live engine, alongside the "after"
ones, in `tests/integration/test_guide_draw_form_compiles.py`.

Two details settled during implementation that the evaluation had not:

* **Colours travel as strings.** `draw s orange` passes the *variable* `orange`
  (undefined -> 0 -> black): a GLE colour name is a parser-level constant, not
  a value a sub parameter can carry. The subs take `clr$` and convert with
  GLE's `cvtcolor()`, which handles names and colour expressions alike —
  `cvtcolor("rgba255(255,0,0,128)")` renders pixel-identically to the literal
  form under `-cairo`.
* **Recognition also requires the canonical layer number.** A gleplot-authored
  block whose layer someone edited to change the z-order stays passthrough and
  is re-emitted verbatim, rather than being recognized and then silently
  written back at 349/699.

The rest of this note is the original evaluation, unchanged.

Everything numeric here was measured against the installed engine, GLE
4.3.10 (`/usr/local/bin/gle`). Probe scripts are inlined so the measurements
are reproducible without this branch.

## 1. The root cause

`Axes.materialize_reflines` / `materialize_spans` (`src/gleplot/axes.py`)
turn a `RefLine`/`Span` *declaration* into a concrete two-point
`LineSeries`/`FillSeries` at write time. The writer then emits it as an
ordinary `data <file> dN=c1,c2` + `dN line` (or `fill dA,dB`) pair, backed by
a real `.dat` sidecar. The guide's extent along the axis it crosses is
therefore frozen, in literal data coordinates, into the script — *before* GLE
has decided anything.

Two consequences, both ledgered:

* **(a) A guide across a deferred axis spans the wrong band.** When G15
  (`Figure._defer_degenerate_range`) hands a collapsed range back to the
  engine, gleplot no longer has a range to measure the guide's fractional
  extent against, so `Axes._spanned_range` substitutes G14's
  `EMPTY_AXIS_FALLBACK_RANGE` (0..1). GLE then picks something else.
* **(b) The writer→parse→writer fixed point breaks for a lone guide on an
  empty axes.** The materialized dataset re-parses as an ordinary series,
  its bounds feed autoscale, and the second write emits a range the first
  did not. Pinned by
  `test_a_materialized_guide_still_costs_the_round_trip_its_fixed_point`.

There is a third, unledgered consequence worth recording, because it makes
(a) strictly worse than the docstring in `_spanned_range` says: **the
materialized dataset also perturbs the range GLE chooses.** The guide is not
merely measured against the wrong range — it helps create it.

### 1.1 Residual (a), measured

Figure: `ax.plot([5.0], [7.0])` + `ax.axvline(5.0, ymin=0.0, ymax=1.0)`
(y collapses to 7..7 → deferred; the guide declares the *full* frame height).

Current emission (verbatim, `dg` prefix):

```
begin graph
    size 7.83196 5.71524
    scale 1 1
    data dg_1.dat d1=c1,c2          ! the guide: "x y\n5 0\n5 1\n"
    d1 line color BLACK lwidth 0.05292 key ""
    data dg_0.dat d2=c1,c2          ! the datum: "x y\n5 7\n"
    d2 line color BLUE lwidth 0.05292 key ""
end graph
```

Appending `print "..."+num$(ygmin)+...` and compiling:

| quantity | current emission | correct answer |
| --- | --- | --- |
| engine y range | `ygmin=0 ygmax=7` | `0 .. 12` |
| frame bottom / top | 1.26984 / 6.98508 cm | same |
| guide top (`yg(1)`) | 2.0863 cm | 6.98508 cm |
| **fraction of frame covered** | **14.3 %** | **100 %** |

The engine range is 0..7 rather than the 0..12 GLE picks for the lone point
(5, 7) *precisely because* the guide's own `0`/`1` rows joined the autoscale.
So the guide covers 14.3 % of the frame it declared 100 % of.

Note that gleplot's *own* limit computation already excludes the fractional
extent from autoscale on purpose (`figure._refline_axis_values`: "the extent
along the other axis is an axes fraction, so feeding it back into autoscale
would be circular"). The literal-dataset emission reintroduces exactly that
circularity inside the engine, where gleplot cannot see it.

## 2. Engine probes

### 2.1 `draw` inside a graph block sees the engine-chosen range

`graph/graph.tex:515` of the manual: *"Executes subroutine `call` while
drawing the graph. The call is drawn in the current layer. The output is
clipped to the graph window and the subroutine can use the functions `xg()`,
`yg()`, and variables `xgmin`, `ygmin`, etc."*

```gle
size 10 8
sub guide
   print "GUIDE xgmin="+num$(xgmin)+" xgmax="+num$(xgmax)+" ygmin="+num$(ygmin)+" ygmax="+num$(ygmax)
   set color red lwidth 0.05
   amove xg(5) yg(ygmin)
   aline xg(5) yg(ygmax)
end sub
amove 1 1
begin graph
   size 8 6
   scale 1 1
   data "one.dat"     ! a single row: "5 7"
   d1 marker circle
   draw guide
end graph
```

→ `GUIDE xgmin=0 xgmax=10 ygmin=0 ygmax=12`.

That is GLE's nice-number expansion of the lone point, **available to the
guide, inside the block, after the range is fixed**. Residual (a) is fixed by
construction: the guide is drawn in the range the reader sees, and it
contributes nothing to choosing that range.

On an axes with no data at all the same probe reports `0 .. 1` on both axes —
the value G14 already hard-codes as `EMPTY_AXIS_FALLBACK_RANGE`, so the
fallback constant becomes a *derivation* rather than a coincidence.

### 2.2 Per-graph, not per-file

Two stacked graph blocks calling one parameterised sub:

```
TOP xgmin=0  xgmax=3  ygmin=0   ygmax=9
BOT xgmin=10 xgmax=20 ygmin=100 ygmax=200
```

Each block's `draw` sees its own range. Subplot grids are safe.

### 2.3 Z-order is exactly reproducible

`src/gle/graph.h:49-57` fixes the default layers:

```
GRID 200   FILL 350   BAR 350   AXIS 500   LINE 700   ERROR_BAR 700
MARKER 700   DRAW_COMMAND 700
```

Layers draw low→high; within a layer the order is by element type, with
**draw commands last**. So a bare `draw` would land on top of everything —
*not* today's stacking. `begin layer N` fixes it. Probing a graph with an
orange span-draw in `layer 349`, a red refline-draw in `layer 699` and a blue
data line, and reading the generated PostScript in order:

```
50:  1 0.647059 0 setrgbcolor    ! orange span   (layer 349, below fills/axis)
504: 1 0 0 setrgbcolor           ! red refline   (layer 699, above axis)
522: 0 0 1 setrgbcolor           ! blue data line
```

which is today's order (spans in the background layer, reflines above the
axis but below data). Layer choice is a pure emission constant; no
approximation involved.

### 2.4 The legend gap has a clean bridge

A `draw` command owns no dataset, so it cannot carry `key "…"`, and gleplot
emits guide labels today as `dN … key "threshold"` inside the graph's own
auto-key. A standalone `begin key` block after the graph *works* but draws a
**second, overlapping key box** — not acceptable.

The bridge: GLE accepts a `dN` line that declares style and key and is never
given any data.

```gle
begin graph
   data "d.dat" d1=c1,c2
   d1 line color blue key "data"
   d5 line color red lstyle 3 key "threshold"   ! no data, no let
   key pos tr
end graph
```

Compiles clean; `pdftotext` shows both `data` and `threshold` in the key, in
order; the printed range is unchanged (`0..3`, `0..9`), i.e. the empty
dataset contributes **no ink and no autoscale**. So a labelled guide keeps
its legend entry with a one-line, data-free `dN` declaration alongside its
`draw` call.

### 2.5 Miscellaneous confirmations

* A `sub` may be defined **after** the block that calls it (GLE hoists).
* Subs take positional parameters (`draw gleplot_vline 5 0 1 …`).
* `gsave` / `set color/lstyle/lwidth` / `grestore` inside the sub work and do
  not leak.
* `box … fill rgba255(r,g,b,a)` compiles under `-cairo`, matching how
  `Span` alpha is already emitted (`fill dA,dB color rgba255(255,165,0,89)`).
* `let dN = <expr>` is **not** an alternative: it is evaluated *before* the
  range exists (`let d2 = ygmin` reads a stale value) and it *does* feed
  autoscale (`let d2 = 20` pushed `ygmax` to 20). It also cannot express a
  vertical guide at all, since `let` is `y = f(x)`.

### 2.6 The idiom already exists in gleplot

This is not a new emission concept for the repo:

* `src/gleplot/palettes.py` already emits self-contained `sub gleplot_…`
  blocks.
* `recognizer._scan_gleplot_sub_lines` already drops `sub gleplot_*` bodies
  wholesale and regenerates them from the model.
* `recognizer._consume_post_graph_calls` / `_try_one_post_call` already map
  `gleplot_colorbar_v` / `gleplot_contour_labels` **calls back into model
  state**, and `_amove_colorbar_sep` already regex-recovers a number out of
  an `xg(xgmax)+S yg(ygmin)` expression.

So "a `gleplot_*` sub plus a recognised call site carrying named arguments"
is an established, tested round-trip pattern here. A guide is the same shape.

### 2.7 Backward compatibility of the new form

Feeding the current recognizer a hand-written file in the proposed shape
(layer blocks + `draw gleplot_vline` + `sub gleplot_*` bodies) produces
**zero warnings** and preserves every line verbatim through passthrough; the
re-emitted file keeps the subs and the draw blocks (moved after the
recognized statements, which is z-order-neutral because the layers are
explicit). An older gleplot therefore does not silently drop a newer file's
guides — it keeps them as opaque content. That satisfies the "no silent
drops" rule for the cross-version direction.

## 3. Candidate evaluation

### Candidate 1 — emit guides as in-graph `draw` calls over `xgmin`/`ygmax`

Shape (sketch; the sub is emitted once per file, like the palette subs):

```gle
begin graph
    ...
    begin layer 349
       draw gleplot_vspan 0.5 1 0 1 LIGHTGRAY 1
    end layer
    begin layer 699
       draw gleplot_vline 1.5 0 1 RED 0.07056 3
    end layer
    d9 line color RED lstyle 3 lwidth 0.07056 key "threshold"   ! legend only
end graph
```

* **Residuals fixed:** (a) and (b), both, at the root.
* **Bonus:** guides survive `.gle` → model → `.gle` **as guides**. Today the
  recognizer has no guide recognition at all — every `axvline` opened in
  GLEstudio comes back as a plain `LineSeries`, silently losing its SPEC
  §14.3 identity, its fractional extent and its editability in the S5.2
  panel. Candidate 1 closes that too.
* **Recogniser safety:** recognition keys off the literal call name
  `gleplot_vline` / `gleplot_hline` / `gleplot_vspan` / `gleplot_hspan`.
  It is explicit, never inferred from shape, so a user's genuine two-point
  line can never be misclassified. (The reverse mistake — a user writing
  `draw gleplot_vline` by hand — is the same risk gleplot already accepts
  for `gleplot_colorbar_v`.)
* **Axis ranges do not change.** `figure._refline_axis_values` already feeds
  guide *data* coordinates into gleplot's own autoscale, so every
  `xaxis min … max …` line gleplot writes stays exactly what it is today.
  Only the deferred/unresolvable cases change, which is the point.
* **GLE syntax landmines:** the extent expression
  `ygmin+(ygmax-ygmin)*0.25` is space-free (verified compiling); no `bar`
  comma-lists involved; `draw` sits inside the graph block after `data`, and
  layer blocks are order-independent by construction.
* **Invariant risks:** none found on the engine side. The real cost is
  emission churn — see §4.

### Candidate 2 — a provenance marker on the materialized dataset

A structured comment (e.g. `! gleplot-guide: kind=vline value=1.5 …`) that
the recognizer maps back to a `RefLine`/`Span`.

* **Residuals fixed:** (b) only. (a) is untouched — the dataset is still
  literal, still materialized against a range gleplot does not have, and
  still perturbs the engine's choice (§1.1). Closing (a) still needs the
  range variables, i.e. candidate 1 anyway.
* **Also fixes** the model round-trip identity noted above.
* **Cost:** roughly the same recogniser work as candidate 1 and the same
  emission-churn problem (a new comment line per guide changes the bytes of
  every guide-bearing figure), for half the outcome. The one thing it buys
  that candidate 1 does not is that the *rendered* PDF stays bit-identical.
* **Verdict:** dominated by candidate 1 unless "rendered output must not
  move at all" turns out to be a hard requirement.

### Candidate 3 — accept (a) permanently, fix only (b)

Costs the same recogniser machinery as candidate 2 while leaving a measured
14.3 %-instead-of-100 % rendering error documented as intended behaviour.
Not recommended; the note in `_spanned_range` is already the documentation,
and it currently understates the problem (it does not mention that the
fallback dataset also moves the engine's range).

### Candidate 1a — candidate 1, but **only where today's emission is wrong**

This is the option that did not appear in the original framing, and it is the
one worth putting to the supervisor.

Route a guide through `draw` **iff a bound of the axis it spans is `None`**
at write time — i.e. exactly the branch where `_spanned_range` reaches for
the 0..1 fallback (G14's empty axes, G15's deferred range). Every guide whose
spanned axis resolves keeps the literal-dataset emission, byte for byte.

Blast radius, checked against the fixture batteries:

| oracle | contains guides? | affected by 1a? |
| --- | --- | --- |
| `tests/parser/_golden_battery.py` (wide digest sweep) | **no** | no |
| `tests/integration/test_project_io.py` (wide digest sweep) | **no** | no |
| `tests/unit/wide_battery_digests.json` (43 figures) | — | **no** |
| `tests/unit/refline_resolvable_emissions.json` (12 builders, pinned to pre-G14 83dcdd9) | yes, all resolvable by construction | **no** |
| `tests/unit/degenerate_neighbour_emissions.json` (`guides_over_data`) | yes, resolvable | **no** |
| `tests/unit/test_refline_fallback.py` cases at lines 73–132, 158 | the G14 fallback itself | **yes — these are the pinning tests to flip** |
| `test_degenerate_autoscale.py::test_a_guide_spanning_a_deferred_axis_falls_back_to_the_g14_range` | residual (a) | **yes — flip** |
| `test_degenerate_autoscale.py::test_a_materialized_guide_still_costs_the_round_trip_its_fixed_point` | residual (b) | **yes — flip** |

So candidate 1a fixes both residuals with **zero byte change to any figure
whose guides are currently emitted correctly**, and changes exactly the
figures whose current emission is the documented defect.

Its cost is a *second* guide emission form, chosen by write-time limit
resolution — so adding data to an axes silently switches a guide between the
two forms, and the model round-trip identity (§ candidate 1's bonus) is only
restored for the minority case. That asymmetry is a policy call, not an
implementation detail.

## 4. What kills the universal form today

Candidate 1 applied to *all* guides is a **breaking emission change to
shipped figures** (v2.7.0 is released):

1. Guide `.dat` sidecars stop being written, so the
   `! gleplot: import-data = …` metadata list changes for every guide-bearing
   file.
2. Guides stop consuming graph-block dataset indices, so every later series
   renumbers (`d5`/`d6` → gone, `d7` → `d1` in the
   `guides_over_data` fixture). (Sidecar *names* are unaffected: `data_file`
   is assigned at declaration time, not at write time.)
3. `refline_resolvable_emissions.json` — a battery that exists specifically
   to prove G14 changed nothing for resolvable figures — is invalidated in
   purpose, not just in data.
4. Downstream: GLEstudio's structure tree, S5.2 series panel, §6.2
   calibration instrumentation and §14.8 hit-target work all assume the
   current shape.

None of that is *unsafe*; it is simply a decision above this task's pay
grade, which is why this branch stops here.

## 5. Recommendation

1. **Schedule candidate 1a** (`draw`-based emission restricted to the
   unresolvable/deferred branch) as the G17 implementation. It closes both
   ledgered residuals, leaves every currently-correct figure byte-identical,
   and flips exactly the pinning tests G17 was created to flip. Estimated
   surface: `axes.py` (a descriptor beside the two `materialize_*`
   methods), `figure.py` (route the two branches), `writer.py` + a
   `gleplot_*` sub source, `recognizer.py` (one call-site recogniser beside
   `_try_one_post_call`), plus fixture and test churn across ~6 test
   modules. Test discipline: byte-identity fixtures unchanged (they must
   *stay* green untouched — that is the proof), fixed-point battery extended
   with the lone-guide case, `gle`-marked compile tests asserting the
   numeric frame fractions from §1.1 and §2.1, serialization-completeness if
   any field is added (none is expected — the emission stays a write-time
   decision, exactly as G15's deferral is).
2. **Then consider candidate 1 universal** as a deliberate, versioned
   emission migration at a minor/major bump, on the `metadata v1 → v2`
   precedent (one-time byte diff, warned on load). Its payoff is the guide
   *identity* round-trip — SPEC §14.3 guides currently degrade to plain
   lines on every open, which is a bigger gap than either ledgered residual.
   Recommend ledgering that separately rather than smuggling it into G17.
3. **Reject candidates 2 and 3.** Candidate 2 costs candidate 1's recogniser
   work for half its outcome; candidate 3 documents a measured 14.3 %
   rendering error as intended.
4. **Amend `_spanned_range`'s docstring** whenever G17 lands (or sooner, as a
   one-line docs fix): it says the guide "spans 0..1 rather than the rendered
   frame", which understates the defect — the fallback dataset also *moves*
   the frame GLE renders.

## 6. Postscript: G18-lite closed the identity gap the other way

Recommendation 2 above — the universal `draw` form, as a versioned emission
migration — was **not** taken. Ben's decision (2026-08-09) was **G18-lite**:
leave the dataset form's bytes exactly where they are and give it a
structured provenance **comment**, recognized on the literal marker:

```gle
    ! gleplot:guide refline v value 1.5 extent 0,1
    data rlb_1.dat d5=c1,c2
    d5 line color RED lwidth 0.07056 lstyle 3 key "threshold"
```

It buys recommendation 2's payoff — SPEC §14.3 identity survives re-import —
without any of §4's costs: sidecars are still written, dataset indices do not
renumber, downstream shapes are untouched, and the only fixture churn is the
added comment lines themselves (`test_the_g18_lite_marker_is_a_pure_insertion`
holds the writer to that). The two emission forms therefore both round-trip to
`RefLine`/`Span` now, keyed on a literal gleplot wrote — a sub name for the
draw form, a marker comment for the dataset form — and never on the shape of
the commands. See `gleplot/guides.py` for the marker grammar and for the rule
that decides what may live in it (the model residue only; anything a visible
command already states is read back from that command).

The form asymmetry itself (§3) stands, and G18-full stays ledgered.

**One defect found on the way, in G17's own recognizer, not fixed here.**
`_guide_call_args` reads a draw call's arguments with `_collect_value`, which
consumes a maximal expression — so two adjacent negative arguments merge:
`draw gleplot_vspan -4 -3 0 1 "LIGHTGRAY" ""` collects `-4 -3` as `-7`, yields
five arguments instead of six, and the block falls through to raw passthrough.
The *rendering* is correct (GLE splits sub-call arguments on whitespace itself
— probed on 4.3.10: `A=-4 B=-3 LO=0 HI=1`), so this costs identity, not ink,
and only for a band whose two coordinates are both negative. G18-lite's marker
sidesteps the same hazard by separating pairs with a comma, which is not a
value operator; the draw form would need a positional argument splitter.

**G17.1 fixed it with exactly that splitter.** `_split_call_words` groups a
`draw gleplot_*` call's tokens by the token *spans* the lexer already
records — a gap between two tokens starts a new argument, no gap keeps them
in the same one — instead of `_collect_value`'s expression grammar. That
mirrors GLE's own rule (whitespace splits sub-call arguments, full stop)
exactly: `-4 -3` lexes as `OP '-'` `NUMBER '4'` `OP '-'` `NUMBER '3'`, and the
one-space gap the writer always emits between arguments (`" ".join(args)` in
`GLEWriter._add_guide_draw`) falls exactly between the first pair and the
second, so they now split into two words. A spaceless expression like `2*pi`
or a signed literal like `-4` (`OP '-'` glued to `NUMBER '4'` with no gap)
still reads as one argument, because nothing in it has a gap either.
`_guide_call_args` now calls `_split_call_words` and evaluates each word
whole with `eval_gle_number` (numeric) or unwraps it if it is a single
`STRING` token (so an escaped quote or an embedded space in a color/label
string survives unchanged — nothing about string handling needed to move).

**No-silent-drops, extended to the recognizer's own near-misses.** Before
G17.1, three shapes that are recognizably gleplot's own — the call name has
gleplot's guide-sub prefix but isn't one of the four it writes, the call name
and arity match but the enclosing layer number was edited, or the arity
itself is wrong (this splitter fix included, since a still-mismatched arg
count is possible from hand-edited files) — degraded to raw passthrough with
no note at all, same as a genuinely foreign `draw` or a bare call with no
`layer` wrapper (which are *not* gleplot's to explain and correctly stay
silent). `_try_guide_layer_block` now emits a `structure:` `ImportNote` for
the first three cases, naming the call and what was wrong, matching the
"no silent drops" rule already applied to the G18-lite marker's own
tampering cases (§ above).

Fixed on branch `fix/g17-1-subcall-args`, tests in
`tests/unit/test_refline_fallback.py`: the documented `gleplot_vspan -4 -3`
case now recovers as a `Span`; the round-trip parametrization
(`test_a_drawn_guide_round_trips_as_a_guide`) gained an adjacent-negative
build for all four guide kinds (the refline cases force `span_lo` negative
directly on the model, since `axvline`/`axhline`'s public API clamps
`ymin`/`xmin` to `[0, 1]` and so can never reach this shape on its own); and
`test_a_degraded_gleplot_guide_block_is_never_silent` pins the `structure:`
note for each near-miss shape and its absence for the two shapes that stay
silent.
