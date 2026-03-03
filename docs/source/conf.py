# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from pathlib import Path

# Add parent directory to path so we can import gleplot
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# -- Project information --
project = "gleplot"
copyright = "2025, gleplot contributors"
author = "gleplot contributors"

# Get version from pyproject.toml
import tomllib

with open(project_root / "pyproject.toml", "rb") as f:
    pyproject = tomllib.load(f)
    release = pyproject["project"]["version"]

version = release

# -- General configuration --
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output --
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

# Theme options
html_theme_options = {
    "logo_only": False,
    "display_version": True,
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
    "vcs_pageview_mode": "edit",
    "style_nav_header_background": "#1a1a1a",
}

# HTML context for repository links
html_context = {
    "github_user": "BenHuddart",
    "github_repo": "gleplot",
    "github_version": "main",
    "conf_py_path": "/docs/source/",
    "display_github": True,
}

# -- Options for intersphinx --
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

# -- Options for autodoc --
autodoc_typehints = "description"
autodoc_member_order = "bysource"

# -- Options for Napoleon --
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_method = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
