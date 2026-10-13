"""Zdrowa Trasa API (v1). Start: uvicorn api.main:app --no-access-log

Privacy: route requests are processed in memory and discarded; nothing about a request is stored
and the access log is off (the geocoder query string could contain an address).
"""

from __future__ import annotations

import csv
import io
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from api import routing
from api.models import GeocodeResult, Health, RouteRequest, RouteResponse
from api.store import Store, load_store
from etl.common import PROCESSED

log = logging.getLogger("api")
STORE: dict[str, Store] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    STORE["s"] = load_store()
    yield
    STORE.clear()


app = FastAPI(
    title="Zdrowa Trasa API",
    version="1.0.0",
    description="Healthier walking and cycling routes in Kraków (noise, air, greenery).",
    lifespan=lifespan,
    docs_url="/api/v1/docs",
    redoc_url=None,
    openapi_url="/api/v1/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"])


def store() -> Store:
    return STORE["s"]


@app.get("/api/v1/health", response_model=Health)
def health() -> dict[str, Any]:
    s = store()
    ok = bool(s.networks) and s.geocoder is not None
    return {
        "status": "ok" if ok else "degraded",
        "networks": sorted(s.networks),
        "geocoder": s.geocoder is not None,
        "air": bool(s.air.get().get("available")),
        "planner": "planner_hotspots" in s.planner,
    }


@app.get("/api/v1/geocode", response_model=list[GeocodeResult])
def geocode(q: str = Query(min_length=2, max_length=120), limit: int = Query(8, ge=1, le=20)):
    s = store()
    if s.geocoder is None:
        raise HTTPException(503, "geocoder not built")
    return [p.__dict__ for p in s.geocoder.search(q, limit)]


@app.post("/api/v1/route", response_model=RouteResponse)
def route(req: RouteRequest) -> dict[str, Any]:
    try:
        return routing.plan(store(), req)
    except routing.RouteError as exc:
        status = 422 if exc.code in ("outside_city", "far_from_network", "same_point") else 404
        raise HTTPException(status, {"code": exc.code, "message": str(exc)}) from exc


@app.get("/api/v1/air/now")
def air_now() -> dict[str, Any]:
    a = store().air.get()
    a = dict(a)
    a["source"] = "Główny Inspektorat Ochrony Środowiska, Portal Jakość Powietrza (API)"
    a["note"] = "Dane GIOŚ nie są na bieżąco weryfikowane. Wskaźnik miejski jest orientacyjny."
    return a


@app.get("/api/v1/meta/sources")
def sources() -> list[dict[str, Any]]:
    """The "About data" panel, generated from data/manifest.yml."""
    out = []
    for key, d in store().manifest["datasets"].items():
        if not isinstance(d, dict):
            continue
        out.append(
            {
                "key": key,
                "title": d.get("title"),
                "provider": d.get("provider"),
                "link": d.get("catalogue_page")
                or d.get("page")
                or d.get("layer_url")
                or d.get("url")
                or d.get("api_base"),
                "data_date": d.get("data_date") or d.get("files_generated"),
                "date_obtained": d.get("date_obtained"),
                "licence": d.get("licence"),
                "citation": d.get("citation_pl") or d.get("citation"),
            }
        )
    return out


@app.get("/api/v1/layers")
def layers() -> dict[str, Any]:
    s = store()
    out = {k: {**v, "url": f"/api/v1/layers/{v['url']}"} for k, v in s.overlays.items()}
    return out


@app.get("/api/v1/layers/{name}.png")
def layer_png(name: str) -> FileResponse:
    s = store()
    if name not in s.overlays:
        raise HTTPException(404, "unknown layer")
    return FileResponse(
        PROCESSED / "overlays" / f"{name}.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


@app.get("/api/v1/points/fountains")
def fountains() -> dict[str, Any]:
    from api.store import TO_4326

    s = store()
    feats = []
    for x, y in s.fountains_xy:
        lon, lat = TO_4326.transform(x, y)
        feats.append(
            {
                "type": "Feature",
                "properties": {},
                "geometry": {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
            }
        )
    return {"type": "FeatureCollection", "features": feats}


@app.get("/api/v1/lines/cycleways")
def cycleways() -> dict[str, Any]:
    """ZTP cycling infrastructure (lines, WGS84, simplified to 2 m) for the map layer."""
    s = store()
    if s.cycleways is None:
        raise HTTPException(503, "cycle infrastructure not downloaded")
    return s.cycleways


@app.get("/api/v1/planner/hotspots")
def hotspots(district: int | None = None, limit: int = Query(20, ge=1, le=500)) -> dict[str, Any]:
    p = store().planner.get("planner_hotspots")
    if p is None:
        raise HTTPException(503, "planner not built")
    feats = [
        f for f in p["features"] if district is None or f["properties"]["district_id"] == district
    ]
    return {"type": "FeatureCollection", "features": feats[:limit], "meta": p.get("meta", {})}


@app.get("/api/v1/planner/districts")
def districts() -> list[dict[str, Any]]:
    p = store().planner.get("planner_districts")
    if p is None:
        raise HTTPException(503, "planner not built")
    return p


@app.get("/api/v1/planner/export.csv")
def export_csv(district: int | None = None) -> Response:
    fc = hotspots(district=district, limit=500)
    buf = io.StringIO()
    cols = [
        "rank",
        "priority",
        "district",
        "street",
        "noise_db",
        "green",
        "traffic",
        "schools",
        "pupils",
        "kindergartens",
        "nurseries",
        "lon",
        "lat",
    ]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for f in fc["features"]:
        pr = dict(f["properties"])
        pr["lon"], pr["lat"] = f["properties"]["centre"]
        w.writerow(pr)
    return Response(
        buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=hotspots.csv"},
    )
