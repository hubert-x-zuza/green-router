# Źródła danych

Pełne metadane (URL, CRS, pola, daty, warunki, cytowanie) są w `data/manifest.yml`; z niego
generowany jest panel „O danych” w aplikacji. Stan na 2026-10-13.

| Warstwa | Dostawca / zbiór | Format i dostęp | Data danych | Pozyskano | Użycie |
|---|---|---|---|---|---|
| Hałas | GMK, MSIP, „Mapy hałasu 2022” (katalog 1361) | GeoJSON w zip, EPSG:2178 | pliki z 2026-03-23 | 2026-10-13 | kara hałasu (LDWN, LN) |
| Zieleń | GMK, MSIP, Atlas MONIT-AIR 2016 „Mapa zieleni” | ArcGIS REST, 128 221 poligonów | 2016 (ortofoto 2014) | 2026-10-13 | kara zieleni |
| Granica miasta | GMK, MSIP, „Granica Krakowa” | ArcGIS REST | — | 2026-10-13 | zasięg, bufor 500 m |
| Poidełka | GMK, MSIP, „Lokalizacja pitników wody kranowej”, zewnętrzne (1359) | GeoJSON w zip, 63 punkty | 2026-10-10 | 2026-10-13 | profil „Zieleń i woda” |
| Punkty adresowe | GMK, MSIP, EMUiA (1492) | GeoJSON w zip, 70 277 punktów | 2026-10-13 | 2026-10-13 | geokoder, lokalizacja placówek |
| Ulice | GMK, MSIP, EMUiA (1379) | GeoJSON w zip, 3036 linii | 2026-10-13 | 2026-10-13 | geokoder, nazwy w rankingu |
| Dzielnice | GMK, MSIP (1483) | GeoJSON w zip, 18 poligonów | 2025-12-05 | 2026-10-13 | agregacja dla planisty |
| Szkoły, przedszkola, żłobki, kluby dziecięce | GMK, otwartedane.um.krakow.pl | API api.um.krakow.pl (JSON) | rok szk. 2025/26 | 2026-10-13 | obecność osób wrażliwych |
| Mieszkańcy | GMK, otwartedane, „Mieszkańcy zameldowani na pobyt stały” | API, dzielnica × płeć × rok ur. | 31.12.2025 | 2026-10-13 | tabela dzielnic |
| Parki | ZZM, otwartedane, „Parki miejskie w Krakowie” | API (tabela, bez geometrii) | 2026-04-27 | 2026-10-13 | statystyki (rozwój) |
| Infrastruktura rowerowa | ZTP, „Liniowa infrastruktura rowerowa” (otwartedane, ArcGIS Hub) | ArcGIS FeatureServer, 2637 linii | 2026-10 | 2026-10-13 | preferencja dróg odseparowanych, warstwa mapy |
| Miejsca (wyszukiwarka) | © współtwórcy OpenStreetMap (ODbL) | Overpass API (osmnx), 5582 miejsca | 2026-10-13 | 2026-10-13 | wyszukiwanie: obiekty, restauracje, przystanki, części miasta |
| Jakość powietrza | GIOŚ, Portal Jakość Powietrza, API v1 | JSON-LD, co godzinę, 8 stacji | na bieżąco | od 2026-10-11 | indeks miejski `level(t)` |
| Sieć ulic | © współtwórcy OpenStreetMap (ODbL) | Overpass API (osmnx) | 2026-10-13 | 2026-10-13 | grafy, bliskość ruchu |
| Podkład mapy | OpenFreeMap, © OpenMapTiles, dane OSM | kafelki wektorowe | na bieżąco | — | mapa w przeglądarce |

## Warunki wykorzystania

- **Otwarte Dane Kraków:** swobodne, bezpłatne ponowne wykorzystanie. Trzeba podać źródło
  („Gmina Miejska Kraków, otwartedane.um.krakow.pl”) oraz czas wytworzenia i pozyskania danych.
  Pełny tekst: `docs/licences/otwartedane_warunki.md`.
- **MSIP:** „Wykorzystanie danych zgodne z regulaminem MSIP”. Trzeba przywołać źródło („Gmina
  Miejska Kraków, Portal MSIP Obserwatorium (https://msip.krakow.pl)”). Nie wolno redystrybuować
  serwisów mapowych (REST/WMS/WFS), dlatego aplikacja pobiera dane raz i ich nie pośredniczy.
  Pełny tekst: `docs/licences/msip_regulamin.md`.
- **GIOŚ:** wymagane wyraźne wskazanie źródła. Dane nie są na bieżąco weryfikowane.
- **OpenStreetMap:** ODbL. Atrybucja na mapie i w dokumentacji. Przetworzonych tabel krawędzi nie
  publikujemy (share-alike); udostępniamy skrypty ETL.
