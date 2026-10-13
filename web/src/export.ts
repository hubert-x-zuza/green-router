// Route export: a Google Maps directions link and a GPX file.
import type { Mode, Route } from "./api";

/** Google Maps URLs (developers.google.com/maps/documentation/urls): mobile browsers accept at most
 * three waypoints, so we always use three to behave the same on every device. */
export const GOOGLE_MAX_WAYPOINTS = 3;

type LngLat = [number, number];

/** All vertices of the route in order, without repeated joints between edges. */
export function routeCoords(route: Route): LngLat[] {
  const out: LngLat[] = [];
  for (const f of route.geometry.features) {
    for (const c of f.geometry.coordinates) {
      const p: LngLat = [c[0], c[1]];
      const last = out[out.length - 1];
      if (!last || last[0] !== p[0] || last[1] !== p[1]) out.push(p);
    }
  }
  return out;
}

function distM(a: LngLat, b: LngLat): number {
  const k = 111_320;
  const dx = (b[0] - a[0]) * k * Math.cos(((a[1] + b[1]) / 2) * (Math.PI / 180));
  const dy = (b[1] - a[1]) * k;
  return Math.hypot(dx, dy);
}

/** `n` points at equal distances along the line (excluding the ends). */
export function pointsAlong(coords: LngLat[], n: number): LngLat[] {
  if (coords.length < 2 || n <= 0) return [];
  const cum = [0];
  for (let i = 1; i < coords.length; i++) cum.push(cum[i - 1] + distM(coords[i - 1], coords[i]));
  const total = cum[cum.length - 1];
  const out: LngLat[] = [];
  let j = 1;
  for (let k = 1; k <= n; k++) {
    const target = (total * k) / (n + 1);
    while (j < cum.length - 1 && cum[j] < target) j++;
    const seg = cum[j] - cum[j - 1] || 1;
    const t = (target - cum[j - 1]) / seg;
    const a = coords[j - 1];
    const b = coords[j];
    out.push([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]);
  }
  return out;
}

const fmt = (p: LngLat) => `${p[1].toFixed(6)},${p[0].toFixed(6)}`;

export function googleMapsUrl(route: Route, mode: Mode): string {
  const coords = routeCoords(route);
  const origin = coords[0];
  const destination = coords[coords.length - 1];
  const waypoints = pointsAlong(coords, GOOGLE_MAX_WAYPOINTS);
  const params = new URLSearchParams({
    api: "1",
    origin: fmt(origin),
    destination: fmt(destination),
    travelmode: mode === "bike" ? "bicycling" : "walking",
    waypoints: waypoints.map(fmt).join("|"),
  });
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

function esc(s: string): string {
  return s.replace(/[<>&"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

export function gpx(route: Route, name: string): string {
  const pts = routeCoords(route)
    .map((p) => `      <trkpt lat="${p[1].toFixed(6)}" lon="${p[0].toFixed(6)}"/>`)
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="Zdrowa Trasa" xmlns="http://www.topografix.com/GPX/1/1">
  <metadata>
    <name>${esc(name)}</name>
    <copyright author="OpenStreetMap contributors"><license>https://opendatacommons.org/licenses/odbl/</license></copyright>
  </metadata>
  <trk>
    <name>${esc(name)}</name>
    <trkseg>
${pts}
    </trkseg>
  </trk>
</gpx>
`;
}

export function downloadGpx(route: Route, name: string): void {
  const blob = new Blob([gpx(route, name)], { type: "application/gpx+xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `zdrowa-trasa-${route.kind}.gpx`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
