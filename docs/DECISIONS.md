# Decisions

One entry per non-obvious decision: decision, alternatives, reason. These feed the technical documentation.

## D-001 (2026-10-11) Python 3.12 venv via uv, not the system Python 3.14
The Mac's default is Python 3.14. Geo wheels (rasterio, later geopandas/igraph) lag the newest Python, and
`CLAUDE.md` asks for 3.11+. We pin a `uv` venv on 3.12 (`make setup`). Alternative: system 3.14 (risk of
missing wheels); Docker-only (slower iteration). The Docker image will use the same minor version.

## D-002 (2026-10-11) Phase 0 dependencies only
`pyproject.toml` lists only what Phase 0 uses (numpy, rasterio, httpx, pyyaml; dev: pytest, ruff, black,
pre-commit). geopandas, osmnx, python-igraph, FastAPI etc. are added in the phase that needs them, so
Phase 0 installs stay small and failures are attributable.

## D-003 (2026-10-11) `etl/noise_to_grid.py` is kept verbatim and excluded from ruff/black
It is already tested and produced the team's grids; reformatting it would make "unchanged" unverifiable.
Alternative: reformat and re-test. Revisit when the file needs a functional change.

## D-004 (2026-10-11) GIOŚ client: HTTP header, language of keys, and time handling
The API only answers when `Accept: application/ld+json` is sent (plain `application/json` returns HTTP 406,
verified on 2026-10-11). JSON-LD keys are Polish (`Identyfikator stacji`, `Wartość`, ...); the client maps
them to English dataclasses in one place (`etl/fetch/gios.py`). Current-data timestamps are naive local time
(Europe/Warsaw): they are converted to UTC with `zoneinfo`; the repeated hour at the end of DST is resolved by
processing each series in ascending order (second occurrence gets fold=1). Covered by a test for 2026-10-25,
the next DST change. Archive data (fixed UTC+1) is not fetched yet; only the current endpoint is used.

## D-005 (2026-10-11) Hourly PM10 sensor is decided from the API response
For stations 401 and 402 the sensors 2771 and 2793 are manual: `data/getData` returns HTTP 400 with
`API-ERR-100003` ("manual sensors are only available 4-8 weeks later via the archive service"). The client
treats that error as "not hourly" and keeps the candidate whose series code ends in `-1g` and has values.
Not decided by list position. Alternatives: hard-code 2770 and 2792 (breaks silently if GIOŚ renumbers).

## D-006 (2026-10-11) Station 401 has no live PM2.5
Sensor 2773 (Bujaka PM2.5) is also a manual sensor, so the archiver records `no_hourly_sensor` in `fetch_log`
for 401/PM25 and stores nothing for it (no zero filling). Consequence for `level(t)` (plan 3c): PM2.5 is
averaged over stations 400 and 402 only. This follows the plan's rule "mean over stations that reported".

## D-007 (2026-10-11) Archiver storage and idempotence
SQLite `readings` keyed on (sensor_id, ts_utc). Null values (the hour in progress is returned with value null)
are not stored. If GIOŚ later revises a value, the row is updated (the data are "not continuously verified");
`fetch_log` records every run per series with `ok` / `no_hourly_sensor` / `error`, so gaps are explicit.
Station coordinates are cached in `data/raw/gios/metadata.json` (metadata limit: 2 req/min). The archiver
uses ~9 current-data calls per run, far below the 1500/min limit.

## D-008 (2026-10-11) Scheduler: launchd on the developer Mac as a stop-gap
Hourly at minute 7 via a launchd user agent (`ops/install_launchd.sh`); launchd runs a missed job once after
wake. A laptop that sleeps loses hours; the GIOŚ current endpoint keeps ~3 days, so gaps of up to 3 days
can be back-filled by simply running the job. For a permanent host use cron on a VPS (see README/ops notes).

## D-009 (2026-10-11) Use eight GIOŚ stations, not three
Decision: add 10123 Złoty Róg, 10139 Os. Piastów, 10447 Os. Wadów, 11303 Os. Swoszowice, 16896 ul.
Kamieńskiego to 400–402. The user approved adding every station that delivers data. Probe on 2026-10-11:
each of the five has one hourly and one manual PM10 sensor (16896: hourly PM10 and NO2 only); none has
PM2.5; 20367 ul. Półłanki has no PM10/PM2.5/NO2 sensor and is not used. Alternative: keep three (the plan's
original decision). Reason: more stations make the city-level `level(t)` less dependent on one site; we
still do not interpolate a field (eight points are too few). Consequence: station coverage differs per
pollutant (PM10 eight, NO2 four, PM2.5 two), so `level(t)` must average per pollutant over the stations that
reported it, and the NO2 traffic-vs-background validation can use four stations. Station 10139 returned fewer
hourly rows (54 vs ~62) at the time of the probe; gaps are left as gaps.
