"""Preview-only ``deresolve`` decimation (G7; SPEC 6.1/10.7).

``preview_decimation`` is an opt-in, per-call generation argument (never
stored on the figure): the DEFAULT emission (no argument, or ``None``, or
``<=1``) must stay byte-identical to a build before G7 existed, and
``to_dict``/``from_dict`` must never see it.

Kind/threshold rule under test (see
:meth:`gleplot.writer.GLEWriter._deresolve_clause` for the full source-level
and empirical justification):

* line and scatter (marker-only) series -- routed through
  :meth:`~gleplot.writer.GLEWriter.add_plot_line` -- get a trailing
  `` deresolve N`` clause on their ``dN`` line, but only once the series has
  at least :attr:`~gleplot.writer.GLEWriter.MIN_DERESOLVE_POINTS` rows.
* errorbar and bar series never get the clause: GLE's ``err``/``herr``
  whisker geometry and the graph-level ``bar dN fill ...`` statement both
  read the dataset's raw, undecimated arrays directly (verified against GLE
  4.3.10 source and by compiling fixtures -- see
  ``tests/integration/test_deresolve_compilation.py`` and the docstring
  above), so decimating their main dataset would only mislead a preview.
"""

from __future__ import annotations

import re

import numpy as np
import pytest

import gleplot as glp
from gleplot.writer import DecimationCandidate, DecimationRecord, GLEWriter

#: Comfortably above GLEWriter.MIN_DERESOLVE_POINTS.
_BIG_N = 2000
#: Comfortably below it.
_SMALL_N = 50


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    glp.GlobalConfig.reset()
    yield
    glp.close()
    glp.GlobalConfig.reset()


def _big_xy(n=_BIG_N):
    x = np.arange(n, dtype=float)
    y = np.sin(x / 50.0)
    return x, y


def _deresolve_clauses(script: str) -> list[str]:
    return re.findall(r"deresolve \d+", script)


# --------------------------------------------------------------------------- #
# Default path: byte-identical, empty report
# --------------------------------------------------------------------------- #


def test_default_emission_has_no_deresolve():
    """No argument at all: today's output, unchanged."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    script = fig._generate_gle()

    assert "deresolve" not in script
    assert fig.preview_decimation_report == []


def test_explicit_none_matches_default():
    """``preview_decimation=None`` is exactly the default, not a distinct state."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    without_arg = fig._generate_gle()
    with_none = fig._generate_gle(preview_decimation=None)

    assert without_arg == with_none


def test_factor_of_one_is_a_no_op():
    """A factor of 1 keeps every point -- treated as "off", not emitted."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    script = fig._generate_gle(preview_decimation=1)

    assert "deresolve" not in script
    assert fig.preview_decimation_report == []


def test_preview_decimation_is_not_serialized():
    """Snapshot discipline: the parameter never reaches to_dict/from_dict."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    fig._generate_gle(preview_decimation=10)  # side effect: populates the report
    d = fig.to_dict()

    blob = repr(d)
    assert "deresolve" not in blob
    assert "preview_decimation" not in blob

    # A from_dict round trip re-emits the DEFAULT (no argument) script,
    # regardless of the decimated call that happened just before to_dict().
    restored = glp.Figure.from_dict(d)
    assert "deresolve" not in restored._generate_gle()


# --------------------------------------------------------------------------- #
# Threshold rule
# --------------------------------------------------------------------------- #


def test_large_line_series_gets_deresolve():
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    script = fig._generate_gle(preview_decimation=10)

    assert _deresolve_clauses(script) == ["deresolve 10"]


def test_small_line_series_is_exempt():
    """Below MIN_DERESOLVE_POINTS, the factor is requested but not applied."""
    x = np.arange(_SMALL_N, dtype=float)
    y = x * 2.0
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    script = fig._generate_gle(preview_decimation=10)

    assert "deresolve" not in script
    assert fig.preview_decimation_report == []


def test_threshold_is_exact_boundary():
    """Exactly MIN_DERESOLVE_POINTS rows qualifies; one fewer does not."""
    n = GLEWriter.MIN_DERESOLVE_POINTS

    fig_at = glp.figure(figsize=(4, 3))
    ax_at = fig_at.add_subplot(111)
    x_at = np.arange(n, dtype=float)
    ax_at.plot(x_at, x_at)
    script_at = fig_at._generate_gle(preview_decimation=4)
    assert "deresolve" in script_at

    glp.close()
    fig_below = glp.figure(figsize=(4, 3))
    ax_below = fig_below.add_subplot(111)
    x_below = np.arange(n - 1, dtype=float)
    ax_below.plot(x_below, x_below)
    script_below = fig_below._generate_gle(preview_decimation=4)
    assert "deresolve" not in script_below


def test_mixed_series_only_large_one_decimated():
    """A small and a large series on the same axes: only the large one changes."""
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    x_small = np.arange(_SMALL_N, dtype=float)
    ax.plot(x_small, x_small, label="small")
    x_big, y_big = _big_xy()
    ax.plot(x_big, y_big, label="big")

    script = fig._generate_gle(preview_decimation=8)

    assert _deresolve_clauses(script) == ["deresolve 8"]
    report = fig.preview_decimation_report
    assert len(report) == 1
    assert report[0].label == "big"
    assert report[0].factor == 8
    assert report[0].original_points == _BIG_N


# --------------------------------------------------------------------------- #
# Clause placement
# --------------------------------------------------------------------------- #


def test_deresolve_is_trailing_on_its_dataset_line():
    """Appended last on the ``dN`` line, after any ``key`` clause."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y, label="trace")

    script = fig._generate_gle(preview_decimation=5)
    (line,) = [ln.strip() for ln in script.splitlines() if re.match(r"\s+d1\s", ln)]

    assert line.endswith("deresolve 5")
    assert 'key "trace"' in line


# --------------------------------------------------------------------------- #
# Kind exclusions: scatter is included, errorbar and bar are not
# --------------------------------------------------------------------------- #


def test_scatter_series_gets_deresolve():
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.scatter(x, y)

    script = fig._generate_gle(preview_decimation=10)

    assert _deresolve_clauses(script) == ["deresolve 10"]


def test_errorbar_series_is_never_decimated():
    """GLE's err/herr geometry bypasses transform_data -- see writer docstring."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.errorbar(x, y, yerr=np.full_like(y, 0.1))

    script = fig._generate_gle(preview_decimation=10)

    assert "deresolve" not in script
    assert fig.preview_decimation_report == []


def test_bar_series_is_never_decimated():
    """The graph-level `bar dN fill ...` statement reads raw dataset arrays."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.bar(x, np.abs(y))

    script = fig._generate_gle(preview_decimation=10)

    assert "deresolve" not in script
    assert fig.preview_decimation_report == []


# --------------------------------------------------------------------------- #
# Decimation report
# --------------------------------------------------------------------------- #


def test_decimation_report_shape():
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y, label="signal")

    fig._generate_gle(preview_decimation=20)
    report = fig.preview_decimation_report

    assert report == [
        DecimationRecord(
            dataset="d1", label="signal", factor=20, original_points=_BIG_N
        )
    ]


def test_decimation_report_resets_every_generation():
    """Write-time output, not accumulating document state."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    fig._generate_gle(preview_decimation=10)
    assert fig.preview_decimation_report != []

    fig._generate_gle()  # default call right after
    assert fig.preview_decimation_report == []


def test_writer_level_report_via_generate_gle_with_files():
    """The report is also reachable through the lower-level 2-tuple API."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    _script, _files = fig._generate_gle_with_files(preview_decimation=10)

    assert fig.preview_decimation_report[0].factor == 10


# --------------------------------------------------------------------------- #
# Per-series policy: Callable[[DecimationCandidate], Optional[int]]
# --------------------------------------------------------------------------- #


def test_decimation_candidate_is_a_plain_value_object():
    c = DecimationCandidate(dataset="d3", label="trace", n_points=1234, kind="line")
    assert (c.dataset, c.label, c.n_points, c.kind) == ("d3", "trace", 1234, "line")


def test_callable_policy_gives_distinct_per_series_factors():
    """The motivating case: a 1k-ish curve and a much larger trace on the
    same axes get DIFFERENT factors from one callable, instead of a single
    figure-wide int sized off the smaller series."""
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    x_small, y_small = _big_xy(1200)
    ax.plot(x_small, y_small, label="smallbig")
    x_large, y_large = _big_xy(6000)
    ax.plot(x_large, y_large, label="large")

    def policy(candidate: DecimationCandidate):
        # Roughly one drawn point per 500 raw points.
        return max(1, candidate.n_points // 500)

    script = fig._generate_gle(preview_decimation=policy)

    assert sorted(_deresolve_clauses(script)) == sorted(["deresolve 2", "deresolve 12"])
    report = {r.label: r for r in fig.preview_decimation_report}
    assert report.keys() == {"smallbig", "large"}
    assert report["smallbig"].factor == 2
    assert report["smallbig"].original_points == 1200
    assert report["large"].factor == 12
    assert report["large"].original_points == 6000


def test_callable_policy_receives_dataset_label_points_and_kind():
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y, label="trace")

    seen: list[DecimationCandidate] = []

    def policy(candidate: DecimationCandidate):
        seen.append(candidate)
        return 10

    fig._generate_gle(preview_decimation=policy)

    assert len(seen) == 1
    assert seen[0] == DecimationCandidate(
        dataset="d1", label="trace", n_points=_BIG_N, kind="line"
    )


def test_callable_policy_sees_scatter_kind():
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.scatter(x, y, label="pts")

    seen: list[DecimationCandidate] = []
    fig._generate_gle(preview_decimation=lambda c: (seen.append(c), 5)[1])

    assert seen[0].kind == "scatter"


def test_callable_policy_returning_none_exempts_that_series():
    """A callable may leave a normally-eligible series undecimated by
    returning ``None`` -- the per-series analogue of an int policy of 1."""
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y, label="skip_me")

    script = fig._generate_gle(preview_decimation=lambda candidate: None)

    assert "deresolve" not in script
    assert fig.preview_decimation_report == []


def test_ineligible_kinds_never_reach_the_callable():
    """bar/errorbar series must never be offered to the policy, even though
    they are far above MIN_DERESOLVE_POINTS -- only the plain line series on
    the same axes is eligible."""
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    x, y = _big_xy()
    ax.errorbar(x, y, yerr=np.full_like(y, 0.1), label="err_series")
    ax.bar(x, np.abs(y), label="bar_series")
    x2, y2 = _big_xy()
    ax.plot(x2, y2, label="eligible")

    seen_labels: list = []

    def policy(candidate: DecimationCandidate):
        seen_labels.append(candidate.label)
        return 5

    script = fig._generate_gle(preview_decimation=policy)

    assert seen_labels == ["eligible"]
    assert _deresolve_clauses(script) == ["deresolve 5"]


# --------------------------------------------------------------------------- #
# Per-series policy: Mapping[Optional[str], int] keyed by label
# --------------------------------------------------------------------------- #


def test_mapping_policy_keys_by_label():
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    x_a, y_a = _big_xy()
    ax.plot(x_a, y_a, label="mapped")
    x_b, y_b = _big_xy()
    ax.plot(x_b, y_b, label="unmapped")

    script = fig._generate_gle(preview_decimation={"mapped": 7})

    assert _deresolve_clauses(script) == ["deresolve 7"]
    report = fig.preview_decimation_report
    assert len(report) == 1
    assert report[0].label == "mapped"
    assert report[0].factor == 7


def test_mapping_policy_none_key_targets_unlabeled_series():
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    x, y = _big_xy()
    ax.plot(x, y)  # no label -> label is None

    script = fig._generate_gle(preview_decimation={None: 6})

    assert _deresolve_clauses(script) == ["deresolve 6"]


def test_mapping_policy_empty_mapping_decimates_nothing():
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y, label="trace")

    script = fig._generate_gle(preview_decimation={})

    assert "deresolve" not in script
    assert fig.preview_decimation_report == []


# --------------------------------------------------------------------------- #
# Invalid policy shapes
# --------------------------------------------------------------------------- #


def test_unsupported_policy_type_raises_type_error():
    x, y = _big_xy()
    fig = glp.figure(figsize=(4, 3))
    ax = fig.add_subplot(111)
    ax.plot(x, y)

    with pytest.raises(TypeError):
        fig._generate_gle(preview_decimation=object())
