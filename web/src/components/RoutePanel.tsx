import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { LonLat, Mode, Profile, RouteKind, RouteResponse, Weights } from "../api";
import PlaceInput from "./PlaceInput";
import RouteCards from "./RouteCards";
import { Button, Callout, Icon, IconButton, Segmented, Spinner } from "./ui";

export interface Endpoint {
  pos: LonLat;
  label: string;
}

export interface RouteSettings {
  mode: Mode;
  profile: Profile;
  maxDetour: number;
  night: boolean;
  custom: boolean;
  weights: Weights;
}

interface Props {
  origin: Endpoint | null;
  destination: Endpoint | null;
  setOrigin: (e: Endpoint | null) => void;
  setDestination: (e: Endpoint | null) => void;
  settings: RouteSettings;
  setSettings: (s: RouteSettings) => void;
  result: RouteResponse | null;
  selected: RouteKind;
  setSelected: (k: RouteKind) => void;
  busy: boolean;
  error: string | null;
  onNavigate: () => void;
}

const PROFILES: Profile[] = ["balanced", "quiet", "clean_air", "green_water", "fastest"];
const WEIGHT_KEYS: (keyof Weights)[] = ["noise", "air", "traffic", "green", "fountain", "cycleway"];

export default function RoutePanel(p: Props) {
  const { t } = useTranslation();
  const [fromText, setFromText] = useState("");
  const [toText, setToText] = useState("");
  const [geoError, setGeoError] = useState(false);
  const s = p.settings;
  const set = (patch: Partial<RouteSettings>) => p.setSettings({ ...s, ...patch });
  const fromValue = p.origin && fromText === "" ? p.origin.label : fromText;
  const toValue = p.destination && toText === "" ? p.destination.label : toText;
  const hasAny = !!(p.origin || p.destination || fromText || toText);

  // on phones the results sit below the form: bring them into view when they first appear
  const resultsRef = useRef<HTMLElement>(null);
  const hadResult = useRef(false);
  useEffect(() => {
    const has = !!p.result;
    if (has && !hadResult.current && window.matchMedia("(max-width: 899px)").matches)
      resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    hadResult.current = has;
  }, [p.result]);

  const myLocation = () => {
    setGeoError(false);
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        setFromText("");
        p.setOrigin({ pos: { lon: pos.coords.longitude, lat: pos.coords.latitude }, label: t("route.myLocation") });
      },
      () => setGeoError(true),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  const optionsSummary = [
    t("route.detourShort", { pct: s.maxDetour }),
    s.night ? t("route.nightShort") : null,
    s.custom ? t("route.customShort") : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <div className="panel-body">
      <div className="places">
        <div className="places-fields">
          <PlaceInput
            label={t("route.from")}
            placeholder={t("route.fromPlaceholder")}
            variant="from"
            value={fromValue}
            onChange={(v) => {
              setFromText(v);
              if (!v) p.setOrigin(null);
            }}
            onPick={(pl) => {
              setFromText("");
              p.setOrigin({ pos: { lon: pl.lon, lat: pl.lat }, label: pl.label });
            }}
          />
          <PlaceInput
            label={t("route.to")}
            placeholder={t("route.toPlaceholder")}
            variant="to"
            value={toValue}
            onChange={(v) => {
              setToText(v);
              if (!v) p.setDestination(null);
            }}
            onPick={(pl) => {
              setToText("");
              p.setDestination({ pos: { lon: pl.lon, lat: pl.lat }, label: pl.label });
            }}
          />
        </div>
        <IconButton
          icon="swap"
          label={t("route.swap")}
          disabled={!p.origin && !p.destination}
          onClick={() => {
            const o = p.origin;
            p.setOrigin(p.destination);
            p.setDestination(o);
            setFromText("");
            setToText("");
          }}
        />
      </div>
      {("geolocation" in navigator || hasAny) && (
        <div className="place-tools">
          {"geolocation" in navigator && (
            <Button variant="ghost" size="sm" icon="locate" onClick={myLocation}>
              {t("route.myLocation")}
            </Button>
          )}
          {hasAny && (
            <Button
              variant="ghost"
              size="sm"
              icon="x"
              onClick={() => {
                p.setOrigin(null);
                p.setDestination(null);
                setFromText("");
                setToText("");
              }}
            >
              {t("route.clear")}
            </Button>
          )}
        </div>
      )}
      {geoError && (
        <Callout tone="danger" role="alert">
          {t("errors.geolocation")}
        </Callout>
      )}

      <Segmented<Mode>
        name="mode"
        legend={t("route.mode")}
        value={s.mode}
        onChange={(m) => set({ mode: m })}
        options={[
          { value: "walk", label: t("route.walk"), icon: "walk" },
          { value: "bike", label: t("route.bike"), icon: "bike" },
        ]}
      />

      <fieldset className="chips">
        <legend className="group-title">{t("route.profile")}</legend>
        {PROFILES.map((pr) => (
          <label key={pr} className={!s.custom && s.profile === pr ? "on" : undefined}>
            <input
              type="radio"
              name="profile"
              checked={!s.custom && s.profile === pr}
              onChange={() => set({ profile: pr, custom: false })}
            />
            {t(`profiles.${pr}`)}
          </label>
        ))}
      </fieldset>

      <details className="disclosure">
        <summary>
          <Icon name="sliders" size={16} />
          {t("route.advanced")}
          <span className="sum">{optionsSummary}</span>
          <Icon name="chevron" size={16} />
        </summary>
        <div className="disclosure-body">
          <label className="slider">
            <span className="slider-head">
              {t("route.maxDetourLabel")}
              <b>{s.maxDetour} %</b>
            </span>
            <input type="range" min={0} max={60} step={5} value={s.maxDetour} onChange={(e) => set({ maxDetour: Number(e.target.value) })} />
          </label>
          <label className="check">
            <input type="checkbox" checked={s.night} onChange={(e) => set({ night: e.target.checked })} />
            {t("route.night")}
          </label>
          <label className="check">
            <input type="checkbox" checked={s.custom} onChange={(e) => set({ custom: e.target.checked })} />
            {t("route.custom")}
          </label>
          {s.custom && (
            <div className="weights">
              {WEIGHT_KEYS.map((k) => (
                <label key={k} className="slider">
                  <span className="slider-head">
                    {t(k === "cycleway" ? `weights.cycleway_${s.mode}` : `weights.${k}`)}
                    <b>{s.weights[k].toFixed(1)}</b>
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={5}
                    step={0.5}
                    value={s.weights[k]}
                    onChange={(e) => set({ weights: { ...s.weights, [k]: Number(e.target.value) } })}
                  />
                </label>
              ))}
            </div>
          )}
        </div>
      </details>

      {p.error && (
        <Callout tone="danger" role="alert">
          {t(`errors.${p.error}`, { defaultValue: t("errors.generic") })}
        </Callout>
      )}

      {!p.result && !p.busy && !p.error && (
        <div className="empty-state">
          <h2>{t("empty.title")}</h2>
          <ol className="steps">
            <li>
              <span className="n">1</span>
              {t("empty.step1")}
            </li>
            <li>
              <span className="n">2</span>
              {t("empty.step2")}
            </li>
            <li>
              <span className="n">3</span>
              {t("empty.step3")}
            </li>
          </ol>
        </div>
      )}

      {(p.result || p.busy) && (
        <section ref={resultsRef} className={p.busy ? "results busy" : "results"} aria-labelledby="results-title" aria-busy={p.busy}>
          <div className="results-head">
            <h2 id="results-title">{t("route.results")}</h2>
            {p.busy && <Spinner label={t("route.planning")} />}
          </div>
          {p.result ? (
            <>
              {p.result.warnings.map((w) => (
                <Callout key={w} tone="warn" role="status">
                  {t(`warnings.${w}`)}
                </Callout>
              ))}
              <RouteCards
                routes={p.result.routes}
                selected={p.selected}
                onSelect={p.setSelected}
                mode={p.result.mode}
                names={[p.origin?.label ?? "", p.destination?.label ?? ""]}
                onNavigate={p.onNavigate}
              />
            </>
          ) : (
            <div className="options" aria-hidden="true">
              <div className="skeleton" style={{ height: 64 }} />
              <div className="skeleton" style={{ height: 64 }} />
              <div className="skeleton" style={{ height: 140 }} />
            </div>
          )}
        </section>
      )}
    </div>
  );
}
