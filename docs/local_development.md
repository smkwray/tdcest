# Local development

## Environment

```bash
make bootstrap
```

`make bootstrap` creates a virtual environment at `$HOME/venvs/tdcest`, upgrades `pip`, and installs the package in editable mode with its development dependencies. Set `TDC_VENV=/path/to/environment` to use another location, or pass `PYTHON=/path/to/python` to any `make` target to use an existing interpreter.

The `Makefile` keeps bytecode and caches outside the repository:

| Variable | Default |
|---|---|
| `PYTHONPYCACHEPREFIX` | `$HOME/venvs/tdcest/pycache` |
| `PYTEST_CACHE_DIR` | `$HOME/venvs/tdcest/pytest-cache` |
| `PIP_CACHE_DIR` | `$HOME/venvs/.pip-cache` |

## Common commands

```bash
make test    # default test suite (excludes integration tests)
make demo    # offline synthetic demonstration
make build   # download baseline series and build estimates
```

Integration tests reproduce retained local outputs and fail when their inputs are absent:

```bash
"$HOME/venvs/tdcest/bin/python" -m pytest -m integration
```

To include supporting Treasury datasets in a build:

```bash
"$HOME/venvs/tdcest/bin/python" scripts/build_all.py --include-treasury-support
```

## FRED API key

No API key is required. Without one, downloads use FRED's public graph endpoint. To use the FRED API instead, export the key in your shell:

```bash
export FRED_API_KEY=your_key_here
```

## Reserve-side input acquisition

`scripts/acquire_trc_inputs.py` runs [fiscus](https://github.com/smkwray/fiscus) through [uv](https://docs.astral.sh/uv/). It needs `uv` on the path and a fiscus checkout, passed with `--fiscus-project` as a path relative to this repository's root:

```bash
"$HOME/venvs/tdcest/bin/python" scripts/acquire_trc_inputs.py --registry trc --fiscus-project ../fiscus
```

The `--registry` option selects the input set: `trc`, `h41-ledger`, `weekly-trc`, `bank-composition`, `deficit` or `interest-rate-debt`.

## Local files

Raw downloads, processed outputs, figures, caches and environments are ignored by Git. Keep API keys and other local configuration in your shell environment or an ignored `.env` file.
