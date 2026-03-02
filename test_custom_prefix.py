#!/usr/bin/env python
"""Test custom data file prefix feature."""

import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / 'src'))

import gleplot as glp

output_dir = Path(__file__).parent / 'test_custom_prefix_output'
output_dir.mkdir(exist_ok=True)

print("Testing custom data file prefix feature...\n")

# Test 1: Single figure with custom prefix
print("1. Creating figure with data_prefix='mytest'...")
fig1 = glp.figure(figsize=(6, 4.5), data_prefix='mytest')
ax1 = fig1.add_subplot(111)

x = np.linspace(0, 10, 50)
ax1.plot(x, np.sin(x), color='blue', label='sin(x)')
ax1.plot(x, np.cos(x), color='red', label='cos(x)')
ax1.set_xlabel('x')
ax1.set_ylabel('y')
ax1.set_title('Test with custom prefix')
ax1.legend()

fig1.savefig(str(output_dir / 'test_mytest.gle'))
print("   ✓ Saved. Check for mytest_0.dat and mytest_1.dat\n")

# Test 2: Subplots with custom prefix
print("2. Creating subplots with data_prefix='subplot_test'...")
fig2, axes = glp.subplots(1, 3, sharey=True, figsize=(12, 4.5), data_prefix='subplot_test')

x1 = np.linspace(0, 5, 30)
axes[0].scatter(x1, x1**2, color='blue', marker='o')
axes[0].set_xlabel('Input A')
axes[0].set_ylabel('Response')
axes[0].set_title('Subplot 1')

axes[1].scatter(x1, 1.5*x1**2, color='red', marker='s')
axes[1].set_xlabel('Input B')
axes[1].set_title('Subplot 2')

axes[2].scatter(x1, 0.8*x1**2, color='green', marker='^')
axes[2].set_xlabel('Input C')
axes[2].set_title('Subplot 3')

fig2.savefig(str(output_dir / 'test_subplots.gle'))
print("   ✓ Saved. Check for subplot_test_0.dat, subplot_test_1.dat, subplot_test_2.dat\n")

# Test 3: Figure without custom prefix (uses global counter)
print("3. Creating figure without custom prefix (default behavior)...")
fig3 = glp.figure(figsize=(6, 4.5))
ax3 = fig3.add_subplot(111)

ax3.bar([1, 2, 3, 4], [10, 20, 15, 25], color='purple')
ax3.set_xlabel('Category')
ax3.set_ylabel('Value')
ax3.set_title('Test with default prefix')

fig3.savefig(str(output_dir / 'test_default.gle'))
print("   ✓ Saved. Check for data_X.dat files\n")

print("="*60)
print("All tests complete!")
print(f"Output directory: {output_dir.absolute()}")
print("="*60)

# List generated data files
data_files = sorted(output_dir.glob('*.dat'))
if data_files:
    print("\nGenerated data files:")
    for f in data_files:
        print(f"  - {f.name}")
else:
    print("\nNo data files found (check output)")
