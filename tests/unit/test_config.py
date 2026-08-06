"""Per-figure config independence: ``Figure``/``GLEWriter`` copy the
:class:`~gleplot.config.GlobalConfig` defaults at construction time instead
of holding the shared singleton by reference.

Before this fix, ``Figure()`` with no explicit ``style=``/``graph=``/
``marker=`` stored ``GlobalConfig.get_style()`` (etc.) BY REFERENCE. Editing
``fig.style.font = ...`` in place therefore mutated process-global state:
every other default-styled ``Figure()`` created before or after in the same
interpreter saw the leaked value, including ``GlobalConfig.style`` itself.
This was hit twice in practice: GLEstudio's inspector panel had to work
around it with ``dataclasses.replace(figure.style, ...)`` instead of
in-place mutation (see the module docstring of
``glestudio/gui/inspector/figure_panel.py`` in the sibling GLEstudio repo),
and ``tests/gui/test_export_dialog.py`` (``_make_document_with_font``) had
to pass an explicit ``style=glp.GLEStyleConfig(font=font)`` per test instead
of relying on the default -- both are still valid, but no longer load-
bearing for correctness.

These tests pin two contracts:

1. **Isolation**: mutating one figure's copied config never affects another
   figure, and never mutates ``GlobalConfig`` itself.
2. **Defaults still propagate**: changing ``GlobalConfig.style``/``.graph``/
   ``.marker`` *before* constructing a figure still seeds that figure's
   defaults -- only the object *identity* is no longer shared, not the
   values.
"""

from __future__ import annotations

import dataclasses

import pytest

import gleplot as glp
from gleplot.config import GLEGraphConfig, GLEMarkerConfig, GLEStyleConfig, GlobalConfig
from gleplot.writer import GLEWriter


@pytest.fixture(autouse=True)
def _fresh():
    """Deterministic global config around every test in this module."""
    GlobalConfig.reset()
    yield
    GlobalConfig.reset()


# --------------------------------------------------------------------------- #
# Figure: isolation
# --------------------------------------------------------------------------- #


def test_default_style_is_not_the_global_singleton():
    """A default-styled figure's ``style`` is its own object, not
    ``GlobalConfig.style`` itself -- otherwise every in-place edit below
    would be a global mutation."""
    fig = glp.Figure()
    assert fig.style is not GlobalConfig.style


def test_mutating_one_figures_style_does_not_leak_to_a_later_figure():
    """The core regression: ``fig_a.style.font = ...`` must not change the
    font seen by a ``Figure()`` created afterwards with no explicit style."""
    fig_a = glp.Figure()
    fig_a.style.font = "helvetica"

    fig_b = glp.Figure()
    assert fig_b.style.font != "helvetica"
    assert fig_b.style.font == GLEStyleConfig().font


def test_mutating_one_figures_style_does_not_leak_to_an_earlier_figure():
    """Same hazard, opposite order: an earlier figure must not see a later
    figure's in-place edit either (both held the same object before the
    fix, so order didn't matter -- confirm it doesn't now either)."""
    fig_a = glp.Figure()
    fig_b = glp.Figure()

    fig_b.style.font = "courier"

    assert fig_a.style.font != "courier"
    assert fig_a.style.font == GLEStyleConfig().font


def test_mutating_a_figures_style_does_not_mutate_global_config():
    """In-place edits on a figure's copied style must not write back into
    the process-global default."""
    fig = glp.Figure()
    fig.style.font = "helvetica"
    fig.style.fontsize = 99

    assert GlobalConfig.style.font != "helvetica"
    assert GlobalConfig.style.fontsize != 99
    assert GlobalConfig.style == GLEStyleConfig()


@pytest.mark.parametrize(
    "attr_name, config_cls, field_name, value",
    [
        ("graph", GLEGraphConfig, "legend_position", "bl"),
        ("marker_config", GLEMarkerConfig, "msize_scale", 3.5),
    ],
)
def test_mutating_graph_and_marker_config_does_not_leak(
    attr_name, config_cls, field_name, value
):
    """Same isolation contract for ``Figure.graph`` and
    ``Figure.marker_config`` -- the audited siblings of ``Figure.style``."""
    fig_a = glp.Figure()
    setattr(getattr(fig_a, attr_name), field_name, value)

    fig_b = glp.Figure()
    default = getattr(config_cls(), field_name)
    assert getattr(getattr(fig_b, attr_name), field_name) == default
    assert getattr(getattr(fig_b, attr_name), field_name) != value

    # And GlobalConfig itself is untouched.
    global_attr = {"graph": "graph", "marker_config": "marker"}[attr_name]
    assert getattr(GlobalConfig, global_attr) == config_cls()


def test_explicit_style_objects_are_still_independent_figure_to_figure():
    """Two figures constructed with separate explicit ``GLEStyleConfig``
    instances were always independent; confirm the fix hasn't changed that
    unrelated case."""
    style_a = GLEStyleConfig(font="timesroman")
    style_b = GLEStyleConfig(font="helvetica")
    fig_a = glp.Figure(style=style_a)
    fig_b = glp.Figure(style=style_b)

    fig_a.style.font = "courier"
    assert fig_b.style.font == "helvetica"


def test_an_explicit_config_object_is_still_stored_by_reference():
    """The copy-at-construction fix must be scoped to the ``GlobalConfig``
    fallback ONLY. An explicitly passed config keeps its pre-fix identity
    contract: ``fig.graph is graph`` for the object passed in.

    ``gleplot.parser.recognizer.parse_gle_figure`` depends on exactly this:
    it builds a ``GLEGraphConfig``, hands it to ``Figure(graph=...)``, then
    mutates ``smooth_curves`` on that same object AFTER construction, once
    it has walked the parsed series (see ``_apply_smooth``). Copying the
    explicit object here would silently detach ``fig.graph`` from the
    object the recognizer keeps mutating -- caught by
    ``tests/unit/test_smooth_default.py::test_open_gle_recovers_smoothed_figures_as_smoothed``
    the first time this fix over-applied the copy to explicit configs too.
    """
    style = GLEStyleConfig()
    graph = GLEGraphConfig()
    marker = GLEMarkerConfig()
    fig = glp.Figure(style=style, graph=graph, marker=marker)

    assert fig.style is style
    assert fig.graph is graph
    assert fig.marker_config is marker

    # And a post-construction mutation on the ORIGINAL object -- exactly
    # what the recognizer does -- must be visible through the figure.
    graph.smooth_curves = True
    assert fig.graph.smooth_curves is True


# --------------------------------------------------------------------------- #
# Figure: defaults still propagate (copy-AT-CONSTRUCTION, not a frozen copy)
# --------------------------------------------------------------------------- #


def test_global_config_change_before_construction_still_seeds_new_figures():
    """Setting ``GlobalConfig.style.font`` before creating a figure must
    still change that figure's default -- the fix must not turn
    ``GlobalConfig`` into dead configuration."""
    GlobalConfig.style.font = "palatino"
    GlobalConfig.graph.legend_position = "bl"
    GlobalConfig.marker.msize_scale = 2.0

    fig = glp.Figure()

    assert fig.style.font == "palatino"
    assert fig.graph.legend_position == "bl"
    assert fig.marker_config.msize_scale == 2.0


def test_global_config_change_after_construction_does_not_retroactively_apply():
    """The copy is taken once, at construction: a ``GlobalConfig`` edit made
    afterwards does not reach back into an already-built figure (this was
    already true before the fix, since attribute lookup on the shared
    object still needed the figure to re-read it; confirmed here as part of
    the documented contract)."""
    fig = glp.Figure()
    GlobalConfig.style.font = "palatino"

    assert fig.style.font != "palatino"


# --------------------------------------------------------------------------- #
# GLEWriter: same pattern, audited and fixed identically
# --------------------------------------------------------------------------- #


def test_writer_default_style_is_not_the_global_singleton():
    writer = GLEWriter()
    assert writer.style is not GlobalConfig.style


def test_mutating_one_writers_style_does_not_leak_to_another():
    writer_a = GLEWriter()
    writer_a.style.font = "helvetica"

    writer_b = GLEWriter()
    assert writer_b.style.font != "helvetica"
    assert GlobalConfig.style.font != "helvetica"


def test_writer_explicit_config_object_is_still_stored_by_reference():
    """Same identity contract as ``Figure`` (see
    ``test_an_explicit_config_object_is_still_stored_by_reference``): an
    explicitly passed config is not copied."""
    style = GLEStyleConfig()
    writer = GLEWriter(style=style)
    assert writer.style is style


# --------------------------------------------------------------------------- #
# Serialization: the copy must not change to_dict() output for an untouched
# figure (SPEC: byte-stable to_dict()/GLE generation for unmodified state).
# --------------------------------------------------------------------------- #


def test_untouched_figure_to_dict_matches_explicit_default_style():
    """A figure that took the (copied) global default must serialize
    identically to one built with an explicit, freshly-constructed default
    config -- the copy must be a faithful, field-for-field duplicate."""
    fig_default = glp.Figure(figsize=(4, 3), data_prefix="cfgtest")
    fig_default.add_subplot(111).plot([1, 2, 3], [1, 4, 9])

    fig_explicit = glp.Figure(
        figsize=(4, 3),
        data_prefix="cfgtest",
        style=GLEStyleConfig(),
        graph=GLEGraphConfig(),
        marker=GLEMarkerConfig(),
    )
    fig_explicit.add_subplot(111).plot([1, 2, 3], [1, 4, 9])

    d_default = fig_default.to_dict()
    d_explicit = fig_explicit.to_dict()
    # axes_id (G5) is a fresh uuid4 per Axes instance by design -- two
    # independently constructed figures never share one, and are not meant
    # to; strip it from both sides before the field-for-field comparison.
    for d in (d_default, d_explicit):
        for ax in d["figure"]["axes"]:
            ax.pop("axes_id", None)

    assert d_default == d_explicit


def test_untouched_figure_gle_text_matches_explicit_default_style(tmp_path):
    """Same check at the GLE-text level (what actually reaches disk)."""
    fig_default = glp.Figure(figsize=(4, 3), data_prefix="cfgtext")
    fig_default.add_subplot(111).plot([1, 2, 3], [1, 4, 9])

    fig_explicit = glp.Figure(
        figsize=(4, 3),
        data_prefix="cfgtext",
        style=GLEStyleConfig(),
        graph=GLEGraphConfig(),
        marker=GLEMarkerConfig(),
    )
    fig_explicit.add_subplot(111).plot([1, 2, 3], [1, 4, 9])

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    fig_default.savefig_gle(str(dir_a / "figure.gle"))
    fig_explicit.savefig_gle(str(dir_b / "figure.gle"))

    assert (dir_a / "figure.gle").read_text(encoding="utf-8") == (
        dir_b / "figure.gle"
    ).read_text(encoding="utf-8")


def test_config_dataclasses_have_no_mutable_fields():
    """Guards the copy-mechanism choice: ``dataclasses.replace`` (a shallow
    copy) is only a *complete* copy because every field on these three
    dataclasses is an immutable scalar (str/float/int/bool/Optional[float]).
    If a future field adds a list/dict/set member, a shallow copy would
    silently start aliasing it again -- this test fails loudly instead,
    flagging that ``Figure.__init__``/``GLEWriter.__init__`` need a deep
    copy for that field.
    """
    mutable_containers = (list, dict, set)
    for cls in (GLEStyleConfig, GLEGraphConfig, GLEMarkerConfig):
        for f in dataclasses.fields(cls):
            instance = cls()
            value = getattr(instance, f.name)
            assert not isinstance(value, mutable_containers), (
                f"{cls.__name__}.{f.name} is a mutable container "
                f"({type(value).__name__}); dataclasses.replace() only "
                "shallow-copies it, so Figure/GLEWriter would still share "
                "it by reference."
            )
