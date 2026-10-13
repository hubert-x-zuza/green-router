import { useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type District, type HotspotProps } from "../api";
import { btnClass, Icon, Meter, Spinner } from "./ui";

interface Props {
  hotspots: HotspotProps[];
  loading: boolean;
  districts: District[];
  district: number | undefined;
  setDistrict: (d: number | undefined) => void;
  onFocus: (h: HotspotProps) => void;
  selected: HotspotProps | null;
}

/** Exposure facts as compact chips. */
export function HotspotFacts({ h }: { h: HotspotProps }) {
  const { t } = useTranslation();
  return (
    <span className="facts">
      <span className="fact">{t("planner.factNoise", { v: h.noise_db.toFixed(0) })}</span>
      <span className="fact">{t("planner.factGreen", { v: Math.round(h.green * 100) })}</span>
      <span className="fact">{t("planner.factTraffic", { v: Math.round(h.traffic * 100) })}</span>
    </span>
  );
}

export function HotspotWho({ h }: { h: HotspotProps }) {
  const { t } = useTranslation();
  return (
    <span className="who">
      {t("planner.who", { schools: h.schools, pupils: h.pupils, kg: h.kindergartens, nur: h.nurseries })}
    </span>
  );
}

type SortKey = keyof Pick<
  District,
  "number" | "population" | "children_0_14" | "seniors_65" | "sensitive_sites" | "noise_mean_db" | "share_loud_cells" | "hotspots_top100"
>;

export default function PlannerPanel(p: Props) {
  const { t, i18n } = useTranslation();
  const nf = new Intl.NumberFormat(i18n.language);
  const top = p.hotspots.slice(0, 20);
  // null keeps the server order (priority sum)
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean } | null>(null);

  const rows = !sort
    ? p.districts
    : [...p.districts].sort((a, b) => {
    const k = sort.key;
    const va = k === "number" ? a.district_id : (a[k] ?? -Infinity);
    const vb = k === "number" ? b.district_id : (b[k] ?? -Infinity);
    return (va < vb ? -1 : va > vb ? 1 : 0) * (sort.desc ? -1 : 1);
  });
  const cols: [SortKey, string][] = [
    ["number", t("planner.district")],
    ["population", t("planner.pop")],
    ["children_0_14", t("planner.kids")],
    ["seniors_65", t("planner.seniors")],
    ["sensitive_sites", t("planner.sites")],
    ["noise_mean_db", t("planner.noiseMean")],
    ["share_loud_cells", t("planner.loudShare")],
    ["hotspots_top100", t("planner.hotspots")],
  ];

  return (
    <div className="panel-body">
      <p className="intro">{t("planner.intro")}</p>
      <div className="toolbar">
        <label className="grow">
          <span className="field-label">{t("planner.district")}</span>
          <select
            className="select-input"
            value={p.district ?? ""}
            onChange={(e) => p.setDistrict(e.target.value ? Number(e.target.value) : undefined)}
          >
            <option value="">{t("planner.all")}</option>
            {[...p.districts]
              .sort((a, b) => a.district_id - b.district_id)
              .map((d) => (
                <option key={d.district_id} value={d.district_id}>
                  {d.number}. {d.name}
                </option>
              ))}
          </select>
        </label>
        <a className={btnClass("secondary")} href={api.exportUrl(p.district)} download>
          <Icon name="download" size={16} />
          {t("planner.export")}
        </a>
      </div>

      <section className="group" aria-labelledby="top-title">
        <div className="section-head">
          <h2 id="top-title">{t("planner.top")}</h2>
          {p.loading ? <Spinner label={t("planner.loading")} /> : <span>{t("planner.showing", { n: top.length })}</span>}
        </div>
        {!p.loading && top.length === 0 && <p className="same-note">{t("planner.none")}</p>}
        <ol className="hotspots">
          {top.map((h) => (
            <li key={h.rank}>
              <button
                type="button"
                className="hotspot"
                aria-current={p.selected?.rank === h.rank ? "true" : undefined}
                onClick={() => p.onFocus(h)}
              >
                <span className="rank">{h.rank}</span>
                <span className="hotspot-title">
                  <strong>{h.street ?? "–"}</strong>
                  <span>{h.district}</span>
                </span>
                <span className="prio" title={t("planner.priority", { value: h.priority.toFixed(2) })}>
                  <Meter value={h.priority} tone="bad" />
                  <span className="num">{h.priority.toFixed(2)}</span>
                </span>
                <span>
                  <HotspotFacts h={h} />
                </span>
                <span style={{ gridColumn: 2 }}>
                  <HotspotWho h={h} />
                </span>
              </button>
            </li>
          ))}
        </ol>
      </section>

      <section className="group" aria-labelledby="districts-title">
        <div className="section-head">
          <h2 id="districts-title">{t("planner.districts")}</h2>
          <span>{t("planner.sortHint")}</span>
        </div>
        <div className="table-wrap" tabIndex={0} role="region" aria-labelledby="districts-title">
          <table>
            <thead>
              <tr>
                {cols.map(([k, label]) => (
                  <th
                    key={k}
                    scope="col"
                    aria-sort={sort?.key === k ? (sort.desc ? "descending" : "ascending") : undefined}
                  >
                    <button
                      type="button"
                      onClick={() => setSort((s) => ({ key: k, desc: s?.key === k ? !s.desc : k !== "number" }))}
                    >
                      {label}
                      {sort?.key === k && <span aria-hidden="true">{sort.desc ? "↓" : "↑"}</span>}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((d) => (
                <tr key={d.district_id} className={p.district === d.district_id ? "selected" : undefined}>
                  <th scope="row">
                    {d.number}. {d.name}
                  </th>
                  <td>{nf.format(d.population)}</td>
                  <td>{nf.format(d.children_0_14)}</td>
                  <td>{nf.format(d.seniors_65)}</td>
                  <td>{d.sensitive_sites}</td>
                  <td>{d.noise_mean_db == null ? "–" : `${d.noise_mean_db.toFixed(0)} dB`}</td>
                  <td>{d.share_loud_cells == null ? "–" : `${Math.round(d.share_loud_cells * 100)} %`}</td>
                  <td>{d.hotspots_top100}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <p className="method">{t("planner.method")}</p>
    </div>
  );
}
