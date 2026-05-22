TDC_VENV ?= $(HOME)/venvs/tdcest
PYTHON ?= $(or $(firstword $(wildcard $(TDC_VENV)/.venv/bin/python $(TDC_VENV)/bin/python)),python3)
PYTHONPYCACHEPREFIX ?= $(TDC_VENV)/pycache
PIP_CACHE_DIR ?= $(HOME)/venvs/.pip-cache
PYTEST_CACHE_DIR ?= $(TDC_VENV)/pytest-cache
FED_COUPON_OUT ?= data/raw/support__fed_tsy_coupon_interest_proxy.csv
BANK_COUPON_OUT ?= data/raw/support__bank_tsy_coupon_interest_proxy.csv
ROW_COUPON_OUT ?= data/raw/support__row_tsy_coupon_interest_proxy.csv
CU_COUPON_OUT ?= data/raw/support__credit_union_tsy_coupon_interest_proxy.csv

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

fed-coupon-proxy:
ifdef WAMEST_ROOT
	$(PYTHON) scripts/build_fed_coupon_proxy.py --root . --wamest-root $(WAMEST_ROOT) --out $(FED_COUPON_OUT)
else
ifndef SOMA_FILE
	$(error SOMA_FILE is required, for example: make fed-coupon-proxy SOMA_FILE=path/to/soma_holdings.csv)
endif
	$(PYTHON) scripts/build_fed_coupon_proxy.py --soma-file $(SOMA_FILE) --out $(FED_COUPON_OUT)
endif

tier2-coupon-proxies:
ifndef WAMEST_ROOT
ifndef SECTOR_MATURITY_FILE
	$(error Either WAMEST_ROOT or the full set of SECTOR_MATURITY_FILE, SECTOR_PANEL_FILE, and CURVE_FILE is required.)
endif
ifndef SECTOR_PANEL_FILE
	$(error Either WAMEST_ROOT or the full set of SECTOR_MATURITY_FILE, SECTOR_PANEL_FILE, and CURVE_FILE is required.)
endif
ifndef CURVE_FILE
	$(error Either WAMEST_ROOT or the full set of SECTOR_MATURITY_FILE, SECTOR_PANEL_FILE, and CURVE_FILE is required.)
endif
	$(PYTHON) scripts/build_tier2_coupon_proxies.py tier2-coupon-proxies --sector-maturity-file $(SECTOR_MATURITY_FILE) --sector-panel-file $(SECTOR_PANEL_FILE) --curve-file $(CURVE_FILE) --bank-out $(BANK_COUPON_OUT) --row-out $(ROW_COUPON_OUT) --credit-union-out $(CU_COUPON_OUT)
else
	$(PYTHON) scripts/build_tier2_coupon_proxies.py tier2-coupon-proxies --wamest-root $(WAMEST_ROOT) --bank-out $(BANK_COUPON_OUT) --row-out $(ROW_COUPON_OUT) --credit-union-out $(CU_COUPON_OUT)
endif

tier3-support-files:
ifdef TIER3_INPUT
	$(PYTHON) scripts/build_tier3_support_files.py --root . --quarterly-input $(TIER3_INPUT) $(if $(OVERWRITE),--overwrite,) --fill-value $(or $(FILL_VALUE),0.0)
else
	$(PYTHON) scripts/build_tier3_support_files.py --root . $(if $(OVERWRITE),--overwrite,) --fill-value $(or $(FILL_VALUE),0.0)
endif

tier3-provisional-input:
	$(PYTHON) scripts/build_tier3_provisional_input.py

tier3-source-input:
ifdef TIER3_OUT
	$(PYTHON) scripts/build_tier3_source_input.py --root . --out $(TIER3_OUT) $(if $(TIER3_BASE_INPUT),--base-input $(TIER3_BASE_INPUT),) $(if $(MTS_OUTLAYS_FILE),--mts-outlays-file $(MTS_OUTLAYS_FILE),)
else
	$(PYTHON) scripts/build_tier3_source_input.py --root . $(if $(TIER3_BASE_INPUT),--base-input $(TIER3_BASE_INPUT),) $(if $(MTS_OUTLAYS_FILE),--mts-outlays-file $(MTS_OUTLAYS_FILE),)
endif

irs-bank-tax-shares:
	$(PYTHON) scripts/build_irs_soi_bank_tax_shares.py

irs-bank-minor-industry-availability:
	$(PYTHON) scripts/build_irs_soi_bank_minor_industry_availability.py

state-visa-monthly:
	$(PYTHON) scripts/build_state_visa_monthly_issuances.py

ncua-credit-union-deposits:
	$(PYTHON) scripts/build_ncua_credit_union_deposits.py

fdic-savings-institution-deposits:
	$(PYTHON) scripts/build_fdic_savings_institution_deposits.py

site-stage:
	mkdir -p site/data
	cp data/site/bundle.json site/data/bundle.json

site-serve: site-stage
	python3 -m http.server 8123

release-hygiene:
	$(PYTHON) -B scripts/check_release_hygiene.py

test:
	$(PYTHON) -m pytest -q -o cache_dir=$(PYTEST_CACHE_DIR)
