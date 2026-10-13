// Route export (Google Maps link, GPX) and helpers for in-app guidance.
import type { Mode, Route } from "./api";

/** Documented Google Maps URLs (developers.google.com/maps/documentation/urls): mobile browsers
 * accept at most three waypoints. */
export const GOOGLE_MAX_WAYPOINTS = 3;

/** Undocumented path format google.com/maps/dir/<point>/<point>/.../data=!4m2!4m1!3e<mode>:
 * up to 10 points (origin, 8 waypoints, destination), also opened by the mobile app. Google does not
 * document it and may change it at any time: set USE_LEGACY_GOOGLE_URL to false to fall back to the
 * documented format (decision D-029). */
export const USE_LEGACY_GOOGLE_URL = false;
export const GOOGLE_LEGACY_MAX_WAYPOINTS = 8;
// travel mode codes used by Google Maps in the `data` parameter (undocumented)
const LEGACY_MODE: Record<Mode, string> = { walk: "3e2", bike: "3e1" };

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

const MIN_WAYPOINT_SPACING_M = 500;
// a junction this far from the fastest route is worth forcing Google through
const MIN_DEVIATION_M = 80;

const fmt = (p: LngLat) => `${p[1].toFixed(6)},${p[0].toFixed(6)}`;

/** Distance (m) from p to the polyline (local equirectangular projection, fine at city scale). */
export function distToLine(p: LngLat, line: LngLat[]): number {
  const k = 111_320;
  const cos = Math.cos(p[1] * (Math.PI / 180));
  const X = (q: LngLat) => (q[0] - p[0]) * k * cos;
  const Y = (q: LngLat) => (q[1] - p[1]) * k;
  let best = Infinity;
  for (let i = 1; i < line.length; i++) {
    const ax = X(line[i - 1]), ay = Y(line[i - 1]);
    const bx = X(line[i]), by = Y(line[i]);
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy || 1;
    const t = Math.max(0, Math.min(1, -(ax * dx + ay * dy) / len2));
    best = Math.min(best, Math.hypot(ax + t * dx, ay + t * dy));
  }
  return best;
}

interface Node {
  p: LngLat;
  along: number; // metres from the start
  named: boolean; // a street name on an adjacent edge
}

/** Junctions of the route (edge boundaries), with distance from the start. */
function routeNodes(route: Route): Node[] {
  const feats = route.geometry.features;
  const nodes: Node[] = [];
  let along = 0;
  feats.forEach((f, i) => {
    const c = f.geometry.coordinates as LngLat[];
    const named = !!f.properties.name || !!feats[i - 1]?.properties.name;
    nodes.push({ p: [c[0][0], c[0][1]], along, named });
    for (let j = 1; j < c.length; j++) along += distM(c[j - 1], c[j]);
  });
  const last = feats[feats.length - 1]?.geometry.coordinates as LngLat[] | undefined;
  if (last) nodes.push({ p: [last[last.length - 1][0], last[last.length - 1][1]], along, named: false });
  return nodes;
}

/** Waypoints that make Google follow our route: junctions where the route departs furthest from
 * the fastest route (Google's own choice is close to our fastest). Points sit exactly on a path
 * junction, preferably on a named street, so Google does not snap them to a nearby venue. None at
 * all when the route equals the fastest one. Exported for tests. */
export function waypointsFor(route: Route, fastest: Route | undefined, n = GOOGLE_MAX_WAYPOINTS): LngLat[] {
  if (!fastest || route.kind === "fastest" || route.same_as === "fastest") return [];
  const ref = routeCoords(fastest);
  const nodes = routeNodes(route);
  const total = nodes[nodes.length - 1]?.along ?? 0;
  const margin = total * 0.05;
  const scored = nodes
    .filter((nd) => nd.along > margin && nd.along < total - margin)
    .map((nd) => ({ ...nd, dev: distToLine(nd.p, ref) }))
    // Google snaps a point between buildings to the nearest venue and detours to it: junctions
    // on named streets are strongly preferred
    .map((nd) => ({ ...nd, score: nd.dev * (nd.named ? 1 : 0.4) }));
  const chosen: typeof scored = [];
  // points packed close together each get snapped to a different venue: keep them apart
  const spacing = Math.max(MIN_WAYPOINT_SPACING_M, total / (n + 1) / 2);
  for (let k = 0; k < n; k++) {
    const pick = scored
      .filter((c) => c.dev >= MIN_DEVIATION_M && chosen.every((x) => Math.abs(x.along - c.along) >= spacing))
      .sort((a, b) => b.score - a.score)[0];
    if (!pick) break;
    chosen.push(pick);
  }
  return chosen.sort((a, b) => a.along - b.along).map((c) => c.p);
}

export function googleMapsUrl(route: Route, mode: Mode, fastest?: Route): string {
  return USE_LEGACY_GOOGLE_URL
    ? googleMapsLegacyUrl(route, mode, fastest)
    : googleMapsDocumentedUrl(route, mode, fastest);
}

/** Undocumented format with up to 8 waypoints (see USE_LEGACY_GOOGLE_URL). */
export function googleMapsLegacyUrl(route: Route, mode: Mode, fastest?: Route): string {
  const coords = routeCoords(route);
  const wps: LngLat[] = (route.google_waypoints ?? waypointsFor(route, fastest, GOOGLE_LEGACY_MAX_WAYPOINTS)).slice(
    0,
    GOOGLE_LEGACY_MAX_WAYPOINTS,
  );
  const points = [coords[0], ...wps, coords[coords.length - 1]];
  const path = points.map(fmt).join("/");
  return `https://www.google.com/maps/dir/${path}/data=!4m2!4m1!${LEGACY_MODE[mode]}`;
}

/** Documented format (Maps URLs, api=1) with at most 3 waypoints. */
export function googleMapsDocumentedUrl(route: Route, mode: Mode, fastest?: Route): string {
  const coords = routeCoords(route);
  const params = new URLSearchParams({
    api: "1",
    origin: fmt(coords[0]),
    destination: fmt(coords[coords.length - 1]),
    travelmode: mode === "bike" ? "bicycling" : "walking",
  });
  // chosen by the API (api/google_link.py: detours, streets, away from venues); the client-side
  // choice is only a fallback for an older API
  const wps: LngLat[] = route.google_waypoints ?? waypointsFor(route, fastest);
  if (wps.length) params.set("waypoints", wps.map(fmt).join("|"));
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

/** Hand the exact route to a navigation app (Organic Maps, OsmAnd, Komoot...) through the system
 * share sheet. Returns false where sharing files is not supported (most desktops). */
export async function shareGpx(route: Route, name: string): Promise<boolean> {
  const file = new File([gpx(route, name)], `zdrowa-trasa-${route.kind}.gpx`, {
    type: "application/gpx+xml",
  });
  const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
  if (!nav.canShare?.({ files: [file] })) return false;
  try {
    await navigator.share({ files: [file], title: name });
  } catch {
    /* the user closed the share sheet */
  }
  return true;
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

/** Progress along the route for in-app guidance: remaining metres from the closest route vertex,
 * and how far the user is from the route line. */
export function progress(route: Route, me: LngLat): { remainingM: number; offRouteM: number } {
  const coords = routeCoords(route);
  let best = 0;
  let bestD = Infinity;
  coords.forEach((c, i) => {
    const d = distM(c, me);
    if (d < bestD) {
      bestD = d;
      best = i;
    }
  });
  let remaining = 0;
  for (let i = best + 1; i < coords.length; i++) remaining += distM(coords[i - 1], coords[i]);
  return { remainingM: remaining, offRouteM: distToLine(me, coords) };
}
