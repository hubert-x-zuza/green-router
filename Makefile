PY ?= .venv/bin/python
UV ?= uv
NOISE_IN ?= data/raw/noise_2022/Mapa_imisyjna_2022_JSON

.PHONY: setup fetch data noise graph layers enrich geocoder planner air-once api web test lint up

setup:  ## Python 3.12 venv with all dependencies (D-001)
	$(UV) venv --python 3.12 .venv
	$(UV) pip install --python $(PY) -e ".[dev]"

fetch:  ## download every external dataset into data/raw/ (MSIP incl. the 614 MB noise map, ArcGIS, otwartedane)
	$(PY) -m etl.fetch.msip --large
	$(PY) -m etl.fetch.otwartedane

noise:  ## 10 m noise grids (LDWN, LN)
	$(PY) etl/noise_to_grid.py --in $(NOISE_IN) --out data/processed

graph:  ## OSM walk/bike graphs + roads (Overpass, cached in data/raw/osm)
	$(PY) -m etl.graph

layers:  ## exposure grids and map overlays
	$(PY) -m etl.layers

enrich:  ## per-edge exposure + penalties -> network_<mode>.parquet
	$(PY) -m etl.enrich
	$(PY) -m etl.normalise

geocoder:
	$(PY) -m etl.geocoder

planner:
	$(PY) -m etl.planner

data:  ## rebuild everything from data/raw (run `make fetch` first on a fresh clone)
	$(MAKE) noise graph layers enrich geocoder planner
	$(PY) -m etl.air

air-once:  ## one archiver run (the hourly job calls the same thing)
	$(PY) -m etl.air

api:
	$(PY) -m uvicorn api.main:app --reload --port 8000

web:
	cd web && npm install && npm run dev

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .
	$(PY) -m black --check .
	cd web && npm run lint --if-present

up:
	docker compose up --build
