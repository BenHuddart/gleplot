# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import sys
from pathlib import Path

# Add parent directory to path so we can import gleplot
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

# -- Project information --
project = "gleplot"
copyright = "2026, gleplot contributors"
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
    "sphinx.ext.napoleon",
    "myst_parser",
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output --
html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["api_fonts.css"]

# Theme options
html_theme_options = {
    "logo_only": False,
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


# -- Example gallery --
# The gallery is generated from EXAMPLES in examples/run_and_compile.py, so it
# shows exactly the examples CI runs, with their code as it is in the file.
import ast
import inspect
import textwrap

from docutils import nodes
from docutils.statemachine import StringList
from PIL import Image
from sphinx.util.docutils import SphinxDirective
from sphinx.util.nodes import nested_parse_with_titles

sys.path.insert(0, str(project_root / "docs"))
from prepare_gallery import GALLERY_DIR, GALLERY_WIDTH, registered_examples

SOURCE_URL = "https://github.com/BenHuddart/gleplot/blob/main/"


def _code_without_docstring(func):
    """Return the source of ``func`` without its docstring, which is the caption."""
    lines, _ = inspect.getsourcelines(func)
    function = ast.parse(textwrap.dedent("".join(lines))).body[0]
    if ast.get_docstring(function) is None:
        raise ValueError(
            f"{func.__module__}.{func.__name__} has no docstring; the gallery "
            "uses an example's docstring as its caption"
        )
    docstring = function.body[0]
    return "".join(lines[: docstring.lineno - 1] + lines[docstring.end_lineno :])


class ExampleGallery(SphinxDirective):
    """One section per registered example: caption, images, code, source link."""

    def run(self):
        rst = []
        self.env.note_dependency(str(project_root / "examples" / "run_and_compile.py"))
        for title, func, basenames in registered_examples():
            path = Path(inspect.getsourcefile(func)).resolve()
            self.env.note_dependency(str(path))
            relpath = path.relative_to(project_root).as_posix()
            code = _code_without_docstring(func)
            rst += [title, "-" * len(title), "", inspect.getdoc(func), ""]
            for basename in basenames:
                rst += self._image(f"{basename}.webp", title)
            rst += [".. raw:: html", "", "   <details><summary>Code</summary>", ""]
            rst += [".. code-block:: python", ""]
            rst += [f"   {line}" if line.strip() else "" for line in code.splitlines()]
            rst += ["", ".. raw:: html", "", "   </details>", ""]
            rst += [f"Source: `{relpath} <{SOURCE_URL}{relpath}>`_", ""]
        container = nodes.Element()
        nested_parse_with_titles(
            self.state, StringList(rst, source=self.get_source_info()[0]), container
        )
        return container.children

    def _image(self, name, alt):
        """Return the image directive for one gallery image.

        Unitless ``:width:`` and ``:height:`` become the ``<img>`` width and
        height attributes, which reserve the image's space before it arrives,
        so ``loading="lazy"`` defers the images below the fold.
        """
        path = GALLERY_DIR / name
        size = []
        if path.is_file():  # a missing image is reported by the image directive
            self.env.note_dependency(str(path))
            with Image.open(path) as img:
                height = round(GALLERY_WIDTH * img.height / img.width)
            size = [f"   :width: {GALLERY_WIDTH}", f"   :height: {height}"]
        return [
            f".. image:: /_static/gallery/{name}",
            *size,
            "   :align: center",
            "   :loading: lazy",
            f"   :alt: {alt}",
            "",
        ]


def setup(app):
    app.add_directive("example-gallery", ExampleGallery)
