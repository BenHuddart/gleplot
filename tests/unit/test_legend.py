"""Legend visibility semantics.

``Axes.legend_on`` is tri-state:

* ``None`` (default) — auto: a legend is shown iff any series has a label.
* ``True`` — always show (what ``Axes.legend()`` sets).
* ``False`` — never show; the writer must emit ``key off`` because GLE
  draws an implicit key from per-dataset ``key "label"`` tokens.

Regression tests for the GUI legend toggle having no effect.
"""

import gleplot as glp


def _generate_gle(fig, tmp_path):
    out = tmp_path / "legend_test.gle"
    fig.savefig_gle(str(out))
    return out.read_text()


def _labeled_figure():
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4], label="squares")
    return fig, ax


def test_auto_legend_shown_when_labels_present(tmp_path):
    fig, ax = _labeled_figure()
    assert ax.legend_on is None
    gle = _generate_gle(fig, tmp_path)
    assert "key pos" in gle
    assert "key off" not in gle


def test_auto_no_legend_without_labels(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4])
    gle = _generate_gle(fig, tmp_path)
    assert "key pos" not in gle
    assert "key off" not in gle


def test_explicit_off_emits_key_off_for_labeled_series(tmp_path):
    fig, ax = _labeled_figure()
    ax.legend_on = False
    gle = _generate_gle(fig, tmp_path)
    assert "key off" in gle
    assert "key pos" not in gle
    # the label token is still present; only the key display is suppressed
    assert 'key "squares"' in gle


def test_explicit_on_without_labels_emits_key_pos(tmp_path):
    fig = glp.figure(data_prefix="legtest")
    ax = fig.add_subplot(1, 1, 1)
    ax.plot([0, 1, 2], [0, 1, 4])
    ax.legend_on = True
    gle = _generate_gle(fig, tmp_path)
    assert "key pos" in gle


def test_legend_call_sets_explicit_on():
    fig, ax = _labeled_figure()
    ax.legend()
    assert ax.legend_on is True


def test_tristate_survives_round_trip():
    from gleplot.figure import Figure

    for state in (None, True, False):
        fig, ax = _labeled_figure()
        ax.legend_on = state
        restored = Figure.from_dict(fig.to_dict())
        assert restored.axes_list[0].legend_on is state
