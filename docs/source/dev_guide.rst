Developer Guide
===============

uv
--

This project is utilizing `uv <https://docs.astral.sh/uv/>`_ as its package manager for managing dependencies and ensuring consistent and reproducible environments.
See `uv's documentation <https://docs.astral.sh/uv/getting-started/installation/>`_ for details on installing uv.


Installing developer dependencies
---------------------------------

.. code-block:: bash

   uv sync --group dev


Running the unit-tests
----------------------

.. code-block:: bash

   uv run pytest


Coverage report
---------------

.. code-block:: bash

   uv run coverage report


Checking and formatting of code
-------------------------------

.. code-block:: bash

   uv run ruff format
   uv run ruff check --fix
   uv run mypy


Building the documentation
--------------------------

.. code-block:: bash

   uv run sphinx-build ./docs/source ./docs/build


Building the package
--------------------

.. code-block:: bash

   uv build