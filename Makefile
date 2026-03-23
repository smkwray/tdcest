TDC_VENV ?= $(HOME)/venvs/tdcest
PYTHON ?= $(TDC_VENV)/bin/python
PYTHONPYCACHEPREFIX ?= $(TDC_VENV)/pycache
PIP_CACHE_DIR ?= $(HOME)/venvs/.pip-cache
PYTEST_CACHE_DIR ?= $(TDC_VENV)/pytest-cache

export PYTHONPYCACHEPREFIX
export PIP_CACHE_DIR

bootstrap:
	python3 -m venv $(TDC_VENV)
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e .[dev]

install:
	$(PYTHON) -m pip install -e .[dev]

demo:
	$(PYTHON) scripts/run_demo.py

download:
	$(PYTHON) scripts/download_all.py --required-only

build:
	$(PYTHON) scripts/build_all.py --required-only

site-stage:
	mkdir -p site/data
	cp data/site/bundle.json site/data/bundle.json

site-serve: site-stage
	python3 -m http.server 8123

test:
	$(PYTHON) -m pytest -q -o cache_dir=$(PYTEST_CACHE_DIR)
