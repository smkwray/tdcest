# Local Development

This project is set up to keep local environments, caches, and secrets out of the repo tree.

## External environment

Use an external virtual environment under `$HOME/venvs`:

```bash
make bootstrap
```

That target creates `$HOME/venvs/tdcest`, upgrades `pip`, and installs the package in editable mode with dev dependencies.

The `Makefile` also keeps Python bytecode and pytest cache outside the repo:

- `PYTHONPYCACHEPREFIX=$HOME/venvs/tdcest/pycache`
- `PYTEST_CACHE_DIR=$HOME/venvs/tdcest/pytest-cache`
- `PIP_CACHE_DIR=$HOME/venvs/.pip-cache`

## Private local files

Put all private or local-only material under `do/`. This directory is gitignored.

Examples:

- `do/.env`
- copied API keys
- unpublished notes
- scratch analysis files
- local release checklists

## FRED API key

The public repo and default CI do not require a FRED API key.

For manual live-data runs, load the key from `do/.env` or your shell:

```bash
export FRED_API_KEY=your_key_here
```

## Common commands

```bash
make test
make demo
make build
```

If you want supporting Treasury datasets in a live-data build:

```bash
$HOME/venvs/tdcest/bin/python scripts/build_all.py --include-treasury-support
```
