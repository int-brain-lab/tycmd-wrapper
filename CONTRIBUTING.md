Contributing
============

uv
--

This project uses [uv](https://docs.astral.sh/uv/) as its package manager, for managing
dependencies and ensuring consistent, reproducible environments. See uv's
[installation instructions](https://docs.astral.sh/uv/getting-started/installation/) for
details on installing it.

Installing developer dependencies
----------------------------------

```shell
uv sync --group dev
```

Building tycmd
--------------

The bundled `tycmd` binary isn't committed to this repository - it's built from source
automatically whenever it's needed (e.g. by `uv sync`, `uv build`, or `uv run tox`): the first
time, and again whenever the pinned version (`_TYCMD_VERSION` in `tycmd/__init__.py`), the
pinned commit (`_TYCMD_COMMIT`) or the build settings recorded by `_build_stamp()` in
`pdm_build.py` change (anything else needs a manual rebuild: delete `bin/`). The build checks
that rygel's release tag still points to the pinned commit - update both together. Building it
requires `git` and a C++ compiler; on Linux you'll also need `libudev-dev`.

Running the test suite
-----------------------

Tests, linting, and type checking all run through [tox](https://tox.wiki/) (via the
[tox-uv](https://github.com/tox-dev/tox-uv) plugin), across every supported Python version -
uv provisions whichever interpreters are missing automatically:

```shell
uv run tox -p
```

Coverage report
---------------

After running the test suite, a merged coverage report is available via:

```shell
uv run coverage report
```

Checking and formatting code
-----------------------------

```shell
uv run ruff format
uv run ruff check --fix
uv run mypy
```

Building the documentation
---------------------------

```shell
uv run sphinx-build -b dirhtml docs/source docs/build
```

Building the package
---------------------

```shell
uv build
```

CI dependencies
---------------

GitHub Actions are pinned to commit SHAs and updated weekly by Dependabot. The manylinux images
(`<image>:<tag>@sha256:<digest>`) aren't covered by Dependabot - bump them by hand, with a tag
and its digest from [quay.io](https://quay.io/organization/pypa), everywhere in
`.github/workflows/`.
