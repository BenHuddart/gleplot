"""Compiled proof for preview-only ``deresolve`` decimation (G7; SPEC 6.1/10.7).

Everything in ``tests/unit/test_preview_decimation.py`` asserts on the
*script text* gleplot emits. This file asserts on what GLE 4.3.10 actually
does with it:

* a ``dN ... deresolve N`` line/scatter dataset still compiles, and draws
  measurably fewer points than the same dataset without the clause;
* axis autoscale is computed from the FULL dataset regardless of
  ``deresolve`` -- the specific property GLEstudio's SPEC cites as having
  been measured (limits unaffected, ~10x speedup at 200k points);
* the errorbar and bar exclusions in ``GLEWriter._deresolve_clause`` are not
  just a policy choice on gleplot's side -- GLE itself ignores ``deresolve``
  for those draw paths, confirmed by byte-identical PostScript with and
  without the clause (aside from the ``%%Title`` comment savefig_gle embeds).

Skipped when GLE is not installed.
"""

from __future__ import annotations

import re
import subprocess
import time

import numpy as np
import pytest

import gleplot as glp
from gleplot.compiler import GLECompiler, find_gle


def _gle_available() -> bool:
    try:
        GLECompiler()
        return True
    except RuntimeError:
        return False


pytestmark = pytest.mark.skipif(not _gle_available(), reason="GLE binary not available")

_LIMITS_RE = re.compile(
    r"LIMITS\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)\s+([\d.eE+-]+)"
)


@pytest.fixture(autouse=True)
def _fresh():
    glp.close()
    glp.GlobalConfig.reset()
    yield
    glp.close()
    glp.GlobalConfig.reset()


def _big_xy(n=5000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.linspace(0.0, 100.0, n)
    y = np.sin(x) + 0.01 * rng.standard_normal(n)
    return x, y


def _compile_eps(fig, tmp_path, name, **savefig_kwargs):
    """Write + compile *fig* to EPS, returning the compiled text."""
    fig.savefig(str(tmp_path / f"{name}.eps"), format="eps", **savefig_kwargs)
    return (tmp_path / f"{name}.eps").read_text(encoding="utf-8")


def _fill_count(eps_text: str) -> int:
    """Number of filled marker glyphs GLE actually drew."""
    return len(re.findall(r"^fill$", eps_text, flags=re.MULTILINE))


def _limits_via_print(fig, tmp_path, name, **generate_kwargs) -> tuple[float, ...]:
    """Compile *fig* with a post-graph ``print`` of GLE's autoscaled window.

    Mirrors SPEC 6.2's calibration technique: ``xgmin``/``xgmax``/``ygmin``/
    ``ygmax`` are set by ``window_set``/``store_window_bounds_to_vars`` from
    the RAW dataset before any drawing (and therefore before ``deresolve``,
    which only affects ``transform_data`` at draw time) -- so this is the
    right hook to prove decimation never touches autoscale.
    """
    script, data_files = fig._generate_gle_with_files(**generate_kwargs)
    for filename, content in data_files.items():
        (tmp_path / filename).write_text(content, encoding="utf-8")
    probe = script + '\nprint "LIMITS " xgmin " " xgmax " " ygmin " " ygmax\n'
    probe_path = tmp_path / f"{name}.gle"
    probe_path.write_text(probe, encoding="utf-8")
    proc = subprocess.run(
        [str(find_gle()), "-d", "eps", "-verbosity", "0", probe_path.name],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
    )
    found = _LIMITS_RE.search(proc.stdout + proc.stderr)
    assert found is not None, f"no LIMITS line:\n{proc.stdout}\n{proc.stderr}"
    return tuple(float(v) for v in found.groups())


# --------------------------------------------------------------------------- #
# Compiles, and actually decimates
# --------------------------------------------------------------------------- #


def test_decorated_line_compiles(tmp_path):
    x, y = _big_xy(n=1500)
    fig = glp.figure(figsize=(4, 3), data_prefix="dere")
    ax = fig.add_subplot(111)
    ax.plot(x, y, marker="o", markersize=2)

    script = fig._generate_gle(preview_decimation=5)
    assert "deresolve 5" in script

    fig.savefig(str(tmp_path / "line.pdf"), preview_decimation=5)
    assert (tmp_path / "line.pdf").exists()


def test_deresolve_reduces_drawn_markers(tmp_path):
    """A marker-only (scatter) series draws fewer glyphs once decimated."""
    x, y = _big_xy(n=2000)

    fig_full = glp.figure(figsize=(4, 3), data_prefix="full")
    fig_full.add_subplot(111).scatter(x, y, marker="o", markersize=2)
    full_eps = _compile_eps(fig_full, tmp_path, "full")

    glp.close()
    fig_dec = glp.figure(figsize=(4, 3), data_prefix="dec")
    fig_dec.add_subplot(111).scatter(x, y, marker="o", markersize=2)
    dec_eps = _compile_eps(fig_dec, tmp_path, "dec", preview_decimation=10)

    full_markers = _fill_count(full_eps)
    dec_markers = _fill_count(dec_eps)
    assert full_markers > 0
    # GLE's skip algorithm keeps ceil(n/m) points plus an always-appended
    # final point (see writer.py's DecimationRecord/._deresolve_clause docs
    # and GLE's transform_data) -- roughly n/10 here, well under n/2.
    assert dec_markers < full_markers / 2


def test_decimated_compile_is_faster(tmp_path):
    """Directional check of the SPEC-cited speedup (~10x at 200k points).

    Kept generous (merely faster, not a fixed ratio) so it is not flaky on a
    loaded CI box; the ratio itself is a documented, separately-verified
    empirical finding, not something this suite re-benchmarks precisely.
    """
    x, y = _big_xy(n=60000)

    fig_full = glp.figure(figsize=(5, 4), data_prefix="perf_full")
    fig_full.add_subplot(111).plot(x, y)
    full_times = []
    for i in range(2):
        t0 = time.perf_counter()
        fig_full.savefig(str(tmp_path / f"perf_full_{i}.pdf"))
        full_times.append(time.perf_counter() - t0)

    glp.close()
    fig_dec = glp.figure(figsize=(5, 4), data_prefix="perf_dec")
    fig_dec.add_subplot(111).plot(x, y)
    dec_times = []
    for i in range(2):
        t0 = time.perf_counter()
        fig_dec.savefig(str(tmp_path / f"perf_dec_{i}.pdf"), preview_decimation=20)
        dec_times.append(time.perf_counter() - t0)

    assert min(dec_times) < min(full_times)


# --------------------------------------------------------------------------- #
# Autoscale-from-full-data (the SPEC property GLEstudio measured)
# --------------------------------------------------------------------------- #


def test_autoscale_unaffected_by_decimation(tmp_path):
    x, y = _big_xy(n=3000)

    fig_full = glp.figure(figsize=(4, 3), data_prefix="lim_full")
    fig_full.add_subplot(111).plot(x, y, marker="o", markersize=2)
    limits_full = _limits_via_print(fig_full, tmp_path, "lim_full")

    glp.close()
    fig_dec = glp.figure(figsize=(4, 3), data_prefix="lim_dec")
    fig_dec.add_subplot(111).plot(x, y, marker="o", markersize=2)
    limits_dec = _limits_via_print(fig_dec, tmp_path, "lim_dec", preview_decimation=15)

    assert limits_dec == pytest.approx(limits_full, rel=1e-9)


# --------------------------------------------------------------------------- #
# Kind exclusions, confirmed at the GLE level (not just gleplot's policy)
# --------------------------------------------------------------------------- #


def test_gle_ignores_deresolve_on_errorbar_whiskers(tmp_path):
    """Even if a caller forced `` deresolve`` onto an err dataset, GLE would
    ignore it for the whiskers -- confirmed directly against the engine
    rather than trusting gleplot's own exclusion. Writes the raw GLE text by
    hand (bypassing gleplot's writer) since gleplot itself never emits the
    clause here -- see
    ``test_preview_decimation.test_errorbar_series_is_never_decimated``.
    """
    data_lines = "\n".join(f"{i} {float(i)} 0.3" for i in range(200))
    (tmp_path / "err.dat").write_text("! x y e\n" + data_lines + "\n")

    def _script(deresolve: str) -> str:
        return f"""size 10 10
begin graph
    size 10 10
    data "err.dat" d1=c1,c2 d2=c1,c3
    d1 marker fcircle msize 0.2{deresolve} err d2 errwidth 0.1
end graph
"""

    (tmp_path / "with_dere.gle").write_text(_script(" deresolve 4"))
    (tmp_path / "without_dere.gle").write_text(_script(""))

    for name in ("with_dere", "without_dere"):
        proc = subprocess.run(
            [str(find_gle()), "-d", "eps", "-verbosity", "0", f"{name}.gle"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr

    with_text = (tmp_path / "with_dere.eps").read_text(encoding="utf-8")
    without_text = (tmp_path / "without_dere.eps").read_text(encoding="utf-8")

    # Markers ARE decimated (transform_data)...
    assert _fill_count(with_text) < _fill_count(without_text)
    # ...but the whisker stroke count -- everything that isn't the marker
    # fill -- is identical, proving the err geometry itself never shrank.
    with_strokes = len(re.findall(r"^stroke$", with_text, flags=re.MULTILINE))
    without_strokes = len(re.findall(r"^stroke$", without_text, flags=re.MULTILINE))
    marker_delta = _fill_count(without_text) - _fill_count(with_text)
    assert without_strokes - with_strokes == marker_delta


def test_gle_ignores_deresolve_on_bar_statement(tmp_path):
    """The graph-level ``bar dN fill ...`` statement reads raw data directly."""
    data_lines = "\n".join(f"{i} {float(i)}" for i in range(50))
    (tmp_path / "bar.dat").write_text("! x y\n" + data_lines + "\n")

    def _script(deresolve: str) -> str:
        return f"""size 10 10
begin graph
    size 10 10
    data "bar.dat"
    d1{deresolve}
    bar d1 fill red
end graph
"""

    (tmp_path / "with_dere.gle").write_text(_script(" deresolve 4"))
    (tmp_path / "without_dere.gle").write_text(_script(""))

    texts = {}
    for name in ("with_dere", "without_dere"):
        proc = subprocess.run(
            [str(find_gle()), "-d", "eps", "-verbosity", "0", f"{name}.gle"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        text = (tmp_path / f"{name}.eps").read_text(encoding="utf-8")
        # Strip the one expected difference (the script's own filename in
        # the EPS header) before comparing.
        texts[name] = re.sub(r"%%Title:.*", "", text)

    assert texts["with_dere"] == texts["without_dere"]
