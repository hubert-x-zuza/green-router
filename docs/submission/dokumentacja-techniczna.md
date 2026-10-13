# Zdrowa Trasa: dokumentacja techniczna

*Szkic do zgłoszenia. Zawiera wymagane części: technologie, wykorzystane dane, opis architektury
i możliwości rozwoju. Szczegóły są w plikach `docs/` repozytorium.*

## 1. Technologie

| Obszar | Technologie |
|---|---|
| Przetwarzanie danych (ETL) | Python 3.12, geopandas, shapely 2, rasterio, scipy, pyproj, osmnx 2, pandas, pyarrow |
| Routing | python-igraph (algorytm Dijkstry), numpy (wektor kosztów na zapytanie) |
| Serwer API | FastAPI, Pydantic 2, Uvicorn; OpenAPI pod `/api/v1/docs` |
| Geokoder | SQLite FTS5, indeks z punktów adresowych i ulic EMUiA |
| Dane bieżące | Klient API GIOŚ (httpx), archiwum SQLite, czas w UTC |
| Frontend | React 19, TypeScript (tryb strict), Vite, MapLibre GL JS 6, i18next (PL/EN) |
| Podkład mapy | OpenFreeMap (kafelki wektorowe, bez kluczy i ciasteczek) |
| Uruchomienie | Docker Compose (api, web/nginx, air, etl), Makefile |
| Jakość | pytest (57 testów), ruff, black, GitHub Actions |

## 2. Wykorzystane dane

Tabela zbiorów z datami wytworzenia i pozyskania: `docs/data-sources.md` (pełne metadane w
`data/manifest.yml`, z którego aplikacja generuje panel „O danych”). W skrócie:

- **Gmina Miejska Kraków, MSIP:** Mapa hałasu 2022, Mapa zieleni (Atlas MONIT-AIR 2016), granica
  miasta, punkty adresowe, ulice, dzielnice, poidełka.
- **Gmina Miejska Kraków, otwartedane.um.krakow.pl:** szkoły, przedszkola, żłobki, kluby dziecięce,
  mieszkańcy, parki; **ZTP:** liniowa infrastruktura rowerowa (drogi dla rowerów, ciągi
  pieszo-rowerowe, pasy, kontrapasy).
- **GIOŚ:** 8 stacji, PM10, PM2.5, NO₂, co godzinę.
- **OpenStreetMap** (ODbL): sieć ulic oraz około 5600 nazwanych miejsc do wyszukiwarki.

Warunki wykorzystania i ich pełne teksty są w `docs/licences/`. Każdy zbiór jest cytowany w panelu
„O danych” razem z datą wytworzenia i pozyskania.

## 3. Architektura

Schemat i opis: `docs/architecture.md`. Trzy warstwy:

1. **ETL (offline, powtarzalny):** pobiera źródła, buduje grafy OSM, siatki ekspozycji 10 m, kary
   na odcinkach, geokoder i ranking dla planisty. Jedno polecenie: `make fetch && make data` albo
   `docker compose --profile etl run --rm etl`.
2. **Archiwizator powietrza:** co godzinę pobiera pomiary GIOŚ do SQLite.
3. **API + frontend:** bezstanowe API ładuje dane do pamięci (~1 s) i liczy trzy trasy w < 0,1 s;
   frontend w przeglądarce pokazuje mapę, trasy, porównanie i widok dla miasta.

Metoda (funkcja kosztu, normalizacja, indeks powietrza, priorytet dla planisty, ograniczenia):
`docs/methodology.md`. Najważniejsze decyzje projektowe z uzasadnieniem: `docs/DECISIONS.md`.

## 4. Testy i jakość

- Funkcja kosztu: testy jednostkowe.
- Własności routingu: wagi 0 dają najkrótszą ścieżkę; rosnąca waga hałasu nie zwiększa średniego
  hałasu trasy; limit wydłużenia jest zawsze dotrzymany.
- 10 tras wzorcowych między punktami orientacyjnymi Krakowa (Dworzec, Rynek, Wawel, AGH, Kazimierz,
  Tauron Arena, Nowa Huta, Kampus UJ, Bronowice, Podgórze), pieszo i rowerem.
- Kontrakt API (kody odpowiedzi, kształt danych), przetwarzanie danych, geokoder.
- Testy nie łączą się z zewnętrznymi serwisami: używają nagranych odpowiedzi GIOŚ i danych syntetycznych.

## 5. Możliwości rozwoju

- Ostatni odcinek podróży komunikacją miejską (GTFS ZTP, także opóźnienia na żywo).
- Liczniki rowerowe ZTP (natężenie ruchu rowerowego w widoku dla miasta).
- Wyspy ciepła latem (miejskie rastry MWC; prototyp dekodera istnieje).
- Prognoza jakości powietrza na jutro (IOŚ-PIB) i powiadomienia smogowe.
- Moduł „co jeśli” dla planisty: nasadzenia, ograniczenie prędkości i ich efekt na ranking.
- Integracja z mKraków; otwarte API dla innych aplikacji.
- Skala: PostGIS + pgRouting, kafelki wektorowe; kalibracja na sieci tanich czujników.
- Inne miasta: ten sam proces, wystarczy podmienić źródła w `config/sources.yml`.
