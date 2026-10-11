#!/usr/bin/env python3
"""
Kraków strategic noise map 2022 -> single 10 m GeoTIFF per indicator (LDWN, LN).

Input : MSIP "Mapy hałasu" GeoJSON files (EPSG:2178), e.g.
          halas_2022_imisja_dr_LDWN.geojson    (roads, polygons by dB class)
          halas_2022_imisja_szyn_LDWN.geojson  (rail/tram, polygons by dB class)
        The *_izofony files (isolines) and the *_przem_* files (industry; no
        geometry in the export) are NOT used.
Output: data/processed/noise_<IND>_10m.tif  (float32, EPSG:2178, dB)

Method:
  * each polygon carries isov1..isov2 (dB class bounds). Lowest class has a
    meaningless negative isov1 and means "below the lowest mapped level";
    highest class has isov1 == isov2 and means ">= that level".
  * rasterise class midpoints (higher classes overwrite lower ones)
  * lowest class contributes NOTHING to the energy sum (it is 'below mapped range')
  * sources are combined energetically: L = 10 log10(sum 10^(Li/10))
  * if no source reaches its first real class, the cell gets a floor value
    (LDWN 50 dB, LN 45 dB) meaning "quiet / below mapped range".
  * cells outside every polygon (outside the city boundary) are written as nodata.
Usage: python noise_to_grid.py --in data/raw/noise --out data/processed
Memory: each input file is up to ~375 MB of JSON; use >= 4 GB RAM or switch to
        a streaming reader (ijson) / convert to GeoPackage first.
"""
import argparse, json, os, time
import numpy as np
import rasterio
from rasterio import features
from rasterio.transform import from_origin

# Extent of the Kraków noise model in EPSG:2178 (all files share it), rounded outward.
XMIN, XMAX, YMIN, YMAX = 7413400.0, 7443980.0, 5537300.0, 5555100.0
RES = 10.0
FLOOR = {"LDWN": 50.0, "LN": 45.0}
NODATA = -9999.0
SOURCES = ("dr", "szyn")  # road, rail+tram

W = int(np.ceil((XMAX - XMIN) / RES))
H = int(np.ceil((YMAX - YMIN) / RES))
TRANSFORM = from_origin(XMIN, YMAX, RES, RES)


def class_value(v1, v2):
    """Return (midpoint_dB, is_real_class)."""
    if v1 is None or v1 < 0:           # lowest open class: 'below mapped range'
        return None, False
    if v1 == v2:                       # highest open class: '>= v1'
        return v1 + 2.5, True
    return (v1 + v2) / 2.0, True


def rasterise_source(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    shapes, cover, skipped = [], [], 0
    for ft in data["features"]:
        g = ft.get("geometry")
        if not g or not g.get("coordinates"):
            skipped += 1
            continue
        p = ft["properties"]
        cover.append((g, 1))             # every class (incl. lowest) = inside the mapped city
        val, real = class_value(p["isov1"], p["isov2"])
        if real:
            shapes.append((g, val))
    shapes.sort(key=lambda s: s[1])    # ascending: higher dB overwrites lower
    arr = features.rasterize(shapes, out_shape=(H, W), transform=TRANSFORM,
                             fill=np.nan, dtype="float32")
    mask = features.rasterize(cover, out_shape=(H, W), transform=TRANSFORM,
                              fill=0, dtype="uint8").astype(bool)
    return arr, mask, skipped


def build(indicator, in_dir, out_dir):
    energy = np.zeros((H, W), dtype="float64")
    inside = np.zeros((H, W), dtype=bool)
    for src in SOURCES:
        path = os.path.join(in_dir, f"halas_2022_imisja_{src}_{indicator}.geojson")
        t = time.time()
        arr, mask, skipped = rasterise_source(path)
        inside |= mask
        energy += np.where(np.isfinite(arr), 10 ** (arr / 10.0), 0.0)
        print(f"  {os.path.basename(path)}: skipped_empty={skipped} {time.time()-t:.0f}s")
        del arr
    with np.errstate(divide="ignore"):
        L = 10 * np.log10(energy)
    L = np.where(energy > 0, L, FLOOR[indicator]).astype("float32")
    L = np.maximum(L, FLOOR[indicator])
    L = np.where(inside, L, NODATA).astype("float32")
    out = os.path.join(out_dir, f"noise_{indicator}_10m.tif")
    with rasterio.open(out, "w", driver="GTiff", height=H, width=W, count=1,
                       dtype="float32", crs="EPSG:2178", transform=TRANSFORM,
                       compress="deflate", predictor=3, nodata=NODATA) as dst:
        dst.write(L, 1)
    print(f"  wrote {out}")
    return L


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", required=True)
    ap.add_argument("--out", dest="out_dir", required=True)
    ap.add_argument("--indicators", nargs="+", default=["LDWN", "LN"])
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    for ind in a.indicators:
        print(ind)
        build(ind, a.in_dir, a.out_dir)
