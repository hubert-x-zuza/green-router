"""Hourly air-quality archiver: GIOŚ current data -> SQLite, every timestamp in UTC.

Run once:   python -m etl.air            (the scheduler calls exactly this)
Re-check metadata (coordinates, configured sensor IDs; ~2 min because of the 2 req/min limit):
            python -m etl.air --refresh-metadata

Rules (CLAUDE.md): nulls are never stored as zeros; a pollutant with no hourly sensor is logged
as `no_hourly_sensor` in fetch_log; the same (sensor, hour) is stored once and updated if GIOŚ
revises the value (the data are not continuously verified).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from etl.fetch.gios import UTC, GiosClient, GiosError, choose_hourly_sensor, load_config

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("etl.air")

SCHEMA = """
CREATE TABLE IF NOT EXISTS stations (
  station_id INTEGER PRIMARY KEY, code TEXT, name TEXT, lat REAL, lon REAL, fetched_utc TEXT);
CREATE TABLE IF NOT EXISTS readings (
  sensor_id INTEGER NOT NULL, station_id INTEGER NOT NULL, pollutant TEXT NOT NULL,
  series_code TEXT NOT NULL, ts_utc TEXT NOT NULL, value REAL NOT NULL,
  first_seen_utc TEXT NOT NULL, fetched_utc TEXT NOT NULL,
  PRIMARY KEY (sensor_id, ts_utc));
CREATE INDEX IF NOT EXISTS idx_readings_station_poll_ts ON readings(station_id, pollutant, ts_utc);
CREATE TABLE IF NOT EXISTS fetch_log (
  run_utc TEXT NOT NULL, station_id INTEGER NOT NULL, pollutant TEXT NOT NULL,
  status TEXT NOT NULL, sensor_id INTEGER, n_rows INTEGER, note TEXT);
"""


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def load_cache(path: Path) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"stations": {}, "hourly_sensor": {}}


def save_cache(path: Path, cache: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def refresh_metadata(client: GiosClient, cfg: dict[str, Any], cache: dict[str, Any]) -> None:
    wanted = {int(k) for k in cfg["stations"]}
    for st in client.stations():
        if st.station_id in wanted:
            cache["stations"][str(st.station_id)] = {
                "code": st.code, "name": st.name, "lat": st.lat, "lon": st.lon,
                "fetched_utc": iso(datetime.now(UTC)),
            }  # fmt: skip
    missing = wanted - {int(k) for k in cache["stations"]}
    if missing:
        raise GiosError(f"stations not in findAll: {sorted(missing)}")
    for sid, scfg in cfg["stations"].items():
        by_id = {s.sensor_id: s for s in client.sensors(int(sid))}
        for pol, cands in scfg["sensors"].items():
            for c in cands:
                s = by_id.get(c)
                if s is None or s.indicator_id != cfg["indicator_ids"][pol]:
                    raise GiosError(f"station {sid}: sensor {c} is not {pol} in the API")


def run_once(
    client: GiosClient, cfg: dict[str, Any], con: sqlite3.Connection, cache: dict[str, Any]
) -> int:
    """Fetch every configured pollutant; return the number of series that delivered data."""
    now = iso(datetime.now(UTC))
    for sid, st in cache["stations"].items():
        con.execute(
            "INSERT OR REPLACE INTO stations VALUES (?,?,?,?,?,?)",
            (int(sid), st["code"], st["name"], st["lat"], st["lon"], st["fetched_utc"]),
        )
    ok = 0
    for sid, scfg in cfg["stations"].items():
        for pol, cands in scfg["sensors"].items():
            key = f"{sid}/{pol}"
            pinned = cache["hourly_sensor"].get(key)
            try:
                if pinned:
                    chosen, readings = choose_hourly_sensor(
                        [pinned], client.readings, cfg["hourly_code_suffix"]
                    )
                    if chosen is None:  # pinned sensor stopped delivering: re-decide
                        pinned = None
                if not pinned:
                    chosen, readings = choose_hourly_sensor(
                        cands, client.readings, cfg["hourly_code_suffix"]
                    )
            except GiosError as exc:
                log.warning("station %s %s: %s", sid, pol, exc)
                con.execute(
                    "INSERT INTO fetch_log VALUES (?,?,?,?,?,?,?)",
                    (now, int(sid), pol, "error", None, None, str(exc)[:300]),
                )
                continue
            if chosen is None:
                log.warning("station %s %s: no hourly sensor among %s", sid, pol, cands)
                cache["hourly_sensor"].pop(key, None)
                con.execute(
                    "INSERT INTO fetch_log VALUES (?,?,?,?,?,?,?)",
                    (now, int(sid), pol, "no_hourly_sensor", None, None, f"candidates {cands}"),
                )
                continue
            cache["hourly_sensor"][key] = chosen
            for r in readings:
                con.execute(
                    "INSERT INTO readings VALUES (?,?,?,?,?,?,?,?) "
                    "ON CONFLICT(sensor_id, ts_utc) DO UPDATE SET value=excluded.value, "
                    "fetched_utc=excluded.fetched_utc WHERE value != excluded.value",
                    (chosen, int(sid), pol, r.series_code, iso(r.ts_utc), r.value, now, now),
                )
            con.execute(
                "INSERT INTO fetch_log VALUES (?,?,?,?,?,?,?)",
                (now, int(sid), pol, "ok", chosen, len(readings), None),
            )
            log.info("station %s %s: sensor %s, %d rows", sid, pol, chosen, len(readings))
            ok += 1
    con.commit()
    return ok


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--refresh-metadata", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = load_config()
    db = Path(os.environ.get("AIR_DB_PATH", ROOT / "data/processed/air_history.sqlite"))
    cache_path = Path(os.environ.get("GIOS_METADATA_CACHE", ROOT / "data/raw/gios/metadata.json"))
    cache = load_cache(cache_path)
    client = GiosClient(cfg)
    try:
        if a.refresh_metadata or len(cache["stations"]) < len(cfg["stations"]):
            refresh_metadata(client, cfg, cache)
            save_cache(cache_path, cache)
        con = connect(db)
        ok = run_once(client, cfg, con, cache)
        save_cache(cache_path, cache)
    except GiosError as exc:
        log.error("run failed: %s", exc)
        return 1
    log.info("done: %d series delivered data", ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())


# ---- city-level index (plan 3c point 1) ---------------------------------------------------


def band(value: float, bounds: list[float]) -> int:
    """Index band 0..len(bounds): the first band whose upper bound is >= value."""
    for i, ub in enumerate(bounds):
        if value <= ub:
            return i
    return len(bounds)


def city_level(con: sqlite3.Connection, cfg: dict[str, Any], now: datetime) -> dict[str, Any]:
    """level(t) from the newest readings. Never fills gaps: a pollutant with no fresh station is
    reported as missing and left out of the max."""
    ic = cfg["index"]
    rows = con.execute(
        "SELECT r.station_id, r.pollutant, r.ts_utc, r.value, s.name, s.lat, s.lon "
        "FROM readings r JOIN (SELECT station_id, pollutant, MAX(ts_utc) AS ts FROM readings "
        "GROUP BY station_id, pollutant) m ON r.station_id = m.station_id "
        "AND r.pollutant = m.pollutant AND r.ts_utc = m.ts LEFT JOIN stations s "
        "ON s.station_id = r.station_id"
    ).fetchall()
    if not rows:
        return {"available": False}
    newest = max(datetime.strptime(r[2], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) for r in rows)
    window = ic["window_h"] * 3600
    stations: dict[int, dict[str, Any]] = {}
    per_pol: dict[str, list[float]] = {}
    for sid, pol, ts, value, name, lat, lon in rows:
        t = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
        st = stations.setdefault(sid, {"station_id": sid, "name": name, "lat": lat, "lon": lon,
                                       "values": {}})  # fmt: skip
        fresh = (newest - t).total_seconds() <= window
        st["values"][pol] = {"value": value, "ts_utc": ts, "fresh": fresh,
                             "band": band(value, ic["bands"][pol])}  # fmt: skip
        if fresh:
            per_pol.setdefault(pol, []).append(value)
    pollutants = {}
    for pol, vals in per_pol.items():
        mean = sum(vals) / len(vals)
        pollutants[pol] = {
            "mean": round(mean, 1),
            "n_stations": len(vals),
            "normalised": min(1.0, max(0.0, mean / ic["normalise_at"][pol])),
            "band": band(mean, ic["bands"][pol]),
        }
    level = max(p["normalised"] for p in pollutants.values())
    worst = max(p["band"] for p in pollutants.values())
    age_h = (now - newest).total_seconds() / 3600
    return {
        "available": True,
        "level": round(level, 3),
        "band": worst,
        "band_pl": ic["band_names_pl"][worst],
        "band_en": ic["band_names_en"][worst],
        "data_ts_utc": iso(newest),
        "stale": age_h > ic["stale_after_h"],
        "pollutants": pollutants,
        "missing": sorted(set(ic["bands"]) - set(pollutants)),
        "stations": sorted(stations.values(), key=lambda s: s["station_id"]),
    }
