Developer Guide
===============

PDM
---

This project is utilizing `PDM <https://pdm-project.org/>`_ as its package manager for managing dependencies and ensuring consistent and reproducible environments.
See `PDM's documentation <https://pdm-project.org/en/latest/#recommended-installation-method>`_ for details on installing PDM.


Installing developer dependencies
---------------------------------

.. code-block:: bash

   pdm sync -d


Running the unit-tests
----------------------

.. code-block:: bash

   pdm run pytest


Coverage report
---------------

.. code-block:: bash

   pdm run coverage report


Checking and formatting of code
-------------------------------

.. code-block:: bash

   pdm run ruff format
   pdm run ruff check --fix
   pdm run mypy


Building the documentation
--------------------------

.. code-block:: bash

   pdm run sphinx-build ./docs/source ./docs/build


Building the package
--------------------

.. code-block:: bash

   pdm build