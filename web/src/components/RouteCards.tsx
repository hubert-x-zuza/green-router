import type { KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import type { Mode, Route, RouteKind, RouteMetrics, Tradeoff } from "../api";
import { downloadGpx, googleMapsUrl, shareGpx } from "../export";
import { btnClass, Button, Icon, Meter } from "./ui";

interface Props {
  routes: Route[];
  selected: RouteKind;
  onSelect: (k: RouteKind) => void;
  mode: Mode;
  names: [string, string];
  onNavigate: () => void;
}

const fmtPct = (v: number | null) => (v == null ? null : Math.round(v * 100));
const sign = (v: number) => (v > 0 ? "+" : v < 0 ? "−" : "±");

/** One-line trade-off against the fastest route: the extra minutes first, then the gains. */
function tradeoffParts(tr: Tradeoff, t: (k: string, o?: Record<string, unknown>) => string): string[] {
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
  return parts;
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

interface TileSpec {
  key: string;
  value: string | null;
  /** difference to the fastest route, already formatted, and whether lower is better */
  delta?: { diff: number; text: string; lowerIsBetter: boolean } | null;
  meter?: { value: number | null; tone: "good" | "bad" };
}

function delta(
  cur: number | null,
  ref: number | null | undefined,
  fmt: (d: number) => string,
  lowerIsBetter: boolean,
  eps = 0.5,
): TileSpec["delta"] {
  if (cur == null || ref == null) return null;
  const d = cur - ref;
  if (Math.abs(d) < eps) return { diff: 0, text: "±0", lowerIsBetter };
  return { diff: d, text: `${sign(d)}${fmt(Math.abs(d))}`, lowerIsBetter };
}

function tiles(m: RouteMetrics, ref: RouteMetrics | null, mode: Mode, t: (k: string) => string): TileSpec[] {
  const pct = (v: number | null) => (v == null ? null : `${fmtPct(v)} %`);
  const out: TileSpec[] = [
    {
      key: t("metrics.noise"),
      value: m.noise_mean_db == null ? null : `${m.noise_mean_db.toFixed(0)} dB`,
      delta: ref && delta(m.noise_mean_db, ref.noise_mean_db, (d) => `${d.toFixed(0)} dB`, true),
    },
    {
      key: t("metrics.loud"),
      value: pct(m.share_loud),
      delta: ref && delta(m.share_loud, ref.share_loud, (d) => `${Math.round(d * 100)} pp`, true, 0.005),
      meter: { value: m.share_loud, tone: "bad" },
    },
    {
      key: t("metrics.green"),
      value: pct(m.green_mean),
      delta: ref && delta(m.green_mean, ref.green_mean, (d) => `${Math.round(d * 100)} pp`, false, 0.005),
      meter: { value: m.green_mean, tone: "good" },
    },
    {
      key: t("metrics.exposure"),
      value: m.exposure_index == null ? null : m.exposure_index.toFixed(0),
      delta: ref && delta(m.exposure_index, ref.exposure_index, (d) => d.toFixed(0), true),
      meter: { value: m.exposure_index == null ? null : m.exposure_index / 100, tone: "bad" },
    },
    {
      key: t("metrics.air"),
      value: m.air_index == null ? null : (m.air_index * 100).toFixed(0),
      delta:
        ref &&
        delta(
          m.air_index == null ? null : m.air_index * 100,
          ref.air_index == null ? null : ref.air_index * 100,
          (d) => d.toFixed(0),
          true,
        ),
    },
    { key: t("metrics.fountains"), value: String(m.fountains_near) },
  ];
  if (m.cycle_separated != null)
    out.push({
      key: t(`metrics.separated_${mode}`),
      value: pct(m.cycle_separated),
      meter: { value: m.cycle_separated, tone: "good" },
    });
  if (mode === "bike" && m.cycle_on_street != null) out.push({ key: t("metrics.on_street"), value: pct(m.cycle_on_street) });
  return out;
}

function Export({
  route,
  fastest,
  mode,
  names,
  onNavigate,
}: {
  route: Route;
  fastest: Route | undefined;
  mode: Mode;
  names: [string, string];
  onNavigate: () => void;
}) {
  const { t } = useTranslation();
  const title = `${names[0]} → ${names[1]} (${t(`kinds.${route.kind}`)})`;
  return (
    <div className="group">
      <div className="actions">
        {"geolocation" in navigator && (
          <Button variant="primary" icon="nav" onClick={onNavigate}>
            {t("export.navigate")}
          </Button>
        )}
        <a
          className={btnClass("secondary", "sm")}
          href={googleMapsUrl(route, mode, fastest)}
          target="_blank"
          rel="noopener noreferrer"
        >
          <Icon name="external" size={16} />
          {t("export.googleShort")}
        </a>
        <Button size="sm" icon="download" onClick={() => downloadGpx(route, title)}>
          {t("export.gpx")}
        </Button>
        {canShareFiles() && (
          <Button size="sm" icon="share" onClick={() => void shareGpx(route, title)} style={{ gridColumn: "1 / -1" }}>
            {t("export.share")}
          </Button>
        )}
      </div>
      <details className="hint-toggle">
        <summary>
          <Icon name="chevron" size={14} />
          {t("export.how")}
        </summary>
        <p>{t("export.hint")}</p>
      </details>
    </div>
  );
}

export default function RouteCards({ routes, selected, onSelect, mode, names, onNavigate }: Props) {
  const { t } = useTranslation();
  const distinct = routes.filter((r) => !r.same_as);
  const dupes = routes.filter((r) => r.same_as);
  const sel = distinct.find((r) => r.kind === selected) ?? distinct[0];
  const fastest = routes.find((r) => r.kind === "fastest");
  const ref = sel && sel.kind !== "fastest" && fastest ? fastest.metrics : null;

  const select = (k: RouteKind) => onSelect(k);
  const onKey = (e: KeyboardEvent, i: number) => {
    const n = distinct.length;
    let j = -1;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") j = (i + 1) % n;
    if (e.key === "ArrowUp" || e.key === "ArrowLeft") j = (i - 1 + n) % n;
    if (j < 0) return;
    e.preventDefault();
    select(distinct[j].kind);
    (e.currentTarget.parentElement?.children[j] as HTMLElement | undefined)?.focus();
  };

  return (
    <>
      <div className="options" role="radiogroup" aria-label={t("metrics.show")}>
        {distinct.map((r, i) => {
          const isSel = r.kind === sel?.kind;
          const m = r.metrics;
          const parts = r.tradeoff ? tradeoffParts(r.tradeoff, t) : [];
          return (
            <button
              key={r.kind}
              type="button"
              role="radio"
              aria-checked={isSel}
              tabIndex={isSel ? 0 : -1}
              className={`option option-${r.kind}`}
              onClick={() => select(r.kind)}
              onKeyDown={(e) => onKey(e, i)}
            >
              <span className="stripe" aria-hidden="true" />
              <span>
                <span className="name">
                  {t(`kinds.${r.kind}`)}
                  {r.kind !== "fastest" && r.profile !== r.kind && (
                    <span className="tag">{t(`profiles.${r.profile}`)}</span>
                  )}
                  {r.limited_by_detour && <span className="tag tag-warn">{t("metrics.limitedShort")}</span>}
                </span>
                <span className="sub">
                  {r.kind === "fastest" ? (
                    t("metrics.reference")
                  ) : parts.length ? (
                    <>
                      <span className="part">{parts[0]}</span>
                      {parts.slice(1).map((x) => (
                        <span key={x} className="part gain">
                          · {x}
                        </span>
                      ))}
                    </>
                  ) : null}
                </span>
              </span>
              <span className="time">
                <b>{t("metrics.time", { min: Math.round(m.duration_min) })}</b>
                <span>{t("metrics.distance", { km: (m.distance_m / 1000).toFixed(1) })}</span>
              </span>
            </button>
          );
        })}
      </div>
      {dupes.map((r) => (
        <p key={r.kind} className="same-note">
          {r.same_as === "fastest" && r.kind === "healthiest"
            ? t("metrics.sameAsFastest")
            : t("metrics.sameAsNamed", { kind: t(`kinds.${r.kind}`), other: t(`kinds.${r.same_as}`) })}
        </p>
      ))}

      {sel && (
        <div className="details">
          <div className="details-head">
            <h3>{t("metrics.detailsOf")}: {t(`kinds.${sel.kind}`)}</h3>
            {ref && <span>{t("metrics.vsFastest")}</span>}
          </div>
          <ul className="mlist">
            {tiles(sel.metrics, ref, mode, t).map((x) => {
              const d = x.delta;
              const cls = !d || d.diff === 0 ? "d" : (d.diff < 0) === d.lowerIsBetter ? "d better" : "d worse";
              return (
                <li key={x.key} className="mrow">
                  <span className="k">{x.key}</span>
                  <span className="m">{x.meter && <Meter value={x.meter.value} tone={x.meter.tone} />}</span>
                  <span className={x.value == null ? "v nd" : "v"}>{x.value ?? t("metrics.noData")}</span>
                  {ref && <span className={cls}>{d?.text ?? ""}</span>}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {sel && <Export route={sel} fastest={fastest} mode={mode} names={names} onNavigate={onNavigate} />}
    </>
  );
}
