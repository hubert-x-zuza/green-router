"""Shared ETL helpers: paths, config, the city boundary and the common 10 m grid."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import yaml
from affine import Affine
from rasterio import features
from shapely.geometry.base import BaseGeometry

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config"


@lru_cache
def load_yaml(name: str) -> dict[str, Any]:
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))


def etl_config() -> dict[str, Any]:
    return load_yaml("etl.yml")


def read_geojson(path: Path, crs: str = "EPSG:2178") -> gpd.GeoDataFrame:
    """Read a city GeoJSON. The files declare EPSG:2178 in a legacy `crs` member, which some
    readers ignore, so the CRS is set explicitly."""
    gdf = gpd.read_file(path)
    return gdf.set_crs(crs, allow_override=True)


def city_boundary() -> BaseGeometry:
    gdf = read_geojson(RAW / "city_boundary" / "city_boundary.geojson")
    return gdf.geometry.union_all()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


@dataclass(frozen=True)
class Grid:
    """A north-up raster grid in EPSG:2178."""

    xmin: float
    ymax: float
    res: float
    width: int
    height: int

    @classmethod
    def around(cls, geom: BaseGeometry, res: float, pad: float = 0.0) -> Grid:
        x0, y0, x1, y1 = geom.bounds
        x0, y0 = np.floor((x0 - pad) / res) * res, np.floor((y0 - pad) / res) * res
        x1, y1 = np.ceil((x1 + pad) / res) * res, np.ceil((y1 + pad) / res) * res
        return cls(x0, y1, res, int(round((x1 - x0) / res)), int(round((y1 - y0) / res)))

    @property
    def transform(self) -> Affine:
        return Affine(self.res, 0, self.xmin, 0, -self.res, self.ymax)

    @property
    def shape(self) -> tuple[int, int]:
        return self.height, self.width

    def rasterize(self, shapes: Any, fill: float = 0, dtype: str = "uint8") -> np.ndarray:
        return features.rasterize(
            shapes, out_shape=self.shape, transform=self.transform, fill=fill, dtype=dtype
        )

    def sample(self, arr: np.ndarray, x: np.ndarray, y: np.ndarray, nodata: float) -> np.ndarray:
        """Nearest-cell values at points; points outside the grid get `nodata`."""
        col = np.floor((x - self.xmin) / self.res).astype(np.int64)
        row = np.floor((self.ymax - y) / self.res).astype(np.int64)
        ok = (col >= 0) & (col < self.width) & (row >= 0) & (row < self.height)
        out = np.full(x.shape, nodata, dtype="float64")
        out[ok] = arr[row[ok], col[ok]]
        return out
