"""Example demonstrating secondary y-axis (y2axis) functionality.

This example shows how to plot data with different scales on the same graph
using both the left y-axis (yaxis) and right y-axis (y2axis).
"""

import sys
from pathlib import Path

import numpy as np

# Add parent directory to path to import gleplot
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import gleplot as glp


def example_secondary_yaxis():
    """Four figures with a second data set on the right-hand y-axis
    (``yaxis='y2'``): temperature and humidity, two growth curves with a log
    scale on the right, voltages and currents in a circuit, and error bars.
    """

    # Example 1: Temperature and Humidity on same plot
    print("Creating temperature and humidity plot with secondary y-axis...")

    # Generate sample data
    days = np.arange(1, 31)  # 30 days
    temperature = (
        20 + 5 * np.sin(2 * np.pi * days / 10) + np.random.randn(30) * 1.5
    )  # °C
    humidity = 60 + 15 * np.cos(2 * np.pi * days / 12) + np.random.randn(30) * 5  # %

    fig = glp.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)

    # Plot temperature on left y-axis (default)
    ax.plot(
        days, temperature, color="red", linewidth=2, label="Temperature", marker="o"
    )

    # Plot humidity on right y-axis (y2)
    ax.plot(
        days,
        humidity,
        color="blue",
        linewidth=2,
        label="Humidity",
        marker="s",
        yaxis="y2",
    )

    # Configure axes
    ax.set_xlabel("Day of Month")
    ax.set_ylabel("Temperature (°C)", axis="y")
    ax.set_ylabel("Humidity (%)", axis="y2")
    ax.set_title("Daily Temperature and Humidity")

    # Set y-axis limits
    ax.set_ylim(10, 30, axis="y")  # Temperature range
    ax.set_ylim(30, 90, axis="y2")  # Humidity range

    ax.legend()

    # Save the figure
    output_file = "secondary_yaxis_temp_humidity.gle"
    fig.savefig_gle(output_file)
    print(f"Saved: {output_file}")

    # Example 2: Exponential growth with different scales
    print("\nCreating exponential growth plot with log scale on y2axis...")

    x = np.linspace(0, 5, 50)
    y1 = x**2  # Quadratic growth
    y2 = np.exp(x)  # Exponential growth

    fig2 = glp.figure(figsize=(10, 6))
    ax2 = fig2.add_subplot(111)

    # Plot quadratic on left axis
    ax2.plot(x, y1, color="green", linewidth=2, label="Quadratic: x²")

    # Plot exponential on right axis with log scale
    ax2.plot(x, y2, color="purple", linewidth=2, label="Exponential: $e^x$", yaxis="y2")

    ax2.set_xlabel("x")
    ax2.set_ylabel("x²", axis="y")
    ax2.set_ylabel("$e^x$", axis="y2")
    ax2.set_title("Comparing Growth Rates")

    # Set logarithmic scale for y2axis
    ax2.set_yscale("log", axis="y2")

    ax2.legend()

    output_file2 = "secondary_yaxis_growth.gle"
    fig2.savefig_gle(output_file2)
    print(f"Saved: {output_file2}")

    # Example 3: Multiple datasets on each axis
    print("\nCreating plot with multiple datasets on each axis...")

    t = np.linspace(0, 10, 100)
    voltage1 = 5 * np.sin(t)
    voltage2 = 3 * np.sin(t + np.pi / 4)
    current1 = 2 * np.cos(t)
    current2 = 1.5 * np.cos(t - np.pi / 3)

    fig3 = glp.figure(figsize=(10, 6))
    ax3 = fig3.add_subplot(111)

    # Plot voltages on left y-axis
    ax3.plot(t, voltage1, color="red", linewidth=2, label="Voltage 1", linestyle="-")
    ax3.plot(
        t, voltage2, color="darkred", linewidth=2, label="Voltage 2", linestyle="--"
    )

    # Plot currents on right y-axis
    ax3.plot(
        t,
        current1,
        color="blue",
        linewidth=2,
        label="Current 1",
        linestyle="-",
        yaxis="y2",
    )
    ax3.plot(
        t,
        current2,
        color="darkblue",
        linewidth=2,
        label="Current 2",
        linestyle="--",
        yaxis="y2",
    )

    ax3.set_xlabel("Time (s)")
    ax3.set_ylabel("Voltage (V)", axis="y")
    ax3.set_ylabel("Current (A)", axis="y2")
    ax3.set_title("AC Circuit: Voltage and Current vs Time")
    ax3.legend()

    output_file3 = "secondary_yaxis_circuit.gle"
    fig3.savefig_gle(output_file3)
    print(f"Saved: {output_file3}")

    # Example 4: Scatter plot with errorbar on y2axis
    print("\nCreating errorbar plot with secondary y-axis...")

    x_data = np.array([1, 2, 3, 4, 5])
    y_left = np.array([10, 15, 13, 17, 16])
    y_right = np.array([100, 120, 110, 130, 125])
    yerr_right = np.array([5, 8, 6, 7, 6])

    fig4 = glp.figure(figsize=(10, 6))
    ax4 = fig4.add_subplot(111)

    # Scatter on left axis
    ax4.scatter(x_data, y_left, color="orange", s=100, label="Measurement A")

    # Errorbar on right axis
    ax4.errorbar(
        x_data,
        y_right,
        yerr=yerr_right,
        color="teal",
        marker="o",
        markersize=8,
        label="Measurement B",
        capsize=5,
        yaxis="y2",
    )

    ax4.set_xlabel("Sample Number")
    ax4.set_ylabel("Measurement A (units)", axis="y")
    ax4.set_ylabel("Measurement B (units)", axis="y2")
    ax4.set_title("Dual-Axis Measurements with Error Bars")
    ax4.legend()

    output_file4 = "secondary_yaxis_errorbar.gle"
    fig4.savefig_gle(output_file4)
    print(f"Saved: {output_file4}")

    print("\nAll examples created successfully!")
    print("\nUsage notes:")
    print(
        "- Use yaxis='y2' parameter in plot(), scatter(), or errorbar() to plot on right axis"
    )
    print("- Use ax.set_ylabel(label, axis='y2') to set right axis label")
    print("- Use ax.set_ylim(min, max, axis='y2') to set right axis limits")
    print("- Use ax.set_yscale('log', axis='y2') to set right axis scale")


def example_twin_axes():
    """matplotlib's ``twinx`` and ``twiny``. ``twinx`` returns a view of the
    same axes bound to GLE's right-hand ``y2axis``, and ``twiny`` one bound to
    the top ``x2axis``; each has its own limits and label. Here the right axis
    carries a second quantity and the top axis gives the temperature in
    degrees Celsius.
    """
    print("Creating example: Twin axes...")

    fig, ax = glp.subplots(figsize=(8, 6))

    T = np.linspace(5, 300, 120)  # kelvin
    resistivity = 2 + 0.05 * T + 40 / (1 + np.exp((T - 60) / 8))
    susceptibility = 1 / (T + 15)

    ax.plot(T, resistivity, color="C0", label="resistivity")
    ax.set_xlim(0, 300)
    ax.set_ylim(0, 60)
    ax.set_xlabel("Temperature (K)")
    ax.set_ylabel(r"Resistivity ($\mu\Omega$ cm)")

    right = ax.twinx()
    right.plot(T, 1000 * susceptibility, "--", color="C3", label="susceptibility")
    right.set_ylim(0, 60)
    right.set_ylabel(r"Susceptibility ($10^{-3}$ emu/mol)")

    # The top axis is the same temperature in Celsius: a shifted copy.
    top = ax.twiny()
    top.set_xlim(-273.15, 300 - 273.15)
    top.set_xlabel("Temperature (C)")

    ax.legend(loc="upper right")

    fig.savefig("example_twin_axes.gle")
    print("  ✓ Saved to example_twin_axes.gle")


if __name__ == "__main__":
    example_secondary_yaxis()
    example_twin_axes()
