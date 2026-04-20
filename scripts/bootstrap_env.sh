#!/usr/bin/env bash
set -euo pipefail

TDC_VENV="${TDC_VENV:-$HOME/venvs/tdcest}"
PIP_CACHE_DIR="${PIP_CACHE_DIR:-$HOME/venvs/.pip-cache}"

mkdir -p "$(dirname "$TDC_VENV")" "$PIP_CACHE_DIR"
python3 -m venv "$TDC_VENV"
"$TDC_VENV/bin/python" -m pip install --upgrade pip
"$TDC_VENV/bin/python" -m pip install -e '.[dev]'

cat <<EOF
Bootstrapped environment at $TDC_VENV
Use:
  $TDC_VENV/bin/python -m pytest -q -o cache_dir=$TDC_VENV/pytest-cache
  $TDC_VENV/bin/python scripts/run_demo.py
EOF
