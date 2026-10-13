"""Planner view (plan 5.5): priority = exposure_severity x sensitive_presence per cell.

Run:  python -m etl.planner    (after etl.normalise, etl.geocoder, etl.fetch.otwartedane)

Units: square cells of `planner.cell_m` covering the city; only cells with walkable street
length count. Per cell:
  exposure_severity  length-weighted mean over walk edges (covered by data) of
                     sum(w_k * p_k) / sum(w_k), weights `planner.exposure_weights`
  sensitive_presence sum over sites within radius_m of weight * min(cap, people / people_ref)
                     + resident_weight * address density (address points per cell / 95th pct)
Sites (schools, kindergartens, nurseries, children's clubs; 2025/2026 tables from otwartedane)
carry only a street address: they are placed with the city's address points (exact street and
number). About 10 % of the source rows have no house number (the API types the column as a
number, so values like "9-11" are lost): those are placed at the centre of the address points with
the same street and postcode, only if these lie within `approx_max_spread_m`, and flagged
`approx`. Everything else is listed in planner_meta.json, never guessed.
Output: data/processed/planner_hotspots.json (top cells as GeoJSON with explanations),
planner_districts.json (district aggregates), planner_sites.parquet.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree

from etl.common import PROCESSED, RAW, etl_config, read_geojson, write_json
from etl.geocoder import normalise, strip_diacritics

log = logging.getLogger("etl.planner")
OD = RAW / "otwartedane"
TO_4326 = Transformer.from_crs("EPSG:2178", "EPSG:4326", always_xy=True)


@dataclass(frozen=True)
class SiteTable:
    kind: str
    path: str
    name: str
    street: str
    number: str
    people: str


SITE_TABLES = [
    SiteTable("school", "szkoly-podstawowe-w-krakowie-liczba-dzieci/uczniowie-szkoly-podstawowe-samorzadowe-2025-2026.json", "Nazwa szkoły_placówki", "Ulica", "Nr domu", "Liczba uczniów ogółem"),  # noqa: E501
    SiteTable("school", "szkoly-podstawowe-w-krakowie-liczba-dzieci/uczniowie-szkoly-podstawowe-niesamorzadowe-2025-2026.json", "Nazwa szkoły_placówki", "Ulica", "Nr domu", "Liczba uczniów ogółem"),  # noqa: E501
    SiteTable("school", "szkoly-ponadpodstawowe-w-krakowie-liczba-uczniow/uczniowie-szkoly-ponadpodstawowe-samorzadowe-2025-2026.json", "Nazwa szkoły_placówki", "Ulica", "Nr domu", "Liczba uczniów ogółem"),  # noqa: E501
    SiteTable("school", "szkoly-ponadpodstawowe-w-krakowie-liczba-uczniow/uczniowie-szkoly-ponadpodstawowe-niesamorzadowe-2025-2026.json", "Nazwa szkoły_placówki", "Ulica", "Nr domu", "Liczba uczniów ogółem"),  # noqa: E501
    SiteTable("kindergarten", "przedszkola-w-krakowie-liczba-dzieci/liczba-dzieci-przedszkola-samorzadowe-2025-2026.json", "Nazwa szkoły_placówki", "Ulica", "Nr domu", "Liczba dzieci ogółem"),  # noqa: E501
    SiteTable("kindergarten", "przedszkola-w-krakowie-liczba-dzieci/liczba-dzieci-przedszkola-niesamorzadowe-2025-2026.json", "Nazwa szkoły_placówki", "Ulica", "Nr domu", "Liczba dzieci ogółem"),  # noqa: E501
    SiteTable("nursery", "zlobki-samorzadowe-w-krakowie/zlobki-samorzadowe.json", "Nazwa", "Ulica", "Numer budynku", "Liczba miejsc "),  # noqa: E501
    SiteTable("nursery", "zlobki-prywatne-w-krakowie/zlobki-prywatne.json", "Nazwa", "Ulica", "Numer budynku", "Liczba miejsc "),  # noqa: E501
    SiteTable("nursery", "zlobki-niesamorzadowe-prowadzone-na-zlecenie-gminy-miejskiej-krakow/zlobki-zlecenie-gmk.json", "Nazwa", "Ulica", "Numer budynku", "Liczba miejsc "),  # noqa: E501
    SiteTable("nursery", "kluby-dzieciece-w-krakowie/kluby-dzieciece.json", "Nazwa", "Ulica", "Numer budynku", "Liczba miejsc "),  # noqa: E501
]  # fmt: skip


def _num(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return strip_diacritics(str(v).strip().lower()).replace(" ", "")


def _postcode(r: dict) -> str:
    for k, v in r.items():
        if k.strip() == "Kod pocztowy" and v:
            return str(v).strip()
    return ""


def place_sites(addr: gpd.GeoDataFrame, max_spread: float) -> tuple[pd.DataFrame, list[dict]]:
    """Match each site's street + number to an address point; return placed sites and misses."""
    addr = addr.assign(
        k_street=addr.nazwa_ulicy.map(normalise), k_num=addr.numer_adresowy.map(_num)
    )
    by_street_pc = {
        k: np.column_stack([g.geometry.x, g.geometry.y])
        for k, g in addr.groupby([addr.k_street, addr.kod_pocztowy])
    }
    exact = {
        (s, n): (g.x, g.y) for s, n, g in zip(addr.k_street, addr.k_num, addr.geometry, strict=True)
    }
    # street words may be abbreviated differently ("ks. Stefana Pawlickiego" vs full name):
    # fall back to "the address whose street ends with the same last word and has this number"
    by_last: dict[tuple[str, str], list[tuple[float, float]]] = {}
    for (s, n), xy in exact.items():
        by_last.setdefault((s.split(" ")[-1] if s else "", n), []).append(xy)
    rows, misses = [], []
    for t in SITE_TABLES:
        for r in json.loads((OD / t.path).read_text(encoding="utf-8")):
            raw_street = str(r.get(t.street) or "").strip()
            m = re.match(r"^(.*\D)\s+(\d+\w*)(/\S*)?$", raw_street)
            num = _num(r.get(t.number))
            if m:  # number written into the street field ("Barska 69/U6")
                raw_street, num = m.group(1), num or _num(m.group(2))
            street = normalise(raw_street)
            approx = False
            xy = exact.get((street, num))
            if xy is None and street:
                cands = by_last.get((street.split(" ")[-1], num), [])
                xy = cands[0] if len(cands) == 1 else None
            if xy is None and not num:
                pts = by_street_pc.get((street, _postcode(r)))
                if pts is not None:
                    c = pts.mean(axis=0)
                    if np.hypot(*(pts - c).T).max() <= max_spread:
                        xy, approx = (float(c[0]), float(c[1])), True
            people = r.get(t.people)
            if xy is None:
                misses.append({"kind": t.kind, "name": r.get(t.name), "street": r.get(t.street),
                               "number": r.get(t.number)})  # fmt: skip
                continue
            rows.append({"kind": t.kind, "name": r.get(t.name), "x": xy[0], "y": xy[1],
                         "approx": approx,
                         "people": float(people) if people is not None else np.nan})  # fmt: skip
    sites = pd.DataFrame(rows).drop_duplicates(subset=["kind", "name", "x", "y"])
    return sites, misses


def build() -> dict:
    cfg = etl_config()
    pc = cfg["planner"]
    cell = pc["cell_m"]
    net = gpd.read_parquet(PROCESSED / "network_walk.parquet")
    # walk edges exist in both directions: keep one per undirected pair
    a, b = np.minimum(net.u, net.v), np.maximum(net.u, net.v)
    net = net.loc[~pd.DataFrame({"a": a, "b": b, "l": net.length_m.round(1)}).duplicated()]
    net = net[net.data_coverage]
    mid = shapely.line_interpolate_point(net.geometry.to_numpy(), 0.5, normalized=True)
    mx, my = shapely.get_x(mid), shapely.get_y(mid)
    x0, y0 = np.floor(mx.min() / cell) * cell, np.floor(my.min() / cell) * cell
    ci, cj = ((mx - x0) // cell).astype(int), ((my - y0) // cell).astype(int)
    ew = pc["exposure_weights"]
    sev_edge = sum(w * net[f"p_{k}"].to_numpy() for k, w in ew.items()) / sum(ew.values())
    L = net.length_m.to_numpy()
    df = pd.DataFrame({"i": ci, "j": cj, "L": L, "sev": sev_edge * L,
                       "noise": net.noise_ldwn_mean.to_numpy() * L,
                       "green": net.green_score.to_numpy() * L,
                       "traffic": net.traffic_prox.to_numpy() * L,
                       "name": net["name"].fillna("").to_numpy()})  # fmt: skip
    g = df.groupby(["i", "j"])
    cells = g[["L", "sev", "noise", "green", "traffic"]].sum()
    for c in ("sev", "noise", "green", "traffic"):
        cells[c] = cells[c] / cells["L"]
    named = df[df.name != ""].groupby(["i", "j", "name"]).L.sum().reset_index()
    named = named.sort_values("L").groupby(["i", "j"]).tail(1).set_index(["i", "j"]).name
    cells["street"] = named
    cells = cells[cells.L >= pc.get("min_street_m", 100)].reset_index()
    cells["cx"] = x0 + (cells.i + 0.5) * cell
    cells["cy"] = y0 + (cells.j + 0.5) * cell

    addr = read_geojson(RAW / "address_points" / "Adresy.geojson")
    sites, misses = place_sites(addr, pc["approx_max_spread_m"])
    tree = cKDTree(sites[["x", "y"]].to_numpy())
    centres = cells[["cx", "cy"]].to_numpy()
    presence = np.zeros(len(cells))
    for kind, sc in pc["sites"].items():
        sel = sites[sites.kind == kind].reset_index(drop=True)
        if sel.empty:
            continue
        t = cKDTree(sel[["x", "y"]].to_numpy())
        hits = t.query_ball_point(centres, r=sc["radius_m"] + cell / 2)
        ppl = np.nan_to_num(sel.people.to_numpy(), nan=pc["people_ref"])
        contrib = np.minimum(pc["site_cap"], ppl / pc["people_ref"]) * sc["weight"]
        cells[f"{kind}s"] = [len(h) for h in hits]
        cells[f"{kind}_people"] = [float(ppl[h].sum()) if h else 0.0 for h in hits]
        presence += np.array([contrib[h].sum() if h else 0.0 for h in hits])
    del tree
    ai = ((addr.geometry.x - x0) // cell).astype(int)
    aj = ((addr.geometry.y - y0) // cell).astype(int)
    dens = pd.Series(1, index=pd.MultiIndex.from_arrays([ai, aj])).groupby(level=[0, 1]).sum()
    cells["addresses"] = [int(dens.get((i, j), 0)) for i, j in zip(cells.i, cells.j, strict=True)]
    ref = max(1.0, float(np.percentile(cells.addresses, 95)))
    presence += pc["resident_weight"] * np.minimum(1.0, cells.addresses / ref)
    cells["presence_raw"] = presence
    # saturating: a few sensitive sites already make a place important; ten do not make it 10x
    cells["presence"] = 1 - np.exp(-presence / pc["presence_scale"])
    cells["priority"] = cells.sev * cells.presence
    streets = read_geojson(RAW / "streets" / "Ulice.geojson")[["nazwa_ulicy", "geometry"]]
    cpts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(cells.cx, cells.cy), crs="EPSG:2178")
    near = gpd.sjoin_nearest(cpts, streets, how="left", max_distance=cell)
    near = near[~near.index.duplicated()]
    cells["street"] = cells["street"].where(cells["street"].notna(), near.nazwa_ulicy.to_numpy())

    districts = read_geojson(RAW / "districts" / "Dzielnice.geojson")
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(cells.cx, cells.cy), crs="EPSG:2178")
    j = gpd.sjoin(pts, districts[["id_dzielni", "nazwa", "geometry"]], how="left",
                  predicate="within")  # fmt: skip
    j = j[~j.index.duplicated()]
    cells["district_id"] = j.id_dzielni.fillna(0).astype(int).to_numpy()
    cells["district"] = j.nazwa.fillna("").to_numpy()
    cells = cells[cells.district_id > 0].sort_values("priority", ascending=False)
    cells["rank"] = np.arange(1, len(cells) + 1)

    feats = []
    half = cell / 2
    for r in cells.head(500).itertuples():
        poly = shapely.box(r.cx - half, r.cy - half, r.cx + half, r.cy + half)
        xs, ys = TO_4326.transform(*np.array(poly.exterior.coords).T)
        clon, clat = TO_4326.transform(r.cx, r.cy)
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon",
                         "coordinates": [np.round(np.column_stack([xs, ys]), 6).tolist()]},
            "properties": {
                "rank": int(r.rank), "priority": round(float(r.priority), 3),
                "presence_raw": round(float(r.presence_raw), 2),
                "severity": round(float(r.sev), 3), "presence": round(float(r.presence), 2),
                "district_id": int(r.district_id), "district": r.district,
                "street": r.street if isinstance(r.street, str) else None,
                "noise_db": round(float(r.noise), 1), "green": round(float(r.green), 2),
                "traffic": round(float(r.traffic), 2),
                "schools": int(r.schools), "pupils": int(r.school_people),
                "kindergartens": int(r.kindergartens), "nurseries": int(r.nurserys),
                "children_small": int(r.kindergarten_people + r.nursery_people),
                "addresses": int(r.addresses),
                "centre": [round(clon, 6), round(clat, 6)],
            },
        })  # fmt: skip
    meta = {"cell_m": cell, "n_cells": int(len(cells)), "n_sites": int(len(sites)),
            "sites_unplaced": len(misses), "exposure_weights": ew}  # fmt: skip
    write_json(PROCESSED / "planner_hotspots.json",
               {"type": "FeatureCollection", "features": feats, "meta": meta})  # fmt: skip
    write_json(PROCESSED / "planner_meta.json", {**meta, "unplaced_sites": misses})
    sites.to_parquet(PROCESSED / "planner_sites.parquet", index=False)
    write_json(PROCESSED / "planner_districts.json", district_stats(cells, districts, sites))
    return meta


def district_stats(cells: pd.DataFrame, districts: gpd.GeoDataFrame, sites: pd.DataFrame) -> list:
    res_path = (
        OD / "mieszkancy-zameldowani-na-pobyt-staly" / "zameldowani-na-pobyt-staly-31-12-2025.json"
    )  # noqa: E501
    res = pd.DataFrame(json.loads(res_path.read_text(encoding="utf-8")))
    age = 2025 - res.Rok_Urodzenia
    pop = res.groupby("Nr_Dzielnicy").Liczba_osób.sum()
    kids = res[age <= 14].groupby("Nr_Dzielnicy").Liczba_osób.sum()
    seniors = res[age >= 65].groupby("Nr_Dzielnicy").Liczba_osób.sum()
    sp = gpd.GeoDataFrame(sites, geometry=gpd.points_from_xy(sites.x, sites.y), crs="EPSG:2178")
    sj = gpd.sjoin(sp, districts[["id_dzielni", "geometry"]], predicate="within")
    n_sites = sj.groupby("id_dzielni").size()
    out = []
    for d in districts.sort_values("id_dzielni").itertuples():
        c = cells[cells.district_id == d.id_dzielni]
        w = c.L
        out.append({
            "district_id": int(d.id_dzielni), "number": d.nr_dzielni, "name": d.nazwa,
            "population": int(pop.get(float(d.id_dzielni), 0)),
            "children_0_14": int(kids.get(float(d.id_dzielni), 0)),
            "seniors_65": int(seniors.get(float(d.id_dzielni), 0)),
            "sensitive_sites": int(n_sites.get(d.id_dzielni, 0)),
            "severity_mean": round(float(np.average(c.sev, weights=w)), 3) if len(c) else None,
            "noise_mean_db": round(float(np.average(c.noise, weights=w)), 1) if len(c) else None,
            "green_mean": round(float(np.average(c.green, weights=w)), 3) if len(c) else None,
            "share_loud_cells": round(float((c.noise >= 65).mean()), 3) if len(c) else None,
            "hotspots_top100": int((c["rank"] <= 100).sum()),
            "priority_sum": round(float(c.priority.sum()), 1),
        })  # fmt: skip
    return sorted(out, key=lambda r: -r["priority_sum"])


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    meta = build()
    log.info("planner: %s", meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
