import { useTranslation } from "react-i18next";
import { api, type District, type HotspotProps } from "../api";

interface Props {
  hotspots: HotspotProps[];
  districts: District[];
  district: number | undefined;
  setDistrict: (d: number | undefined) => void;
  onFocus: (h: HotspotProps) => void;
  selected: HotspotProps | null;
}

export function HotspotText({ h }: { h: HotspotProps }) {
  const { t } = useTranslation();
  return (
    <>
      <span>
        {t("planner.explain", {
          noise: h.noise_db.toFixed(0),
          green: Math.round(h.green * 100),
          traffic: Math.round(h.traffic * 100),
        })}
      </span>
      <br />
      <span className="muted">
        {t("planner.who", { schools: h.schools, pupils: h.pupils, kg: h.kindergartens, nur: h.nurseries })}
      </span>
    </>
  );
}

export default function PlannerPanel(p: Props) {
  const { t, i18n } = useTranslation();
  const nf = new Intl.NumberFormat(i18n.language);
  const top = p.hotspots.slice(0, 20);
  return (
    <div className="panel-body">
      <p className="hint">{t("planner.intro")}</p>
      <div className="row">
        <label className="select">
          {t("planner.district")}
          <select
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
        <a className="button" href={api.exportUrl(p.district)} download>
          {t("planner.export")}
        </a>
      </div>

      <h2>{t("planner.top")}</h2>
      <ol className="hotspots">
        {top.map((h) => (
          <li key={h.rank} className={p.selected?.rank === h.rank ? "selected" : undefined}>
            <button type="button" onClick={() => p.onFocus(h)}>
              <strong>
                {t("planner.rank", { rank: h.rank })} {h.street ?? "–"}
              </strong>{" "}
              <span className="muted">
                · {h.district} · {t("planner.priority", { value: h.priority.toFixed(2) })}
              </span>
              <br />
              <HotspotText h={h} />
            </button>
          </li>
        ))}
      </ol>

      <h2>{t("planner.districts")}</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">{t("planner.district")}</th>
              <th scope="col">{t("planner.pop")}</th>
              <th scope="col">{t("planner.kids")}</th>
              <th scope="col">{t("planner.seniors")}</th>
              <th scope="col">{t("planner.sites")}</th>
              <th scope="col">{t("planner.noiseMean")}</th>
              <th scope="col">{t("planner.loudShare")}</th>
              <th scope="col">{t("planner.hotspots")}</th>
            </tr>
          </thead>
          <tbody>
            {p.districts.map((d) => (
              <tr key={d.district_id} className={p.district === d.district_id ? "selected" : undefined}>
                <th scope="row">
                  {d.number}. {d.name}
                </th>
                <td>{nf.format(d.population)}</td>
                <td>{nf.format(d.children_0_14)}</td>
                <td>{nf.format(d.seniors_65)}</td>
                <td>{d.sensitive_sites}</td>
                <td>{d.noise_mean_db?.toFixed(0) ?? "–"} dB</td>
                <td>{d.share_loud_cells == null ? "–" : `${Math.round(d.share_loud_cells * 100)} %`}</td>
                <td>{d.hotspots_top100}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">{t("planner.method")}</p>
    </div>
  );
}
