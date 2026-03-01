"""Example: Using gleplot's Configuration System

This example demonstrates how to customize gleplot's appearance and behavior
through the configuration system.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import gleplot as glp
import numpy as np


def example_global_config():
    """Example 1: Modify global defaults that apply to all new figures."""
    print("Example 1: Global Configuration")
    print("=" * 50)
    
    # Modify global defaults
    # Note: Use GLE font names, not matplotlib names
    # Valid GLE fonts: rm (serif), ss (sans-serif), tt (monospace), times8, psb, etc.
    print("Setting global font to 'ss' (sans-serif)...")
    glp.GlobalConfig.style.font = 'ss'  # GLE sans-serif font
    glp.GlobalConfig.style.fontsize = 12
    glp.GlobalConfig.graph.legend_position = 'tl'
    
    # Create figure (uses global defaults)
    fig = glp.figure(figsize=(8, 5))
    ax = fig.add_subplot(111)
    
    x = np.linspace(0, 2*np.pi, 50)
    ax.plot(x, np.sin(x), 'b-', label='sin(x)')
    ax.plot(x, np.cos(x), 'r--', label='cos(x)')
    ax.set_xlabel('Angle (radians)')
    ax.set_ylabel('Value')
    ax.set_title('Global Config Example')
    ax.legend()
    
    fig.savefig(Path(__file__).parent / 'output' / 'example_global_config.pdf')
    print("✓ Saved to example_global_config.pdf\n")
    
    # Reset for next example
    glp.GlobalConfig.reset()


def example_per_figure_config():
    """Example 2: Create figures with different configurations."""
    print("Example 2: Per-Figure Configuration")
    print("=" * 50)
    
    # Style for Figure 1: Publication quality
    pub_style = glp.GLEStyleConfig(
        font='rm',  # GLE serif font (Roman)
        fontsize=10,
        default_linewidth=1.5,
    )
    
    pub_graph = glp.GLEGraphConfig(
        scale_mode='auto',
        legend_position='br',
    )
    
    fig1 = glp.figure(figsize=(8, 5), style=pub_style, graph=pub_graph)
    ax1 = fig1.add_subplot(111)
    
    x = np.linspace(0, 4*np.pi, 100)
    ax1.plot(x, np.sin(x), 'b-', linewidth=1.5, label='Publication style')
    ax1.set_xlabel('x')
    ax1.set_ylabel('sin(x)')
    ax1.set_title('Publication Quality')
    ax1.legend()
    
    fig1.savefig(Path(__file__).parent / 'output' / 'example_publication.pdf')
    print("✓ Saved to example_publication.pdf")
    
    # Style for Figure 2: Presentation quality
    pres_style = glp.GLEStyleConfig(
        font='ss',  # GLE sans-serif font
        fontsize=14,
        default_linewidth=2.0,
    )
    
    pres_graph = glp.GLEGraphConfig(
        scale_mode='auto',
        legend_position='tl',
    )
    
    fig2 = glp.figure(figsize=(10, 6), style=pres_style, graph=pres_graph)
    ax2 = fig2.add_subplot(111)
    
    ax2.plot(x, np.cos(x), 'r-', linewidth=2.0, label='Presentation style')
    ax2.set_xlabel('x')
    ax2.set_ylabel('cos(x)')
    ax2.set_title('Presentation Quality')
    ax2.legend()
    
    fig2.savefig(Path(__file__).parent / 'output' / 'example_presentation.pdf')
    print("✓ Saved to example_presentation.pdf\n")


def example_marker_config():
    """Example 3: Customize marker appearance."""
    print("Example 3: Marker Configuration")
    print("=" * 50)
    
    marker_cfg = glp.GLEMarkerConfig(
        default_marker='fsquare',  # Filled squares
        msize_scale=1.2,            # Slightly larger markers
    )
    
    fig = glp.figure(figsize=(8, 5), marker=marker_cfg)
    ax = fig.add_subplot(111)
    
    x = np.random.rand(30)
    y = np.random.rand(30)
    
    ax.scatter(x, y, s=100, color='blue', label='Data points')
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_title('Custom Marker Appearance')
    ax.legend()
    
    fig.savefig(Path(__file__).parent / 'output' / 'example_markers.pdf')
    print("✓ Saved to example_markers.pdf\n")


def example_smooth_curves():
    """Example 4: Control smooth curve rendering."""
    print("Example 4: Smooth Curves Configuration")
    print("=" * 50)
    
    # Figure with smooth curves (default)
    graph_smooth = glp.GLEGraphConfig(smooth_curves=True)
    fig1 = glp.figure(figsize=(8, 4), graph=graph_smooth)
    ax1 = fig1.add_subplot(111)
    
    x = [0, 1, 2, 3, 4, 5]
    y = [1, 3, 2, 4, 3, 5]
    
    ax1.plot(x, y, 'b-', label='Smooth')
    ax1.set_title('With Smooth Curves')
    ax1.set_xlabel('x')
    ax1.set_ylabel('y')
    ax1.legend()
    
    fig1.savefig(Path(__file__).parent / 'output' / 'example_smooth.pdf')
    print("✓ Saved to example_smooth.pdf")
    
    # Figure without smooth curves
    graph_sharp = glp.GLEGraphConfig(smooth_curves=False)
    fig2 = glp.figure(figsize=(8, 4), graph=graph_sharp)
    ax2 = fig2.add_subplot(111)
    
    ax2.plot(x, y, 'r-', label='Sharp')
    ax2.set_title('Without Smooth Curves')
    ax2.set_xlabel('x')
    ax2.set_ylabel('y')
    ax2.legend()
    
    fig2.savefig(Path(__file__).parent / 'output' / 'example_sharp.pdf')
    print("✓ Saved to example_sharp.pdf\n")


def example_line_styles():
    """Example 5: Customize line style codes."""
    print("Example 5: Custom Line Styles")
    print("=" * 50)
    
    style = glp.GLEStyleConfig(
        font='rm',  # GLE Roman (serif) font
        line_style_solid=1,       # Solid
        line_style_dashed=2,      # Dashed (default)
        line_style_dotted=3,      # Dotted (default)
        line_style_dashdot=4,     # Dash-dot (default)
    )
    
    fig = glp.figure(figsize=(10, 5), style=style)
    ax = fig.add_subplot(111)
    
    x = np.linspace(0, 4*np.pi, 100)
    
    ax.plot(x, np.sin(x) + 3, 'b-', label='Solid')
    ax.plot(x, np.sin(x) + 2, 'r--', label='Dashed')
    ax.plot(x, np.sin(x) + 1, 'g:', label='Dotted')
    ax.plot(x, np.sin(x), 'm-.', label='Dash-dot')
    
    ax.set_xlim(0, 4*np.pi)
    ax.set_ylabel('f(x)')
    ax.set_title('Line Style Examples')
    ax.legend(loc='upper right')
    
    fig.savefig(Path(__file__).parent / 'output' / 'example_line_styles.pdf')
    print("✓ Saved to example_line_styles.pdf\n")


def main():
    """Run all configuration examples."""
    output_dir = Path(__file__).parent / 'output'
    output_dir.mkdir(exist_ok=True)
    
    print("\ngleplot Configuration Examples")
    print("=" * 50)
    print()
    
    try:
        from gleplot.compiler import GLECompiler
        compiler = GLECompiler()
        print(f"GLE compiler found: {compiler.gle_path}\n")
    except Exception as e:
        print(f"Warning: GLE compiler not available. Saving as .gle only.\n")
    
    example_global_config()
    example_per_figure_config()
    example_marker_config()
    example_smooth_curves()
    example_line_styles()
    
    print("=" * 50)
    print(f"All examples completed!")
    print(f"Output saved to: {output_dir}")
    print()


if __name__ == '__main__':
    main()
