# Metodologia

Zdrowa Trasa wyznacza trasy piesze i rowerowe, które omijają hałas, ruch uliczny i zanieczyszczone
powietrze, a prowadzą przez zieleń. Pokazuje przy tym, ile kosztuje to w minutach. Ten dokument
opisuje, jak liczymy ekspozycję i koszt trasy. Wszystkie progi i wagi są w `config/*.yml`.

## 1. Sieć ulic

- Źródło: OpenStreetMap (Overpass API, biblioteka osmnx). Obszar to granica Krakowa z MSIP plus 500 m.
- Dwa grafy: **pieszy** (chodniki, ścieżki, deptaki, ulice osiedlowe) i **rowerowy** (drogi dla
  rowerów i ulice, po których wolno jechać rowerem). Graf rowerowy respektuje ulice jednokierunkowe,
  a tam, gdzie OSM dopuszcza jazdę pod prąd (`oneway:bicycle=no`, `cycleway=opposite*`), dodajemy
  krawędź w drugą stronę. Takich krawędzi jest 2127.
- Krawędź to odcinek między skrzyżowaniami. Pieszych krawędzi skierowanych jest 429 582, rowerowych 184 004.
- Wewnętrzny układ współrzędnych to EPSG:2178 (PL-2000 strefa 7), ten sam co w danych miejskich.
  Do przeglądarki wysyłamy WGS84.

## 2. Ekspozycja na odcinku

Każdą warstwę zamieniamy na siatkę 10 m w EPSG:2178. Każdy odcinek próbkujemy co 15 m (co najmniej
2 punkty, w środkach równych części) i uśredniamy.

| Warstwa | Źródło | Wartość na odcinku | Kara `p ∈ [0, 1]` |
|---|---|---|---|
| Hałas dzienno-wieczorno-nocny | MSIP, Mapa hałasu 2022, LDWN, drogi + szyny | średnia i maksimum, dB | liniowo: 45 dB → 0, 75 dB → 1 |
| Hałas nocny | jw., LN | średnia, dB | 40 dB → 0, 65 dB → 1 (tryb „pora nocna”) |
| Zieleń | MSIP, Mapa zieleni (Atlas MONIT-AIR 2016) | udział klas w promieniu 30 m | `1 − (1,0·wysoka + 0,4·niska + 0,2·sportowa)` |
| Bliskość ruchu | OSM, klasy dróg | maks. po klasach: waga klasy × (1 − odległość/50 m) | wartość w [0, 1] |
| Poidełka | MSIP, pitniki zewnętrzne | odległość do najbliższego | ≤ 100 m → 0, ≥ 500 m → 1 |
| Powietrze (na żywo) | GIOŚ, 8 stacji | patrz punkt 3 | patrz punkt 3 |

**Mapa hałasu.** Źródła drogowe i szynowe łączymy energetycznie: `L = 10·log10(Σ 10^(Lᵢ/10))`.
Najniższa klasa mapy („poniżej progu”) nic nie dodaje, a komórka bez źródła powyżej progu dostaje
wartość minimalną 50 dB (LDWN) lub 45 dB (LN). Sumowanie samych progów dałoby fałszywe 53 dB.
Zweryfikowane statystyki: 63,1 % powierzchni miasta ma wartość minimalną, 14,6 % ma ≥ 65 dB.

**Brak danych to brak danych.** Punkty poza granicą miasta nie mają hałasu ani zieleni. Odcinek, na
którym ponad połowa próbek wypada poza miastem, dostaje `data_coverage = false` i karę neutralną 0,5.
Surowa wartość pozostaje pusta, więc interfejs pokazuje „brak danych” i ostrzega, gdy trasa
wychodzi poza zasięg.

**Sprawdzenie na znanych miejscach** (średnia ważona długością): Al. Pokoju 78 dB, Al. Słowackiego
81 dB, Al. Mickiewicza 80 dB (graf rowerowy, jezdnie), ścieżki parkowe i leśne 52 dB przy zieleni
0,44, Floriańska (deptak) 52 dB.

## 3. Powietrze: indeks miejski, nie mapa

W Krakowie jest tylko 8 stacji GIOŚ z danymi godzinowymi: PM10 na wszystkich ośmiu, NO₂ na czterech,
PM2.5 na dwóch. Z tylu punktów nie da się rzetelnie interpolować mapy zanieczyszczeń, dlatego tego nie robimy.

1. `level(t)`: dla każdego zanieczyszczenia liczymy średnią ze stacji, których najnowszy pomiar ma
   najwyżej 3 h, i dzielimy ją przez dolną granicę klasy „bardzo zły” indeksu GIOŚ (PM10 150,
   PM2.5 110, NO₂ 400 µg/m³). Bierzemy maksimum po zanieczyszczeniach.
2. Rozkład przestrzenny daje statyczny wskaźnik bliskości ruchu:
   `air_penalty = clamp(level(t) · (0,3 + 0,7 · traffic_proximity), 0, 1)`.
   W czysty dzień kara jest mała wszędzie, a w smogu rośnie i odsuwa trasę od ruchliwych ulic.
3. Gdy dane są starsze niż 3 h, składnik powietrza nie wpływa na trasę, a interfejs mówi „brak
   aktualnych danych”. Nie pokazujemy starych danych jako bieżących.
4. Czas zapisujemy w UTC. Dane bieżące GIOŚ są w czasie lokalnym z DST; podwójną godzinę przy zmianie
   czasu 25.10.2026 obsługuje test.

**Walidacja wskaźnika ruchu (13.10.2026, 2,5 doby danych, NO₂):**

| Stacja | NO₂ śr. [µg/m³] | Wskaźnik ruchu w miejscu stacji |
|---|---|---|
| Al. Krasińskiego (400) | 31,1 | 0,72 |
| ul. Bulwarowa (402) | 20,8 | 0,05 |
| ul. Bujaka (401) | 20,3 | 0,28 |
| ul. Kamieńskiego (16896) | 14,8 | 0,54 |

Stacja przy największej arterii ma zarówno najwyższe NO₂, jak i najwyższy wskaźnik, ale
ul. Kamieńskiego wyłamuje się z tego układu. PM10 nie zależy od wskaźnika ruchu (najwyżej Złoty Róg
przy wskaźniku 0,12). To zgodne z tym, że krakowski smog pyłowy pochodzi głównie z ogrzewania i tła
regionalnego. Cztery punkty i 2,5 doby niczego nie dowodzą. **Składnik powietrza jest orientacyjny**
i przede wszystkim odzwierciedla ekspozycję związaną z ruchem. Tak też opisujemy go w aplikacji.
Analizę powtórzymy przed oddaniem pracy, na danych z około 3 tygodni.

## 4. Koszt trasy i profile

```
koszt(e) = długość_m / prędkość(tryb) · (1 + Σ_k w_k(profil) · p_k(e, t))
```

Prędkości: pieszo 1,33 m/s (4,8 km/h), rowerem 4,2 m/s (15 km/h).

| Profil | hałas | powietrze | ruch | zieleń | poidełka |
|---|---|---|---|---|---|
| Najszybsza | 0 | 0 | 0 | 0 | 0 |
| Zrównoważona | 1,0 | 1,0 | 0,5 | 0,7 | 0 |
| Cicha | 3,0 | 0,5 | 0,5 | 0,5 | 0 |
| Czyste powietrze | 0,5 | 3,0 | 1,5 | 0,5 | 0 |
| Zieleń i woda | 0,7 | 0,7 | 0,3 | 2,5 | 1,0 |

Każde zapytanie zwraca trzy trasy: **najszybszą**, **najzdrowszą w limicie** (wybrany profil) i
**zrównoważoną**. Limit wydłużenia (domyślnie 30 % czasu) pilnuje, żeby zdrowsza trasa nie była
absurdalnie dłuższa. Gdy trasa profilu go przekracza, wagi są zmniejszane (bisekcja) do największych,
które mieszczą się w limicie, a karta trasy o tym informuje.

**Metryki trasy:** czas, długość, średni hałas (dB), udział odcinków ≥ 65 dB, średnia zieleń,
indeks powietrza, liczba poidełek w promieniu 100 m, **indeks ekspozycji** 0–100 (średnia ważona
kar z wagami profilu „Zrównoważona”) oraz zdanie o kompromisie względem trasy najszybszej, np.
„+6 min, −34 % ekspozycji, −37 % hałasu, +108 % zieleni”. Procenty hałasu liczymy na karze, a nie
na decybelach, bo dB są w skali logarytmicznej.

**Własności sprawdzane testami:** wagi 0 dają najkrótszą ścieżkę; rosnąca waga hałasu nigdy nie
zwiększa średniego hałasu trasy (całkowita ekspozycja nie rośnie, długość nie maleje); limit
wydłużenia jest zawsze dotrzymany; 10 tras wzorcowych między punktami orientacyjnymi Krakowa.

## 5. Widok dla miasta (planista)

```
priorytet = dotkliwość_ekspozycji × obecność_osób_wrażliwych
```

- Jednostka: kwadrat 150 m (10 062 komórki z ulicami). Komórki agregujemy do 18 dzielnic.
- **Dotkliwość:** średnia ważona długością z kar na odcinkach pieszych w komórce,
  `(1,0·hałas + 1,0·ruch + 0,5·brak zieleni) / 2,5`.
- **Obecność osób wrażliwych:** szkoły podstawowe i ponadpodstawowe (liczba uczniów), przedszkola,
  żłobki i kluby dziecięce (liczba dzieci lub miejsc) w promieniu 200 m, każda placówka do
  3 jednostek (300 osób = 1). Do tego gęstość punktów adresowych jako przybliżenie liczby
  mieszkańców. Wynik ma saturację: `1 − exp(−x/2)`. Kilka placówek już czyni miejsce ważnym, ale
  dziesięć nie czyni go dziesięć razy ważniejszym. Bez tego pierwsza dziesiątka byłaby samym
  Starym Miastem.
- Placówki mają tylko adres, więc umieszczamy je według miejskich punktów adresowych (ulica i numer).
  133 wiersze z portalu nie mają numeru domu. Te umieszczamy w środku punktów adresowych tej samej
  ulicy i kodu pocztowego, jeśli leżą w promieniu 300 m, i oznaczamy jako przybliżone. 96 placówek
  (8 %) pozostaje nieumieszczonych i jest wypisanych w `planner_meta.json`.
- Wynik: ranking 500 komórek z wyjaśnieniem (np. „#1 Al. Mickiewicza: hałas 77 dB, zieleń 22 %,
  bliskość ruchu 63 %; w promieniu 200 m 5 szkół, 1686 uczniów”), tabela dzielnic (mieszkańcy,
  dzieci 0–14 i seniorzy 65+ z danych meldunkowych, placówki, średni hałas, udział głośnych komórek)
  i eksport CSV.

## 6. Ograniczenia (mówimy o nich wprost)

1. Mapa hałasu to model strategiczny z 2022 r. (aktualizowany co 5 lat), a nie pomiar na żywo.
   Klasy co 5 dB oznaczają funkcję schodkową. Deptaki są „ciche”, bo model obejmuje tylko ruch
   drogowy i szynowy. Nie wiemy jeszcze, które drogi model obejmuje (pytanie B3).
2. Mapa zieleni pochodzi z atlasu z 2016 r. (ortofoto 2014). To klasy wysokości, a nie rejestr drzew:
   nie zna gatunków, koron ani cienia.
3. Powietrze to wskaźnik miejski z 8 stacji, rozłożony według bliskości ruchu. Nie widzi lokalnego
   dymu z kominów.
4. Indeks ekspozycji porównuje trasy między sobą. **Nie jest oceną medyczną** i nie mówi nic
   o skutkach zdrowotnych dla konkretnej osoby.
5. Dane obejmują tylko Kraków. Poza granicą miasta przyjmujemy karę neutralną i ostrzegamy.

Inspiracją metody jest Green Paths 2 (DigitalGeographyLab, licencja MIT): ekspozycja per odcinek
doliczana do kosztu czasu. Nie używamy kodu ani zależności Green Paths 2 (r5py, Java).
