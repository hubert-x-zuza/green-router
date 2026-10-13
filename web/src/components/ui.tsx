// Small shared UI primitives. Icons are simple strokes drawn for this project (24×24 grid).
import type { ButtonHTMLAttributes, ReactNode } from "react";

const PATHS = {
  swap: "M7 4v16M7 4 3.5 7.5M7 4l3.5 3.5M17 20V4m0 16-3.5-3.5M17 20l3.5-3.5",
  locate: "M12 3v3m0 12v3M3 12h3m12 0h3M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10Zm0-3a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  x: "M6 6l12 12M18 6 6 18",
  walk: "M13 4.5a1.5 1.5 0 1 0 0-.01M10 21l2-6 3 3v3m-5-12 3-1 3 3 3 1M12 9l-1 5",
  bike: "M5.5 18a3.5 3.5 0 1 0 0-.01M18.5 18a3.5 3.5 0 1 0 0-.01M5.5 17.5 9 10h6l3.5 7.5M9 10 12 17.5h1M14 6h2l1 4",
  layers: "M12 3 3 8l9 5 9-5-9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5",
  info: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm0-5v-5m0-3v.01",
  chevron: "m9 6 6 6-6 6",
  down: "m6 9 6 6 6-6",
  download: "M12 4v11m0 0-4-4m4 4 4-4M5 19h14",
  nav: "M4 11 20 4l-7 16-2-7-7-2Z",
  external: "M14 4h6v6m0-6-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  share: "M12 15V3m0 0L8 7m4-4 4 4M5 12v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Zm-9-9h18M12 3c2.5 2.6 3.5 5.6 3.5 9s-1 6.4-3.5 9c-2.5-2.6-3.5-5.6-3.5-9s1-6.4 3.5-9Z",
  route: "M6 19a2 2 0 1 0 0-.01M18 5a2 2 0 1 0 0-.01M6 17V9a3 3 0 0 1 3-3h1m8 1v8a3 3 0 0 1-3 3h-1",
  chart: "M4 20h16M7 16v-5m5 5V7m5 9v-8",
  sliders: "M4 7h10m4 0h2M4 17h4m4 0h8M16 5v4M10 15v4",
  alert: "M12 9v4m0 4v.01M10.3 4.3 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0Z",
  pin: "M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21Zm0-9a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={className ? `icon ${className}` : "icon"}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

type Variant = "primary" | "secondary" | "ghost";
type Size = "md" | "sm";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: IconName;
  block?: boolean;
}

export function btnClass(variant: Variant = "secondary", size: Size = "md", block = false, extra?: string): string {
  return ["btn", `btn-${variant}`, size === "sm" && "btn-sm", block && "btn-block", extra].filter(Boolean).join(" ");
}

export function Button({ variant = "secondary", size = "md", icon, block, className, children, type, ...rest }: ButtonProps) {
  return (
    <button type={type ?? "button"} className={btnClass(variant, size, block, className)} {...rest}>
      {icon && <Icon name={icon} size={size === "sm" ? 16 : 18} />}
      {children}
    </button>
  );
}

/** Square icon-only button; `label` is the accessible name and tooltip. */
export function IconButton({
  icon,
  label,
  className,
  ...rest
}: { icon: IconName; label: string } & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button type="button" className={className ? `icon-btn ${className}` : "icon-btn"} aria-label={label} title={label} {...rest}>
      <Icon name={icon} />
    </button>
  );
}

/** Radio group rendered as a segmented control (native radios keep keyboard behaviour). */
export function Segmented<T extends string>({
  name,
  legend,
  value,
  options,
  onChange,
}: {
  name: string;
  legend: string;
  value: T;
  options: { value: T; label: string; icon?: IconName }[];
  onChange: (v: T) => void;
}) {
  return (
    <fieldset className="segmented">
      <legend className="sr-only">{legend}</legend>
      {options.map((o) => (
        <label key={o.value} className={value === o.value ? "on" : undefined}>
          <input type="radio" name={name} checked={value === o.value} onChange={() => onChange(o.value)} />
          {o.icon && <Icon name={o.icon} size={16} />}
          {o.label}
        </label>
      ))}
    </fieldset>
  );
}

export function Callout({
  tone,
  children,
  role,
}: {
  tone: "warn" | "danger" | "info";
  children: ReactNode;
  role?: "alert" | "status";
}) {
  return (
    <div className={`callout callout-${tone}`} role={role}>
      <Icon name={tone === "info" ? "info" : "alert"} size={16} />
      <div>{children}</div>
    </div>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <span className="spinner-wrap" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      {label}
    </span>
  );
}

/** Horizontal 0..1 gauge used for metrics and priorities. */
export function Meter({ value, tone }: { value: number | null; tone: "good" | "bad" | "neutral" }) {
  if (value == null) return null;
  const v = Math.max(0, Math.min(1, value));
  return (
    <span className="meter" aria-hidden="true">
      <span className={`meter-fill meter-${tone}`} style={{ width: `${v * 100}%` }} />
    </span>
  );
}
