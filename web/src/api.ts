// Typed client for the Zdrowa Trasa API (/api/v1). Shapes mirror api/models.py.

export type Mode = "walk" | "bike";
export type Profile = "fastest" | "balanced" | "quiet" | "clean_air" | "green_water";
export type RouteKind = "fastest" | "healthiest" | "balanced";
export type LonLat = { lon: number; lat: number };
export type Weights = {
  noise: number;
  air: number;
  traffic: number;
  green: number;
  fountain: number;
  cycleway: number;
};

export interface RouteMetrics {
  distance_m: number;
  duration_min: number;
  noise_mean_db: number | null;
  noise_night_mean_db: number | null;
  share_loud: number | null;
  exposure_noise: number | null;
  green_mean: number | null;
  traffic_mean: number | null;
  air_index: number | null;
  exposure_index: number | null;
  coverage: number;
  fountains_near: number;
  cycle_separated: number | null;
  cycle_on_street: number | null;
}

export interface Tradeoff {
  extra_min: number;
  noise_pct: number | null;
  exposure_pct: number | null;
  green_pct: number | null;
  air_pct: number | null;
  text: string;
}

export interface SegmentProps {
  noise_db: number | null;
  green: number | null;
  air: number;
  covered: boolean;
  name: string | null;
}

export interface Route {
  kind: RouteKind;
  profile: string;
  weights_scale: number;
  limited_by_detour: boolean;
  metrics: RouteMetrics;
  tradeoff: Tradeoff | null;
  same_as: RouteKind | null;
  geometry: GeoJSON.FeatureCollection<GeoJSON.LineString, SegmentProps>;
}

export interface AirBrief {
  available: boolean;
  level?: number;
  band?: number;
  band_pl?: string;
  band_en?: string;
  data_ts_utc?: string;
  stale?: boolean;
}

export interface RouteResponse {
  mode: Mode;
  profile: string;
  air: AirBrief;
  routes: Route[];
  warnings: string[];
}

export interface RouteRequest {
  origin: LonLat;
  destination: LonLat;
  mode: Mode;
  profile: Profile;
  weights?: Weights;
  max_detour_pct: number;
  night: boolean;
  lang: "pl" | "en";
}

export interface Place {
  label: string;
  kind: "address" | "street" | "poi";
  district: string | null;
  lon: number;
  lat: number;
  category: string | null;
  category_pl: string | null;
  category_en: string | null;
}

export interface Station {
  station_id: number;
  name: string;
  lat: number;
  lon: number;
  values: Record<string, { value: number; ts_utc: string; fresh: boolean; band: number }>;
}

export interface AirNow extends AirBrief {
  pollutants?: Record<string, { mean: number; n_stations: number; normalised: number; band: number }>;
  stations?: Station[];
  missing?: string[];
  source: string;
  note: string;
}

export interface Source {
  key: string;
  title: string | null;
  provider: string | null;
  link: string | null;
  data_date: string | null;
  date_obtained: string | null;
  licence: string | null;
  citation: string | null;
}

export interface Overlay {
  url: string;
  coordinates: [[number, number], [number, number], [number, number], [number, number]];
}

export interface HotspotProps {
  rank: number;
  priority: number;
  presence_raw: number;
  severity: number;
  presence: number;
  district_id: number;
  district: string;
  street: string | null;
  noise_db: number;
  green: number;
  traffic: number;
  schools: number;
  pupils: number;
  kindergartens: number;
  nurseries: number;
  children_small: number;
  addresses: number;
  centre: [number, number];
}

export interface District {
  district_id: number;
  number: string;
  name: string;
  population: number;
  children_0_14: number;
  seniors_65: number;
  sensitive_sites: number;
  severity_mean: number | null;
  noise_mean_db: number | null;
  green_mean: number | null;
  share_loud_cells: number | null;
  hotspots_top100: number;
  priority_sum: number;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

const BASE = "/api/v1";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new ApiError(r.status, `http_${r.status}`);
  return (await r.json()) as T;
}

export const api = {
  geocode: (q: string) => get<Place[]>(`/geocode?q=${encodeURIComponent(q)}&limit=6`),
  air: () => get<AirNow>("/air/now"),
  sources: () => get<Source[]>("/meta/sources"),
  layers: () => get<Record<string, Overlay>>("/layers"),
  fountains: () => get<GeoJSON.FeatureCollection<GeoJSON.Point>>("/points/fountains"),
  cycleways: () => get<GeoJSON.FeatureCollection<GeoJSON.LineString>>("/lines/cycleways"),
  hotspots: (district?: number) =>
    get<GeoJSON.FeatureCollection<GeoJSON.Polygon, HotspotProps>>(
      `/planner/hotspots?limit=500${district ? `&district=${district}` : ""}`,
    ),
  districts: () => get<District[]>("/planner/districts"),
  exportUrl: (district?: number) =>
    `${BASE}/planner/export.csv${district ? `?district=${district}` : ""}`,
  async route(req: RouteRequest): Promise<RouteResponse> {
    const r = await fetch(BASE + "/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!r.ok) {
      let code = `http_${r.status}`;
      try {
        const body = (await r.json()) as { detail?: { code?: string } };
        code = body.detail?.code ?? code;
      } catch {
        /* keep the HTTP code */
      }
      throw new ApiError(r.status, code);
    }
    return (await r.json()) as RouteResponse;
  },
};
