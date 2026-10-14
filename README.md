# Zdrowa Trasa

Zdrowsze trasy piesze i rowerowe po Krakowie: cichsze, z czystszym powietrzem, bardziej zielone.
Aplikacja pokazuje też, ile to kosztuje w minutach. Druga zakładka, „Dla miasta”, wskazuje miejsca,
gdzie wysoka ekspozycja spotyka wielu wrażliwych użytkowników (szkoły, przedszkola, żłobki,
mieszkańcy). Projekt na konkurs „Open Data App” Gminy Miejskiej Kraków.

Dokumentacja: [metodologia](docs/methodology.md) · [architektura](docs/architecture.md) ·
[źródła danych](docs/data-sources.md) · [decyzje](docs/DECISIONS.md) ·
[otwarte pytania](docs/OPEN_QUESTIONS.md).

## Uruchomienie (Docker, zalecane)

Wymagania: Docker z Compose, około 4 GB RAM do budowy danych i 2 GB do działania.

```sh
# 1. Dane: pobranie źródeł i przetworzenie (jednorazowo, ok. 20 min; Overpass i MSIP)
docker compose --profile etl run --rm etl

# 2. Aplikacja
docker compose up --build -d
```

Aplikacja działa pod **http://localhost:8080**, dokumentacja API (OpenAPI) pod
http://localhost:8080/api/v1/docs. Usługa `air` co godzinę
dopisuje odczyty GIOŚ do `data/processed/air_history.sqlite`.

Przykładowe dane wejściowe: Skąd „Basztowa 20”, Dokąd „Wawel 5”, pieszo, profil „Cicha”. Można też
kliknąć na mapie: pierwszy klik to start, drugi to cel.

```sh
curl -s -X POST localhost:8080/api/v1/route -H 'content-type: application/json' \
  -d '{"origin":{"lon":19.9456,"lat":50.0680},"destination":{"lon":19.9361,"lat":50.0542},"mode":"walk","profile":"quiet"}'
```

Publiczne wdrożenie (maszyna wirtualna Azure, HTTPS): [docs/deployment.md](docs/deployment.md).

## Uruchomienie bez Dockera (deweloperskie)

Wymagania: Python 3.12 i [uv](https://docs.astral.sh/uv/), Node.js 20 lub nowszy.

```sh
make setup        # .venv z Pythonem 3.12 i zależnościami
make fetch        # pobranie danych do data/raw/ (MSIP z mapą hałasu 614 MB, otwartedane)
make data         # siatki hałasu, grafy OSM, ekspozycja, geokoder, planista (ok. 15 min)
make api          # API na :8000
make web          # frontend na :5173 (proxy /api → :8000)
make test         # pytest (57 testów; trasy wzorcowe wymagają make data)
make lint         # ruff, black, tsc
./ops/install_launchd.sh   # archiwizator powietrza co godzinę (macOS)
```

Na Linuksie zamiast launchd można użyć crona:
`7 * * * * cd /ścieżka/do/repo && .venv/bin/python -m etl.air >> logs/air.log 2>&1`.

## Dane i licencje

Źródła: Gmina Miejska Kraków, Portal MSIP Obserwatorium (https://msip.krakow.pl) i
otwartedane.um.krakow.pl; Główny Inspektorat Ochrony Środowiska, Portal Jakość Powietrza (dane nie
są na bieżąco weryfikowane); © współtwórcy OpenStreetMap (ODbL); podkład OpenFreeMap / OpenMapTiles.
Daty wytworzenia i pozyskania każdego zbioru są w `data/manifest.yml` i w panelu „O danych”.
Inspiracją metody jest Green Paths 2 (DigitalGeographyLab, licencja MIT).

Indeks ekspozycji służy do porównywania tras i nie jest oceną medyczną.

---

**English summary.** Healthier walking and cycling routes for Kraków (noise, live air quality,
greenery) with the time trade-off, plus a planner view that ranks street segments where high
exposure meets many sensitive users. Run `docker compose --profile etl run --rm etl` once to build
the data, then `docker compose up --build -d` and open http://localhost:8080. The UI is Polish by
default; switch to English in the header.
