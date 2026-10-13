"""API contract: status codes and response shapes (synthetic store, no data files)."""

import pytest
from fastapi.testclient import TestClient

from api import main
from api.store import TO_4326


@pytest.fixture
def client(fake_store):
    main.STORE["s"] = fake_store
    yield TestClient(main.app)  # not used as a context manager: lifespan (real data) is skipped
    main.STORE.clear()


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert (
        body["networks"] == ["walk"] and body["geocoder"] is False and body["status"] == "degraded"
    )


def test_route_contract(client, fake_store):
    xy = fake_store.networks["walk"].node_xy
    o, d = TO_4326.transform(*xy[0]), TO_4326.transform(*xy[-1])
    r = client.post("/api/v1/route", json={"origin": {"lon": o[0], "lat": o[1]},
                                           "destination": {"lon": d[0], "lat": d[1]},
                                           "mode": "walk", "profile": "quiet"})  # fmt: skip
    assert r.status_code == 200
    body = r.json()
    assert {x["kind"] for x in body["routes"]} == {"fastest", "healthiest", "balanced"}
    route = body["routes"][1]
    assert route["geometry"]["type"] == "FeatureCollection"
    assert set(route["metrics"]) >= {
        "duration_min",
        "distance_m",
        "noise_mean_db",
        "exposure_index",
    }
    assert route["tradeoff"]["text"]


def test_route_errors(client):
    far = {"origin": {"lon": 21.0, "lat": 52.2}, "destination": {"lon": 19.94, "lat": 50.06}}
    r = client.post("/api/v1/route", json=far)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "outside_city"
    r = client.post("/api/v1/route", json={**far, "mode": "car"})
    assert r.status_code == 422  # validation error
    r = client.post("/api/v1/route", json={**far, "mode": "bike"})
    assert r.status_code == 404 and r.json()["detail"]["code"] == "mode_unavailable"


def test_geocoder_missing_is_503(client):
    assert client.get("/api/v1/geocode", params={"q": "Basztowa"}).status_code == 503


def test_sources_from_manifest(client):
    r = client.get("/api/v1/meta/sources")
    assert r.status_code == 200 and r.json()[0]["citation"] == "C"


def test_openapi_is_published(client):
    assert client.get("/api/v1/openapi.json").json()["info"]["title"] == "Zdrowa Trasa API"
