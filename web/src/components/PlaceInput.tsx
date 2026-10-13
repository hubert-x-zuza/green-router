import { useEffect, useId, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type Place } from "../api";

interface Props {
  label: string;
  placeholder: string;
  variant: "from" | "to";
  value: string;
  onChange: (text: string) => void;
  onPick: (p: Place) => void;
}

/** Address search with a keyboard-accessible suggestion list (ARIA combobox pattern). */
export default function PlaceInput({ label, placeholder, variant, value, onChange, onPick }: Props) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const [items, setItems] = useState<Place[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const typed = useRef(false);

  useEffect(() => {
    if (!typed.current || value.trim().length < 2) {
      setItems([]);
      return;
    }
    const h = setTimeout(() => {
      api
        .geocode(value)
        .then((r) => {
          setItems(r);
          setOpen(true);
          setActive(r.length ? 0 : -1);
        })
        .catch(() => setItems([]));
    }, 200);
    return () => clearTimeout(h);
  }, [value]);

  const pick = (p: Place) => {
    typed.current = false;
    onPick(p);
    setOpen(false);
  };

  return (
    <div className={`place ${variant}`}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        className="input"
        type="search"
        role="combobox"
        aria-expanded={open && items.length > 0}
        aria-controls={`${id}-list`}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${id}-opt-${active}` : undefined}
        autoComplete="off"
        placeholder={placeholder}
        value={value}
        onChange={(e) => {
          typed.current = true;
          onChange(e.target.value);
        }}
        onFocus={() => items.length && setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (!open || !items.length) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((a) => (a + 1) % items.length);
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((a) => (a - 1 + items.length) % items.length);
          } else if (e.key === "Enter" && active >= 0) {
            e.preventDefault();
            pick(items[active]);
          } else if (e.key === "Escape") {
            setOpen(false);
          }
        }}
      />
      {open && (
        <ul id={`${id}-list`} role="listbox" className="suggest">
          {items.length === 0 && <li className="empty">{t("route.noResults")}</li>}
          {items.map((p, i) => (
            <li
              key={`${p.label}-${i}`}
              id={`${id}-opt-${i}`}
              role="option"
              aria-selected={i === active}
              onMouseDown={(e) => {
                e.preventDefault();
                pick(p);
              }}
            >
              <span>{p.label}</span>
              {p.kind === "poi" && <span className="cat">{i18n.language === "en" ? p.category_en : p.category_pl}</span>}
              {p.district && <span className="where">{p.district.replace("Dzielnica ", "")}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
