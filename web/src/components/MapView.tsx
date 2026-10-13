import * as maplibregl from "maplibre-gl";
import type { GeoJSONSource, MapMouseEvent } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import type { AirNow, HotspotProps, LonLat, Overlay, Route, RouteKind } from "../api";

export type LayerKey = "noise" | "green" | "traffic" | "fountains" | "stations" | "hotspots";
export type LayerState = Record<LayerKey, boolean>;

interface Props {
  overlays: Record<string, Overlay>;
  layers: LayerState;
  routes: Route[];
  selected: RouteKind;
  origin: LonLat | null;
  destination: LonLat | null;
  fountains: GeoJSON.FeatureCollection | null;
  air: AirNow | null;
  hotspots: GeoJSON.FeatureCollection<GeoJSON.Polygon, HotspotProps> | null;
  focus: [number, number] | null;
  onMapClick: (p: LonLat) => void;
  onHotspotClick: (p: HotspotProps) => void;
}

const STYLE = "https://tiles.openfreemap.org/styles/positron";
const KRAKOW: [number, number] = [19.945, 50.061];
const ROUTE_COLOURS: Record<RouteKind, string> = {
  fastest: "#6b7280",
  healthiest: "#1b7f4c",
  balanced: "#2563eb",
};
const BAND_COLOURS = ["#2e9d47", "#8bc34a", "#e7c500", "#f08c00", "#d9381e", "#8b1a1a"];
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };

// names come from OSM and other external data: never insert them as HTML
function esc(s: unknown): string {
  return String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

function routeFeatures(routes: Route[], selected: RouteKind): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = [];
  for (const r of routes) {
    if (r.same_as) continue;
    for (const f of r.geometry.features) {
      features.push({ ...f, properties: { ...f.properties, kind: r.kind, sel: r.kind === selected } });
    }
  }
  return { type: "FeatureCollection", features };
}

function stationFeatures(air: AirNow | null): GeoJSON.FeatureCollection {
  if (!air?.stations) return EMPTY;
  return {
    type: "FeatureCollection",
    features: air.stations.map((s) => {
      const bands = Object.values(s.values).filter((v) => v.fresh).map((v) => v.band);
      return {
        type: "Feature",
        geometry: { type: "Point", coordinates: [s.lon, s.lat] },
        properties: {
          name: s.name,
          band: bands.length ? Math.max(...bands) : -1,
          text: Object.entries(s.values)
            .map(([k, v]) => `${k.replace("PM25", "PM2.5")}: ${v.value.toFixed(0)} µg/m³`)
            .join(" · "),
        },
      };
    }),
  };
}

export default function MapView(p: Props) {
  const { t } = useTranslation();
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const ready = useRef(false);
  const markers = useRef<{ o?: maplibregl.Marker; d?: maplibregl.Marker }>({});
  const props = useRef(p);
  props.current = p;

  // create the map once
  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: STYLE,
      center: KRAKOW,
      zoom: 12,
      minZoom: 9,
      maxBounds: [
        [19.5, 49.85],
        [20.4, 50.25],
      ],
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.on("load", () => {
      const beforeId = m.getStyle().layers.find((l) => l.type === "symbol")?.id;
      m.addSource("routes", { type: "geojson", data: EMPTY });
      m.addLayer({
        id: "routes-other",
        type: "line",
        source: "routes",
        filter: ["!", ["get", "sel"]],
        paint: {
          "line-color": ["match", ["get", "kind"], "fastest", ROUTE_COLOURS.fastest, "healthiest", ROUTE_COLOURS.healthiest, ROUTE_COLOURS.balanced],
          "line-width": 4,
          "line-opacity": 0.55,
          "line-dasharray": [2, 1],
        },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      m.addLayer({
        id: "route-casing",
        type: "line",
        source: "routes",
        filter: ["get", "sel"],
        paint: { "line-color": "#ffffff", "line-width": 9 },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      m.addLayer({
        id: "route-selected",
        type: "line",
        source: "routes",
        filter: ["get", "sel"],
        paint: {
          "line-color": [
            "case",
            ["==", ["get", "noise_db"], null],
            "#9ca3af",
            ["interpolate", ["linear"], ["get", "noise_db"], 50, "#1b7f4c", 60, "#e7c500", 68, "#f08c00", 75, "#c0262d"],
          ],
          "line-width": 6,
        },
        layout: { "line-cap": "round", "line-join": "round" },
      });
      m.addSource("hotspots", { type: "geojson", data: EMPTY });
      m.addLayer(
        {
          id: "hotspots",
          type: "fill",
          source: "hotspots",
          paint: {
            "fill-color": ["interpolate", ["linear"], ["get", "priority"], 0.2, "#fde0c5", 0.45, "#f59e0b", 0.6, "#dc2626", 0.75, "#7f1d1d"],
            "fill-opacity": 0.65,
            "fill-outline-color": "#7f1d1d",
          },
        },
        beforeId,
      );
      m.addSource("fountains", { type: "geojson", data: EMPTY });
      m.addLayer({
        id: "fountains",
        type: "circle",
        source: "fountains",
        paint: { "circle-radius": 5, "circle-color": "#0ea5e9", "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 },
      });
      m.addSource("stations", { type: "geojson", data: EMPTY });
      m.addLayer({
        id: "stations",
        type: "circle",
        source: "stations",
        paint: {
          "circle-radius": 8,
          "circle-color": ["match", ["get", "band"], 0, BAND_COLOURS[0], 1, BAND_COLOURS[1], 2, BAND_COLOURS[2], 3, BAND_COLOURS[3], 4, BAND_COLOURS[4], 5, BAND_COLOURS[5], "#9ca3af"],
          "circle-stroke-color": "#fff",
          "circle-stroke-width": 2,
        },
      });
      ready.current = true;
      sync();
    });

    const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false, maxWidth: "260px" });
    m.on("mousemove", "route-selected", (e) => {
      const f = e.features?.[0];
      if (!f) return;
      const pr = f.properties as Record<string, unknown>;
      const noise = pr.noise_db == null || pr.noise_db === "null" ? "–" : `${pr.noise_db} dB`;
      const green = pr.green == null || pr.green === "null" ? "–" : `${Math.round(Number(pr.green) * 100)} %`;
      const name = pr.name && pr.name !== "null" ? `<strong>${esc(pr.name)}</strong><br>` : "";
      popup.setLngLat(e.lngLat).setHTML(`${name}${noise} · ${green}`).addTo(m);
      m.getCanvas().style.cursor = "crosshair";
    });
    m.on("mouseleave", "route-selected", () => popup.remove());
    m.on("click", "stations", (e) => {
      const pr = e.features?.[0]?.properties as { name: string; text: string } | undefined;
      if (pr) new maplibregl.Popup().setLngLat(e.lngLat).setHTML(`<strong>${esc(pr.name)}</strong><br>${esc(pr.text)}`).addTo(m);
    });
    m.on("click", "hotspots", (e) => {
      const pr = e.features?.[0]?.properties;
      if (!pr) return;
      const hs = props.current.hotspots?.features.find((f) => f.properties.rank === Number(pr.rank));
      if (hs) props.current.onHotspotClick(hs.properties);
    });
    m.on("click", (e: MapMouseEvent) => {
      const hit = m.queryRenderedFeatures(e.point, { layers: ["stations", "hotspots"].filter((l) => m.getLayer(l)) });
      if (hit.length) return;
      props.current.onMapClick({ lon: e.lngLat.lng, lat: e.lngLat.lat });
    });
    return () => {
      ready.current = false;
      m.remove();
      map.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function sync() {
    const m = map.current;
    if (!m || !ready.current) return;
    const cur = props.current;
    const beforeId = m.getLayer("hotspots") ? "hotspots" : undefined;
    for (const [key, ov] of Object.entries(cur.overlays)) {
      const id = `ov-${key}`;
      if (!m.getSource(id)) {
        m.addSource(id, { type: "image", url: ov.url, coordinates: ov.coordinates });
        m.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": 0.75, "raster-resampling": "nearest" } }, beforeId);
      }
      m.setLayoutProperty(id, "visibility", cur.layers[key as LayerKey] ? "visible" : "none");
    }
    (m.getSource("routes") as GeoJSONSource).setData(routeFeatures(cur.routes, cur.selected));
    (m.getSource("fountains") as GeoJSONSource).setData(cur.fountains ?? EMPTY);
    (m.getSource("stations") as GeoJSONSource).setData(stationFeatures(cur.air));
    (m.getSource("hotspots") as GeoJSONSource).setData(cur.hotspots ?? EMPTY);
    for (const id of ["fountains", "stations", "hotspots"] as const) {
      m.setLayoutProperty(id, "visibility", cur.layers[id] ? "visible" : "none");
    }
  }

  useEffect(sync, [p.overlays, p.layers, p.routes, p.selected, p.fountains, p.air, p.hotspots]);

  // origin / destination markers
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    const set = (key: "o" | "d", pos: LonLat | null, colour: string, label: string) => {
      markers.current[key]?.remove();
      markers.current[key] = undefined;
      if (pos) {
        const mk = new maplibregl.Marker({ color: colour }).setLngLat([pos.lon, pos.lat]).addTo(m);
        mk.getElement().setAttribute("aria-label", label);
        markers.current[key] = mk;
      }
    };
    set("o", p.origin, "#1b7f4c", t("route.from"));
    set("d", p.destination, "#c0262d", t("route.to"));
  }, [p.origin, p.destination, t]);

  // fit to the routes when they change
  useEffect(() => {
    const m = map.current;
    if (!m || !p.routes.length) return;
    const b = new maplibregl.LngLatBounds();
    for (const r of p.routes) for (const f of r.geometry.features) for (const c of f.geometry.coordinates) b.extend(c as [number, number]);
    if (!b.isEmpty()) m.fitBounds(b, { padding: { top: 60, bottom: 60, left: 60, right: 60 }, maxZoom: 16, duration: 600 });
  }, [p.routes]);

  useEffect(() => {
    if (p.focus && map.current) map.current.flyTo({ center: p.focus, zoom: 15, duration: 600 });
  }, [p.focus]);

  return <div ref={el} className="map" role="application" aria-label={t("app.title")} />;
}
