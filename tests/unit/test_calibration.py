"""Unit tests for calibration record v2 (:mod:`gleplot.calibration`).

Everything here is Qt-free and GLE-free: injection is a text transform, the
parse layer is a text->records function, and the CTM guard runs on the parser.
The numeric invariants that can only be established by *compiling* live in
``tests/integration/test_calibration_v2_gle.py``.

The stderr fixtures reproduce what GLE 4.3.10 actually emits, ANSI prefix and
variable inter-field padding included -- see the module docstring of
:mod:`gleplot.calibration` for how those shapes were established.
"""

from __future__ import annotations

import math

import pytest

from gleplot.calibration import (
    BOX_MARKER,
    CAL_MARKER,
    TW_MARKER,
    AxesSpec,
    AxisMap,
    TextMetricRequest,
    block_name_for,
    build_text_metric_script,
    find_ctm_hazards,
    inject_text_metrics,
    instrument_script,
    parse_calibration_records,
    strip_ansi,
)
from gleplot.parser.syntax import parse_gle_source

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

#: A minimal two-graph script in the shape gleplot's writer emits: ``amove``
#: outside the block, ``size``/``scale 1 1`` as the block's first statements.
TWO_GRAPHS = """\
size 15 11
set hei 0.4

amove 1.5 1.2
begin graph
    size 5 4
    scale 1 1
    xaxis min 0 max 10
    yaxis min 0 max 20
end graph

amove 8.5 1.2
begin graph
    size 5 4
    scale 1 1
    xaxis min 1 max 100
    yaxis min 0 max 5
end graph
"""

#: One real ANSI-prefixed stderr line as GLE emits it (ESC[0m then the record,
#: with GLE's own variable padding between numeric fields).
ANSI = "\x1b[0m"


def cal_line(axes_id, values):
    """Render a ``glestudio-cal`` stderr line with GLE's spacing and prefix."""
    body = "   ".join(f"{v:g}" for v in values)
    return f"{ANSI}{CAL_MARKER} {axes_id}  {body}"


def box_line(axes_id, values):
    """Render a ``glestudio-box`` stderr line."""
    body = "   ".join(f"{v:g}" for v in values)
    return f"{ANSI}{BOX_MARKER} {axes_id}  {body}"


def tw_line(measure_id, values):
    """Render a ``glestudio-tw`` stderr line."""
    body = "   ".join(f"{v:g}" for v in values)
    return f"{ANSI}{TW_MARKER} {measure_id}  {body}"


#: The 12 numbers of a well-formed record: x, y, x2, y2 ranges then the four
#: frame-corner cm values ``xg(xgmin) yg(ygmin) xg(xgmax) yg(ygmax)``.
GOOD_VALUES = [0, 10, 0, 20, 100, 200, 0.5, 1.5, 1.5, 1.2, 6.5, 5.2]


# --------------------------------------------------------------------------- #
# ANSI stripping
# --------------------------------------------------------------------------- #


def test_strip_ansi_removes_gle_colour_codes():
    raw = "\x1b[0m\x1b[91m>> \x1b[94merr.gle\x1b[0m (\x1b[96m13\x1b[0m)"
    assert strip_ansi(raw) == ">> err.gle (13)"


# --------------------------------------------------------------------------- #
# Block naming
# --------------------------------------------------------------------------- #


def test_block_name_is_a_legal_gle_identifier_for_leading_digit_uuid():
    # GLE rejects an identifier starting with a digit; uuid4 hex often does.
    name = block_name_for("0a1b2c3d4e5f6789abcdef0123456789")
    assert name[0].isalpha()
    assert name.replace("_", "a").isalnum()


def test_block_name_sanitizes_illegal_characters():
    assert block_name_for("ab-cd.ef") == "glestudio_axab_cd_ef"


def test_block_name_resolves_collisions_against_taken_names():
    first = block_name_for("a-b")
    second = block_name_for("a.b", taken=[first])
    assert first != second
    assert second.startswith(first)


# --------------------------------------------------------------------------- #
# Injection
# --------------------------------------------------------------------------- #


def test_instrument_wraps_each_graph_and_prints_both_records():
    out = instrument_script(TWO_GRAPHS, ["idA", "idB"])
    assert out.warnings == []
    lines = out.text.splitlines()

    # Wrapper opens immediately before each ``begin graph`` and closes
    # immediately after each ``end graph``.
    for i, line in enumerate(lines):
        if line.strip() == "begin graph":
            assert lines[i - 1].strip().startswith("begin name glestudio_ax")
        if line.strip() == "end graph":
            assert lines[i + 1].strip() == "end name"

    assert sum(line.startswith(f'print "{CAL_MARKER}') for line in lines) == 2
    assert sum(line.startswith(f'print "{BOX_MARKER}') for line in lines) == 2
    assert f'print "{CAL_MARKER} idA "' in out.text
    assert f'print "{CAL_MARKER} idB "' in out.text


def test_instrumented_record_has_the_thirteen_normative_fields():
    out = instrument_script(TWO_GRAPHS, ["idA", "idB"])
    line = next(
        line
        for line in out.text.splitlines()
        if line.startswith(f'print "{CAL_MARKER}')
    )
    # SPEC 6.2 field order, in GLE variable names.
    for token in (
        "xgmin",
        "xgmax",
        "ygmin",
        "ygmax",
        "x2gmin",
        "x2gmax",
        "y2gmin",
        "y2gmax",
        "xg(xgmin)",
        "yg(ygmin)",
        "xg(xgmax)",
        "yg(ygmax)",
    ):
        assert token in line
    assert line.index("x2gmin") > line.index("ygmax")
    assert line.index("xg(xgmin)") > line.index("y2gmax")


def test_instrumentation_preserves_every_original_line_verbatim():
    out = instrument_script(TWO_GRAPHS, ["idA", "idB"])
    original = TWO_GRAPHS.splitlines()
    produced = out.text.splitlines()
    injected = {"begin name", "end name", 'print "glestudio'}
    kept = [
        line
        for line in produced
        if not any(line.strip().startswith(p) for p in injected)
    ]
    assert kept == original


def test_instrumentation_preserves_crlf_line_endings():
    out = instrument_script(TWO_GRAPHS.replace("\n", "\r\n"), ["idA", "idB"])
    assert "\r\n" in out.text
    assert "\n" not in out.text.replace("\r\n", "")


def test_instrumentation_is_a_noop_when_there_are_no_graph_blocks():
    src = "size 5 5\namove 1 1\nbox 2 2\n"
    out = instrument_script(src, [])
    assert out.text == src
    assert out.block_names == {}


def test_unclosed_graph_block_warns_and_is_skipped():
    out = instrument_script("size 5 5\nbegin graph\n    xaxis min 0 max 1\n", ["idA"])
    assert out.text == "size 5 5\nbegin graph\n    xaxis min 0 max 1\n"
    assert [w.category for w in out.warnings] == ["injection"]
    assert "never closed" in out.warnings[0].message


def test_missing_axes_id_degrades_to_positional_key_with_a_warning():
    out = instrument_script(TWO_GRAPHS, ["idA"])
    assert f'print "{CAL_MARKER} idA "' in out.text
    assert f'print "{CAL_MARKER} 1 "' in out.text
    assert any("positional index" in w.message for w in out.warnings)


def test_axes_id_with_whitespace_is_refused_not_silently_mangled():
    out = instrument_script(TWO_GRAPHS, ["id A", "idB"])
    assert "id A" not in out.text
    assert f'print "{CAL_MARKER} idB "' in out.text
    assert any(w.subject == "id A" for w in out.warnings)


def test_duplicate_axes_ids_instrument_only_the_first_block():
    out = instrument_script(TWO_GRAPHS, ["same", "same"])
    assert out.text.count(f'print "{CAL_MARKER} same "') == 1
    assert any("more than one graph" in w.message for w in out.warnings)


def test_instrument_accepts_an_already_parsed_document():
    doc = parse_gle_source(TWO_GRAPHS)
    out = instrument_script(doc, ["idA", "idB"])
    assert f'print "{CAL_MARKER} idA "' in out.text


# --------------------------------------------------------------------------- #
# Text metric injection
# --------------------------------------------------------------------------- #


def test_text_metrics_are_appended_with_font_state_scoped_by_gsave():
    out = inject_text_metrics(
        "size 5 5\n",
        [TextMetricRequest("m1", "Hello", font="psh", hei=0.35)],
    )
    lines = out.text.splitlines()
    assert lines[0] == "size 5 5"
    assert lines[1] == "gsave"
    assert "set font psh" in lines
    assert "set hei 0.35" in lines
    assert lines[-1] == "grestore"
    metric = next(line for line in lines if line.startswith(f'print "{TW_MARKER}'))
    assert 'twidth("Hello")' in metric
    assert 'theight("Hello")' in metric
    assert 'tdepth("Hello")' in metric


def test_text_metric_extra_state_is_emitted_verbatim_inside_the_scope():
    out = inject_text_metrics(
        "size 5 5\n",
        [TextMetricRequest("m1", "x", extra_state=("set just lc",))],
    )
    lines = out.text.splitlines()
    assert lines.index("set just lc") > lines.index("gsave")
    assert lines.index("set just lc") < lines.index("grestore")


def test_text_containing_a_double_quote_switches_to_single_quoting():
    out = inject_text_metrics("size 5 5\n", [TextMetricRequest("m1", 'say "hi"')])
    assert """twidth('say "hi"')""" in out.text
    assert out.warnings == []


def test_text_with_both_quote_characters_is_refused_with_a_warning():
    # GLE 4.3.10's doubled-"" escape is broken and aborts the whole script, so
    # emitting anything here would cost every other record in the compile.
    out = inject_text_metrics("size 5 5\n", [TextMetricRequest("m1", """a"b'c""")])
    assert TW_MARKER not in out.text
    assert [w.category for w in out.warnings] == ["injection"]
    assert out.warnings[0].subject == "m1"


def test_duplicate_measure_ids_emit_once_and_warn():
    out = inject_text_metrics(
        "size 5 5\n",
        [TextMetricRequest("m1", "a"), TextMetricRequest("m1", "b")],
    )
    assert out.text.count(f'print "{TW_MARKER} m1 "') == 1
    assert any(w.category == "injection" for w in out.warnings)


def test_measure_id_with_whitespace_is_refused():
    out = inject_text_metrics("size 5 5\n", [TextMetricRequest("m 1", "a")])
    assert TW_MARKER not in out.text
    assert out.warnings


def test_metric_injection_composes_with_calibration_injection():
    stage1 = instrument_script(TWO_GRAPHS, ["idA", "idB"])
    stage2 = inject_text_metrics(stage1.text, [TextMetricRequest("m1", "T")])
    assert stage2.text.startswith(stage1.text)
    assert f'print "{CAL_MARKER} idA "' in stage2.text
    assert f'print "{TW_MARKER} m1 "' in stage2.text


def test_standalone_metric_script_is_self_contained():
    out = build_text_metric_script(
        [TextMetricRequest("m1", "T", hei=0.3)],
        page_size_cm=(3.0, 2.0),
        preamble=["set font texcmr"],
    )
    lines = out.text.splitlines()
    assert lines[0] == "size 3 2"
    assert lines[1] == "set font texcmr"
    assert f'print "{TW_MARKER} m1 "' in out.text


# --------------------------------------------------------------------------- #
# Parse layer
# --------------------------------------------------------------------------- #


def test_parse_recovers_all_three_record_kinds():
    stream = "\n".join(
        [
            cal_line("idA", GOOD_VALUES),
            box_line("idA", [1.0, 0.8, 5.6, 4.6]),
            tw_line("m1", [1.2489, 0.2049, -0.0654]),
        ]
    )
    res = parse_calibration_records(
        stream, [AxesSpec("idA", has_x2=True, has_y2=True)], measure_ids=["m1"]
    )
    assert res.warnings == []
    cal = res.calibrations["idA"]
    assert cal.x_range == (0.0, 10.0)
    assert cal.y_range == (0.0, 20.0)
    assert cal.x2_range == (100.0, 200.0)
    assert cal.y2_range == (0.5, 1.5)
    assert cal.frame_corners_cm == (1.5, 1.2, 6.5, 5.2)
    assert res.boxes["idA"].rect == pytest.approx((1.0, 0.8, 6.6, 5.4))
    assert res.metrics["m1"].depth == pytest.approx(-0.0654)
    assert res.metrics["m1"].total_height == pytest.approx(0.2703)


def test_parse_ignores_interleaved_gle_chatter():
    stream = "\n".join(
        [
            "\x1b[0m GLE 4.3.10 startup banner",
            "dud pcode in wrap pcode -979026429   i=21 ",
            cal_line("idA", GOOD_VALUES),
            "dud3 pcode in text pcode 24734 22 ",
            box_line("idA", [1.0, 0.8, 5.6, 4.6]),
        ]
    )
    res = parse_calibration_records(stream, [AxesSpec("idA")])
    assert res.warnings == []
    assert set(res.calibrations) == {"idA"}


def test_records_are_matched_by_id_not_position():
    # The whole point of G5: the record order is graph-block order, but the
    # caller may hand the specs over in any order and still get the right map.
    stream = "\n".join(
        [
            cal_line("second", [0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1]),
            cal_line("first", GOOD_VALUES),
        ]
    )
    res = parse_calibration_records(stream, [AxesSpec("first"), AxesSpec("second")])
    assert res.calibrations["first"].x_range == (0.0, 10.0)
    assert res.calibrations["second"].x_range == (0.0, 1.0)


def test_malformed_record_warns_and_does_not_raise():
    res = parse_calibration_records(cal_line("idA", GOOD_VALUES[:5]), [AxesSpec("idA")])
    assert res.calibrations == {}
    categories = [w.category for w in res.warnings]
    assert "malformed" in categories
    assert "missing" in categories


def test_non_numeric_field_warns_as_malformed():
    line = f"{ANSI}{CAL_MARKER} idA  0 10 0 20 nan? 200 0.5 1.5 1.5 1.2 6.5 5.2"
    res = parse_calibration_records(line, [AxesSpec("idA")])
    assert res.calibrations == {}
    assert any(w.category == "malformed" for w in res.warnings)


def test_record_for_an_unknown_id_is_kept_but_warned():
    res = parse_calibration_records(cal_line("ghost", GOOD_VALUES), [AxesSpec("idA")])
    assert "ghost" in res.calibrations
    assert any(
        w.category == "unknown-id" and w.subject == "ghost" for w in res.warnings
    )


def test_declared_id_without_a_record_is_warned_for_both_kinds():
    res = parse_calibration_records("", [AxesSpec("idA")])
    subjects = [(w.category, w.subject) for w in res.warnings]
    assert subjects.count(("missing", "idA")) == 2


def test_duplicate_record_keeps_the_first_and_warns():
    stream = "\n".join([cal_line("idA", GOOD_VALUES), cal_line("idA", [9] * 12)])
    res = parse_calibration_records(stream, [AxesSpec("idA")])
    assert res.calibrations["idA"].x_range == (0.0, 10.0)
    assert any(w.category == "duplicate" for w in res.warnings)


def test_degenerate_range_is_dropped_as_invalid():
    values = [5, 5, 0, 20, 0, 1, 0, 1, 1.5, 1.2, 6.5, 5.2]
    res = parse_calibration_records(cal_line("idA", values), [AxesSpec("idA")])
    assert res.calibrations == {}
    assert any(w.category == "invalid" for w in res.warnings)


def test_log_axis_with_non_positive_bound_is_dropped_as_invalid():
    values = [-1, 10, 0, 20, 0, 1, 0, 1, 1.5, 1.2, 6.5, 5.2]
    res = parse_calibration_records(
        cal_line("idA", values), [AxesSpec("idA", x_log=True)]
    )
    assert res.calibrations == {}
    assert any(w.category == "invalid" for w in res.warnings)


def test_non_positive_box_extent_is_dropped_as_invalid():
    res = parse_calibration_records(
        box_line("idA", [1.0, 0.8, 0.0, 4.6]), [AxesSpec("idA")]
    )
    assert res.boxes == {}
    assert any(w.category == "invalid" for w in res.warnings)


def test_undeclared_metric_is_kept_but_warned_when_ids_were_declared():
    res = parse_calibration_records(tw_line("m9", [1, 1, 0]), [], measure_ids=["m1"])
    assert "m9" in res.metrics
    assert any(w.category == "unknown-id" and w.subject == "m9" for w in res.warnings)


def test_metrics_parse_without_declared_ids_and_without_warnings():
    res = parse_calibration_records(tw_line("m9", [1, 1, 0]), [])
    assert res.metrics["m9"].width == 1.0
    assert res.warnings == []


def test_parsing_without_specs_warns_once_about_assumed_flags():
    res = parse_calibration_records(cal_line("idA", GOOD_VALUES), [])
    assert res.calibrations["idA"].x_log is False
    assert sum(w.category == "unknown-id" for w in res.warnings) == 1


def test_empty_output_is_the_fail_closed_error_state():
    # GLE aborts before any print when the script has an error, so this is
    # what a failed compile looks like -- not a parse failure.
    res = parse_calibration_records("\x1b[91mErrors, GLE aborting.\x1b[0m", [])
    assert res.is_empty
    assert res.warnings == []


# --------------------------------------------------------------------------- #
# Axis maps and derivation
# --------------------------------------------------------------------------- #


def _cal(**spec_kwargs):
    res = parse_calibration_records(
        cal_line("idA", GOOD_VALUES), [AxesSpec("idA", **spec_kwargs)]
    )
    return res.calibrations["idA"]


def test_primary_maps_are_affine_over_the_frame():
    cal = _cal()
    assert cal.data_to_cm(0, 0) == pytest.approx((1.5, 1.2))
    assert cal.data_to_cm(10, 20) == pytest.approx((6.5, 5.2))
    assert cal.data_to_cm(5, 10) == pytest.approx((4.0, 3.2))
    assert cal.cm_to_data(4.0, 3.2) == pytest.approx((5.0, 10.0))


def test_secondary_maps_share_the_frame_and_use_the_secondary_range():
    cal = _cal(has_x2=True, has_y2=True)
    x2 = cal.axis_map("x2")
    y2 = cal.axis_map("y2")
    assert x2 is not None and y2 is not None
    # x2 borrows the horizontal cm extent, y2 the vertical one.
    assert x2.cm_range == (1.5, 6.5)
    assert y2.cm_range == (1.2, 5.2)
    assert x2.to_cm(100) == pytest.approx(1.5)
    assert x2.to_cm(200) == pytest.approx(6.5)
    assert x2.to_cm(150) == pytest.approx(4.0)
    assert y2.to_cm(0.5) == pytest.approx(1.2)
    assert y2.to_cm(1.5) == pytest.approx(5.2)
    assert y2.to_data(3.2) == pytest.approx(1.0)


def test_secondary_map_is_none_when_the_model_says_there_is_none():
    # GLE reports the primary range in x2gmin/y2gmin when no secondary axis
    # exists, so returning a map here would hand back a silent duplicate.
    cal = _cal()
    assert cal.axis_map("x2") is None
    assert cal.axis_map("y2") is None
    assert cal.data_to_cm(1, 1, y_axis="y2") is None


def test_log_axis_is_affine_in_log10():
    values = [1, 1000, 0, 20, 0, 1, 0, 1, 1.5, 1.2, 6.5, 5.2]
    res = parse_calibration_records(
        cal_line("idA", values), [AxesSpec("idA", x_log=True)]
    )
    cal = res.calibrations["idA"]
    # Three decades over 5 cm -> one decade per 5/3 cm, exactly.
    assert cal.axis_map("x").to_cm(1) == pytest.approx(1.5)
    assert cal.axis_map("x").to_cm(10) == pytest.approx(1.5 + 5.0 / 3.0)
    assert cal.axis_map("x").to_cm(100) == pytest.approx(1.5 + 10.0 / 3.0)
    assert cal.axis_map("x").to_cm(1000) == pytest.approx(6.5)
    assert cal.axis_map("x").to_data(1.5 + 5.0 / 3.0) == pytest.approx(10.0)


def test_log_secondary_axis_uses_its_own_log_flag():
    values = [0, 10, 0, 20, 0, 1, 1, 100, 1.5, 1.2, 6.5, 5.2]
    res = parse_calibration_records(
        cal_line("idA", values), [AxesSpec("idA", has_y2=True, y2_log=True)]
    )
    y2 = res.calibrations["idA"].axis_map("y2")
    assert y2.is_log is True
    assert y2.to_cm(10) == pytest.approx(3.2)  # midpoint of two decades


def test_log_map_clamps_a_non_positive_point_instead_of_returning_nan():
    m = AxisMap((1.0, 1000.0), (1.5, 6.5), is_log=True)
    assert math.isfinite(m.to_cm(0.0))
    assert math.isfinite(m.to_cm(-5.0))


def test_axis_map_round_trips_for_a_reversed_cm_extent():
    m = AxisMap((0.0, 10.0), (6.5, 1.5))
    assert m.to_cm(0) == pytest.approx(6.5)
    assert m.to_data(m.to_cm(3.7)) == pytest.approx(3.7)


def test_unknown_axis_name_raises():
    with pytest.raises(ValueError):
        _cal().axis_map("z")


def test_frame_rect_normalizes_corner_ordering_and_contains_works():
    cal = _cal()
    assert cal.frame_rect_cm == (1.5, 1.2, 6.5, 5.2)
    assert cal.contains_cm(4.0, 3.2)
    assert not cal.contains_cm(0.0, 3.2)


# --------------------------------------------------------------------------- #
# CTM guard
# --------------------------------------------------------------------------- #


def test_no_hazards_in_a_plain_gleplot_style_script():
    assert find_ctm_hazards(TWO_GRAPHS) == []


@pytest.mark.parametrize(
    "stmt", ["translate 1 1", "tran 1 1", "scale 2 2", "rotate 30", "rot 30"]
)
def test_bare_ctm_statements_are_flagged(stmt):
    hazards = find_ctm_hazards(f"size 5 5\n{stmt}\namove 1 1\nbox 1 1\n")
    assert len(hazards) == 1
    assert hazards[0].kind == "statement"
    assert hazards[0].keyword == stmt.split()[0]
    assert hazards[0].line_no == 2
    assert hazards[0].encloses_graph is False


@pytest.mark.parametrize(
    "block", ["translate 1 1", "scale 2 2", "rotate 30", "origin", "shear 1 1"]
)
def test_ctm_blocks_are_flagged_and_report_whether_they_wrap_a_graph(block):
    kind = block.split()[0]
    src = (
        "size 15 11\n"
        f"begin {block}\n"
        "amove 1 1\n"
        "begin graph\n"
        "   xaxis min 0 max 1\n"
        "end graph\n"
        f"end {kind}\n"
    )
    hazards = find_ctm_hazards(src)
    assert len(hazards) == 1
    assert hazards[0].kind == "block"
    assert hazards[0].keyword == kind
    assert hazards[0].encloses_graph is True


def test_ctm_block_without_a_graph_inside_is_still_flagged():
    src = "size 5 5\nbegin translate 1 1\namove 1 1\nbox 1 1\nend translate\n"
    hazards = find_ctm_hazards(src)
    assert len(hazards) == 1
    assert hazards[0].encloses_graph is False


def test_graph_internal_scale_is_never_a_hazard():
    # ``scale 1 1`` inside a graph block is the frame fraction (SPEC 3.3), a
    # different primitive from the page transform. This is the false positive
    # that would demote every gleplot figure ever written.
    assert find_ctm_hazards(TWO_GRAPHS) == []
    assert "scale 1 1" in TWO_GRAPHS


def test_scale_inside_a_string_or_comment_is_not_mistaken_for_a_transform():
    src = 'size 5 5\n! scale 2 2 would be bad\namove 1 1\nwrite "scale 2 2"\n'
    assert find_ctm_hazards(src) == []


def test_hazard_hiding_in_a_subroutine_is_found_with_an_absolute_line_number():
    src = (
        "size 5 5\n"
        "begin sub draw_it\n"
        "   translate 2 2\n"
        "   box 1 1\n"
        "end sub\n"
        "@draw_it\n"
    )
    hazards = find_ctm_hazards(src)
    assert len(hazards) == 1
    assert hazards[0].keyword == "translate"
    assert hazards[0].line_no == 3


def test_prose_blocks_are_not_descended_into():
    src = "size 5 5\nbegin text\n   translate is a word\nend text\n"
    assert find_ctm_hazards(src) == []


def test_hazards_are_returned_in_document_order():
    src = (
        "size 5 5\n"
        "rotate 10\n"
        "begin scale 2 2\n"
        "box 1 1\n"
        "end scale\n"
        "translate 1 1\n"
    )
    hazards = find_ctm_hazards(src)
    assert [h.line_no for h in hazards] == [2, 3, 6]
    assert [h.keyword for h in hazards] == ["rotate", "scale", "translate"]


def test_find_ctm_hazards_accepts_a_parsed_document():
    doc = parse_gle_source("size 5 5\ntranslate 1 1\n")
    assert len(find_ctm_hazards(doc)) == 1
