# Zdrowa Trasa — Implementation Plan

Competition: "Open Data App" (Gmina Miejska Kraków). Plan written 10 Oct 2026; updated 11 Oct 2026 with Phase 0 data findings (sections 3a to 3c).
Audience: the team (review) and Claude Code (execution). Copy this file to `docs/PLAN.md` in the repo.

---

## 0. How Claude Code should work with this plan

1. Read this whole file first. Then create `CLAUDE.md` in the repo root summarising sections 1, 2 and 9 (goal, constraints, conventions).
2. Work phase by phase (section 7). Do not start a phase until the previous phase's acceptance criteria pass. Commit at the end of each task.
3. **Do not trust dataset names, URLs, field names or API shapes in this plan.** They were collected without being able to open the city portal directly. Phase 0 exists to verify them. Record every finding in `docs/data-sources.md` and `data/manifest.yml`.
4. Never invent a URL, endpoint or column name. If something cannot be verified, write it down in `docs/OPEN_QUESTIONS.md` and ask the user.
5. Record every non-obvious decision in `docs/DECISIONS.md` (one short paragraph each: decision, alternatives, reason). This file feeds the technical documentation required for submission.
6. No secrets in git. Use `.env` + `.env.example`.
7. Keep it small. This is a 4-week competition prototype. Prefer boring, well-known tools over clever ones.

---

## 1. Product

**One line:** a web app that routes people on foot or by bike through Kraków along the healthiest streets, using open data on noise, air quality and greenery, and gives city planners a view of where exposure is worst.

**Two views, one data backend:**

| View | User | Core question |
|---|---|---|
| Route planner | Resident, commuter, parent, runner | "Which way is healthier, and what does it cost me in minutes?" |
| Planner dashboard | City staff (ZDMK, ZZM, Referat Smart City), NGOs | "Which street segments combine high exposure with many sensitive users, and what would fix them?" |

**Reference project:** Green Paths 2 (`DigitalGeographyLab/green-paths-2`, MIT licence). Key takeaways from its documentation:
- It is an offline, expert-oriented Python CLI. It depends on Java via r5/r5py, and it has no web UI, no live data and no end-user audience.
- Its method is: split the OSM network into segments, rasterise exposure layers, sample points along each segment, average, normalise to 0–1, then add weighted exposure to travel time as the edge cost.
- We reuse the *idea* (per-edge normalised exposure folded into the routing cost). We do not use r5py or Java. We differentiate with: a web app, live air-quality data, Kraków-specific open data, exposure profiles, and the planner view.
- Cite Green Paths 2 in the docs as inspiration. If any code is copied, keep the MIT notice.

**Scope decision (11 Oct):** the urban heat-island layer is **not** part of this version. The routing layers are noise, air quality, greenery (and optionally fountains). The heat research is kept in Appendix A in case the team revisits it. Consequences: the greenery layer and the traffic-proximity proxy carry more of the discrimination between quiet-looking residential streets, and the demo needs no "summer mode".

### Differentiators to emphasise in the pitch
1. Live + static data fused in one routing cost (hourly air quality + static noise and green).
2. Local geocoder built from the city's own address points (no dependence on Nominatim).
3. Planner view with a "who is exposed" weighting (schools, stops, residents), not just a map of bad places.
4. Transparent: each route shows its numbers and the data sources/dates behind them.

---

## 2. Constraints from the competition rules

| Item | Requirement | Consequence |
|---|---|---|
| Team | 2–5 people, one leader | Decide team and leader this week |
| Application form | Paper form must **arrive** at ul. Basztowa 20, Mon–Fri 08:00–14:30; deadline stated as 25 Oct 2026 | 25 Oct 2026 is a **Sunday**. Treat **Fri 23 Oct, 14:30** as the real deadline and send by courier by ~20 Oct. Consider emailing the organiser to confirm |
| Submission | Email to konkursopendata@um.krakow.pl by **5 Nov 2026** | Freeze code on 3 Nov |
| Must include | Title; description PDF ≤ 2 pages; working demo; launch instructions; technical documentation (technologies, data used, architecture, development possibilities) | Section 8 lists the deliverables |
| Data | At least 1 Kraków open data source; other open data allowed (dane.gov.pl, GUS, other cities) | We use several Kraków sources plus GIOŚ and OSM |
| Originality | Authors' own work; no third-party copyright violations | Respect licences (section 6). Credit sources |
| Finals | 5-minute pitch + 5-minute Q&A (rules state max 20 min total) | Prepare a scripted demo (section 8) |
| Ambiguity | The rules say the contest ends "31 listopada" (not a real date) | Ask the organiser to confirm |
| Licence granted to city | Non-exclusive, covers presentation/promotion; **excludes source code and technical docs** | We keep the code; still decide whether to open-source it after the contest |

### Scoring → where the effort goes
| Criterion | Weight | How this project earns it |
|---|---|---|
| City impact | 30% | Health, accessibility of information, planner decision support |
| Data use | 20% | 6+ datasets fused; correlations (e.g. noise vs. green vs. traffic class) |
| Innovation | 15% | Live+static multi-objective routing, what-if planner |
| Architecture | 15% | Reproducible ETL, stateless API, docs, tests, Docker |
| Business potential | 10% | Planner licence, health/insurer wellness apps, real-estate, tourism, employer wellness |
| UX | 5% | Mobile-first, accessible, PL/EN |
| UI | 5% | Clean, consistent; do not over-invest |

---

## 3. Data inventory (all items must be verified in Phase 0)

Legend: ✅ seen in a catalogue listing, ⚠️ plausible but unverified, ❓ must be researched.

| # | Layer | Source | Status | Notes / fallback |
|---|---|---|---|---|
| 1 | Street network | OpenStreetMap extract for Kraków (Geofabrik Małopolskie or OSMnx/Overpass) | ✅ | ODbL, attribution required |
| 2 | Noise | MSIP open data catalogue, "Mapy hałasu" (catalogue lists it under Open Data; maps for 2012, 2017, 2022 exist as a viewer) | ✅ listed, ⚠️ format | Expect polygons by dB band (Lden/Ln, possibly per source: road/tram/rail). Use the newest year (2022). Check which indicator and which sources are included |
| 3 | Drinking fountains | MSIP catalogue, "Lokalizacja pitników wody kranowej" | ✅ | Points. Check for seasonal availability field |
| 4 | Heat island (MSIP "MWC" rasters) | MSIP / LIFE-IP EkoMałopolska | ⛔ **parked** | Not used in this version (decision 11 Oct). See Appendix A |
| 5 | Greenery | **MSIP "Mapa zieleni"** (city feature layer, polygons) | ✅ found 11 Oct | Classes `200 Zieleń wysoka` (tall greenery), `300 Zieleń niska` (low greenery), `400 Zieleń sportowa, ogródki działkowe` (sports greenery, allotments); field `area_ha`. Queryable and downloadable. See 3c |
| 6 | Address points | MSIP "Punkty adresowe (EMUiA)" | ✅ | Local geocoder (address → coordinates) |
| 7 | Street names | MSIP "Ulice (EMUiA)" | ✅ | Street-level search and name normalisation |
| 8 | District boundaries | MSIP "Podział administracyjny – dzielnice" | ✅ | Aggregation for the planner view |
| 9 | Air quality (live) | GIOŚ API v1 | ✅ | **Three stations reachable through the API**: ul. Bujaka (401), ul. Bulwarowa (402), Aleja Krasińskiego (400). See 3c |
| 10 | Schools | otwartedane: school datasets (municipal + private, ~973 schools incl. sports grounds) | ✅ per third-party report | Sensitive-user weight in planner view |
| 11 | Bike counters | otwartedane (ZDMK automatic counters) | ✅ per third-party report | Use in planner view and for cycling relevance, not for routing |
| 12 | Public transport | ZTP GTFS static + realtime (`gtfs.ztp.krakow.pl`) | ✅ | Stops as sensitive-user proxy; optional last-leg features (stretch) |
| 13 | Residents | MSIP "Zameldowania stałe i czasowe" | ✅ | Population weight for planner view (check aggregation level; privacy) |
| 14 | Defibrillators, school grounds, other points of interest | otwartedane | ⚠️ | Optional "healthy stops" layer |

### Known data caveats (put these in the docs honestly)
- Only **three** air-quality stations are used, so the app cannot know street-level air quality. The air term is a city-level level from the stations (hourly) shaped spatially by a **static traffic-proximity proxy** from OSM road classes. It mainly reflects traffic-related exposure (NO₂, near-road particles). Smog episodes in Kraków are commonly attributed to residential heating and regional background, which this model cannot see. Label the air term as an indicative model, not a measurement, and word the UI accordingly.
- The noise map is a strategic (modelled) map, updated every five years, not live noise.
- Do not make medical claims. Use "exposure index" and add a short disclaimer.

---

## 3a. Phase 0 findings (reported by the team on 11 Oct; these override section 3 where they conflict)

### Verified facts
| Layer | What was found | Consequence |
|---|---|---|
| Noise | MSIP "Mapa hałasu 2022" viewer. Indicators **LN and LDWN**. **Road, tram and rail are separate** (distinguishable in the legend). A 2017 map also exists. The viewer has **no export button**. A queryable service exists at `https://msip.um.krakow.pl/arcgis/rest/services/Mapa_halasu_2022`. Viewer coordinates are EPSG:2178 | Pull data through the ArcGIS REST service (task 0.1). Also check whether catalogue dataset 1361 offers a direct download. Combine sources energetically (5.2a) |
| Air quality | GIOŚ API **v1** is current (old `/pjp-api/rest/...` endpoints were withdrawn 30 Jun 2025). Responses are JSON-LD. Values in µg/m³. Current data: last full hour up to 3 days back, local time, limit **1500 req/min**. Archive data: **fixed UTC+1**, limit **2 req/min**. Station metadata: limit 2 req/min. Air-quality index endpoint exists. **Attribution of the source is mandatory.** Data are not continuously verified and may change later | See 5.3a. Cache station metadata. Handle the UTC+1 vs local-time difference explicitly |
| Kraków stations | Superseded on 11 Oct: only **three** stations are reachable through the API (see 3c) | Use these three. The earlier list of nine station codes is not needed |
| Air forecast | IOŚ-PIB forecast API: daily mean PM10, NO₂, SO₂, O₃ per gmina by TERYT code. Kraków: `https://api.prognozy.ios.edu.pl/v1/PM10/1261/`. Response is a date → value map | City-wide, daily. Use for a "plan for tomorrow" feature and as a fallback. It cannot give spatial detail |
| Parks | Dataset page `otwartedane.um.krakow.pl/zbiory-danych/parki-miejskie-w-krakowie` | Check whether it has geometry (task 0.3) |
| Address points | Downloads: xlsx, shp, dxf, json. WFS/WMS available. **EPSG:2178**. Owner: Wydział Geodezji UMK (gd.umk@um.krakow.pl). Use restrictions: "per the MSIP regulations" | Local geocoder is feasible. Read the MSIP regulamin for derivative-use terms |
| Fountains | Four subsets: restaurants, schools/universities, offices/hospitals, **outdoor**. Each in dxf/json/shp, plus WMS/WFS. EPSG:2178. Programme: "Dobra woda dla Krakowa" | Use **outdoor** for routing. The other three are indoor and likely limited by opening hours, so treat them as an optional separate layer |

### Design changes resulting from the findings
1. **Internal CRS is EPSG:2178**, not 2180 (sections 5.1 and 9 say 2180). All city data arrives in 2178, so this avoids needless reprojection. OSM (WGS84) is reprojected on load. Output to WGS84 at the API boundary.
2. **5.2a Noise processing (implemented and tested; see `etl/noise_to_grid.py`).** Use the polygon files (`*_dr_*` road, `*_szyn_*` rail+tram) for LDWN (primary) and LN (night profile). Rasterise the dB class midpoints to a 10 m grid in EPSG:2178, higher classes overwriting lower ones. The lowest class of each file ("below the lowest mapped level", with a meaningless negative lower bound) contributes nothing to the energy sum. Combine sources by energy sum, `L = 10·log10(Σ 10^(Lᵢ/10))`, and give cells with no source above its lowest class a floor value (LDWN 50 dB, LN 45 dB). Cells outside the city polygons are nodata. Do **not** sum the lowest-class placeholders: doing so creates a fake 53 dB. Ignore the `*_izofony_*` isoline files and the `*_przem_*` (industrial) files, which came with no geometry. Keep 2017 as a second grid for a "noise change 2017→2022" layer in the planner view.
3. **5.3a Air quality.** Superseded by section 3c (three stations, city-level index shaped by the traffic proxy). Still valid: map each station to its API ID, store everything in UTC (archive data is fixed UTC+1, current data is local time with DST), cache station metadata (2 req/min limit), show the mandatory source attribution and the note that the data are unverified.
4. **Forecast feature.** Add a "tomorrow" indicator from the IOŚ-PIB forecast (daily PM10 for Kraków). Read its terms first.
5. **Greenery.** Superseded by section 3c: the city's own "Mapa zieleni" is the primary source. OSM and ESA WorldCover are no longer needed.

### Phase 0 tasks still open (do these next, in this order)
- **0.1 Noise REST service.** Open the service page, add `?f=pjson`, and note the layers (index, name, geometry type, fields, `capabilities` containing Query, `maxRecordCount`). If a layer supports Query, the download URL pattern is `<service>/<layerId>/query?where=1%3D1&outFields=*&outSR=2178&f=geojson&resultOffset=0&resultRecordCount=<max>`, paged until no further records. Record the result in `data/manifest.yml`. Also open catalogue dataset 1361 (`msip.krakow.pl/dataset/1361`) and look for a download.
- **0.2** (dropped on 11 Oct: the heat-island layer is parked, see Appendix A).
- **0.3 Parks dataset.** Open the page: geometry or only a table? Which fields (name, area, class)? Download format and licence.
- **0.4 GIOŚ (mostly done).** Sensors for all three stations are confirmed (see 3c). Remaining: (a) call `station/findAll` once to read each station's coordinates and type; (b) for stations 401 and 402, which list two PM10 sensors each, call `data/getData/{sensorId}` for both and keep the one with hourly values; (c) fetch one current reading per sensor used; (d) handle pagination in the sensors call; (e) record the exact URLs in the manifest.
- **0.5 Licence check (done per team).** The team reports that all the city's resources may be used provided the source is cited. Keep the exact wording: save the regulamin clause (screenshot or quoted text with URL and date) in `docs/licences/`, because the technical documentation should show it.
- **0.6 Greenery (found, two checks open).** (a) Confirm that the URL ending in `/7` is the same layer as the JSON that reported `id: 0`. (b) List the other layers of that service and the other services in the `MONIT-AIR` folder, looking for a ventilation or air-flow layer (see 3c). (c) Record the data date.

---

## 3b. Phase 0 results, round 2 (11 Oct)

### Noise: verified, working
- Files received: road, rail/tram and industrial noise for LDWN and LN, as polygons and as isolines (about 1.4 GB in total). Generation date stated by the city's export: **2026-03-23**. Record it in `data/manifest.yml` as the date of data creation, and the download date (11 Oct 2026) as the date obtained. The city asks for both.
- Polygon attributes: `isov1`, `isov2` (class bounds in dB), `nazwa` (district name), `objectid`. Road LDWN classes: below 55, then 5 dB steps to 80, plus a "≥80" class. Road LN: below 50, then 5 dB steps to "≥75". Rail LDWN/LN: 1 dB steps from 55 (LDWN) / 50 (LN).
- Every file covers the whole city, **including a "below the lowest level" class**, so there is no ambiguity about unmapped areas inside the city.
- **Industrial files have no geometry** in this export (only area/length attributes). Ignore them. Industrial noise is unlikely to matter for routing.
- Tested result: `etl/noise_to_grid.py` produces `noise_LDWN_10m.tif` and `noise_LN_10m.tif` (about 0.8 MB each, so they can be committed to the repo; the raw files cannot). Run time about 1.5 min per indicator, needing roughly 3–4 GB RAM because the largest GeoJSON is 375 MB. Preview image looks correct (ring roads, arterials, rail corridors clearly visible).
- Statistics of the 2022 LDWN grid inside the city: about 63 % of the area is at the floor (below 55 dB), 37 % is ≥ 55, 15 % is ≥ 65, 8 % is ≥ 70. For LN: about 71 % at the floor.
- Spot values (LDWN): Rondo Mogilskie 67.9, Al. Pokoju near Fabryczna 72.6, Dworzec Główny area 67.0, Planty and Rynek Główny at the floor, Las Wolski at the floor. Plausible overall.

**Limitations to state in the docs (and to keep in mind for routing):**
1. Road classes are 5 dB wide, so the grid is a step function. That is fine for ranking streets.
2. About two thirds of the city is "below 55 dB", so noise alone cannot separate most residential streets from each other. The traffic-proximity proxy (5.2) and greenery terms must carry that discrimination.
3. Check the map's metadata for which roads were modelled. If minor streets are not modelled, they show as quiet simply because they are not in the model. Mention it in the methodology.
4. Pedestrianised areas (Rynek, Planty) show as quiet. That reflects traffic noise only, not crowd or event noise.

### Parks
The parks dataset has only **type, name, district and area** (no geometry). It cannot be mapped directly. Use it for (a) per-district park statistics in the planner view and (b) naming/labelling if a name match against OSM park polygons is wanted. It is not used for the greenery penalty (see 3c).

### Air quality: station IDs
Superseded by 3c: three stations (400, 401, 402).

---

## 3c. Decisions and findings, round 3 (11 Oct)

> **Update 2026-10-11 (Phase 0, after the API probe):** `station/findAll` lists nine Kraków stations. Five more deliver hourly data and are now used besides 400–402: 10123, 10139, 10447, 11303 (PM10 only) and 16896 (PM10 and NO₂). Station 20367 has none of the three pollutants. No other station has PM2.5, and station 401 has no live PM2.5 (sensor 2773 is manual). Wherever this plan says "three stations", read "eight stations"; `level(t)` averages over the stations that reported each pollutant. Details: `config/air_stations.yml`, `docs/DECISIONS.md` D-009.

### 1. Air quality: three stations
Only three stations are reachable through the API, and the team will use them:

| API ID | Station |
|---|---|
| 400 | Kraków, Aleja Krasińskiego |
| 401 | Kraków, ul. Bujaka |
| 402 | Kraków, ul. Bulwarowa |

**Sensors confirmed (11 Oct)** from the `station/sensors/{id}` responses. All three stations have PM10, PM2.5 and NO₂:

| Station (API ID) | PM10 sensor | PM2.5 sensor | NO₂ sensor | Also measured |
|---|---|---|---|---|
| 400 Al. Krasińskiego | 2750 | 2752 | 2747 | CO 2745, NO, NOx, benzene 16500 |
| 401 ul. Bujaka | **2770 and 2771** | 2773 | 2766 | O₃ 2768, SO₂ 2774, NO, NOx, metals and PAHs bound to PM10 |
| 402 ul. Bulwarowa | **2792 and 2793** | 2794 | 2788 | SO₂ 2797, benzene 2779, NO, NOx, metals and BaP in PM10 |

Details to handle in the ETL:
- **Stations 401 and 402 list two PM10 sensors each.** They probably differ by measurement method (for example an automatic hourly analyser versus a manual sampler used for the metals and PAH analyses), but that is an inference. Call `data/getData/{sensorId}` for both and keep the one that returns **hourly** values. Do not assume by position.
- Station 400 has CO and benzene and no O₃ or SO₂, while 401 and 402 have SO₂ and the metal/PAH analyses. That is consistent with 400 being the traffic station and the other two background stations, which is what the validation in point "Validation" needs. Confirm the station type in the `station/findAll` metadata.
- The sensors endpoint is paginated (`page`, `size=20`). Station 401 has 19 sensors and fits on one page, but implement pagination anyway.
- Use only these indicators: PM10 (indicator id 3), PM2.5 (69), NO₂ (6). The others are not needed for routing.

Interpolating a city-wide field from three points would look precise without being so. Therefore:
- **City level:** `level(t)` = the mean over stations that reported in the last N hours of the per-pollutant values normalised to thresholds (PM2.5, PM10, NO₂; thresholds in config, reviewed against current EU/Polish limits and WHO guidelines), then the maximum across pollutants (index-style). Stations stay visible individually in the UI.
- **Spatial pattern:** `air_penalty(edge, t) = clamp( level(t) · (a + (1 − a) · traffic_proximity(edge)), 0, 1 )`, with `a` in config (suggested start 0.3). Effect: on clean days the air term is small everywhere, so routes are driven by noise and green; during smog the penalty grows and steers routes away from busy roads.
- **Validation:** compare the traffic station (check its type in the metadata) with the other two on NO₂ as a sanity check of the proxy. Three stations cannot prove a correlation, so say that.
- **Forecast:** the IOŚ-PIB daily PM10 forecast (Kraków, TERYT 1261) stays as the "tomorrow" indicator.

### 2. Greenery: the city's "Mapa zieleni"
- Polygon feature layer, classes in field `class_name`: `200 Zieleń wysoka` (tall greenery, the closest thing to tree canopy), `300 Zieleń niska` (low greenery, e.g. lawns), `400 Zieleń sportowa, ogródki działkowe` (sports greenery and allotments). Also `area_ha`. Capabilities: Map, Query, Data. Max 1000 records per request, pagination and distinct-value queries supported, GeoJSON output supported.
- Source CRS is reported as WKID 102176, which pyproj identifies as ETRS_1989_UWPP_2000_PAS_7, the same Polish CS2000 zone-7 projection as EPSG:2178. Request `outSR=2178` anyway.
- The renderer lists three classes. The data may contain more: check with a distinct-values query.
- **Download pattern** (verify in the browser; replace `<layer>` with the layer URL):
  - count: `<layer>/query?where=1%3D1&returnCountOnly=true&f=json`
  - classes: `<layer>/query?where=1%3D1&outFields=class_name&returnDistinctValues=true&returnGeometry=false&f=json`
  - data, paged: `<layer>/query?where=1%3D1&outFields=*&orderByFields=objectid&outSR=2178&f=geojson&resultOffset=0&resultRecordCount=1000`, then increase `resultOffset` by 1000 until fewer records return (or no `exceededTransferLimit`).
- **Method (replaces the greenery row of 5.2):** rasterise the three classes to a 10 m class grid in EPSG:2178. For each edge, take the share of each class within a 30 m buffer: `green_score = w200·share200 + w300·share300 + w400·share400`, clamped to [0, 1], with starting weights 1.0 / 0.4 / 0.2 in config (to review). `p_green = 1 − green_score`. Use `area_ha` for the planner and district statistics.
- **Layer URL (11 Oct):** `https://msip.um.krakow.pl/arcgis/rest/services/MONIT-AIR/WS_MA_Atlas_02_mapa_zieleni_przewietrzania_Krakowa/MapServer/7` (folder `MONIT-AIR`, service name mentions "mapa zieleni przewietrzania", i.e. a greenery and ventilation map of Kraków).
- **Check before relying on it:** the layer JSON received earlier reported `id: 0`, but this URL ends in `/7`. Open `<url>?f=pjson` and confirm it is the same layer (name "Mapa zieleni", fields `class_name`, `area_ha`). If they differ, use the one whose fields and classes match and whose data are newer, and record both in the manifest.
- **Possible bonus for the air term:** the service name suggests other layers about ventilation or air flow. List the service's layers (`.../MapServer?f=pjson`) and the other services in the `MONIT-AIR` folder. Such a layer could give the air term a spatial pattern beyond the traffic proxy. Adopt it only if its meaning, date and licence are documented and it can be downloaded; otherwise skip it.
- Still to record in the manifest: the data date and last update (layer metadata, or portal item `ffc310c95ea74ed388d94cf5d9c4b49d`), and the citation line.
- Limitation to state: the map classifies greenery by height class but is not a tree register, so it does not tell tree species, crown size or shade at a given hour.

### 3. Licence and citation
The team reports that all the city's resources may be used as long as they are cited. Operational rules:
- Cite every dataset in the UI "About data" panel and the documentation: provider, dataset name, date of data creation, date obtained, and link.
- GIOŚ requires a clear, visible indication of the source. IOŚ-PIB forecast terms are still to be read.
- **OSM is ODbL.** Attribution is mandatory. If the processed edge table derived from OSM is published, the share-alike term applies to it, so either publish it under ODbL or ship only the ETL scripts and let others rebuild it.
- Keep a copy of the exact regulamin wording in `docs/licences/`.

### 4. Coverage: Kraków only (interpretation)
I read "all in Kraków" as: all the data sources (stations, noise, greenery) cover Kraków only. Consequences:
- Build the OSM graph for the Kraków boundary plus about 500 m (boundary from the district polygons).
- Edges outside the noise or greenery coverage get `data_coverage = false` and a neutral penalty, and the UI warns when a route uses them.
- The origin and destination must be inside the city (plus buffer). Otherwise show a clear message that the app covers Kraków only.
- This is also a stated limit and a development path (other cities, using the same ETL).

---

## 4. Architecture

```
            ┌────────────── ETL (offline, reproducible: `make data`) ──────────────┐
 OSM PBF ──►│ build walk/bike graph → split edges → sample points per edge        │
 MSIP/otw.─►│ rasterise/overlay noise, green, fountains → normalise 0–1           │──► data/processed/
 GIOŚ ─────►│ (separate hourly job) fetch stations → store                         │     edges.parquet
 Addresses ►│ build geocoder index                                                 │     graph.pkl / igraph
            └──────────────────────────────────────────────────────────────────────┘     geocoder.sqlite
                                                                                          air_history.sqlite
                                   ┌───────────────── API (FastAPI) ────────────────┐
 browser (React + MapLibre) ◄────► │ /route  /geocode  /air/now  /layers  /planner  │
                                   │ loads graph + edge arrays in memory at start   │
                                   │ per request: cost vector = f(profile, live AQ) │
                                   └────────────────────────────────────────────────┘
```

**Stack (proposed; change only with a DECISIONS.md entry):**
- Python 3.11+, `geopandas`, `shapely`, `pyproj`, `rasterio`, `numpy`, `pandas`, `osmnx` (graph building), `python-igraph` (fast shortest paths; fall back to `networkx` if igraph is a problem), `pyarrow`.
- API: FastAPI + Uvicorn, Pydantic models, OpenAPI docs auto-generated.
- Storage: GeoParquet/Parquet + SQLite files. **No PostGIS in the MVP** (less to run); document PostGIS/pgRouting as the scale-up path.
- Frontend: React + TypeScript + Vite, MapLibre GL JS, a charting library for the comparison card. PL primary, EN secondary (`i18next`).
- Base map: pick a free vector-tile source or self-hosted PMTiles with proper attribution. Do **not** use the public OSM tile servers for production load. Verify the chosen provider's terms.
- Packaging: `docker compose up` starts api + web. ETL outputs are either built on first run or downloaded from a release artifact.
- CI: GitHub Actions running lint + tests (small).

### Repository layout
```
zdrowa-trasa/
  CLAUDE.md
  README.md                 # PL + short EN; launch instructions (a deliverable)
  Makefile                  # make data | make api | make web | make test
  docker-compose.yml
  .env.example
  data/
    manifest.yml            # every dataset: name, URL, licence, date obtained, CRS, fields used
    raw/  processed/        # gitignored
  etl/                      # python package
    fetch/                  # one module per source
    graph.py  enrich.py  normalise.py  geocoder.py  air.py  planner.py
  api/                      # FastAPI app
    main.py  routing.py  costs.py  models.py  tests/
  web/                      # React app
  docs/
    PLAN.md  DECISIONS.md  OPEN_QUESTIONS.md  data-sources.md
    architecture.md  methodology.md
    submission/             # 2-page PDF source, technical documentation, pitch script
```

---

## 5. Methodology (core logic)

### 5.1 Graph
- Build separate walk and bike graphs from OSM (walk: footways, paths, pedestrian streets, residential; bike: cycleways + roads where cycling is allowed). Split ways at intersections so each edge is a short segment. Keep OSM way ID, highway class, length, geometry, surface if present.
- Work internally in EPSG:2178 (all city data arrives in 2178, see 3a); output WGS84 for the web.

- Coverage: Kraków boundary plus ~500 m; edges outside the data coverage get `data_coverage = false` and a neutral penalty (see 3c).

### 5.2 Per-edge exposure (computed once in ETL)
For each edge, sample points every ~15 m (min. 2 per edge), read the value at each point, aggregate:

| Layer | Per-edge value | Aggregate | Normalisation to penalty `p ∈ [0,1]` |
|---|---|---|---|
| Noise | dB (Lden or the verified indicator) | mean (also store max) | clamp 45 dB → 0, 75 dB → 1 (thresholds in config; review) |
| Green | share of each "Mapa zieleni" class within a 30 m buffer | weighted sum (see 3c) | `p_green = 1 − green_score` (good exposure inverted) |
| Fountains | distance to nearest fountain | min | `p = 0` if ≤ 100 m, rising to 1 at ≥ 500 m (used by the Green & water profile; check the dataset for seasonal availability) |
| Traffic proximity | OSM highway class of the edge and of roads within 50 m | weighted sum | 0–1 by class weights in config |

Store raw values and normalised penalties side by side so the UI can show real numbers.

### 5.3 Air quality (live, hourly)
1. Poll the GIOŚ stations hourly (eight stations, see the update note in 3c) for PM2.5, PM10 and NO₂ where available. Store every reading with a UTC timestamp.
2. City level `level(t)` from the stations (see 3c): normalised per pollutant, mean over stations, maximum across pollutants.
3. `air_penalty(edge, t) = clamp( level(t) · (a + (1 − a) · traffic_proximity(edge)), 0, 1 )`; `a` in config.
4. **Validation task (Phase 1):** compare the traffic-type station with the other two on NO₂ and write the outcome and the limits of the proxy to `docs/methodology.md`.
5. If the feed fails, use the last good value and show a "data from HH:MM" badge. Never show stale data as live.

### 5.4 Cost function
```
cost(e) = length_m / speed_mps(mode) · ( 1 + Σ_k  w_k(profile) · p_k(e, t) )
```
- `w_k` come from profiles; users can also adjust sliders.
- Profiles (initial values to be tuned; keep in `config/profiles.yml`):
  - **Fastest**: all weights 0.
  - **Balanced**: moderate weights on all active layers.
  - **Quiet**: noise high.
  - **Clean air**: air high, traffic proximity high.
  - **Green & water**: green and fountains high, noise and air moderate.
  - **Smog alert**: not a separate profile; when live PM10 exceeds a configurable threshold the UI suggests the Clean air profile.
- Default profile: Balanced. No seasonal logic in this version. The user can always override the profile or the sliders.
- **Guard rail:** `max_detour_pct` (default 30 %). If the best exposure route exceeds it, return the best route within the limit and say so.
- Each request returns up to three routes: fastest, healthiest within the limit, balanced. Compute per-route metrics: time, distance, mean/peak noise, green share, fountains within 100 m, air index, and the **trade-off statement** ("+4 min, −18 % noise exposure").

### 5.5 Planner score (dashboard)
```
priority(unit) = exposure_severity(unit) × sensitive_presence(unit)
```
- Unit: edge or ~100–200 m hex cell; aggregated to districts.
- `exposure_severity`: weighted combination of the penalties (same weights as "Balanced", configurable).
- `sensitive_presence`: schools within 200 m (weighted by school count), transit stops within 100 m, bike-counter volume where available, population from registrations if the aggregation level is safe.
- Output: ranked list (top 20) + priority map layer + per-item explanation ("near 2 schools, noise 72 dB, canopy 8 %").
- **Stretch — what-if:** the planner adds a hypothetical tree row/fountain/speed reduction on a street; recompute penalties in a radius and report the change in total exposure and in priority score. Use a simple documented model (e.g. canopy +x % within 30 m).

---

## 6. Licences, attribution, privacy

- Credit every dataset in the UI (an "O danych" / "About data" panel generated from `data/manifest.yml`): provider, dataset name, **date of creation and date obtained** (the city's reuse terms, as reported for its open-data portal, ask for credit and dates), licence.
- OSM: ODbL attribution on the map and in the docs.
- The team reports that the city's resources may be used with citation (see 3c, point 3). Still record each dataset's own terms in `data/manifest.yml`. If a dataset prohibits redistribution, ship the ETL script that downloads it rather than the data.
- Terms of any third-party API (GIOŚ, base-map provider): read and record them. No scraping of services that forbid it.
- Privacy: do not store user locations server-side. Route requests are processed and discarded; logs contain no coordinates. State this in the docs. No analytics cookies in the MVP.
- Population/registration data: use only at an aggregation level the city already publishes.

---

## 7. Phases, tasks and acceptance criteria

Dates assume start 10-11 Oct, freeze Tue 3 Nov, submit by Thu 5 Nov. Phase 0 is partly done (see section 3a for what remains).

### Phase 0 — Verify everything (10–12 Oct)
- [ ] Create repo, layout, `CLAUDE.md`, `Makefile`, linting, pytest, pre-commit.
- [ ] For every row in section 3: locate the dataset, record URL, format, CRS, fields, update date, licence, size, and whether a direct download or API works. Update `data/manifest.yml` and `docs/data-sources.md`.
- [ ] Download the OSM extract for Kraków; confirm graph builds.
- [ ] Verify the GIOŚ API: endpoints, station IDs for Kraków, pollutants available, rate limits. Fetch one reading end to end.
- [ ] For every ⚠️/❓ row, choose a fallback and record it in `DECISIONS.md`.
- [ ] Start the **hourly air-quality archiver now** (cron/GitHub Action/small VPS) so there is history by 5 Nov.
- **Accept when:** `docs/data-sources.md` has a verified row for each layer; a script `etl/fetch/*.py` downloads each into `data/raw/`; `OPEN_QUESTIONS.md` lists what still needs the user.

### Phase 1 — ETL and edge enrichment (12–17 Oct)
- [ ] `etl/graph.py`: walk and bike graphs with split edges, saved as Parquet + igraph pickle.
- [ ] `etl/enrich.py`: sampling + overlay for noise, green, fountains, traffic proximity.
- [ ] `etl/normalise.py`: thresholds from `config/`, outputs `edges.parquet` with raw + penalty columns.
- [ ] `etl/air.py`: station fetch, history store, city-level index + traffic-proximity shaping (see 3c; no IDW).
- [ ] `etl/geocoder.py`: SQLite FTS index from address points + streets; handle Polish diacritics, "ul."/"al." prefixes, house numbers.
- [ ] Notebook or script producing quick sanity maps (QGIS or `folium`) per layer.
- [ ] Air proxy validation write-up.
- **Accept when:** `make data` rebuilds everything from scratch in one command; `edges.parquet` has no NaN penalties (missing data handled explicitly, with a `data_coverage` flag); sanity maps look right at known places (e.g. a busy arterial is loud and a park path is quiet); geocoder resolves 20 sample addresses correctly.

### Phase 2 — Routing API (17–22 Oct)
- [ ] FastAPI app loading graph and edge arrays at startup (target: cold start < 30 s, a route < 1 s on a laptop).
- [ ] `/api/geocode`, `/api/route`, `/api/air/now`, `/api/meta/sources`, `/api/health`.
- [ ] `/api/layers/{layer}`: tiles or simplified GeoJSON for map display.
- [ ] Cost vector assembly (numpy), profiles from YAML, detour guard, metrics, trade-off text.
- [ ] Tests: cost function unit tests; routing sanity (weights 0 = shortest path; high noise weight never increases mean noise); 10 golden routes between landmark pairs; API contract tests.
- **Accept when:** `curl` a route between two known points returns three distinct GeoJSON routes with metrics; fastest route length matches a reference router within a small tolerance; tests pass in CI.

### Phase 3 — Web app: route planner (22–28 Oct)
- [ ] Map with base layer, layer toggles (noise, green, fountains, air stations), legend.
- [ ] Origin/destination via search box (geocoder) and map click; "use my location" (client-side only).
- [ ] Walk/bike toggle, profile chips, sliders (advanced), max-detour control.
- [ ] Comparison card: time vs. exposure for the three routes; routes coloured by selected exposure along the line; hover shows values.
- [ ] Live air badge with timestamp; "About data" panel.
- [ ] PL default, EN toggle; mobile-first; keyboard-navigable; contrast checked.
- **Accept when:** a non-developer can plan a route on a phone in under 30 seconds without instructions; Lighthouse accessibility score ≥ 90; no console errors.

### Phase 4 — Planner dashboard + polish (28 Oct – 2 Nov)
- [ ] `etl/planner.py`: priority scores per cell/edge, district aggregates.
- [ ] `/api/planner/hotspots`, `/api/planner/district/{id}`.
- [ ] Dashboard tab: priority heatmap layer, top-20 list with explanations, district filter, CSV/GeoJSON export.
- [ ] Stretch: what-if module (only if the previous items are done and stable).
- [ ] Performance pass; error states (data stale, outside Kraków, no route).
- [ ] Deployment: Docker images, a public demo URL if feasible (small VPS or similar). Record the exact launch steps.
- **Accept when:** the demo script in section 8 runs end to end without manual intervention; fresh clone + `docker compose up` works on a clean machine, following the README only.

### Phase 5 — Documentation and submission (2–5 Nov)
- [ ] Freeze features on 3 Nov. Only bug fixes after that.
- [ ] Produce the submission package (section 8).
- [ ] Dry run of the finale pitch; test the demo on poor wifi; prepare a recorded fallback video.
- [ ] Send the email with all attachments by Wed 4 Nov (one day of buffer). Confirm receipt.

---

## 8. Submission package and pitch

**Email to konkursopendata@um.krakow.pl contains:**
1. Project title.
2. Description + goal, **PDF, max 2 pages** (problem, solution, data, impact, screenshot, link).
3. Working demo: public URL and/or the repo/archive.
4. Launch instructions (README: prerequisites, `docker compose up`, expected URL, sample inputs).
5. Technical documentation: technologies; data used (table from `manifest.yml`); architecture description (diagram from section 4); development possibilities (section 10).

Write the submission texts in **Polish**.

**Pitch (5 min) outline:**
1. 30 s — problem: Kraków's smog and noise, and that no router tells you the healthier way.
2. 90 s — live demo: same A→B, fastest vs. healthy route; "+3 min, −20 % noise"; switch to the live-air badge.
3. 60 s — data: the datasets fused, honest about limits.
4. 60 s — planner view: top hotspots near schools; (what-if if built).
5. 30 s — business/rollout: who would pay or adopt; how it plugs into mKraków and city data.
6. 30 s — ask/next steps.

Prepare answers to likely questions: accuracy of the air model, why not Google Maps, maintenance cost, data licences, privacy, scaling to other cities, GP2 comparison.

---

## 9. Conventions

- Python: type hints, `ruff` + `black`, `pytest`. Small functions. Config in YAML, no magic numbers in code (thresholds, weights, buffers all in `config/`).
- All geometry operations in EPSG:2178; convert at the API boundary.
- Every ETL step idempotent and deterministic; `make data` from scratch.
- API: Pydantic request/response models; versioned prefix `/api/v1` (optional but preferred).
- Front end: TypeScript strict; no hard-coded strings (use i18n keys).
- Commits: small, conventional messages. PR-style summaries in commit bodies for each phase.
- Tests must not call live external APIs; use recorded fixtures.

---

## 10. Risks and "development possibilities" (for the docs)

| Risk | Mitigation |
|---|---|
| A key dataset is view-only | Fallback proxies (section 3); decide in Phase 0 |
| GIOŚ API changes/fails | Cache + staleness badge; archived history; recorded fixtures |
| Sparse stations → weak air accuracy | Say so; label as indicative; static proxy; validation write-up |
| Routing too slow | igraph, numpy cost vectors, precomputation; reduce graph to Kraków + small buffer |
| Scope creep | Planner what-if and GTFS features are stretch; freeze 3 Nov |
| Paper form deadline | Send by courier by 20 Oct; keep tracking number |
| Team availability | Four workstreams (data/ETL, routing/API, frontend, docs/pitch); one owner each |

**Development possibilities (for the technical docs):** public transport last-leg integration via GTFS (including real-time delays), night-time lighting/safety layer, pollen and heat-warning integration, an urban heat-island layer (the city publishes hourly/seasonal rasters; a decoder prototype exists, see Appendix A), event-driven alerts ("smog alert" push notification), integration as a layer in the mKraków app, pgRouting/PostGIS for city-scale hosting, calibration with low-cost sensor networks, multi-city rollout via the same ETL, open API for third-party developers.

---

## 11. Open questions for the team (resolve before or during Phase 0)

1. Team members, roles, and who is the leader (named on the form).
2. Who can host the demo and the hourly air-quality archiver (VPS, home server, cloud credits)?
3. Primary mode for the first demo: walking, cycling, or both? (Default: both, walking first.)
4. Is the planner what-if worth the time, or should the effort go into polish?
5. Will the code be open-sourced after the contest? (The licence in the rules does not cover source code either way.)

---

## Appendix A. Parked: urban heat-island layer

Not used in this version. Findings so far, in case the team revisits it:
- The city publishes heat-island rasters as separate MapServer services per season and hour (names like `LIFE_IP_EKOMALOPOLSKA/MWC_Wiosna_00_00`, `.../MWC_Lato_17_00`), EPSG:2178, with the same extent as the noise model. Each service has one raster layer, and the layer id differs between services (1 and 8 were seen), so read it from the service JSON.
- The layers have no attribute fields and no `Data` capability, so values are not directly downloadable. The legend is a 60-colour ramp labelled "2,5 - -2,1" (probably a temperature difference in °C, unconfirmed), which can be inverted. `mwc_decode.py` implements this (self-tested on synthetic data only, never run against the live service).
- Open questions if revived: unit and method (the layer reports metadata), whether the legend range is a display stretch, native resolution, licence (the data come from the LIFE-IP EkoMałopolska project, so terms may differ), and which hours/seasons exist. Urban heat islands are usually strongest in the evening and at night.
- Do not copy `mwc_decode.py` into `etl/` unless the feature is revived.
