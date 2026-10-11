"""GIOŚ client tests. Fixtures are recorded real responses; no live calls."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from etl import air
from etl.fetch import gios

FX = Path(__file__).parent / "fixtures" / "gios"
UTC = timezone.utc


def fx(name: str) -> dict:
    return json.loads((FX / name).read_text(encoding="utf-8"))


def make_client(handler=None, sleeps=None, clock=None) -> gios.GiosClient:
    def default(request: httpx.Request) -> httpx.Response:
        assert request.headers["accept"] == "application/ld+json"
        path = request.url.path
        if path.endswith("/station/findAll"):
            return httpx.Response(200, json=fx("stations_findAll.json"))
        if "/station/sensors/" in path:
            return httpx.Response(200, json=fx(f"sensors_{path.rsplit('/', 1)[1]}.json"))
        if "/data/getData/" in path:
            return httpx.Response(200, json=fx(f"data_{path.rsplit('/', 1)[1]}.json"))
        return httpx.Response(404, json={})

    sleeps = sleeps if sleeps is not None else []
    t = {"now": 0.0}
    return gios.GiosClient(
        http=httpx.Client(transport=httpx.MockTransport(handler or default)),
        sleep=lambda s: (sleeps.append(s), t.__setitem__("now", t["now"] + s)),
        clock=clock or (lambda: t["now"]),
    )


def test_station_metadata_for_the_three_stations():
    by_id = {s.station_id: s for s in gios.parse_stations(fx("stations_findAll.json"))}
    assert by_id[400].name == "Kraków, Aleja Krasińskiego"
    assert (by_id[400].lat, by_id[400].lon) == (50.057678, 19.926189)
    assert by_id[401].code == "MpKrakBujaka" and by_id[402].code == "MpKrakBulwar"


def test_two_pm10_sensors_at_401_and_402():
    for st, expected in ((401, {2770, 2771}), (402, {2792, 2793})):
        sensors = gios.parse_sensors(fx(f"sensors_{st}.json"))
        assert {s.sensor_id for s in sensors if s.indicator_id == 3} == expected


def test_manual_sensor_error_is_recognised():
    for sid in (2771, 2773, 2793):
        with pytest.raises(gios.ManualSensorError):
            gios.parse_readings(fx(f"data_{sid}.json"))


def test_readings_drop_null_and_convert_local_to_utc():
    raw = fx("data_2770.json")
    readings = gios.parse_readings(raw)
    assert all(r.value is not None for r in readings)
    assert len(readings) == sum(1 for r in raw[gios.K_READINGS] if r["Wartość"] is not None)
    # "2026-10-11 14:00:00" local (CEST, UTC+2) with value 5.5 -> 12:00 UTC
    hit = [r for r in readings if r.ts_utc == datetime(2026, 10, 11, 12, tzinfo=UTC)]
    assert hit and hit[0].value == 5.5
    assert readings == sorted(readings, key=lambda r: r.ts_utc)


def test_dst_end_repeated_hour_gets_distinct_utc_times():
    naive = [datetime(2026, 10, 25, h) for h in (1, 2, 2, 3)]  # 02:00 occurs twice (CEST, CET)
    out = gios.local_to_utc(naive, "Europe/Warsaw")
    assert [t.hour for t in out] == [23, 0, 1, 2]
    assert len(set(out)) == 4


def test_hourly_sensor_selected_from_data_not_position():
    c = make_client()
    assert gios.choose_hourly_sensor([2771, 2770], c.readings)[0] == 2770
    assert gios.choose_hourly_sensor([2770, 2771], c.readings)[0] == 2770
    assert gios.choose_hourly_sensor([2793, 2792], c.readings)[0] == 2792
    assert gios.choose_hourly_sensor([2773], c.readings) == (None, [])  # Bujaka PM2.5: manual


def test_metadata_calls_are_throttled_and_data_calls_are_not():
    sleeps: list[float] = []
    c = make_client(sleeps=sleeps)
    c.stations()
    c.sensors(400)
    assert len(sleeps) == 1 and sleeps[0] == pytest.approx(31, abs=0.01)
    sleeps.clear()
    c.readings(2750)
    c.readings(2752)
    assert sleeps == []


def test_pagination_merges_pages():
    pages = {
        0: {gios.K_READINGS: [{"Kod stanowiska": "X-PM10-1g", "Data": "2026-01-01 10:00:00",
                               "Wartość": 1.0}], "totalPages": 2},
        1: {gios.K_READINGS: [{"Kod stanowiska": "X-PM10-1g", "Data": "2026-01-01 11:00:00",
                               "Wartość": 2.0}], "totalPages": 2},
    }  # fmt: skip

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=pages[int(req.url.params["page"])])

    out = make_client(handler).readings(1)
    assert [r.value for r in out] == [1.0, 2.0]


def test_http_error_raises_and_5xx_is_retried():
    calls = {"n": 0}

    def handler(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, json={})

    with pytest.raises(gios.GiosError):
        make_client(handler).readings(1)
    assert calls["n"] == 3
    with pytest.raises(gios.GiosError):
        make_client(lambda r: httpx.Response(406, json={"status": 406})).readings(1)


def test_archiver_run_is_idempotent_and_records_missing_series(tmp_path):
    client = make_client()
    cfg = client.cfg
    cache = {"stations": {}, "hourly_sensor": {}}
    air.refresh_metadata(client, cfg, cache)
    assert set(cache["stations"]) == {
        "400",
        "401",
        "402",
        "10123",
        "10139",
        "10447",
        "11303",
        "16896",
    }
    con = air.connect(tmp_path / "air.sqlite")
    ok = air.run_once(client, cfg, con, cache)
    # 3 original stations: 9 series minus Bujaka PM2.5 (manual); 5 added: 5 PM10 + 1 NO2
    assert ok == 14
    n1 = con.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    assert air.run_once(client, cfg, con, cache) == 14
    assert con.execute("SELECT COUNT(*) FROM readings").fetchone()[0] == n1  # no duplicates
    assert cache["hourly_sensor"]["401/PM10"] == 2770
    assert cache["hourly_sensor"]["402/PM10"] == 2792
    assert cache["hourly_sensor"]["10447/PM10"] == 17309  # manual sensor listed second
    assert cache["hourly_sensor"]["10123/PM10"] == 16786  # manual sensor listed first
    missing = con.execute(
        "SELECT station_id, pollutant FROM fetch_log WHERE status='no_hourly_sensor'"
    ).fetchall()
    assert set(missing) == {(401, "PM25")}
    # all stored timestamps are UTC ISO strings
    ts = con.execute("SELECT ts_utc FROM readings").fetchall()
    assert all(t[0].endswith("Z") for t in ts)
    sqlite3.connect(tmp_path / "air.sqlite").close()
