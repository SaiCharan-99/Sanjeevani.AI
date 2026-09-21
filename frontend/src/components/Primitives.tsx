/**
 * One component per wireframe CSS class (CLAUDE.md "UI-first workflow").
 * Grouped in a single file for Phase 1 velocity — see progress.md > Decisions log
 * for this deviation. All are dumb/presentational; screens compose them.
 * Tokens come from tailwind.config.js, mapped 1:1 from the wireframe's :root vars.
 */
import type { ReactNode } from "react";

export function Top({ children }: { children: ReactNode }) {
  return <div className="flex items-center justify-between mb-4">{children}</div>;
}

export function Title({ children }: { children: ReactNode }) {
  return <h2 className="text-[26px] font-bold tracking-tight leading-tight mb-1.5">{children}</h2>;
}

export function Sub({ children }: { children: ReactNode }) {
  return <p className="text-sm text-text-2 mb-5">{children}</p>;
}

type TagVariant = "accent" | "warn" | "bad" | "mute";
const tagVariantClasses: Record<TagVariant, string> = {
  accent: "bg-accent-soft text-accent",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  mute: "bg-surface-2 text-text-2",
};
export function Tag({ variant = "mute", children }: { variant?: TagVariant; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1.5 h-7 px-3 rounded-full font-semibold text-[11px] tracking-wider uppercase ${tagVariantClasses[variant]}`}>
      {children}
    </span>
  );
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`bg-surface border border-line-soft rounded-r-lg p-4.5 mb-3.5 ${className}`}>{children}</div>;
}

export function Sec({ title, right }: { title: string; right?: ReactNode }) {
  return (
    <div className="flex items-center justify-between my-5 mb-3">
      <h3 className="text-[17px] font-semibold">{title}</h3>
      {right && <span className="text-xs text-text-3">{right}</span>}
    </div>
  );
}

export function ListShell({ children }: { children: ReactNode }) {
  return <div className="bg-surface border border-line-soft rounded-r-lg overflow-hidden mb-3.5">{children}</div>;
}

export function Item({ children }: { children: ReactNode }) {
  return <div className="flex items-center gap-3.5 px-4 py-3.5 border-b border-line-soft last:border-none">{children}</div>;
}

export function Avatar({ initials, tone = "accent" }: { initials: string; tone?: "accent" | "bad" }) {
  const cls = tone === "bad" ? "bg-bad-soft text-bad" : "bg-accent-soft text-accent";
  return <div className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold text-[13px] flex-shrink-0 ${cls}`}>{initials}</div>;
}

export function Meta({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="flex-1 min-w-0">
      <b className="block text-[15px] font-semibold">{title}</b>
      {subtitle && <span className="text-[12.5px] text-text-3">{subtitle}</span>}
    </div>
  );
}

export function Kv({ left, right }: { left: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex justify-between items-baseline gap-3">
      <div>{left}</div>
      {right && <div className="text-right">{right}</div>}
    </div>
  );
}

export function Pill({ children }: { children: ReactNode }) {
  return <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface-2 text-text-2 font-semibold text-xs">{children}</span>;
}

export function PillRow({ children }: { children: ReactNode }) {
  return <div className="flex gap-2 flex-wrap mt-3">{children}</div>;
}

export function Seg({ label, active, onClick }: { label: string; active?: boolean; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 h-14 rounded-r border font-semibold text-[15px] transition-colors ${
        active ? "bg-accent border-accent text-accent-ink" : "bg-surface border-line text-text hover:border-accent-dim"
      }`}
    >
      {label}
    </button>
  );
}

export function Field(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={`w-full h-14 rounded-r border border-line bg-surface text-text px-4 outline-none focus:border-accent ${props.className ?? ""}`} />;
}

export function Cta({ children, ghost, disabled, onClick }: { children: ReactNode; ghost?: boolean; disabled?: boolean; onClick?: () => void }) {
  return (
    <button
      disabled={disabled}
      onClick={onClick}
      className={`w-full h-[58px] rounded-r font-bold text-base flex items-center justify-center gap-2.5 mt-6 disabled:opacity-40 disabled:cursor-not-allowed ${
        ghost ? "bg-transparent border border-line text-text" : "bg-accent text-accent-ink"
      }`}
    >
      {children}
    </button>
  );
}

export function IconBtn({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return (
    <button onClick={onClick} className="w-10 h-10 rounded-full border border-line bg-surface text-text-2 flex items-center justify-center">
      {children}
    </button>
  );
}

export function Stat({ label, value, tone = "text" }: { label: string; value: ReactNode; tone?: "text" | "warn" | "bad" }) {
  const toneCls = tone === "warn" ? "text-warn" : tone === "bad" ? "text-bad" : "text-text";
  return (
    <div className="bg-surface border border-line-soft rounded-r p-3.5">
      <span className="block text-xs text-text-3 mb-1.5">{label}</span>
      <b className={`text-[26px] font-bold tracking-tight ${toneCls}`}>{value}</b>
    </div>
  );
}

export function StatRow({ children }: { children: ReactNode }) {
  return <div className="grid grid-cols-3 gap-2.5 mb-4.5">{children}</div>;
}

export function Bar({ pct, color = "bg-accent" }: { pct: number; color?: string }) {
  return (
    <div className="h-2 rounded-full bg-surface-2 overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Big({ children, color = "" }: { children: ReactNode; color?: string }) {
  return <span className={`text-[30px] font-bold tracking-tight leading-none ${color}`}>{children}</span>;
}

export function Unit({ children }: { children: ReactNode }) {
  return <span className="text-[13px] text-text-3 font-medium">{children}</span>;
}

type NoteTone = "info" | "warn" | "bad";
const noteToneClasses: Record<NoteTone, string> = {
  info: "bg-accent-soft text-text",
  warn: "bg-warn-soft text-text",
  bad: "bg-bad-soft text-text",
};
export function Note({ tone = "info", title, children }: { tone?: NoteTone; title?: string; children: ReactNode }) {
  return (
    <div className={`flex gap-3 items-start rounded-r p-3.5 text-[13px] leading-relaxed mb-3.5 ${noteToneClasses[tone]}`}>
      <div>
        {title && <b className="block mb-0.5 text-[13.5px]">{title}</b>}
        {children}
      </div>
    </div>
  );
}

export function Quote({ text, sub }: { text: string; sub?: string }) {
  return (
    <div className="bg-bg-2 border-l-2 border-accent-dim rounded-[10px] px-3 py-2.5 text-[13.5px] text-text-2 italic mt-2.5">
      {text}
      {sub && <em className="block not-italic text-xs text-text-3 mt-1">{sub}</em>}
    </div>
  );
}

export function FootNote({ children }: { children: ReactNode }) {
  return <div className="flex items-center justify-center gap-1.5 text-xs text-text-3 mt-3">{children}</div>;
}

export function RingWrap({ children }: { children: ReactNode }) {
  return <div className="flex flex-col items-center py-2 pb-5">{children}</div>;
}

export function Camera({ children }: { children: ReactNode }) {
  return (
    <div
      className="relative rounded-r-lg overflow-hidden border border-line p-5 min-h-[520px] flex flex-col justify-between"
      style={{ background: "radial-gradient(circle at 50% 38%, #1B2A25 0%, #0D1412 72%, #080C0B 100%)" }}
    >
      {children}
    </div>
  );
}

export function Tabs({ tabs, active, onChange }: { tabs: string[]; active: number; onChange: (i: number) => void }) {
  return (
    <div className="flex gap-2 overflow-x-auto mb-4">
      {tabs.map((t, i) => (
        <button
          key={t}
          onClick={() => onChange(i)}
          className={`flex-none h-10 px-4 rounded-full border font-semibold text-sm ${
            i === active ? "bg-accent border-accent text-accent-ink" : "bg-surface border-line text-text-2"
          }`}
        >
          {t}
        </button>
      ))}
    </div>
  );
}

export function Turn({ who, time, children, indent }: { who: string; time: string; children: ReactNode; indent?: boolean }) {
  return (
    <div className={`mb-3.5 ${indent ? "pl-6" : ""}`}>
      <div className="flex justify-between font-semibold text-xs text-text-3 mb-1.5 px-1">
        <b className="text-accent font-semibold">{who}</b>
        <span>{time}</span>
      </div>
      <Bubble>{children}</Bubble>
    </div>
  );
}

export function Who({ children }: { children: ReactNode }) {
  return <div className="font-semibold text-xs text-text-3">{children}</div>;
}

export function Bubble({ children }: { children: ReactNode }) {
  return <div className="bg-surface border border-line-soft rounded-r p-3.5">{children}</div>;
}

export function ChipPill({ children, tone = "accent" }: { children: ReactNode; tone?: "accent" | "warn" }) {
  const cls = tone === "warn" ? "bg-warn-soft text-warn" : "bg-accent-soft text-accent";
  return <div className={`inline-flex items-center gap-2 h-10 px-4.5 rounded-full font-semibold text-sm ${cls}`}>{children}</div>;
}

export function Wave({ levels }: { levels?: number[] }) {
  /** `levels` are live mic RMS values in [0,1] from capture/audio.ts. Without
   * them the bars fall back to the wireframe's static pattern. */
  const bars = levels ?? Array.from({ length: 24 }, (_, i) => (20 + ((i * 37) % 60)) / 100);
  return (
    <div className="flex items-center justify-center gap-[3px] h-14 my-5">
      {bars.map((level, i) => (
        <i
          key={i}
          className="w-1 rounded-full bg-accent opacity-85 transition-[height] duration-100"
          style={{ height: `${Math.max(8, Math.min(100, level * 100))}%` }}
        />
      ))}
    </div>
  );
}

export type ConfidenceBand = "high" | "medium" | "low";

export function confidenceBand(confidence: number): ConfidenceBand {
  if (confidence >= 0.85) return "high";
  if (confidence >= 0.6) return "medium";
  return "low";
}

const confidenceDotClasses: Record<ConfidenceBand, string> = {
  high: "bg-accent",
  medium: "bg-warn",
  low: "bg-bad",
};
const confidenceTextClasses: Record<ConfidenceBand, string> = {
  high: "text-accent",
  medium: "text-warn",
  low: "text-bad",
};

export function ConfidenceDot({ confidence }: { confidence: number }) {
  /** Colour by confidence band (specs.md §2 screen 8). Extraction confidence —
   * never a clinical certainty. */
  const band = confidenceBand(confidence);
  const label = band === "high" ? "High" : band === "medium" ? "Medium" : "Low";
  return (
    <p className={`text-[13px] flex items-center gap-1.5 ${confidenceTextClasses[band]}`}>
      <span className={`w-2 h-2 rounded-full ${confidenceDotClasses[band]}`} />
      {label} confidence ({Math.round(confidence * 100)}%)
    </p>
  );
}

export function GreyedOverlay({ children }: { children: ReactNode }) {
  /** Wraps a screen in the Phase-1 "not yet implemented" affordance
   * (CLAUDE.md "UI-first workflow" point 3). Real layout/copy still renders
   * underneath, greyed and non-interactive. */
  return (
    <div className="relative">
      <div className="pointer-events-none opacity-40 grayscale-[.3]">{children}</div>
      <div className="absolute top-2 right-2">
        <Tag variant="mute">Not yet implemented</Tag>
      </div>
    </div>
  );
}
