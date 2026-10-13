# Zdrowa Trasa: zdrowsze trasy po Krakowie

*Szkic opisu do zgłoszenia (PDF, maks. 2 strony). Do uzupełnienia: nazwy autorów, adres demo,
zrzut ekranu.*

## Problem

Krakowianie chodzą i jeżdżą rowerem wzdłuż ulic, przy których hałas przekracza 70 dB, a powietrze
w sezonie grzewczym należy do najgorszych w Polsce. Popularne nawigacje szukają najkrótszej drogi
i nie mówią, że równoległa ulica albo ścieżka przez park jest dużo cichsza i bardziej zielona,
a dłuższa tylko o kilka minut. Miasto ma dane, które to pokazują (mapy hałasu, mapę zieleni,
pomiary powietrza), ale mieszkaniec nie ma z nich praktycznego pożytku na co dzień.

## Rozwiązanie

**Zdrowa Trasa** to aplikacja webowa (telefon i komputer, PL/EN) z dwiema zakładkami.

1. **Trasa:** dla dowolnych dwóch adresów w Krakowie wyznacza trzy trasy piesze lub rowerowe:
   najszybszą, najzdrowszą w zadanym limicie czasu i zrównoważoną. Pokazuje koszt w minutach
   i zysk, np. *„+6 min, −34 % ekspozycji, −37 % hałasu, +108 % zieleni”* (rowerem z Nowej Huty na
   Rynek). Trasa jest pokolorowana według hałasu na każdym odcinku. Użytkownik wybiera priorytet:
   cisza, czyste powietrze, zieleń i woda (poidełka) albo własne wagi. Trasy chętniej prowadzą
   drogami rowerowymi i ciągami pieszo-rowerowymi ZTP, odseparowanymi od ruchu (rowerem z Nowej Huty
   na Rynek: 72 % trasy zamiast 12 %, za +1 min). Cel można wpisać jako adres albo nazwę miejsca
   (Tauron Arena, Kazimierz, restauracja), a gotową trasę otworzyć w Google Maps lub pobrać jako GPX.
2. **Dla miasta:** ranking miejsc, w których wysoka ekspozycja (hałas, ruch, brak zieleni) spotyka
   wielu wrażliwych użytkowników: uczniów, przedszkolaków, dzieci w żłobkach i mieszkańców. Każda
   pozycja ma wyjaśnienie, np. *„#1 Al. Mickiewicza: hałas 77 dB, zieleń 22 %; w promieniu 200 m
   5 szkół, 1686 uczniów”*. Do tego tabela 18 dzielnic i eksport CSV dla ZDMK, ZZM i Referatu
   Smart City.

## Dane

Łączymy **18 zbiorów**, w tym 16 miejskich (7 z MSIP, 9 z portalu otwartych danych, w tym ZTP):

- **Gmina Miejska Kraków (MSIP):** Mapa hałasu 2022 (drogi i szyny, wskaźniki LDWN i LN), Mapa
  zieleni, granica miasta, punkty adresowe i ulice EMUiA (własny geokoder, bez usług zewnętrznych),
  dzielnice, poidełka.
- **Gmina Miejska Kraków (otwartedane.um.krakow.pl):** szkoły podstawowe i ponadpodstawowe,
  przedszkola, żłobki i kluby dziecięce (liczby dzieci), mieszkańcy według dzielnic i wieku,
  infrastruktura rowerowa ZTP.
- **GIOŚ:** pomiary godzinowe z 8 stacji w Krakowie (PM10, PM2.5, NO₂), archiwizowane co godzinę.
- **OpenStreetMap:** sieć ulic i ścieżek oraz klasy dróg.

Dane statyczne i bieżące są połączone w jednej funkcji kosztu trasy:
`czas × (1 + Σ waga × kara)`. Gdy rośnie smog, trasy same odsuwają się od ruchliwych ulic.

## Wpływ na miasto

- **Zdrowie mieszkańców:** mniejsza codzienna ekspozycja na hałas i spaliny bez rezygnacji z
  chodzenia i roweru, a wręcz z zachętą do nich, bo trasa jest przyjemniejsza.
- **Decyzje planistyczne:** lista miejsc, gdzie nasadzenia, strefy ograniczonej prędkości, ekrany
  czy nowe przejścia przyniosą największy efekt dla dzieci i seniorów. Jest gotowa do włączenia
  w prace ZDMK i ZZM.
- **Przejrzystość:** każda liczba ma źródło i datę (panel „O danych”). O ograniczeniach mówimy
  wprost: mapa hałasu to model z 2022 r., a składnik powietrza jest orientacyjny.
- **Prywatność:** bez kont, bez zapisywania lokalizacji, bez ciasteczek analitycznych.

## Innowacyjność i technologia

Łączymy routing wielokryterialny z danymi na żywo i danymi o tym, kto jest narażony. Inspiracją
jest metoda Green Paths 2 (Uniwersytet Helsiński), ale to nasza własna implementacja: aplikacja dla
mieszkańca, a nie narzędzie dla ekspertów. Trasy liczą się w niecałe 0,1 s. Cały proces przetwarzania
danych jest powtarzalny jednym poleceniem, a całość uruchamia się przez `docker compose up`.
Python (FastAPI, igraph, geopandas), React, MapLibre. 57 testów automatycznych.

## Potencjał rozwoju i biznesowy

Warstwa w aplikacji mKraków; licencja dla miast (ten sam proces dla innych miast z mapami
hałasu); API dla aplikacji zdrowotnych, ubezpieczycieli i programów pracowniczych; ostatni odcinek
podróży komunikacją miejską (GTFS); ostrzeżenia smogowe; wyspy ciepła latem.

**Demo:** <adres>  ·  **Kod i instrukcja:** <repozytorium / archiwum>
