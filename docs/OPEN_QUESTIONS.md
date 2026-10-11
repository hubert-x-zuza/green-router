# Open questions

Status date: 2026-10-11. Part A needs your decision; part B is the manual checklist for every manifest entry
still marked TODO (the city portals may block automated requests, so these are checks to do in your browser).
For each item: open the URL, read the listed things, and paste the answers back (or edit `data/manifest.yml`
yourself). Items are ordered by how much they block Phase 1.

## A. Questions for you

**A1. (resolved 2026-10-11) More Kraków stations.** Probed: five of the other six deliver hourly PM10 (16896 also NO₂), none PM2.5; 20367 has none of the three. The five are now archived (decision D-009). Open: station types for all eight (B8).

**A2. Station 401 (Bujaka) has no live PM2.5.** Its PM2.5 sensor 2773 is manual (GIOŚ error API-ERR-100003).
`level(t)` will use PM2.5 from stations 400 and 402 only (recorded as D-006). Tell me if you want something
different.

**A3. Where will the archiver run permanently?** Today it runs on this Mac through launchd (hourly, minute 7).
A sleeping laptop misses hours (the GIOŚ current endpoint keeps about 3 days, so a gap shorter than that is
recovered by the next run). Plan section 11, question 2 is still open: VPS, home server or cloud.

## B. Manual checklist (manifest entries with TODO)

### B1. `green_map` (blocks Phase 1; plan task 0.6)
Open `https://msip.um.krakow.pl/arcgis/rest/services/MONIT-AIR/WS_MA_Atlas_02_mapa_zieleni_przewietrzania_Krakowa/MapServer/7?f=pjson`
1. Is `name` "Mapa zieleni"? Are the fields `class_name`, `area_ha`, `objectid` present? Note the `id`
   (earlier JSON said `id: 0`, the URL ends `/7`). Copy `maxRecordCount` and `capabilities`.
   → `green_map.status`, `green_map.fields`.
2. Open `…/MapServer/7/query?where=1%3D1&outFields=class_name&returnDistinctValues=true&returnGeometry=false&f=json`
   and list every distinct `class_name` (the renderer shows 3, the data may have more). → `classes_seen`.
3. Open `…/MapServer/7/query?where=1%3D1&returnCountOnly=true&f=json` and note the count (sizing the download).
4. Open `…/MapServer?f=pjson` and list all layers (id, name). Is there a ventilation/air-flow layer?
   Then open the folder `https://msip.um.krakow.pl/arcgis/rest/services/MONIT-AIR?f=pjson` and list its services.
   → `green_map.todo`.
5. Data date: in the layer JSON look at `description` / `copyrightText`; otherwise the portal item
   `ffc310c95ea74ed388d94cf5d9c4b49d` (item page → "Updated"). → `green_map.data_date`; write today's date in
   `date_obtained` only after the download is done; fix `citation_pl`.

### B2. `drinking_fountains`
Open `https://msip.krakow.pl/dataset/1359`, the **outdoor** subset ("pitniki zewnętrzne").
Read: the field list (name, status, any column about season or opening months, year), the number of records,
the data creation/update date, the licence/terms line. Is there any field saying a fountain works only in
some months? → `attributes`, `status`, `citation_pl`.

### B3. `address_points` (needed for the geocoder)
Open `https://msip.krakow.pl/dataset/1492`. Read: the field names for street, house number, postcode, any
"full address" column; the JSON/SHP download size; creation/update date; the exact wording of "use restrictions"
and what the MSIP regulamin says about derivative works (a search index built from the points counts as one).
Save the wording to `docs/licences/` (text + URL + date). → `fields`, `citation_pl`, `restrictions`.

### B4. `streets`
Open `https://msip.krakow.pl/dataset/1379`. Read: is there a download (format, size, CRS), the field names
(street name, any short name or "ul./al." type column), date, terms. → `status`, `fields`, `citation_pl`.

### B5. `districts` (also gives the Kraków boundary)
Open `https://msip.krakow.pl/dataset/1483`. Read: download format and CRS, the field with the district name and
any district id, whether the district polygons dissolve into one city boundary, date, terms.
→ `status`, `fields`, `citation_pl`.

### B6. `noise_2022` (the one open limitation)
Open `https://msip.krakow.pl/dataset/1361` and the service
`https://msip.um.krakow.pl/arcgis/rest/services/Mapa_halasu_2022?f=pjson` (also look at each layer's
`description`). Find any metadata that says which roads were modelled (all streets, or only roads above some
traffic volume / classes). If it is not stated anywhere, say so; I will record "not documented".
→ replace the `TODO: check metadata…` line in `limitations`.

### B7. `parks_table`
Open `https://otwartedane.um.krakow.pl/zbiory-danych/parki-miejskie-w-krakowie`. Read the licence/terms line,
the update date, the record count. The manifest has no citation yet. → add `licence`, `data_date`, `citation_pl`.

### B8. `air_quality_gios` (what is left; the rest was verified by calls)
1. **Station type** (traffic / urban background / …) for all eight stations (400, 401, 402, 10123, 10139, 10447, 11303, 16896). The API's `findAll` has no such field, so
   look on the station pages of the GIOŚ air-quality portal (`powietrze.gios.gov.pl`, the address the API's own
   error message points to) for the station-type label. I did not guess a URL path. This is needed for the
   NO₂ proxy validation (plan 3c). → `stations[].type`.
2. Terms of the API (is the visible-source requirement worded anywhere precisely, any further condition?).
   Copy the wording to `docs/licences/`. → `attribution_required`, `citation_pl`.
3. Hour labels: for a row like `Data: 2026-10-11 14:00:00` is the value for the hour *ending* at 14:00 or
   *starting* at 14:00? The API returns the hour in progress with a null value, which suggests "hour
   starting", but I did not confirm it. Look in the API documentation ("content/api" on the portal). The
   archiver stores the label as given (converted to UTC) so nothing is lost either way.

### B9. `air_forecast_iosPIB`
Read the terms of use of the IOŚ-PIB forecast service (the GIOŚ API documentation points to it; I have no
terms URL, so I did not invent one). Then open `https://api.prognozy.ios.edu.pl/v1/PM10/1261/` in the browser and
paste the response shape (a date → value map?). → `status`, `licence`, `citation_pl`. I did not call it.

### B10. `osm`
Decide the source: Geofabrik extract for Małopolskie (then clip to Kraków + 500 m) or osmnx/Overpass for the
boundary. Tell me which, and give the extract's download URL and its date (I have no verified URL in the
manifest, so I did not write one). → `status`, extract date, `citation`.

### B11. Planner-view datasets (Phase 4, not blocking now)
- `schools`: on `otwartedane.um.krakow.pl` find the two school datasets (municipal and private). Read: URL,
  geometry (points?), fields (type of school, address), format, date, terms.
- `bike_counters`: find the ZDMK automatic bike counters dataset. Read: URL, whether counts are published,
  counter coordinates, time resolution, terms.
- `gtfs`: `https://gtfs.ztp.krakow.pl/`. Read: file names, update frequency, licence/terms; confirm stops
  have coordinates.
- `residents`: `https://msip.krakow.pl/dataset/3180`. Read: the aggregation level (district? statistical
  region? address?), the period, terms. Do not use address-level data (privacy).

## C. Findings that contradict or extend the plan (for your information)

- The plan says the 2022 grid spot values are Rondo Mogilskie 67.9 etc. I did not reproduce these: landmark
  coordinates I typed from memory read as the floor value in the rebuilt grid, so they were probably off the
  road. The aggregate shares match the plan (see the Phase 0 report). Spot checks need coordinates read
  from a map by you or from the OSM graph in Phase 1.
- `data/raw/noise/` also holds `halas_2022_tereny_zagrozone_*` files (≈ 0.8 GB, not used, not in the manifest)
  and two `__Aktualnosc__` files with different times (14:47 and 14:41, same date 2026-03-23).
