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
import PlannerPanel, { HotspotFacts, HotspotWho } from "./components/PlannerPanel";
import RoutePanel, { type Endpoint, type RouteSettings } from "./components/RoutePanel";
import { Button, Icon, IconButton, Segmented } from "./components/ui";
import { progress } from "./export";
import { setLang } from "./i18n";

type Tab = "route" | "planner";

const DEFAULT_SETTINGS: RouteSettings = {
  mode: "walk",
  profile: "balanced",
  maxDetour: 30,
  night: false,
  custom: false,
  weights: { noise: 1, air: 1, traffic: 0.5, green: 0.7, fountain: 0, cycleway: 0.7 },
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
  const [cycleways, setCycleways] = useState<GeoJSON.FeatureCollection | null>(null);
  const [layers, setLayers] = useState<LayerState>({
    noise: false,
    green: false,
    traffic: false,
    fountains: false,
    cycleways: false,
    stations: true,
    hotspots: false,
  });
  const [hotspots, setHotspots] = useState<GeoJSON.FeatureCollection<GeoJSON.Polygon, HotspotProps> | null>(null);
  const [hotspotsLoading, setHotspotsLoading] = useState(false);
  const [districts, setDistricts] = useState<District[]>([]);
  const [district, setDistrict] = useState<number | undefined>();
  const [focusHotspot, setFocusHotspot] = useState<HotspotProps | null>(null);
  const [focus, setFocus] = useState<[number, number] | null>(null);
  const [about, setAbout] = useState(false);
  const request = useRef(0);
  // in-app guidance: the position never leaves the browser
  const [nav, setNav] = useState(false);
  const [me, setMe] = useState<{ lon: number; lat: number; acc: number } | null>(null);
  const [navError, setNavError] = useState(false);

  useEffect(() => {
    if (!nav || !("geolocation" in navigator)) return;
    setNavError(false);
    const id = navigator.geolocation.watchPosition(
      (pos) => {
        setNavError(false);
        setMe({ lon: pos.coords.longitude, lat: pos.coords.latitude, acc: pos.coords.accuracy });
      },
      // only a refusal is an error; a timeout or a lost fix keeps the last position
      (err) => err.code === err.PERMISSION_DENIED && setNavError(true),
      { enableHighAccuracy: true, maximumAge: 5000 },
    );
    let lock: { release: () => Promise<void> } | undefined;
    const wl = (navigator as Navigator & { wakeLock?: { request: (t: "screen") => Promise<typeof lock> } }).wakeLock;
    wl?.request("screen").then((l) => (lock = l)).catch(() => undefined);
    return () => {
      navigator.geolocation.clearWatch(id);
      void lock?.release().catch(() => undefined);
      setMe(null);
    };
  }, [nav]);

  useEffect(() => {
    api.air().then(setAir).catch(() => setAir(null));
    api.layers().then(setOverlays).catch(() => undefined);
    api.fountains().then(setFountains).catch(() => undefined);
    api.cycleways().then(setCycleways).catch(() => undefined);
    const h = setInterval(() => api.air().then(setAir).catch(() => undefined), 10 * 60 * 1000);
    return () => clearInterval(h);
  }, []);

  useEffect(() => {
    if (tab !== "planner") return;
    setLayers((l) => ({ ...l, hotspots: true }));
    setHotspotsLoading(true);
    api
      .hotspots(district)
      .then(setHotspots)
      .catch(() => setHotspots(null))
      .finally(() => setHotspotsLoading(false));
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
  const switchTab = (k: Tab) => {
    setTab(k);
    if (k === "route") setLayers((l) => ({ ...l, hotspots: false }));
  };
  const mapHint =
    tab === "route" && !nav && !busy && !(origin && destination)
      ? origin
        ? t("route.mapHintTo")
        : t("route.mapHintFrom")
      : null;
  const showRouteLegend = tab === "route" && !!result?.routes.some((r) => !r.same_as) && !nav;
  return (
    <div className={nav ? "app navigating" : "app"}>
      <header className="top">
        <img className="logo" src="/logo.svg" alt="" width="32" height="32" />
        <div className="brand">
          <h1>{t("app.title")}</h1>
          <span className="tagline">{t("app.tagline")}</span>
        </div>
        <AirBadge air={air} />
        <div className="top-actions">
          <Button variant="ghost" size="sm" icon="info" onClick={() => setAbout(true)} aria-label={t("about.button")}>
            <span className="label-wide">{t("about.button")}</span>
          </Button>
          <Button
            variant="ghost"
            size="sm"
            icon="globe"
            className="lang-btn"
            lang={lang === "pl" ? "en" : "pl"}
            aria-label={t("lang.label")}
            onClick={() => setLang(lang === "pl" ? "en" : "pl")}
          >
            {lang === "pl" ? "EN" : "PL"}
          </Button>
        </div>
      </header>
      <main className="main">
        <section className={tab === "planner" ? "panel wide" : "panel"} aria-label={t(`tabs.${tab}`)}>
          <div className="panel-head">
            <Segmented<Tab>
              name="tab"
              legend={t("tabs.label")}
              value={tab}
              onChange={switchTab}
              options={[
                { value: "route", label: t("tabs.route"), icon: "route" },
                { value: "planner", label: t("tabs.planner"), icon: "chart" },
              ]}
            />
          </div>
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
              onNavigate={() => setNav(true)}
            />
          ) : (
            <PlannerPanel
              hotspots={hotspots?.features.map((f) => f.properties) ?? []}
              loading={hotspotsLoading}
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
            cycleways={cycleways}
            air={air}
            hotspots={hotspots}
            focus={focus}
            onMapClick={onMapClick}
            onHotspotClick={showHotspot}
            me={nav ? me : null}
          />
          <div className="map-ctrl">
            <LayerToggles
              layers={layers}
              setLayers={setLayers}
              keys={tab === "route" ? ["noise", "green", "traffic", "cycleways", "fountains", "stations"] : ["hotspots", "noise", "green", "traffic"]}
            />
          </div>
          {mapHint && (
            <div className="map-hint" aria-hidden="true">
              <Icon name="pin" size={16} />
              {mapHint}
            </div>
          )}
          {showRouteLegend && (
            <div className="map-legend">
              <b>{t("legend.routeTitle")}</b>
              <span className="ramp ramp-noise" />
              <span className="ramp-labels">
                <span>50 dB</span>
                <span>75+ dB</span>
              </span>
              <span className="keys">
                <span>
                  <i style={{ background: "repeating-linear-gradient(90deg,#64748b 0 5px,transparent 5px 8px)" }} />
                  {t("legend.otherRoutes")}
                </span>
              </span>
            </div>
          )}
          {nav && tab === "route" && (
            <NavBanner
              route={result?.routes.find((r) => r.kind === selected && !r.same_as) ?? null}
              mode={settings.mode}
              me={me}
              error={navError}
              onStop={() => setNav(false)}
            />
          )}
          {tab === "planner" && focusHotspot && (
            <div className="map-card" role="status">
              <div className="map-card-head">
                <span className="rank">{focusHotspot.rank}</span>
                <h3>
                  {focusHotspot.street ?? "–"}
                  <span className="muted small"> · {focusHotspot.district}</span>
                </h3>
                <IconButton icon="x" label={t("about.close")} onClick={() => setFocusHotspot(null)} />
              </div>
              <HotspotFacts h={focusHotspot} />
              <HotspotWho h={focusHotspot} />
            </div>
          )}
        </section>
      </main>
      <AboutData open={about} onClose={() => setAbout(false)} />
    </div>
  );
}

function NavBanner({
  route,
  mode,
  me,
  error,
  onStop,
}: {
  route: RouteResponse["routes"][number] | null;
  mode: "walk" | "bike";
  me: { lon: number; lat: number } | null;
  error: boolean;
  onStop: () => void;
}) {
  const { t } = useTranslation();
  let text = t("nav.waiting");
  let off: number | null = null;
  if (error) text = t("nav.error");
  else if (route && me) {
    const pr = progress(route, [me.lon, me.lat]);
    const speed = mode === "bike" ? 4.2 : 1.33;
    text =
      pr.remainingM < 30
        ? t("nav.arrived")
        : t("nav.remaining", { km: (pr.remainingM / 1000).toFixed(1), min: Math.max(1, Math.round(pr.remainingM / speed / 60)) });
    if (pr.offRouteM > 40) off = Math.round(pr.offRouteM);
  }
  return (
    <div className="nav-banner" role="status" aria-live="polite">
      <span className="nav-text">
        <span>{text}</span>
        {off != null && <span className="nav-off">{t("nav.offRoute", { m: off })}</span>}
      </span>
      <Button size="sm" icon="x" onClick={onStop}>
        {t("nav.stop")}
      </Button>
    </div>
  );
}
