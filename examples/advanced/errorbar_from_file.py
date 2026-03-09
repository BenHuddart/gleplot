"""Error bar plotting from file example.

Demonstrates how to create plots that reference data columns directly
from an existing data file, avoiding the need to generate additional
data_*.dat files.
"""

import sys
import numpy as np
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import gleplot as glp


def example_errorbar_from_file():
    """Example: Plot error bars by referencing columns in an existing data file."""
    print("Creating example: Error bars from file...")

    # Create a data file with experimental measurements
    data_file = Path('experimental_data.dat')
    
    with open(data_file, 'w') as f:
        f.write("! Experimental measurements\n")
        f.write("! Column map:\n")
        f.write("!   c1 = Temperature (K)\n")
        f.write("!   c2 = Resistance (Ohm)\n")
        f.write("!   c3 = Resistance Error\n")
        f.write("!   c4 = Voltage (V)\n")
        f.write("!   c5 = Voltage Error\n")
        f.write("!\n")
        f.write("! Temp   Resistance  R_Error  Voltage  V_Error\n")
        
        # Generate some synthetic data
        np.random.seed(42)
        temps = np.linspace(100, 400, 10)
        for T in temps:
            R = 50 + 0.2 * T + np.random.randn() * 2
            R_err = 0.5 + np.random.rand() * 0.3
            V = 2.0 + 0.005 * T + np.random.randn() * 0.1
            V_err = 0.05 + np.random.rand() * 0.02
            f.write(f"{T:8.1f} {R:12.3f} {R_err:10.3f} {V:10.3f} {V_err:10.3f}\n")
    
    # Create a figure with two subplots sharing x-axis
    fig, axes = glp.subplots(2, 1, figsize=(8, 10), sharex=True)
    
    # Top plot: Resistance vs Temperature (columns 1, 2, 3)
    axes[0].errorbar_from_file(
        str(data_file),
        x_col=1,        # Temperature
        y_col=2,        # Resistance
        yerr_col=3,     # Resistance error
        color='blue',
        marker='o',
        markersize=5,
        capsize=3,
        label='Resistance'
    )
    axes[0].set_ylabel('Resistance (Ω)')
    axes[0].set_title('Experimental Data from File')
    axes[0].legend()
    
    # Bottom plot: Voltage vs Temperature (columns 1, 4, 5)
    axes[1].errorbar_from_file(
        str(data_file),
        x_col=1,        # Temperature
        y_col=4,        # Voltage
        yerr_col=5,     # Voltage error
        color='red',
        marker='s',
        markersize=5,
        capsize=3,
        label='Voltage'
    )
    axes[1].set_xlabel('Temperature (K)')
    axes[1].set_ylabel('Voltage (V)')
    axes[1].legend()
    
    fig.savefig('example_errorbar_from_file.gle')
    print(f"  ✓ Saved to example_errorbar_from_file.gle")
    print(f"  ✓ Data file: {data_file}")
    print("  ✓ No additional data_*.dat files generated!")


def example_dual_axis_from_file():
    """Example: Dual y-axis plot using file column references."""
    print("Creating example: Dual axis from file...")

    # Create a data file
    data_file = Path('climate_data.dat')
    
    with open(data_file, 'w') as f:
        f.write("! Climate measurements\n")
        f.write("! c1=Month  c2=Temp(C)  c3=T_err  c4=Humidity(%)  c5=H_err\n")
        f.write("!\n")
        
        # Generate synthetic climate data
        np.random.seed(123)
        for month in range(1, 13):
            temp = 15 + 10 * np.sin((month - 4) * np.pi / 6) + np.random.randn()
            t_err = 0.5 + np.random.rand() * 0.3
            humidity = 65 + 15 * np.cos((month - 1) * np.pi / 6) + np.random.randn() * 2
            h_err = 2 + np.random.rand()
            f.write(f"{month:4.0f} {temp:10.2f} {t_err:8.2f} {humidity:12.1f} {h_err:8.2f}\n")
    
    # Create figure with dual y-axis
    fig = glp.figure(figsize=(10, 6))
    ax = fig.add_subplot(111)
    
    # Temperature on left axis (blue)
    ax.errorbar_from_file(
        str(data_file),
        x_col=1,
        y_col=2,
        yerr_col=3,
        color='blue',
        marker='o',
        markersize=6,
        capsize=3,
        yaxis='y',
        label='Temperature'
    )
    
    # Humidity on right axis (red) 
    ax.errorbar_from_file(
        str(data_file),
        x_col=1,
        y_col=4,
        yerr_col=5,
        color='red',
        marker='s',
        markersize=6,
        capsize=3,
        yaxis='y2',
        label='Humidity'
    )
    
    ax.set_xlabel('Month')
    ax.set_ylabel('Temperature (°C)', axis='y')
    ax.set_ylabel('Humidity (%)', axis='y2')
    ax.set_title('Climate Data - Dual Axis from File')
    ax.legend()
    
    fig.savefig('example_dual_axis_from_file.gle')
    print(f"  ✓ Saved to example_dual_axis_from_file.gle")
    print(f"  ✓ Data file: {data_file}")


if __name__ == '__main__':
    example_errorbar_from_file()
    print()
    example_dual_axis_from_file()
