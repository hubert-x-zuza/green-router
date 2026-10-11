# CLAUDE.md — Zdrowa Trasa

Read this file first, then `docs/PLAN.md` (the full implementation plan) and `data/manifest.yml` (every external dataset, with URLs, IDs and status). If this file and the plan disagree, the plan's sections 3a–3c are the latest decisions; tell the user about the conflict and fix whichever file is outdated.

## What we are building

A web app for the Kraków competition "Open Data App" (organiser: Gmina Miejska Kraków). It routes people on foot or by bike along **healthier streets** (lower noise, cleaner air, more greenery) and shows the trade-off in minutes. A second tab gives city planners a ranked list of street segments where high exposure meets many sensitive users (schools, stops, residents).

Reference (inspiration only, MIT licence, cite it in docs): `DigitalGeographyLab/green-paths-2`. We do not use r5py or Java.

## Hard constraints

- Team of 2–5. Jury scoring: city impact 30 %, data use 20 %, innovation 15 %, architecture 15 %, business potential 10 %, UX 5 %, UI 5 %. Do not over-invest in visual polish.
- **Dates:** paper application form must arrive at ul. Basztowa 20 by **Fri 23 Oct 2026, 14:30** (the rules say 25 Oct, which is a Sunday). Feature freeze **Tue 3 Nov**. Submission email to konkursopendata@um.krakow.pl by **Thu 5 Nov**, aim for Wed 4 Nov.
- Submission package: title; description PDF (max 2 pages); working demo; launch instructions; technical documentation (technologies, data used, architecture, development possibilities). Written in **Polish**. UI is Polish by default, English optional.
- Everything must be original work and respect data licences (see "Data rules").

## Scope

**In:** noise, live air quality, greenery, optionally drinking fountains; walking and cycling; Kraków only; route planner tab; planner dashboard tab; PL/EN.

**Out (do not build or reintroduce without asking the user):**
- The urban heat-island layer. It is parked (plan Appendix A, `mwc_decode.py`). No seasonal/summer logic.
- PostGIS or pgRouting in the MVP (document them as the scale-up path).
- Public transport routing (GTFS is used only as a sensitive-user proxy in the planner view; last-leg routing is a stretch idea, not in scope).
- User accounts, stored user locations, analytics cookies.

## Key technical decisions

- **Internal CRS: EPSG:2178.** All city data arrives in 2178. Reproject OSM on load and convert to WGS84 at the API boundary.
- **Stack:** Python 3.11+, geopandas, shapely, pyproj, rasterio, numpy, pandas, pyarrow, osmnx (graph), python-igraph (routing; networkx as fallback), FastAPI + Pydantic. Frontend: React + TypeScript + Vite + MapLibre GL JS + i18next. Packaging: Docker Compose. Storage: GeoParquet/Parquet + SQLite files, loaded into memory at API start.
- **Cost function:** `cost(e) = length_m / speed_mps(mode) · (1 + Σ_k w_k(profile) · p_k(e, t))`, penalties `p_k ∈ [0, 1]`, weights from `config/profiles.yml`. Profiles: Fastest, Balanced, Quiet, Clean air, Green & water. Guard rail `max_detour_pct` default 30. Each request returns fastest, healthiest-within-limit and balanced routes, with metrics and a trade-off sentence.
- **Noise:** use `etl/noise_to_grid.py` (already tested). 10 m grid per indicator (LDWN primary, LN night), road + rail energy-combined, lowest class contributes nothing, floor 50 dB (LDWN) / 45 dB (LN), nodata outside the city. Raw files are about 1.4 GB: never commit them. The ~1 MB output grids may be committed.
- **Greenery:** city "Mapa zieleni" (class_name: 200 tall, 300 low, 400 sports/allotments). Per edge, share of each class within a 30 m buffer; `green_score = 1.0·tall + 0.4·low + 0.2·sports`, clamped; `p_green = 1 − green_score`. Weights are starting values in config.
- **Air:** eight GIOŚ stations are used (API IDs 400 Al. Krasińskiego, 401 Bujaka, 402 Bulwarowa, plus 10123 Złoty Róg, 10139 Os. Piastów, 10447 Os. Wadów, 11303 Os. Swoszowice, 16896 ul. Kamieńskiego; decided 2026-10-11 after probing the API, see `config/air_stations.yml`). Pollutants PM10, PM2.5, NO₂, but not every station has all three: PM2.5 only at 400 and 402, NO₂ at 400, 401, 402 and 16896, PM10 at all eight. `level(t)` is a city-level index (normalised per pollutant, mean over the stations that reported that pollutant, max across pollutants). Spatial pattern comes from a static OSM traffic-proximity proxy: `air_penalty = clamp(level(t) · (a + (1 − a) · traffic_proximity), 0, 1)`, `a` in config (start 0.3). Do **not** interpolate a city-wide field from a handful of points. Label the air term "indicative"; it mainly reflects traffic-related exposure.
- **Geocoder:** local SQLite FTS index built from the city's address points and streets (not Nominatim). Handle Polish diacritics and "ul."/"al." prefixes.
- **Coverage:** OSM graph for the Kraków boundary plus about 500 m. Edges outside data coverage get `data_coverage = false` and a neutral penalty; the UI warns. Origin/destination outside the city get a clear "Kraków only" message.
- **Planner score:** `priority = exposure_severity × sensitive_presence` per edge or ~100–200 m cell, aggregated to districts, with a short explanation per item. What-if simulation is a stretch goal.

## Data rules

1. **Never invent a URL, endpoint, dataset name or column name.** If it is not in `data/manifest.yml` or verified from the real source, write the question in `docs/OPEN_QUESTIONS.md` and ask the user.
2. Every dataset gets a manifest entry: provider, URL, CRS, fields used, date of data creation, date obtained, licence/terms, citation line, status. Update it as you verify things.
3. Team statement: the city's resources may be used provided the source is cited. Keep the exact regulamin wording in `docs/licences/`. GIOŚ requires a clearly visible source credit. **OpenStreetMap is ODbL**: attribute it, and if a processed edge table derived from OSM is published it falls under share-alike (publish under ODbL or ship only the ETL scripts).
4. The "About data" panel in the UI is generated from the manifest (provider, dataset, dates, link).
5. Time: store every timestamp in UTC. GIOŚ archive data is fixed UTC+1, current data is local time with DST: normalise on ingest.
6. GIOŚ API: base `https://api.gios.gov.pl/pjp-api/v1/rest` (old endpoints were withdrawn). Current data allows 1500 requests/min, but metadata and archive only 2/min: cache station metadata. Stations 401 and 402 each list **two PM10 sensors**: call both and keep the one with hourly values. Never show stale air data as live; show a "data from HH:MM" badge.
7. ArcGIS REST layers (noise, green): page with `resultOffset`/`resultRecordCount`, `orderByFields=objectid`, `outSR=2178`, `f=geojson`. Read the layer id from the service JSON, never hard-code it.
8. Missing data is explicit: never silently fill with zeros.

## Working agreement

- Work **phase by phase** as in `docs/PLAN.md` section 7. Do not start a phase until the previous phase's acceptance criteria pass. Commit at the end of each task with a clear message.
- Record every non-obvious decision in `docs/DECISIONS.md` (decision, alternatives, reason, one paragraph). These feed the technical documentation.
- Ask the user **one focused question at a time**, and only when it blocks progress. Otherwise choose a sensible default, state it, and record it.
- Do not claim something works unless you ran it. Say what was tested and what was not.
- Keep it small: prefer boring, well-known tools. This is a four-week prototype.
- No medical claims. Use "exposure index" and a short disclaimer.
- Privacy: no storage of user locations; route requests are processed and discarded; logs contain no coordinates.

## Conventions

- Python: type hints, `ruff` + `black`, `pytest`. Thresholds, weights, buffers and profile values live in `config/*.yml`, never as magic numbers in code.
- ETL steps are idempotent and deterministic. `make data` rebuilds everything from scratch.
- Tests never call live external APIs; use recorded fixtures. Required tests: cost function; weights 0 gives the shortest path; a high noise weight never increases mean noise; ~10 golden routes between landmarks; API contract tests.
- API: Pydantic models, versioned prefix `/api/v1`, OpenAPI docs on.
- Frontend: TypeScript strict, no hard-coded strings (i18n keys), mobile-first, keyboard accessible, adequate contrast.
- Base map: a free vector tile source with proper attribution, or self-hosted PMTiles. Do **not** hit the public OSM tile servers for production load.

## Repository layout

```
CLAUDE.md  README.md  Makefile  docker-compose.yml  .env.example
config/              # profiles.yml, thresholds, weights
data/                # manifest.yml (committed); raw/ and processed/ (gitignored, small grids excepted)
etl/                 # fetch/, graph.py, enrich.py, normalise.py, noise_to_grid.py, air.py, geocoder.py, planner.py
api/                 # FastAPI app, routing.py, costs.py, models.py, tests/
web/                 # React app
docs/                # PLAN.md, DECISIONS.md, OPEN_QUESTIONS.md, data-sources.md, architecture.md, methodology.md, licences/, submission/
```

Make targets to provide: `make data`, `make api`, `make web`, `make test`, `make lint`, `make up` (docker compose).

## Start here

1. Create the repo skeleton above, copy the plan to `docs/PLAN.md`, the manifest to `data/manifest.yml`, and `noise_to_grid.py` to `etl/`. Do not copy `mwc_decode.py` (parked).
2. Finish Phase 0 (plan section 7): the open checks are listed in plan sections 3a–3c, tasks 0.1 to 0.6. In particular: confirm the green layer id and class values; station coordinates, types and a live reading per sensor; fountain attributes; IOŚ-PIB forecast terms; which roads the noise map models.
3. Start the **hourly air-quality archiver early** (running since 2026-10-11) so there is history before submission.
4. Then Phase 1 (ETL and edge enrichment). Report acceptance-criteria results to the user before moving on.
