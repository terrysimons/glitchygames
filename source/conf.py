import os
import sys
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.abspath('../..'))

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information


project = 'GlitchyGames Engine'
copyright = '2023, Terry Simons <terry.simons@gmail.com>, Rich Saupe <sabadam32@gmail.com>'
author = 'Terry Simons <terry.simons@gmail.com>, Rich Saupe <sabadam32@gmail.com>'
release = '1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.napoleon',
]

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'classic'
html_theme_options = {
    "rightsidebar": "true",
    "relbarbgcolor": "black"
}
# html_favicon = "../../assets/documentation-icon.svg"
# html_logo = "../../assets/favicon.ico"
html_static_path = ['_static']


def setup(app: object) -> None:
    """Add custom CSS file."""
    app.add_css_file('custom.css')