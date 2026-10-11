"""GIOŚ air-quality API v1 client (stations, sensors, current hourly readings).

Shapes below were taken from real responses recorded on 2026-10-11 (tests/fixtures/gios).
The API returns JSON-LD with Polish keys and only answers when
`Accept: application/ld+json` is sent (plain `application/json` gives HTTP 406).

Time: current data carry local time (Europe/Warsaw, with DST) as a naive string;
everything leaves this module as timezone-aware UTC.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx
import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "air_stations.yml"
ACCEPT = "application/ld+json"
UTC = timezone.utc

# Keys of the JSON-LD payloads (Polish, as returned by the API).
K_STATIONS = "Lista stacji pomiarowych"
K_SENSORS = "Lista stanowisk pomiarowych dla podanej stacji"
K_READINGS = "Lista danych pomiarowych"
ERR_MANUAL_SENSOR = "API-ERR-100003"  # manual sensor: no current data, only archive after 4-8 weeks


class GiosError(RuntimeError):
    pass


class ManualSensorError(GiosError):
    """Sensor is manual: no current hourly data from the live endpoint."""


@dataclass(frozen=True)
class Station:
    station_id: int
    code: str
    name: str
    lat: float
    lon: float
    city: str | None
    street: str | None


@dataclass(frozen=True)
class Sensor:
    sensor_id: int
    station_id: int
    indicator: str
    indicator_code: str
    indicator_id: int


@dataclass(frozen=True)
class Reading:
    series_code: str  # e.g. MpKrakBujaka-PM10-1g
    ts_utc: datetime
    value: float


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ---- pure parsers -------------------------------------------------------------------------


def _raise_if_error(payload: dict[str, Any]) -> None:
    if "error_code" in payload:
        msg = f"{payload.get('error_code')}: {payload.get('error_reason')}"
        if payload["error_code"] == ERR_MANUAL_SENSOR:
            raise ManualSensorError(msg)
        raise GiosError(msg)


def parse_stations(payload: dict[str, Any]) -> list[Station]:
    _raise_if_error(payload)
    return [
        Station(
            station_id=s["Identyfikator stacji"],
            code=s["Kod stacji"],
            name=s["Nazwa stacji"],
            lat=float(s["WGS84 φ N"]),
            lon=float(s["WGS84 λ E"]),
            city=s.get("Nazwa miasta"),
            street=s.get("Ulica"),
        )
        for s in payload[K_STATIONS]
    ]


def parse_sensors(payload: dict[str, Any]) -> list[Sensor]:
    _raise_if_error(payload)
    return [
        Sensor(
            sensor_id=s["Identyfikator stanowiska"],
            station_id=s["Identyfikator stacji"],
            indicator=s["Wskaźnik"],
            indicator_code=s["Wskaźnik - kod"],
            indicator_id=s["Id wskaźnika"],
        )
        for s in payload[K_SENSORS]
    ]


def local_to_utc(naive_times: list[datetime], tz_name: str) -> list[datetime]:
    """Convert naive local times to UTC.

    The input must be one series. It is resolved in ascending order so the repeated hour at the
    end of DST (e.g. 02:00 twice) gets fold=0 the first time and fold=1 the second time.
    Returns UTC datetimes in the same order as the input.
    """
    tz = ZoneInfo(tz_name)
    order = sorted(range(len(naive_times)), key=lambda i: naive_times[i])
    out: list[datetime | None] = [None] * len(naive_times)
    prev: datetime | None = None
    for i in order:
        t = naive_times[i]
        utc = t.replace(tzinfo=tz, fold=0).astimezone(UTC)
        if prev is not None and utc <= prev:  # repeated local hour -> second occurrence
            utc = t.replace(tzinfo=tz, fold=1).astimezone(UTC)
        out[i] = utc
        prev = utc
    return [t for t in out if t is not None]


def parse_readings(payload: dict[str, Any], tz_name: str = "Europe/Warsaw") -> list[Reading]:
    """Non-null readings, UTC, ascending. Null values (e.g. the hour in progress) are dropped,
    never replaced by zeros."""
    _raise_if_error(payload)
    rows = [r for r in payload[K_READINGS] if r["Wartość"] is not None]
    times = [datetime.strptime(r["Data"], "%Y-%m-%d %H:%M:%S") for r in rows]
    utc = local_to_utc(times, tz_name)
    out = [
        Reading(series_code=r["Kod stanowiska"], ts_utc=u, value=float(r["Wartość"]))
        for r, u in zip(rows, utc, strict=True)
    ]
    return sorted(out, key=lambda x: x.ts_utc)


def choose_hourly_sensor(
    candidates: list[int],
    fetch: Callable[[int], list[Reading]],
    hourly_suffix: str = "-1g",
) -> tuple[int | None, list[Reading]]:
    """Return (sensor_id, readings) for the candidate that delivers hourly data.

    A candidate that raises ManualSensorError is skipped. A candidate counts as hourly when its
    series code ends with `hourly_suffix` and it has at least one reading. If several qualify the
    one with most readings wins; a tie is an error (we do not guess by list position).
    Returns (None, []) when no candidate delivers hourly data.
    """
    ok: list[tuple[int, list[Reading]]] = []
    for sid in candidates:
        try:
            readings = fetch(sid)
        except ManualSensorError:
            continue
        if readings and all(r.series_code.endswith(hourly_suffix) for r in readings):
            ok.append((sid, readings))
    if not ok:
        return None, []
    ok.sort(key=lambda t: len(t[1]), reverse=True)
    if len(ok) > 1 and len(ok[0][1]) == len(ok[1][1]):
        raise GiosError(f"cannot tell hourly sensor apart among {[s for s, _ in ok]}")
    return ok[0]


# ---- HTTP client --------------------------------------------------------------------------


class GiosClient:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cfg = config or load_config()
        self.base = self.cfg["base_url"].rstrip("/")
        self.http = http or httpx.Client(timeout=self.cfg["request_timeout_s"])
        self._sleep, self._clock = sleep, clock
        self._last_meta: float | None = None

    def _get(self, path: str, params: dict[str, Any], metadata: bool) -> dict[str, Any]:
        if metadata and self._last_meta is not None:  # metadata limit: 2 req/min
            wait = self.cfg["metadata_min_interval_s"] - (self._clock() - self._last_meta)
            if wait > 0:
                self._sleep(wait)
        last_exc: Exception | None = None
        for attempt in range(self.cfg["retries"]):
            if metadata:
                self._last_meta = self._clock()
            try:
                resp = self.http.get(
                    f"{self.base}/{path}", params=params, headers={"Accept": ACCEPT}
                )
            except httpx.TransportError as exc:
                last_exc = exc
            else:
                if resp.status_code >= 500:
                    last_exc = GiosError(f"HTTP {resp.status_code} for {path}")
                else:
                    try:
                        payload = resp.json()
                    except ValueError as exc:
                        raise GiosError(f"HTTP {resp.status_code} non-JSON for {path}") from exc
                    if resp.status_code != 200 and "error_code" not in payload:
                        raise GiosError(f"HTTP {resp.status_code} for {path}")
                    return payload
            self._sleep(2.0 * (attempt + 1))
        raise GiosError(f"giving up on {path}: {last_exc}")

    def _paged(self, path: str, key: str, size: int, metadata: bool) -> dict[str, Any]:
        """Fetch all pages (`page` is 0-based, `totalPages` in the payload) and merge the list."""
        first = self._get(path, {"size": size, "page": 0}, metadata)
        _raise_if_error(first)
        for page in range(1, int(first.get("totalPages", 1))):
            nxt = self._get(path, {"size": size, "page": page}, metadata)
            _raise_if_error(nxt)
            first[key] = first[key] + nxt[key]
        return first

    def stations(self) -> list[Station]:
        return parse_stations(self._paged("station/findAll", K_STATIONS, 500, True))

    def sensors(self, station_id: int) -> list[Sensor]:
        return parse_sensors(self._paged(f"station/sensors/{station_id}", K_SENSORS, 100, True))

    def readings(self, sensor_id: int) -> list[Reading]:
        payload = self._paged(f"data/getData/{sensor_id}", K_READINGS, 100, False)
        return parse_readings(payload, self.cfg["timezone_current"])
