PY ?= .venv/bin/python
NOISE_IN ?= data/raw/noise

.PHONY: setup data noise air-once api web test lint up
setup:
	uv venv --python 3.12 .venv
	uv pip install --python $(PY) -e . pytest ruff black pre-commit

noise:  ## Phase 0: build the two 10 m noise grids
	$(PY) etl/noise_to_grid.py --in $(NOISE_IN) --out data/processed

air-once:  ## one archiver run (the hourly job calls the same thing)
	$(PY) -m etl.air

data:  ## Phase 1 will rebuild everything; for now only the noise grids
	$(MAKE) noise
	@echo "NOTE: graph/enrich/geocoder steps arrive in Phase 1."

api web up:
	@echo "'$@' is not implemented yet (Phase 2/3/4)."; exit 1

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
	$(PY) -m black --check .
