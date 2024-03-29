# -*- coding: utf-8 -*-
#
# Configuration file for the Sphinx documentation builder.
#
# Copyright (c) typedef int GmbH. All rights reserved.
#

import os
import sys

from txaio import use_twisted
use_twisted()

from crossbarfx import __version__

try:
    import sphinx_rtd_theme
except ImportError:
    sphinx_rtd_theme = None

try:
    from sphinxcontrib import spelling
except ImportError:
    spelling = None

# Check if we are building on readthedocs
RTD_BUILD = os.environ.get('READTHEDOCS', None) == 'True'

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
# import os
# import sys
# sys.path.insert(0, os.path.abspath('.'))
# sys.path.insert(0, os.path.abspath('./_extensions'))
sys.path.insert(0, os.path.abspath('.'))

# -- Project information -----------------------------------------------------

project = 'Crossbar.io'
copyright = '2018-2020, Crossbar.io Technologies GmbH'
author = 'Crossbar.io Technologies GmbH'

# The short X.Y version
version = __version__

# The full version, including alpha/beta/rc tags
release = __version__


# -- General configuration ---------------------------------------------------

# If your documentation needs a minimal Sphinx version, state it here.
#
# needs_sphinx = '1.0'

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx_autodoc_typehints',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',

    # Usage: .. thumbnail:: picture.png
    'sphinxcontrib.images',

    # https://nbsphinx.readthedocs.io/
    # 'nbsphinx',
    # 'sphinx.ext.mathjax',
]

# https://pythonhosted.org/sphinxcontrib-images/#how-to-configure
images_config = {
    'override_image_directive': False
}


# extensions not available on RTD
if spelling is not None:
    extensions.append('sphinxcontrib.spelling')
    spelling_lang = 'en_US'
    spelling_show_suggestions = False
    spelling_word_list_filename = 'spelling_wordlist.txt'

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix(es) of source filenames.
# You can specify multiple suffix as a list of string:
#
# source_suffix = ['.rst', '.md']
source_suffix = '.rst'

# The master toctree document.
master_doc = 'contents'

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = None

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path .
exclude_patterns = ['work', '_build', 'Thumbs.db', '.DS_Store', '.venv', '.wheels',
                    '**.ipynb_checkpoints']

# -- Options for HTML output -------------------------------------------------

# the following trickery is to make it build both locally and on RTD
#
# see: https://blog.deimos.fr/2014/10/02/sphinxdoc-and-readthedocs-theme-tricks-2/
#
if RTD_BUILD:
    html_context = {
        'css_files': [
            'https://media.readthedocs.org/css/sphinx_rtd_theme.css',
            'https://media.readthedocs.org/css/readthedocs-doc-embed.css',
            '_static/custom.css'
        ]
    }
else:
    if sphinx_rtd_theme:
        html_theme = 'sphinx_rtd_theme'
        html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]

        # add custom CSS on top of Sphinx RTD standard CSS
        def setup(app):
            app.add_stylesheet('custom.css')
    else:
        html_theme = 'default'

html_logo = '_static/crossbarfx.png'
full_logo = True

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    'collapse_navigation': False,

    # https://pythonhosted.org/sphinxjp.themes.basicstrap/design.html#change-sidebar-width
    # 'sidebar_span': 8, # 1(min) - 12(max)
    # 'nav_fixed': True,
    # 'nav_width': '700px',
}

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

# Custom sidebar templates, must be a dictionary that maps document names
# to template names.
#
# The default sidebars (for documents that don't match any pattern) are
# defined by theme itself.  Builtin themes are using these templates by
# default: ``['localtoc.html', 'relations.html', 'sourcelink.html',
# 'searchbox.html']``.
#
# html_sidebars = {}

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'
#pygments_style = 'monokai'
#pygments_style = 'native'
#pygments_style = 'pastie'
#pygments_style = 'friendly'


# -- Extension configuration -------------------------------------------------

# -- Options for intersphinx extension ---------------------------------------

intersphinx_mapping = {
   'py3': ('https://docs.python.org/3', None),
   'python': ('https://docs.python.org/3', None),
   'rtd': ('https://docs.readthedocs.io/en/latest/', None),
   'txaio': ('https://txaio.readthedocs.io/en/latest/', None),
   'autobahn': ('https://autobahn.readthedocs.io/en/latest/', None),
   'zlmdb': ('https://zlmdb.readthedocs.io/en/latest/', None),

   # FIXME: once we've added RTD to cfxdb
   # 'cfxdb': ('https://cfxdb.readthedocs.io/en/latest/', None),
}

# http://stackoverflow.com/questions/5599254/how-to-use-sphinxs-autodoc-to-document-a-classs-init-self-method
autoclass_content = 'both'

# http://www.sphinx-doc.org/en/stable/ext/autodoc.html#confval-autodoc_member_order
# This value selects if automatically documented members are sorted alphabetical (value
# 'alphabetical'), by member type (value 'groupwise') or by source order (value 'bysource').
# The default is alphabetical. Note that for source order, the module must be a Python module
# with the source code available.
autodoc_member_order = 'bysource'
