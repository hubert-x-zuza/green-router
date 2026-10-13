"""Pydantic request and response models (API v1)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Mode = Literal["walk", "bike"]
Profile = Literal["fastest", "balanced", "quiet", "clean_air", "green_water"]
Lang = Literal["pl", "en"]


class LonLat(BaseModel):
    lon: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class Weights(BaseModel):
    """Optional slider override of the profile weights."""

    noise: float = Field(ge=0, le=5)
    air: float = Field(ge=0, le=5)
    traffic: float = Field(ge=0, le=5)
    green: float = Field(ge=0, le=5)
    fountain: float = Field(ge=0, le=5)


class RouteRequest(BaseModel):
    origin: LonLat
    destination: LonLat
    mode: Mode = "walk"
    profile: Profile = "balanced"
    weights: Weights | None = None
    max_detour_pct: float = Field(default=30, ge=0, le=100)
    night: bool = False
    lang: Lang = "pl"


class RouteMetrics(BaseModel):
    distance_m: float
    duration_min: float
    noise_mean_db: float | None
    noise_night_mean_db: float | None
    share_loud: float | None = Field(description="share of length with LDWN >= 65 dB")
    exposure_noise: float | None
    green_mean: float | None
    traffic_mean: float | None
    air_index: float | None
    exposure_index: float | None = Field(description="0 (none) ... 100 (worst)")
    coverage: float = Field(description="share of length with noise/green data")
    fountains_near: int


class Tradeoff(BaseModel):
    extra_min: float
    noise_pct: float | None
    exposure_pct: float | None
    green_pct: float | None
    air_pct: float | None
    text: str


class Route(BaseModel):
    kind: Literal["fastest", "healthiest", "balanced"]
    profile: str
    weights_scale: float = Field(description="< 1 when the detour guard scaled the weights down")
    limited_by_detour: bool
    metrics: RouteMetrics
    tradeoff: Tradeoff | None
    same_as: str | None = Field(None, description="kind of an identical route listed earlier")
    geometry: dict[str, Any] = Field(description="GeoJSON FeatureCollection, one feature per edge")


class RouteResponse(BaseModel):
    mode: Mode
    profile: str
    air: dict[str, Any]
    routes: list[Route]
    warnings: list[str]


class GeocodeResult(BaseModel):
    label: str
    kind: Literal["address", "street"]
    district: str | None
    lon: float
    lat: float


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    networks: list[str]
    geocoder: bool
    air: bool
    planner: bool
