import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type AirNow, type Source } from "../api";
import type { LayerKey, LayerState } from "./MapView";
import { Button, Icon, IconButton } from "./ui";

// same scale as the station markers on the map
export const BAND_COLOURS = ["#2e9d47", "#8bc34a", "#e7c500", "#f08c00", "#d9381e", "#8b1a1a"];

export function AirBadge({ air }: { air: AirNow | null }) {
  const { t, i18n } = useTranslation();
  const ref = useRef<HTMLDetailsElement>(null);
  // close the popover on an outside click or Escape
  useEffect(() => {
    const close = (e: Event) => {
      const d = ref.current;
      if (!d?.open) return;
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !d.contains(e.target as Node)) d.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);
  if (!air) return null;
  if (!air.available)
    return (
      <span className="air-chip">
        <span className="sr-only">{t("air.title")}: </span>
        <span className="air-detail muted small">{t("air.unavailable")}</span>
      </span>
    );
  const time = new Date(air.data_ts_utc ?? "").toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" });
  const band = i18n.language === "en" ? air.band_en : air.band_pl;
  const colour = air.stale ? "#9ca3af" : BAND_COLOURS[air.band ?? 0];
  return (
    <details className="air-chip" ref={ref}>
      <summary aria-label={`${t("air.title")}: ${band}. ${air.stale ? t("air.stale") : t("air.from", { time })}`}>
        <span className="air-dot" style={{ background: colour }} aria-hidden="true" />
        <span>
          <span className="air-prefix">{t("air.prefix")} </span>
          {band}
        </span>
        <span className="air-detail">· {air.stale ? t("air.stale") : t("air.from", { time })}</span>
        <Icon name="down" size={14} />
      </summary>
      <div className="popover">
        <h3>{t("air.title")}</h3>
        <ul className="pollutants">
          {Object.entries(air.pollutants ?? {}).map(([k, v]) => (
            <li key={k}>
              <span>{k.replace("PM25", "PM2.5")}</span>
              <b>{v.mean}</b>
              <span>µg/m³ · {t("air.nStations", { count: v.n_stations })}</span>
            </li>
          ))}
        </ul>
        <p className="muted">{t("air.indicative")}</p>
        <p className="small muted">{t("air.source")}</p>
      </div>
    </details>
  );
}

function Legend({ k }: { k: LayerKey }) {
  const { t } = useTranslation();
  if (k === "noise" || k === "green" || k === "traffic") {
    const [lo, hi] = t(`legend.${k}`).split("→").map((x) => x.trim());
    return (
      <span className="layer-legend">
        <span className={`ramp ramp-${k}`} />
        <span className="ramp-labels">
          <span>{lo}</span>
          <span>{hi}</span>
        </span>
      </span>
    );
  }
  if (k === "cycleways") {
    const [a, b, c] = t("legend.cycleways").split("·").map((x) => x.trim());
    return (
      <span className="layer-legend keys">
        <span>
          <i style={{ background: "#0f766e", height: 4 }} />
          {a}
        </span>
        <span>
          <i style={{ background: "#7c3aed" }} />
          {b}
        </span>
        <span>
          <i style={{ background: "#94a3b8" }} />
          {c}
        </span>
      </span>
    );
  }
  if (k === "hotspots") {
    return (
      <span className="layer-legend">
        <span className="ramp ramp-priority" />
        <span className="ramp-labels">
          <span>{t("legend.lower")}</span>
          <span>{t("legend.higher")}</span>
        </span>
      </span>
    );
  }
  return null;
}

export function LayerToggles({
  layers,
  setLayers,
  keys,
}: {
  layers: LayerState;
  setLayers: (l: LayerState) => void;
  keys: LayerKey[];
}) {
  const { t } = useTranslation();
  const on = keys.filter((k) => layers[k]).length;
  return (
    <details className="layers">
      <summary>
        <Icon name="layers" size={16} />
        {t("layers.title")}
        {on > 0 && (
          <span className="count" aria-label={t("layers.active", { count: on })}>
            {on}
          </span>
        )}
      </summary>
      <div className="layers-body">
        {keys.map((k) => (
          <div key={k} className="layer-row">
            <label className="check">
              <input type="checkbox" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} />
              {t(`layers.${k}`)}
            </label>
            {layers[k] && <Legend k={k} />}
          </div>
        ))}
      </div>
    </details>
  );
}

export function AboutData({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const [sources, setSources] = useState<Source[]>([]);
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (open && !sources.length) api.sources().then(setSources).catch(() => undefined);
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open, sources.length]);
  return (
    <dialog
      ref={ref}
      className="about"
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="about-title"
    >
      <div className="dialog-head">
        <h2 id="about-title">{t("about.title")}</h2>
        <IconButton icon="x" label={t("about.close")} onClick={onClose} />
      </div>
      <div className="dialog-body">
        <p>{t("about.disclaimer")}</p>
        <ul className="sources">
          {sources
            .filter((s) => s.title)
            .map((s) => (
              <li key={s.key} className="source">
                <strong>{s.title}</strong>
                <span className="meta">
                  {s.provider && <span>{s.provider}</span>}
                  {s.data_date && (
                    <span>
                      {t("about.created")}: {s.data_date}
                    </span>
                  )}
                  {s.date_obtained && (
                    <span>
                      {t("about.obtained")}: {s.date_obtained}
                    </span>
                  )}
                </span>
                {s.link && (
                  <a href={s.link} target="_blank" rel="noreferrer">
                    {s.link.replace(/^https?:\/\//, "").slice(0, 80)}
                  </a>
                )}
                {s.citation && <span className="cite">{s.citation}</span>}
              </li>
            ))}
        </ul>
        <p>{t("about.privacy")}</p>
        <p className="muted">{t("about.inspiration")}</p>
      </div>
      <div className="dialog-foot">
        <Button variant="primary" onClick={onClose} autoFocus>
          {t("about.close")}
        </Button>
      </div>
    </dialog>
  );
}
