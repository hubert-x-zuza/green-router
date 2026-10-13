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

## D-010 (2026-10-13) City data: catalogue zip files first, ArcGIS REST only where no file exists
Noise, districts, address points, streets and fountains come from the MSIP catalogue's direct
downloads (`msip.um.krakow.pl/Dane/*.zip`, URLs read from the catalogue pages). The green map and the
city boundary have no file, so they are paged from the ArcGIS REST layer, with the layer id resolved
by name. Alternative: REST for everything (slower, more requests). The MSIP regulamin forbids
redistributing the map *services* and requires written consent for continuous, organised use of them
in another system (docs/licences/msip_regulamin.md). Therefore the ETL downloads once and the app
never proxies or embeds an MSIP service; it serves only its own derived values. Open question A4.

## D-011 (2026-10-13) OSM through osmnx/Overpass for the city boundary + 500 m (plan B10)
Alternative: Geofabrik Małopolskie extract, clipped. Overpass needs no 200 MB download and no extra
tool; the raw graphs are cached as GraphML in data/raw/osm so `make data` does not hit Overpass again.
The extract date is the download date (source.json).

## D-012 (2026-10-13) Directed edges; bike respects one-way streets plus OSM contraflow
Walk edges exist in both directions (osmnx default for walking). Bike edges follow `oneway`, and a
reverse edge is added where `oneway:bicycle=no` or `cycleway=opposite*` (2127 edges). Only the
largest strongly connected component is kept so every snapped point can reach every other.
Found while testing: overriding `useful_tags_way` without `oneway` made osmnx treat every street as
two-way; the tag list now includes `oneway` and `junction`.

## D-013 (2026-10-13) Enrichment on a common 10 m grid instead of polygon overlays per edge
Every layer is a 10 m raster in EPSG:2178: the 30 m green buffer is a disc filter over the class
masks, the traffic proxy and the fountain distance are Euclidean distance transforms. Each edge is
sampled every 15 m at segment midpoints (so the busy crossing at an edge's end does not dominate).
Alternative: buffer each edge and intersect polygons (exact but ~100x slower). Error is below the
10 m resolution of the inputs. The whole enrichment of 600 k edges takes ~5 s.

## D-014 (2026-10-13) Greenery from the 2016 MONIT-AIR atlas, the only city source
The "Mapa zieleni" layer belongs to "MONIT-AIR Atlas 2016" (2014 orthophoto). It is the only
classified greenery the city publishes; ESA WorldCover (10 m, 2021) was the alternative, but it is
not Kraków data and has no tall/low distinction. Stated as a limitation in the UI and the docs.

## D-015 (2026-10-13) Air index normalisation and stale data
`level(t)`: per pollutant, mean over stations whose newest value is within 3 h of the newest hour,
divided by the lower bound of the GIOŚ "very bad" band (PM10 150, PM2.5 110, NO2 400 µg/m³; to verify,
A5), max across pollutants. If the newest data are older than 3 h the API sets the air term to 0 for
routing and the UI says "no current air data" (plan: never show stale data as live). Alternative:
keep using the last good value; rejected because a smog episode can end within hours.

## D-016 (2026-10-13) Three routes per request
fastest (all weights 0), healthiest (the chosen profile; when it is Fastest or Balanced, the
`healthiest` profile from profiles.yml, otherwise the two would coincide), balanced. Identical routes
are marked `same_as` instead of being drawn twice.

## D-017 (2026-10-13) Detour guard by bisection on a weight scale
If the profile's route takes longer than fastest x (1 + max_detour_pct), the weights are scaled by
s in [0, 1] and the largest s that respects the limit is found by bisection (8 shortest-path runs,
< 0.1 s). Alternative: constrained shortest path (exact but NP-hard in general). The route reports
`weights_scale` and the UI says "limited by the detour cap".

## D-018 (2026-10-13) Trade-off figures are relative to penalties, led by total exposure
dB are logarithmic, so "-18 % noise" is computed on the length-weighted noise *penalty*, and the
sentence leads with the total exposure index (Balanced weights). Reason: a route can trade a little
noise for much more greenery; showing only "+25 % noise" would mislead.

## D-019 (2026-10-13) Planner: 150 m cells, saturating presence, explicit approximate placement
priority = severity x (1 - exp(-presence / 2)). Without saturation the Old Town (dozens of schools
within 200 m) filled the whole top 10; with it, places with a few sensitive sites and very high
exposure rank too (Al. Mickiewicza, Żółkiewskiego, Dietla, Al. Pokoju, Kamieńskiego). School rows
carry no coordinates; they are matched to address points. 133 rows have no house number (the
portal API types the column as a number); those are placed at the centre of the street+postcode
address points when these lie within 300 m and flagged `approx`; 96 sites remain unplaced and are
listed in planner_meta.json. Residents enter as address-point density (the registration data are
per district only, used for the district table).

## D-020 (2026-10-13) Geocoder ranking
FTS5 prefix match on normalised words, then whole-word matches first ("Wawel" -> "Zamek Wawel"
before "Wawelska"), then FTS rank and shorter names. A house number is only the last token, so
"Aleja 29 Listopada" keeps 29 in the name. A missing number falls back to "5a" for "5", never "51",
and otherwise to the street.

## D-021 (2026-10-13) Base map and overlays
Base map: OpenFreeMap "positron" vector style (free, no keys, no cookies, attribution automatic).
Exposure overlays are pre-rendered PNG images in Web Mercator with lon/lat corners (MapLibre image
sources), not tile pyramids: 3 images of ~1 MB, no tile server. Alternative: PMTiles (better at high
zoom, more tooling).

## D-022 (2026-10-13) Graphs rebuilt in memory at API start, no pickle
The API builds igraph graphs from the Parquet edge tables at start (~1 s for both modes) instead of
loading a pickle: one less artefact and no pickle-version coupling.

## D-023 (2026-10-13) Privacy in logs
uvicorn runs with `--no-access-log` and nginx with `access_log off`, because a geocoder query string
can contain a home address. Route requests are POST bodies and are never logged or stored.

## D-024 (2026-10-13) otwartedane.um.krakow.pl: only datasets the app uses
The portal had 45 datasets; 17 are relevant (sensitive users, residents, parks, ZTP layers). The
list and the reason for each is in config/otwartedane.yml; `--all` still downloads everything.

## D-025 (2026-10-13) Named places in the search: OpenStreetMap plus the city's own sites
Users route to places, not only to addresses ("Tauron Arena", "Kościół Mariacki", a restaurant,
"Kazimierz"). Source: OSM features in the graph area for 45 categories (venues, food, culture,
parks, stations, stops, neighbourhoods; config/sources.yml), the 18 districts from MSIP and the
schools/kindergartens/nurseries the planner already placed. Alternatives: Nominatim (external
dependency the plan excludes), Google Places (licence forbids storing). OSM `alt_name`/`short_name`
are indexed so "Mariacki" finds "Bazylika Wniebowzięcia NMP"; categories have search synonyms
("dworzec" finds stations). Stop platforms ("Rondo Mogilskie 01/02") become one entry. Places a route
cannot reach (outside the area or > `coverage.snap_max_m` from a path, 22 of them) are not indexed.
ODbL: the places are shown as search results (a produced work) with OSM attribution; the extract
itself is not published.

## D-026 (2026-10-13) Logo drawn for the project
`web/public/logo.svg` is drawn from scratch from simple geometric shapes (rounded square, leaf,
dashed route, two dots); it copies no existing mark and uses no third-party artwork or font. A web
search on 2026-10-13 found no app or trade mark named "Zdrowa Trasa"; a check in the UPRP and EUIPO
registers is still open (OPEN_QUESTIONS A8).
