"""Exposure grids (10 m, EPSG:2178) and the map overlay images for the web app.

Run:  python -m etl.layers     (after etl.graph: needs roads.parquet)

Writes data/processed/layers/<name>.tif:
  inside        1 inside the city boundary
  green_tall / green_low / green_sports   class share within green.buffer_m
  green_score   weighted sum, clamped to [0, 1]
  fountain_dist distance (m) to the nearest outdoor fountain
  traffic       traffic-proximity proxy in [0, 1]
and data/processed/overlays/<name>.png + overlays.json (EPSG:3857 images with lon/lat corners)
for the noise, green and traffic map layers.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import Resampling, calculate_default_transform, reproject
from scipy import ndimage

from etl.common import PROCESSED, RAW, Grid, city_boundary, etl_config, read_geojson, write_json

log = logging.getLogger("etl.layers")
LAYER_DIR = PROCESSED / "layers"
OVERLAY_DIR = PROCESSED / "overlays"
CRS = "EPSG:2178"


def disc(radius_cells: float) -> np.ndarray:
    r = int(np.ceil(radius_cells))
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    k = (xx**2 + yy**2 <= radius_cells**2).astype("float32")
    return k / k.sum()


def save(name: str, grid: Grid, arr: np.ndarray, nodata: float | None = None) -> None:
    LAYER_DIR.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        LAYER_DIR / f"{name}.tif", "w", driver="GTiff", height=grid.height, width=grid.width,
        count=1, dtype=arr.dtype, crs=CRS, transform=grid.transform, compress="deflate",
        nodata=nodata,
    ) as dst:  # fmt: skip
        dst.write(arr, 1)


def read(path: Path) -> tuple[Grid, np.ndarray]:
    with rasterio.open(path) as src:
        t = src.transform
        grid = Grid(t.c, t.f, t.a, src.width, src.height)
        return grid, src.read(1)


def build_grid(cfg: dict) -> Grid:
    pad = cfg["graph"]["boundary_buffer_m"] + 200
    return Grid.around(city_boundary(), cfg["grid"]["res_m"], pad=pad)


def build(cfg: dict) -> None:
    grid = build_grid(cfg)
    res = grid.res
    boundary = city_boundary()
    inside = grid.rasterize([(boundary, 1)])
    save("inside", grid, inside)

    green = read_geojson(RAW / "green_map" / "green_map.geojson")
    green["cls"] = green["class_name"].str[:3]
    k = disc(cfg["green"]["buffer_m"] / res)
    shares = {}
    for cls, name in (("200", "green_tall"), ("300", "green_low"), ("400", "green_sports")):
        mask = grid.rasterize(((g, 1) for g in green.geometry[green.cls == cls]), dtype="uint8")
        shares[cls] = ndimage.convolve(mask.astype("float32"), k, mode="constant")
        save(name, grid, shares[cls].astype("float32"))
        log.info("%s: %.1f %% of the city", name, 100 * mask[inside > 0].mean())
    w = cfg["green"]["class_weights"]
    score = np.clip(sum(w[c] * shares[c] for c in w), 0, 1).astype("float32")
    save("green_score", grid, score)

    fountains = read_geojson(RAW / "fountains_outdoor" / "Pitniki_zewnetrzne.geojson")
    fmask = grid.rasterize(((g, 1) for g in fountains.geometry), dtype="uint8")
    fdist = (ndimage.distance_transform_edt(fmask == 0) * res).astype("float32")
    save("fountain_dist", grid, fdist)

    roads = gpd.read_parquet(PROCESSED / "roads.parquet").to_crs(CRS)
    reach = cfg["traffic"]["reach_m"]
    traffic = np.zeros(grid.shape, dtype="float32")
    for hw, weight in cfg["traffic"]["class_weights"].items():
        sel = roads.geometry[roads.highway == hw]
        if sel.empty:
            continue
        m = grid.rasterize(((g, 1) for g in sel), dtype="uint8")
        d = ndimage.distance_transform_edt(m == 0) * res
        traffic = np.maximum(traffic, weight * np.clip(1 - d / reach, 0, 1)).astype("float32")
    save("traffic", grid, traffic)
    log.info("traffic: mean %.3f inside the city", traffic[inside > 0].mean())


def load_layers() -> dict:
    cfg = etl_config()
    if not (LAYER_DIR / "traffic.tif").exists():
        build(cfg)
    layers: dict = {}
    for name in ("inside", "green_score", "green_tall", "green_low", "green_sports",
                 "fountain_dist", "traffic"):  # fmt: skip
        grid, arr = read(LAYER_DIR / f"{name}.tif")
        layers[name] = arr
        layers["grid"] = grid
    for ind in cfg["noise"]["indicators"]:
        layers[f"noise_{ind}"] = read(PROCESSED / f"noise_{ind}_10m.tif")
    return layers


# ---- map overlays -------------------------------------------------------------------------

# colour ramps: list of (value, (r, g, b, a))
RAMPS = {
    "noise": [(50, (0, 0, 0, 0)), (55, (255, 237, 160, 150)), (60, (254, 178, 76, 170)),
              (65, (253, 141, 60, 185)), (70, (240, 59, 32, 200)), (75, (189, 0, 38, 215))],
    "green": [(0.05, (0, 0, 0, 0)), (0.2, (199, 233, 192, 140)), (0.5, (116, 196, 118, 170)),
              (0.8, (35, 139, 69, 200)), (1.0, (0, 90, 50, 215))],
    "traffic": [(0.05, (0, 0, 0, 0)), (0.3, (218, 218, 235, 120)), (0.6, (158, 154, 200, 170)),
                (1.0, (84, 39, 143, 210))],
}  # fmt: skip


def colourise(arr: np.ndarray, ramp: list) -> np.ndarray:
    vals = np.array([v for v, _ in ramp], dtype="float32")
    cols = np.array([c for _, c in ramp], dtype="float32")
    out = np.zeros((*arr.shape, 4), dtype="float32")
    a = np.nan_to_num(arr, nan=-np.inf)
    for ch in range(4):
        out[..., ch] = np.interp(a, vals, cols[:, ch], left=0, right=cols[-1, ch])
    out[a < vals[0]] = 0
    return out.astype("uint8")


def overlay(name: str, src_grid: Grid, arr: np.ndarray, ramp: list, nodata: float) -> dict:
    """Reproject to EPSG:3857 (MapLibre image sources are linear in Web Mercator), colour, save."""
    arr = np.where(arr == nodata, np.nan, arr).astype("float32")
    left, top = src_grid.xmin, src_grid.ymax
    right, bottom = left + src_grid.width * src_grid.res, top - src_grid.height * src_grid.res
    dst_t, w, h = calculate_default_transform(
        CRS, "EPSG:3857", src_grid.width, src_grid.height, left, bottom, right, top,
        resolution=src_grid.res * 1.5,
    )  # fmt: skip
    dst = np.full((h, w), np.nan, dtype="float32")
    reproject(arr, dst, src_transform=src_grid.transform, src_crs=CRS, dst_transform=dst_t,
              dst_crs="EPSG:3857", resampling=Resampling.nearest, src_nodata=np.nan,
              dst_nodata=np.nan)  # fmt: skip
    OVERLAY_DIR.mkdir(parents=True, exist_ok=True)
    Image.fromarray(colourise(dst, ramp), "RGBA").save(OVERLAY_DIR / f"{name}.png", optimize=True)
    from pyproj import Transformer

    tr = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    x0, y0 = dst_t.c, dst_t.f
    x1, y1 = x0 + w * dst_t.a, y0 + h * dst_t.e
    corners = [tr.transform(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
    return {"url": f"{name}.png", "coordinates": [[round(a, 6), round(b, 6)] for a, b in corners]}


def build_overlays() -> None:
    grid, inside = read(LAYER_DIR / "inside.tif")
    meta = {}
    g, noise = read(PROCESSED / "noise_LDWN_10m.tif")
    meta["noise"] = overlay("noise", g, noise, RAMPS["noise"], -9999.0)
    _, green = read(LAYER_DIR / "green_score.tif")
    meta["green"] = overlay("green", grid, np.where(inside > 0, green, -1), RAMPS["green"], -1)
    _, traffic = read(LAYER_DIR / "traffic.tif")
    meta["traffic"] = overlay("traffic", grid, traffic, RAMPS["traffic"], -1)
    write_json(OVERLAY_DIR / "overlays.json", meta)
    log.info("overlays: %s", ", ".join(meta))


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    build(etl_config())
    build_overlays()
    return 0


if __name__ == "__main__":
    sys.exit(main())
