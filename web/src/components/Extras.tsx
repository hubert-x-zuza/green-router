import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type AirNow, type Source } from "../api";
import type { LayerKey, LayerState } from "./MapView";

const BAND_CLASS = ["b0", "b1", "b2", "b3", "b4", "b5"];

export function AirBadge({ air }: { air: AirNow | null }) {
  const { t, i18n } = useTranslation();
  if (!air) return null;
  if (!air.available) return <span className="air-badge stale">{t("air.unavailable")}</span>;
  const time = new Date(air.data_ts_utc ?? "").toLocaleTimeString(i18n.language, { hour: "2-digit", minute: "2-digit" });
  const band = i18n.language === "en" ? air.band_en : air.band_pl;
  return (
    <details className={`air-badge ${BAND_CLASS[air.band ?? 0]}${air.stale ? " stale" : ""}`}>
      <summary>
        {t("air.level", { band })} · {air.stale ? t("air.stale") : t("air.from", { time })}
      </summary>
      <div className="air-pop">
        <p className="small">{t("air.indicative")}</p>
        <ul className="small">
          {Object.entries(air.pollutants ?? {}).map(([k, v]) => (
            <li key={k}>
              {k.replace("PM25", "PM2.5")}: {v.mean} µg/m³ ({v.n_stations})
            </li>
          ))}
        </ul>
        <p className="small muted">{t("air.source")}</p>
      </div>
    </details>
  );
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
  return (
    <details className="layers">
      <summary>{t("layers.title")}</summary>
      {keys.map((k) => (
        <label key={k} className="check">
          <input type="checkbox" checked={layers[k]} onChange={(e) => setLayers({ ...layers, [k]: e.target.checked })} />
          {t(`layers.${k}`)}
          {(k === "noise" || k === "green" || k === "traffic" || k === "cycleways") && layers[k] && (
            <span className={`legend legend-${k}`} title={t(`legend.${k}`)}>
              <span className="muted small"> {t(`legend.${k}`)}</span>
            </span>
          )}
        </label>
      ))}
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
    <dialog ref={ref} className="about" onClose={onClose} aria-labelledby="about-title">
      <h2 id="about-title">{t("about.title")}</h2>
      <p className="small">{t("about.disclaimer")}</p>
      <ul className="sources">
        {sources
          .filter((s) => s.title)
          .map((s) => (
            <li key={s.key}>
              <strong>{s.title}</strong>
              {s.provider && <span className="muted"> · {s.provider}</span>}
              <br />
              <span className="small">
                {s.data_date && `${t("about.created")}: ${s.data_date}. `}
                {s.date_obtained && `${t("about.obtained")}: ${s.date_obtained}. `}
                {s.link && (
                  <a href={s.link} target="_blank" rel="noreferrer">
                    {s.link.replace(/^https?:\/\//, "").slice(0, 60)}
                  </a>
                )}
              </span>
              {s.citation && <p className="small muted">{s.citation}</p>}
            </li>
          ))}
      </ul>
      <p className="small">{t("about.privacy")}</p>
      <p className="small muted">{t("about.inspiration")}</p>
      <button type="button" onClick={onClose} autoFocus>
        {t("about.close")}
      </button>
    </dialog>
  );
}
