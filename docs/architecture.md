# Architektura

```
              ┌──────────── ETL (offline, powtarzalne: make fetch && make data) ────────────┐
 MSIP (zip) ─►│ etl/fetch/msip.py        hałas 2022, adresy, ulice, dzielnice, poidełka     │
 MSIP REST ──►│                          mapa zieleni, granica miasta (stronicowanie)       │
 otwartedane ►│ etl/fetch/otwartedane.py szkoły, przedszkola, żłobki, mieszkańcy, parki     │
 OSM ────────►│ etl/graph.py             graf pieszy i rowerowy, drogi (Overpass, osmnx)    │──► data/processed/
              │ etl/noise_to_grid.py     siatki hałasu 10 m (LDWN, LN)                      │    network_walk.parquet
              │ etl/layers.py            siatki zieleni, ruchu, poidełek + nakładki PNG     │    network_bike.parquet
              │ etl/enrich.py            próbkowanie odcinków co 15 m                       │    geocoder.sqlite
              │ etl/normalise.py         kary p ∈ [0,1], pokrycie danymi                    │    planner_*.json
              │ etl/geocoder.py          indeks SQLite FTS5                                 │    overlays/*.png
              │ etl/planner.py           komórki 150 m, priorytety, dzielnice               │
              └─────────────────────────────────────────────────────────────────────────────┘
 GIOŚ API ───► etl/air.py (co godzinę: launchd / cron / usługa „air”) ──► air_history.sqlite

              ┌──────────────────── API (FastAPI, bezstanowe) ────────────────────┐
 przeglądarka │ start: grafy igraph z Parquet, geokoder, nakładki                 │
 React +  ◄──►│ /api/v1/route     trzy trasy, metryki, kompromis (szybkość)         │
 MapLibre     │ /api/v1/geocode   /api/v1/air/now   /api/v1/meta/sources          │
 (nginx)      │ /api/v1/layers    /api/v1/planner/{hotspots,districts,export.csv} │
              └────────────────────────────────────────────────────────────────────┘
```

## Komponenty

| Część | Technologia | Uwagi |
|---|---|---|
| ETL | Python 3.12, geopandas, shapely 2, rasterio, scipy, osmnx 2, pyproj | Kroki idempotentne i deterministyczne; parametry w `config/etl.yml` |
| Routing | python-igraph (Dijkstra), numpy | Wektor kosztów liczony na zapytanie z kar i wag profilu |
| API | FastAPI + Pydantic, Uvicorn | Wersjonowane `/api/v1`, dokumentacja OpenAPI pod `/docs` |
| Geokoder | SQLite FTS5 | Z punktów adresowych i ulic miasta, bez Nominatim |
| Powietrze | httpx, SQLite | Archiwizator co godzinę, czas w UTC, cache metadanych |
| Frontend | React 19, TypeScript (strict), Vite, MapLibre GL 6, i18next | Najpierw mobile, PL/EN, obsługa klawiaturą |
| Podkład | OpenFreeMap (styl positron) | Bez kluczy i ciasteczek, atrybucja OSM |
| Uruchomienie | Docker Compose: `api`, `web` (nginx), `air`, `etl` (profil) | `docker compose up --build` → http://localhost:8080 |
| Jakość | pytest (70 testów), ruff, black, GitHub Actions | Testy bez wywołań zewnętrznych API (nagrane odpowiedzi) |

## Przepływ zapytania o trasę

1. Przeglądarka wysyła `POST /api/v1/route` (start, cel, tryb, profil, opcjonalne wagi, limit
   wydłużenia, pora nocna).
2. API sprawdza, czy punkty leżą w Krakowie (+500 m), i dociąga je do najbliższego węzła
   (najwyżej 300 m).
3. Z kar statycznych i bieżącego `level(t)` składa wektor kosztów i liczy trzy ścieżki Dijkstrą.
   Jeśli trzeba, ogranicza wagi bisekcją, żeby dotrzymać limitu wydłużenia.
4. Zwraca GeoJSON (każdy odcinek z hałasem, zielenią i pokryciem danymi), metryki i kompromis.
   Nic nie jest zapisywane.

## Prywatność

Zapytania o trasy są przetwarzane w pamięci i od razu usuwane. Logi dostępu są wyłączone
(Uvicorn `--no-access-log`, nginx `access_log off`), bo zapytanie geokodera może zawierać adres.
„Moja lokalizacja” działa wyłącznie w przeglądarce. Nie ma kont, ciasteczek analitycznych ani
zewnętrznych skryptów śledzących.

## Skalowanie i rozwój

- Większy ruch: kilka instancji API za load balancerem (API jest bezstanowe; ~1 GB RAM na instancję).
- Skala miasta i aktualizacje na bieżąco: PostGIS + pgRouting zamiast plików Parquet, nakładki jako
  kafelki wektorowe (PMTiles).
- Inne miasta: ten sam ETL. Trzeba podmienić źródła w `config/sources.yml` i granicę miasta.
