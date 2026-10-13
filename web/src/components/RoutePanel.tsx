import { useState } from "react";
import { useTranslation } from "react-i18next";
import type { LonLat, Mode, Profile, RouteKind, RouteResponse, Weights } from "../api";
import PlaceInput from "./PlaceInput";
import RouteCards from "./RouteCards";

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
  const s = p.settings;
  const set = (patch: Partial<RouteSettings>) => p.setSettings({ ...s, ...patch });
  const fromValue = p.origin && fromText === "" ? p.origin.label : fromText;
  const toValue = p.destination && toText === "" ? p.destination.label : toText;

  const myLocation = () => {
    navigator.geolocation?.getCurrentPosition(
      (pos) => {
        setFromText("");
        p.setOrigin({ pos: { lon: pos.coords.longitude, lat: pos.coords.latitude }, label: t("route.myLocation") });
      },
      () => alert(t("errors.geolocation")),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

  return (
    <div className="panel-body">
      <p className="hint">{t("route.clickHint")}</p>
      <PlaceInput
        label={t("route.from")}
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
      <div className="row">
        {"geolocation" in navigator && (
          <button type="button" className="link" onClick={myLocation}>
            {t("route.myLocation")}
          </button>
        )}
        <button
          type="button"
          className="link"
          onClick={() => {
            const o = p.origin;
            p.setOrigin(p.destination);
            p.setDestination(o);
            setFromText("");
            setToText("");
          }}
        >
          {t("route.swap")}
        </button>
        <button
          type="button"
          className="link"
          onClick={() => {
            p.setOrigin(null);
            p.setDestination(null);
            setFromText("");
            setToText("");
          }}
        >
          {t("route.clear")}
        </button>
      </div>

      <fieldset className="seg">
        <legend>{t("route.mode")}</legend>
        {(["walk", "bike"] as Mode[]).map((m) => (
          <label key={m} className={s.mode === m ? "on" : undefined}>
            <input type="radio" name="mode" checked={s.mode === m} onChange={() => set({ mode: m })} />
            {t(`route.${m}`)}
          </label>
        ))}
      </fieldset>

      <fieldset className="chips">
        <legend>{t("route.profile")}</legend>
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

      <details className="advanced">
        <summary>{t("route.advanced")}</summary>
        <label className="slider">
          {t("route.maxDetour", { pct: s.maxDetour })}
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
        {s.custom &&
          WEIGHT_KEYS.map((k) => (
            <label key={k} className="slider">
              {t(k === "cycleway" ? `weights.cycleway_${s.mode}` : `weights.${k}`)}: {s.weights[k].toFixed(1)}
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
      </details>

      {p.busy && <p className="muted" aria-live="polite">{t("route.planning")}</p>}
      {p.error && (
        <p className="error" role="alert">
          {t(`errors.${p.error}`, { defaultValue: t("errors.generic") })}
        </p>
      )}
      {p.result && (
        <>
          {p.result.warnings.map((w) => (
            <p key={w} className="note" role="status">
              {t(`warnings.${w}`)}
            </p>
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
      )}
    </div>
  );
}
