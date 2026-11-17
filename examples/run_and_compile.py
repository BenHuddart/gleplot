"""Run every gleplot example and compile it to PDF, EPS and PNG.

``EXAMPLES`` is the one list of examples. CI runs this script, and the docs
gallery uses the PNGs it writes to ``examples/outputs/``. An ``example_*``
function under ``basic/`` or ``advanced/`` that is not listed fails the run.

Usage::

    python examples/run_and_compile.py               # run and compile; needs GLE
    python examples/run_and_compile.py --no-compile  # run only
"""

import argparse
import importlib
import inspect
import os
import pkgutil
import sys
import traceback
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import advanced
import basic
from advanced import (
    example_1x3_comparison,
    example_2x2_grid,
    example_batch_figures,
    example_both_shared,
    example_broken_axis_line,
    example_broken_axis_none,
    example_broken_axis_slash,
    example_combined_plot,
    example_comparison_with_without,
    example_data_prefix,
    example_dual_axis_from_file,
    example_errorbar_from_file,
    example_fill_between,
    example_fill_between_conditional,
    example_global_config,
    example_line_from_file,
    example_line_overlay_from_file,
    example_line_styles,
    example_log_scale,
    example_marker_config,
    example_multiple_styles,
    example_per_element_styling,
    example_per_figure_config,
    example_phase_diagram,
    example_prl_fig2a_style,
    example_residual_plot,
    example_secondary_yaxis,
    example_sharex_stacked,
    example_sharey_sidebyside,
    example_side_by_side,
    example_smooth_curves,
    example_stacked,
    example_text_annotations,
)
from basic import (
    example_asymmetric_error_bars,
    example_bar_chart,
    example_basic_line_plot,
    example_combined_errorbars,
    example_errorbar_with_line,
    example_heatmap_imshow,
    example_horizontal_error_bars,
    example_scatter_plot,
    example_symmetric_error_bars,
)

# (title, function, the .gle files it writes, without the suffix).
# The docs gallery is generated from this list and shows each one's PNG.
EXAMPLES = [
    ("Basic Line Plot", example_basic_line_plot, ["example_basic_line_plot"]),
    ("Scatter Plot", example_scatter_plot, ["example_scatter_plot"]),
    ("Bar Chart", example_bar_chart, ["example_bar_chart"]),
    (
        "Symmetric Error Bars",
        example_symmetric_error_bars,
        ["example_symmetric_error_bars"],
    ),
    (
        "Asymmetric Error Bars",
        example_asymmetric_error_bars,
        ["example_asymmetric_error_bars"],
    ),
    (
        "Horizontal Error Bars",
        example_horizontal_error_bars,
        ["example_horizontal_error_bars"],
    ),
    ("Error Bars on Line", example_errorbar_with_line, ["example_errorbars_line"]),
    (
        "Combined X+Y Error Bars",
        example_combined_errorbars,
        ["example_combined_errorbars"],
    ),
    ("Heatmap (imshow)", example_heatmap_imshow, ["example_heatmap_imshow"]),
    ("Fill Between", example_fill_between, ["example_fill_between"]),
    (
        "Conditional Fill Between",
        example_fill_between_conditional,
        ["example_fill_between_conditional"],
    ),
    ("Log Scale", example_log_scale, ["example_log_scale"]),
    ("Combined Plot", example_combined_plot, ["example_combined_plot"]),
    ("Multiple Styles", example_multiple_styles, ["example_multiple_styles"]),
    ("Side-by-Side Subplots", example_side_by_side, ["example_subplots_1x2"]),
    ("Stacked Subplots", example_stacked, ["example_subplots_2x1"]),
    ("2x2 Subplot Grid", example_2x2_grid, ["example_subplots_2x2"]),
    ("1x3 Comparison", example_1x3_comparison, ["example_subplots_1x3"]),
    ("Shared X-Axis (Stacked)", example_sharex_stacked, ["example_shared_x_axis"]),
    (
        "Shared Y-Axis (Side-by-side)",
        example_sharey_sidebyside,
        ["example_shared_y_axis"],
    ),
    (
        "Both Axes Shared (2x2 Grid)",
        example_both_shared,
        ["example_shared_both_axes"],
    ),
    ("Residual Plot Analysis", example_residual_plot, ["example_residual_analysis"]),
    (
        "Comparison: Shared vs Non-shared",
        example_comparison_with_without,
        ["example_without_shared_axes", "example_with_shared_axes"],
    ),
    (
        "Secondary Y-Axis",
        example_secondary_yaxis,
        [
            "secondary_yaxis_temp_humidity",
            "secondary_yaxis_growth",
            "secondary_yaxis_circuit",
            "secondary_yaxis_errorbar",
        ],
    ),
    (
        "Error Bars From File",
        example_errorbar_from_file,
        ["example_errorbar_from_file"],
    ),
    (
        "Dual Axis From File",
        example_dual_axis_from_file,
        ["example_dual_axis_from_file"],
    ),
    (
        "Line Overlay From File",
        example_line_overlay_from_file,
        ["example_line_overlay_from_file"],
    ),
    ("Line From File", example_line_from_file, ["example_line_from_file"]),
    ("Data Prefix Naming", example_data_prefix, ["example_data_prefix"]),
    (
        "Batch Figure Generation",
        example_batch_figures,
        [f"batch_outputs/example_batch_{i}" for i in range(1, 5)],
    ),
    ("Text Annotations", example_text_annotations, ["example_text_annotations"]),
    (
        "Per-Element Styling",
        example_per_element_styling,
        ["example_per_element_styling"],
    ),
    (
        "Phase Diagram (tripcolor + tricontour)",
        example_phase_diagram,
        ["example_phase_diagram"],
    ),
    (
        "Broken X-Axis (double-slash break)",
        example_broken_axis_slash,
        ["broken_axis_slash"],
    ),
    ("Broken X-Axis (single rule)", example_broken_axis_line, ["broken_axis_line"]),
    (
        "Broken X-Axis (three segments)",
        example_broken_axis_none,
        ["broken_axis_none"],
    ),
    ("PRL Fig. 2(a)-style panel", example_prl_fig2a_style, ["prl_fig2a_style"]),
    ("Global Configuration", example_global_config, ["example_global_config"]),
    (
        "Per-Figure Configuration",
        example_per_figure_config,
        ["example_publication", "example_presentation"],
    ),
    ("Marker Configuration", example_marker_config, ["example_markers"]),
    (
        "Smooth Curves Configuration",
        example_smooth_curves,
        ["example_smooth", "example_sharp"],
    ),
    ("Custom Line Styles", example_line_styles, ["example_line_styles"]),
]


def unregistered_examples():
    """Return the ``example_*`` functions under basic/ and advanced/ not listed."""
    registered = {func for _, func, _ in EXAMPLES}
    missing = []
    for package in (basic, advanced):
        for info in pkgutil.iter_modules(package.__path__):
            module = importlib.import_module(f"{package.__name__}.{info.name}")
            for name, obj in vars(module).items():
                if (
                    name.startswith("example_")
                    and inspect.isfunction(obj)
                    and obj.__module__ == module.__name__
                    and obj not in registered
                ):
                    missing.append(f"{module.__name__}.{name}")
    return sorted(missing)


def main(argv=None):
    """Run every example, and compile it unless ``--no-compile`` is given.

    Returns the process exit code: 0 when every example ran (and compiled),
    1 otherwise.
    """
    parser = argparse.ArgumentParser(description="Run and compile every example.")
    parser.add_argument(
        "--no-compile",
        action="store_true",
        help="only run the examples; for a machine without GLE",
    )
    args = parser.parse_args(argv)

    missing = unregistered_examples()
    if missing:
        print("Examples not listed in EXAMPLES in examples/run_and_compile.py:")
        for name in missing:
            print(f"  {name}")
        return 1

    compiler = None
    if not args.no_compile:
        from gleplot.compiler import GLECompiler

        try:
            compiler = GLECompiler()
        except RuntimeError:
            print(
                "✗ GLE not found. Install GLE, or set GLE_PATH to the gle "
                "executable; pass --no-compile to run the examples without it."
            )
            return 1
        print(f"✓ GLE compiler found: {compiler.gle_path}\n")

    output_dir = Path(__file__).parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    os.chdir(output_dir)

    print("\n" + "=" * 70)
    print("gleplot Examples - Generating Figures")
    print("=" * 70 + "\n")

    success_count = 0
    failed = []

    for name, example_func, basenames in EXAMPLES:
        try:
            print(f"[{name}]")

            # outputs/ is kept between runs: remove last run's scripts so a
            # leftover cannot stand in for one the example failed to write.
            gle_files = [Path(f"{b}.gle") for b in basenames]
            for gle_file in gle_files:
                gle_file.unlink(missing_ok=True)

            example_func()

            missing_gle = [str(f) for f in gle_files if not f.exists()]
            if missing_gle:
                print(f"  ✗ GLE file not written: {', '.join(missing_gle)}")
                failed.append(name)
                continue

            compile_failed = False
            for gle_file in gle_files if compiler else []:
                # Semi-transparent fills (rgba) fail unless GLE is invoked
                # with -cairo. Pass that only for scripts that need it so the
                # other figures keep the default PostScript device.
                needs_cairo = "rgba" in gle_file.read_text().lower()
                for fmt in ["pdf", "eps", "png"]:
                    try:
                        output = compiler.compile(
                            str(gle_file),
                            output_format=fmt,
                            dpi=150 if fmt == "png" else None,
                            cairo=needs_cairo,
                        )
                        size_kb = output.stat().st_size / 1024
                        print(f"  ✓ {fmt.upper()}: {output.name} ({size_kb:.1f} KB)")
                    except Exception as e:
                        print(f"  ✗ {fmt.upper()} compilation failed: {e}")
                        compile_failed = True

            if compile_failed:
                failed.append(name)
                print()
                continue

            success_count += 1
            print()

        except Exception as e:
            print(f"  ✗ Error: {e}")
            failed.append(name)
            traceback.print_exc()
            print()

    print("=" * 70)
    print(f"Results: {success_count}/{len(EXAMPLES)} examples completed")
    if failed:
        print(f"\nFailed: {', '.join(failed)}")
    print(f"\nOutput directory: {output_dir}")
    print("=" * 70 + "\n")

    # Non-zero when any example failed, so CI and the docs build notice.
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
