"""Sphinx configuration for the tycmd-wrapper documentation."""

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
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',
    'sphinx_autodoc_typehints',  # must be listed after napoleon
    'sphinx.ext.intersphinx',
    'myst_parser',
    'sphinx_llm.txt',
    'sphinx_sitemap',
]
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
}

autodoc_class_signature = 'separated'
autodoc_member_order = 'groupwise'
autodoc_typehints = 'description'
autodoc_default_options = {'show-inheritance': True}
autodoc_preserve_defaults = True

typehints_defaults = 'comma'

source_suffix = ['.rst', '.md']
templates_path = ['_templates']
exclude_patterns = []

napoleon_google_docstring = False
napoleon_preprocess_types = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = True
napoleon_use_keyword = False

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'shibuya'
html_baseurl = 'https://int-brain-lab.github.io/tycmd-wrapper/'
html_theme_options = {
    'color_mode': 'auto',
    'show_ai_links': False,
}
html_copy_source = False

# -- llms.txt ----------------------------------------------------------------
llms_txt_description = 'A thin Python wrapper for tycmd.'
