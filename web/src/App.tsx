import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  api,
  ApiError,
  type AirNow,
  type District,
  type HotspotProps,
  type Overlay,
  type RouteKind,
  type RouteResponse,
} from "./api";
import { AboutData, AirBadge, LayerToggles } from "./components/Extras";
import MapView, { type LayerState } from "./components/MapView";
import PlannerPanel, { HotspotText } from "./components/PlannerPanel";
import RoutePanel, { type Endpoint, type RouteSettings } from "./components/RoutePanel";
import { setLang } from "./i18n";

type Tab = "route" | "planner";

const DEFAULT_SETTINGS: RouteSettings = {
  mode: "walk",
  profile: "balanced",
  maxDetour: 30,
  night: false,
  custom: false,
  weights: { noise: 1, air: 1, traffic: 0.5, green: 0.7, fountain: 0 },
};

export default function App() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("route");
  const [origin, setOrigin] = useState<Endpoint | null>(null);
  const [destination, setDestination] = useState<Endpoint | null>(null);
  const [settings, setSettings] = useState<RouteSettings>(DEFAULT_SETTINGS);
  const [result, setResult] = useState<RouteResponse | null>(null);
  const [selected, setSelected] = useState<RouteKind>("healthiest");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [air, setAir] = useState<AirNow | null>(null);
  const [overlays, setOverlays] = useState<Record<string, Overlay>>({});
  const [fountains, setFountains] = useState<GeoJSON.FeatureCollection | null>(null);
  const [layers, setLayers] = useState<LayerState>({
    noise: false,
    green: false,
    traffic: false,
    fountains: false,
    stations: true,
    hotspots: false,
  });
  const [hotspots, setHotspots] = useState<GeoJSON.FeatureCollection<GeoJSON.Polygon, HotspotProps> | null>(null);
  const [districts, setDistricts] = useState<District[]>([]);
  const [district, setDistrict] = useState<number | undefined>();
  const [focusHotspot, setFocusHotspot] = useState<HotspotProps | null>(null);
  const [focus, setFocus] = useState<[number, number] | null>(null);
  const [about, setAbout] = useState(false);
  const request = useRef(0);

  useEffect(() => {
    api.air().then(setAir).catch(() => setAir(null));
    api.layers().then(setOverlays).catch(() => undefined);
    api.fountains().then(setFountains).catch(() => undefined);
    const h = setInterval(() => api.air().then(setAir).catch(() => undefined), 10 * 60 * 1000);
    return () => clearInterval(h);
  }, []);

  useEffect(() => {
    if (tab !== "planner") return;
    setLayers((l) => ({ ...l, hotspots: true }));
    api.hotspots(district).then(setHotspots).catch(() => setHotspots(null));
    if (!districts.length) api.districts().then(setDistricts).catch(() => undefined);
  }, [tab, district, districts.length]);

  // plan routes whenever both ends and the settings are set
  useEffect(() => {
    if (!origin || !destination) {
      setResult(null);
      return;
    }
    const id = ++request.current;
    setBusy(true);
    setError(null);
    api
      .route({
        origin: origin.pos,
        destination: destination.pos,
        mode: settings.mode,
        profile: settings.profile,
        weights: settings.custom ? settings.weights : undefined,
        max_detour_pct: settings.maxDetour,
        night: settings.night,
        lang: i18n.language === "en" ? "en" : "pl",
      })
      .then((r) => {
        if (id !== request.current) return;
        setResult(r);
        setSelected(r.routes.find((x) => x.kind === "healthiest" && !x.same_as) ? "healthiest" : "fastest");
      })
      .catch((e: unknown) => {
        if (id !== request.current) return;
        setResult(null);
        setError(e instanceof ApiError ? e.code : "generic");
      })
      .finally(() => id === request.current && setBusy(false));
  }, [origin, destination, settings, i18n.language]);

  const onMapClick = useCallback(
    (p: { lon: number; lat: number }) => {
      if (tab !== "route") return;
      const label = `${t("route.pickedOnMap")} (${p.lat.toFixed(4)}, ${p.lon.toFixed(4)})`;
      if (!origin || (origin && destination)) {
        setOrigin({ pos: p, label });
        setDestination(null);
      } else {
        setDestination({ pos: p, label });
      }
    },
    [tab, origin, destination, t],
  );

  const showHotspot = (h: HotspotProps) => {
    setFocusHotspot(h);
    setFocus([h.centre[0], h.centre[1]]);
  };

  const lang = i18n.language === "en" ? "en" : "pl";
  return (
    <div className="app">
      <header className="top">
        <img className="logo" src="/logo.svg" alt="" width="36" height="36" />
        <div className="brand">
          <h1>{t("app.title")}</h1>
          <span className="tagline">{t("app.tagline")}</span>
        </div>
        <AirBadge air={air} />
        <div className="top-actions">
          <button type="button" className="link" onClick={() => setAbout(true)}>
            {t("about.button")}
          </button>
          <button type="button" className="link" aria-label={t("lang.label")} onClick={() => setLang(lang === "pl" ? "en" : "pl")}>
            {t("lang.switch")}
          </button>
        </div>
      </header>
      <main className="main">
        <section className="panel" aria-label={t(`tabs.${tab}`)}>
          <nav className="tabs" role="tablist">
            {(["route", "planner"] as Tab[]).map((k) => (
              <button
                key={k}
                type="button"
                role="tab"
                aria-selected={tab === k}
                className={tab === k ? "on" : undefined}
                onClick={() => {
                  setTab(k);
                  if (k === "route") setLayers((l) => ({ ...l, hotspots: false }));
                }}
              >
                {t(`tabs.${k}`)}
              </button>
            ))}
          </nav>
          {tab === "route" ? (
            <RoutePanel
              origin={origin}
              destination={destination}
              setOrigin={setOrigin}
              setDestination={setDestination}
              settings={settings}
              setSettings={setSettings}
              result={result}
              selected={selected}
              setSelected={setSelected}
              busy={busy}
              error={error}
            />
          ) : (
            <PlannerPanel
              hotspots={hotspots?.features.map((f) => f.properties) ?? []}
              districts={districts}
              district={district}
              setDistrict={setDistrict}
              onFocus={showHotspot}
              selected={focusHotspot}
            />
          )}
        </section>
        <section className="map-wrap">
          <MapView
            overlays={overlays}
            layers={layers}
            routes={tab === "route" ? (result?.routes ?? []) : []}
            selected={selected}
            origin={tab === "route" ? (origin?.pos ?? null) : null}
            destination={tab === "route" ? (destination?.pos ?? null) : null}
            fountains={fountains}
            air={air}
            hotspots={hotspots}
            focus={focus}
            onMapClick={onMapClick}
            onHotspotClick={showHotspot}
          />
          <LayerToggles
            layers={layers}
            setLayers={setLayers}
            keys={tab === "route" ? ["noise", "green", "traffic", "fountains", "stations"] : ["hotspots", "noise", "green", "traffic"]}
          />
          {tab === "planner" && focusHotspot && (
            <div className="hotspot-card" role="status">
              <strong>
                {t("planner.rank", { rank: focusHotspot.rank })} {focusHotspot.street ?? "–"} · {focusHotspot.district}
              </strong>
              <br />
              <HotspotText h={focusHotspot} />
            </div>
          )}
        </section>
      </main>
      <AboutData open={about} onClose={() => setAbout(false)} />
    </div>
  );
}
