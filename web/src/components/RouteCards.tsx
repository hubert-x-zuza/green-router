import { useTranslation } from "react-i18next";
import type { Mode, Route, RouteKind, Tradeoff } from "../api";
import { downloadGpx, googleMapsUrl, shareGpx } from "../export";

interface Props {
  routes: Route[];
  selected: RouteKind;
  onSelect: (k: RouteKind) => void;
  mode: Mode;
  names: [string, string];
}

const fmtPct = (v: number | null) => (v == null ? null : Math.round(v * 100));

function TradeoffLine({ t: tr }: { t: Tradeoff }) {
  const { t } = useTranslation();
  const sign = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "±");
  const parts: string[] = [];
  parts.push(
    Math.abs(tr.extra_min) < 0.5
      ? t("tradeoff.same")
      : t("tradeoff.minutes", { sign: sign(tr.extra_min), min: Math.abs(Math.round(tr.extra_min)) }),
  );
  if (tr.exposure_pct != null && Math.abs(tr.exposure_pct) >= 1)
    parts.push(t("tradeoff.exposure", { sign: sign(tr.exposure_pct), pct: Math.abs(tr.exposure_pct) }));
  if (tr.noise_pct != null && Math.abs(tr.noise_pct) >= 1)
    parts.push(t("tradeoff.noise", { sign: sign(tr.noise_pct), pct: Math.abs(tr.noise_pct) }));
  if (tr.green_pct != null && Math.abs(tr.green_pct) >= 1)
    parts.push(t("tradeoff.green", { sign: sign(tr.green_pct), pct: Math.abs(tr.green_pct) }));
  return <p className="tradeoff">{parts.join(", ")}</p>;
}

/** Bar of a 0..1 value; `good` says whether high is good (green) or bad. */
function Bar({ value, good }: { value: number | null; good: boolean }) {
  if (value == null) return null;
  const v = Math.max(0, Math.min(1, value));
  return (
    <span className="bar" aria-hidden="true">
      <span style={{ width: `${v * 100}%` }} className={good ? "bar-good" : "bar-bad"} />
    </span>
  );
}

function canShareFiles(): boolean {
  try {
    const f = new File([""], "x.gpx", { type: "application/gpx+xml" });
    const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
    return !!nav.canShare?.({ files: [f] });
  } catch {
    return false;
  }
}

interface ExportProps {
  route: Route;
  fastest: Route | undefined;
  mode: Mode;
  names: [string, string];
}

function Export({ route, fastest, mode, names }: ExportProps) {
  const { t } = useTranslation();
  const title = `${names[0]} → ${names[1]} (${t(`kinds.${route.kind}`)})`;
  return (
    <div className="export">
      <div className="row">
        <a
          className="button"
          href={googleMapsUrl(route, mode, fastest)}
          target="_blank"
          rel="noopener noreferrer"
        >
          {t("export.google")}
        </a>
        {canShareFiles() && (
          <button type="button" className="button secondary" onClick={() => void shareGpx(route, title)}>
            {t("export.share")}
          </button>
        )}
        <button type="button" className="button secondary" onClick={() => downloadGpx(route, title)}>
          {t("export.gpx")}
        </button>
      </div>
      <p className="muted small">{t("export.hint")}</p>
    </div>
  );
}

export default function RouteCards({ routes, selected, onSelect, mode, names }: Props) {
  const { t } = useTranslation();
  const sel = routes.find((r) => r.kind === selected && !r.same_as) ?? routes[0];
  return (
    <>
    <div className="cards" role="radiogroup" aria-label={t("metrics.show")}>
      {routes.map((r) => {
        const m = r.metrics;
        const nd = t("metrics.noData");
        const isSel = r.kind === selected;
        return (
          <div
            key={r.kind}
            className={`card card-${r.kind}${isSel ? " selected" : ""}`}
            role="radio"
            aria-checked={isSel}
            tabIndex={0}
            onClick={() => !r.same_as && onSelect(r.kind)}
            onKeyDown={(e) => {
              if ((e.key === "Enter" || e.key === " ") && !r.same_as) {
                e.preventDefault();
                onSelect(r.kind);
              }
            }}
          >
            <div className="card-head">
              <span className="swatch" aria-hidden="true" />
              <strong>{t(`kinds.${r.kind}`)}</strong>
              {r.kind !== "fastest" && r.profile !== r.kind && (
                <span className="muted"> · {t(`profiles.${r.profile}`)}</span>
              )}
            </div>
            {r.same_as ? (
              <p className="muted">
                {r.same_as === "fastest"
                  ? t("metrics.sameAsFastest")
                  : t("metrics.sameAs", { kind: t(`kinds.${r.same_as}`) })}
              </p>
            ) : (
              <>
                <p className="big">
                  {t("metrics.time", { min: Math.round(m.duration_min) })}{" "}
                  <span className="muted">{t("metrics.distance", { km: (m.distance_m / 1000).toFixed(1) })}</span>
                </p>
                {r.tradeoff && <TradeoffLine t={r.tradeoff} />}
                <dl className="metrics">
                  <dt>{t("metrics.noise")}</dt>
                  <dd>{m.noise_mean_db == null ? nd : `${m.noise_mean_db.toFixed(0)} dB`}</dd>
                  <dt>{t("metrics.loud")}</dt>
                  <dd>
                    {m.share_loud == null ? nd : `${fmtPct(m.share_loud)} %`} <Bar value={m.share_loud} good={false} />
                  </dd>
                  <dt>{t("metrics.green")}</dt>
                  <dd>
                    {m.green_mean == null ? nd : `${fmtPct(m.green_mean)} %`} <Bar value={m.green_mean} good />
                  </dd>
                  <dt>{t("metrics.air")}</dt>
                  <dd>{m.air_index == null ? nd : (m.air_index * 100).toFixed(0)}</dd>
                  <dt>{t("metrics.exposure")}</dt>
                  <dd>
                    {m.exposure_index == null ? nd : m.exposure_index.toFixed(0)}
                    <Bar value={m.exposure_index == null ? null : m.exposure_index / 100} good={false} />
                  </dd>
                  <dt>{t("metrics.fountains")}</dt>
                  <dd>{m.fountains_near}</dd>
                  {m.cycle_separated != null && (
                    <>
                      <dt>{t(`metrics.separated_${mode}`)}</dt>
                      <dd>
                        {fmtPct(m.cycle_separated)} % <Bar value={m.cycle_separated} good />
                      </dd>
                    </>
                  )}
                  {mode === "bike" && m.cycle_on_street != null && (
                    <>
                      <dt>{t("metrics.on_street")}</dt>
                      <dd>{fmtPct(m.cycle_on_street)} %</dd>
                    </>
                  )}
                </dl>
                {r.limited_by_detour && <p className="note">{t("metrics.limited")}</p>}
              </>
            )}
          </div>
        );
      })}
    </div>
    {sel && (
      <Export
        route={sel}
        fastest={routes.find((r) => r.kind === "fastest")}
        mode={mode}
        names={names}
      />
    )}
    </>
  );
}
