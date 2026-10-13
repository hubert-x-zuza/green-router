import { useTranslation } from "react-i18next";
import type { Route, RouteKind, Tradeoff } from "../api";

interface Props {
  routes: Route[];
  selected: RouteKind;
  onSelect: (k: RouteKind) => void;
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

export default function RouteCards({ routes, selected, onSelect }: Props) {
  const { t } = useTranslation();
  return (
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
              {r.kind !== "fastest" && <span className="muted"> · {t(`profiles.${r.profile}`)}</span>}
            </div>
            {r.same_as ? (
              <p className="muted">{t("metrics.sameAs", { kind: t(`kinds.${r.same_as}`) })}</p>
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
                </dl>
                {r.limited_by_detour && <p className="note">{t("metrics.limited")}</p>}
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}
