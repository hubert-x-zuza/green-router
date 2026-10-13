# Open questions

Status date: 2026-10-13. Part A needs a decision from the team; part B lists checks that still need a
person (a browser or an e-mail). Everything from the 2026-10-11 checklist that could be verified by
calling the sources was done on 2026-10-13 (see `data/manifest.yml` and `docs/DECISIONS.md`).

## A. Decisions for the team

**A1. Paper application form (deadline).** It must *arrive* at ul. Basztowa 20 by Fri 23 Oct 2026,
14:30 (the rules say 25 Oct, a Sunday). Needs the team members and the leader's name. Send by
courier by ~20 Oct and keep the tracking number.

**A2. Where the air archiver runs permanently.** Today: launchd on this Mac (installed 2026-10-13,
history back to 2026-10-11 00:00 UTC). A sleeping laptop loses hours; gaps up to 3 days are
back-filled automatically. Options: the `air` service in docker-compose on a small VPS (recommended,
it is ready), or keep the Mac awake.

**A3. Public demo URL.** `docker compose up` works locally (http://localhost:8080). A public demo
needs a host (VPS ~2 GB RAM is enough: the API uses ~1 GB). Decide who hosts it.

**A4. MSIP services and the regulamin.** The regulamin forbids redistributing MSIP map services and
requires written consent for continuous, organised use of them in another system. The app does not
do that (it downloads the open data once, D-010). If the city wants the app to refresh from the
services automatically, ask the MSIP administrator (gd.umk@um.krakow.pl) for consent.

**A5. GIOŚ index bands.** `config/air_stations.yml` uses the GIOŚ index bands as we know them
(PM10 20/50/80/110/150, PM2.5 13/35/55/75/110, NO₂ 40/100/150/230/400 µg/m³). Please confirm them
against the GIOŚ index documentation on powietrze.gios.gov.pl.

**A6. Weights and thresholds.** Profiles (`config/profiles.yml`) and ETL values (`config/etl.yml`)
are starting values. The golden-route tests show the effect of a change.

**A7. Open source after the contest?** (Plan section 11.5.) If the repository is published, the
OSM-derived Parquet files stay out of it (ODbL share-alike); the ETL scripts rebuild them.

## B. Checks that need a person

**B1. Station types (traffic / urban background) for the 8 GIOŚ stations.** Not in the API. Needed
for the write-up of the NO₂ traffic-vs-background check (plan 5.3 point 4). Look on the station pages
of powietrze.gios.gov.pl.

**B2. GIOŚ hour labels.** Is the value at "14:00" the hour ending or starting at 14:00? The archiver
stores the label as given (converted to UTC), so nothing is lost either way.

**B3. Which roads the noise map models** (catalogue 1361 / the 2022 report). If minor streets are not
modelled they look quiet only because they are missing. Not stated in the downloaded files.

**B4. IOŚ-PIB forecast terms** (`https://api.prognozy.ios.edu.pl/v1/PM10/1261/`). Not used yet; the
"tomorrow" indicator is a stretch feature.

**B5. Schools with no house number in the portal API.** 133 rows of the school/kindergarten tables
have `Nr domu = null` (the column is typed as a number, so values like "9-11" are probably lost).
Worth reporting to the portal (otwartedane.um.krakow.pl/kontakt); the planner places them
approximately (D-019).

**B6. ZTP layers (transit stops, cycling infrastructure).** They are on ArcGIS Hub
(ztpk-gmk-2.hub.arcgis.com), linked from otwartedane. Not used yet: transit stops would strengthen the
planner's "sensitive presence", cycling infrastructure could lower the bike cost on separated paths.
Resolving the Hub map ids to feature-layer URLs needs a check in the browser.
