from datetime import date
from tycmd import __version__

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'tycmd-wrapper'
author = 'Florian Rau'
copyright = f'{date.today().year}, International Brain Laboratory'
version = '.'.join(__version__.split('.')[:3])
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.napoleon',
    # 'sphinx_toolbox.more_autodoc.typehints',
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'myst_parser',
]
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}
autodoc_typehints = 'description'
source_suffix = ['.rst', '.md']
templates_path = ['_templates']
exclude_patterns = []

napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_preprocess_types = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_rtd_theme'
html_theme_options = {
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 2,
    'includehidden': True,
    'titles_only': False
}