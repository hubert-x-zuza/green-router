Recorded GIOŚ API v1 responses, fetched 2026-10-11 ~15:30 Europe/Warsaw with
`Accept: application/ld+json` (plain `application/json` returns HTTP 406).
`stations_findAll.json` is trimmed to 10 of 288 stations (the 9 Kraków ones + 11 Czerniawa);
everything else is unmodified. `data_2771/2773/2793.json` are the real error bodies
(API-ERR-100003: manual sensor, no current data). Tests must never call the live API.
Added 2026-10-11: sensors_/data_ for the six other Kraków stations (10123, 10139, 10447, 11303, 16896, 20367).
