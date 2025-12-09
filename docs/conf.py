# docs/conf.py
# crossbar documentation configuration - modernized for 2025
import os
import sys
from datetime import datetime

# Add the src directory to sys.path for imports
sys.path.insert(0, os.path.abspath("../src"))

# Add .cicd/scripts to path for shared Sphinx extensions
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.cicd', 'scripts')))

# -- Project information -----------------------------------------------------
project = "crossbar"
author = "The WAMP/Autobahn/Crossbar.io OSS Project"
copyright = f"2013-{datetime.now():%Y}, typedef int GmbH (Germany)"
language = "en"

from crossbar import __version__

version = release = __version__

# -- General configuration ---------------------------------------------------
# Add the _extensions directory to Python path for custom lexers
sys.path.insert(0, os.path.abspath("_extensions"))

# Import and register the Just lexer
from just_lexer import JustLexer
from sphinx.highlighting import lexers

lexers["just"] = JustLexer()

extensions = [
    # MyST Markdown support
    "myst_parser",

    # Core Sphinx extensions
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx.ext.ifconfig",
    "sphinx.ext.doctest",

    # Modern UX extensions
    "sphinx_design",
    "sphinx_copybutton",
    "sphinxext.opengraph",
    "sphinxcontrib.images",
    "sphinxcontrib.spelling",

    # API documentation
    "autoapi.extension",

    # Shared WAMP ecosystem extensions (from .cicd submodule)
    "sphinx_auto_section_anchors",   # Stable slug-based HTML anchors
]

# Source file suffixes (both RST and MyST Markdown)
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# The master toctree document
master_doc = "index"

# Exclude patterns
exclude_patterns = ["_build", "_work", "Thumbs.db", ".DS_Store"]

# -- MyST Configuration ------------------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "tasklist",
    "attrs_block",
    "attrs_inline",
    "smartquotes",
    "linkify",
]
myst_heading_anchors = 3

# -- AutoAPI Configuration ---------------------------------------------------
autoapi_type = "python"
autoapi_dirs = ["../src/crossbar"]
autoapi_add_toctree_entry = True
autoapi_keep_files = False              # Cleaner RTD builds
autoapi_generate_api_docs = True
autoapi_options = [
    "members",
    "undoc-members",
    "private-members",
    "special-members",
    "show-inheritance",
    "show-module-summary",
    "imported-members",
]
autoapi_ignore = [
    "*/_version.py",
    "*/test_*.py",
    "*/*_test.py",
    "*/conftest.py",
    "**/test/**",
    "**/tests/**",
]
autoapi_python_use_implicit_namespaces = True
autoapi_member_order = "alphabetical"   # Predictable ordering

# -- Intersphinx Configuration -----------------------------------------------
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "twisted": ("https://docs.twisted.org/en/stable/", None),
    "txaio": ("https://txaio.readthedocs.io/en/latest/", None),
    "autobahn": ("https://autobahn.readthedocs.io/en/latest/", None),
    "zlmdb": ("https://zlmdb.readthedocs.io/en/latest/", None),
    "cfxdb": ("https://cfxdb.readthedocs.io/en/latest/", None),
}
intersphinx_cache_limit = 5

# -- HTML Output (Furo Theme) ------------------------------------------------
html_theme = "furo"
html_title = f"{project} {release}"

# Furo theme options with Noto fonts
html_theme_options = {
    # Source repository links
    "source_repository": "https://github.com/crossbario/crossbar/",
    "source_branch": "master",
    "source_directory": "docs/",
    "sidebar_hide_name": True,
    # Note: DO NOT use _static/ prefix here (Furo requirement)
    "light_logo": "img/typedefint-vectorized.svg",
    "dark_logo": "img/typedefint-vectorized-white.svg",

    # Noto fonts and Crossbar.io Bright Yellow (#ffff00) accent color
    "light_css_variables": {
        "color-brand-primary": "#d4aa00",
        "color-brand-content": "#d4aa00",
        "color-background-primary": "#fafafa",
        "color-foreground-primary": "#1a1a1a",
        "font-stack": "'Noto Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font-stack--headings": "'Noto Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "font-stack--monospace": "'Noto Sans Mono', SFMono-Regular, Menlo, Consolas, monospace",
    },
    "dark_css_variables": {
        "color-background-primary": "#1A1A1A",
        "color-foreground-primary": "#FAFAFA",
        "color-link": "#F0C359",
        "color-link--hover": "#FFBC1D",
        "color-link--visited": "#B98406",
        "color-link--visited--hover": "#EAB128",
        "color-brand-primary": "#ffff00",
        "color-brand-content": "#ffff00",
        "font-stack": "'Noto Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "font-stack--headings": "'Noto Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        "font-stack--monospace": "'Noto Sans Mono', SFMono-Regular, Menlo, Consolas, monospace",
    },
}

# Logo and favicon (optimized/generated from docs/_graphics/ by `just optimize-images`)
# Uses the Crossbar.io icon for Crossbar.io ecosystem projects
html_logo = "_static/img/crossbar_icon.svg"
html_favicon = "_static/favicon.ico"

# Static files
html_static_path = ["_static"]
html_css_files = [
    # Load Noto fonts from Google Fonts
    "https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&family=Noto+Sans+Mono:wght@400;500&display=swap",
]

# -- sphinxcontrib-images Configuration --------------------------------------
# NOTE: override_image_directive must be False to preserve standard RST image
# directive :target: option support, which is required for clickable badge
# substitutions in docs/index.rst (e.g., |PyPI| |Python| |CI| etc.)
images_config = {
    "override_image_directive": False,
}

# -- Spelling Configuration --------------------------------------------------
spelling_lang = "en_US"
spelling_word_list_filename = "spelling_wordlist.txt"
spelling_show_suggestions = True

# -- OpenGraph (Social Media Meta Tags) -------------------------------------
ogp_site_url = "https://crossbar.readthedocs.io/en/latest/"

# -- Auto Section Anchors Configuration --------------------------------------
# Force overwrite of auto-generated ids (id1, id2, etc.) with slug-based anchors
auto_section_anchor_force = True

# -- Miscellaneous -----------------------------------------------------------
todo_include_todos = True
add_module_names = False
autosectionlabel_prefix_document = True
pygments_style = "sphinx"
pygments_dark_style = "monokai"
autoclass_content = "both"
autodoc_member_order = "bysource"
