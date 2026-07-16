"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import {
  Clock,
  LayoutDashboard,
  ShieldCheck,
  MessageSquareText,
  GanttChartSquare,
  Share2,
  Settings,
  Truck,
  ThermometerSun,
} from "lucide-react";
import {
  API_URL,
  advanceClock,
  getClockState,
  getHealth,
  projectLabel,
  resetClock,
  type ClockState,
  type HealthState,
} from "@/lib/api";
import { cn } from "@/components/ui/primitives";

function useHealth() {
  const [health, setHealth] = useState<HealthState | null>(null);
  const [live, setLive] = useState(false);
  useEffect(() => {
    let cancelled = false;
    getHealth().then(({ data, live }) => {
      if (!cancelled) {
        setHealth(data);
        setLive(live);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return { health, live };
}

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/compliance", label: "Compliance", icon: ShieldCheck },
  { href: "/copilot", label: "Copilot", icon: MessageSquareText },
  { href: "/schedule", label: "Schedule", icon: GanttChartSquare },
  { href: "/supply-chain", label: "Supply Chain", icon: Truck },
  { href: "/commissioning", label: "Commissioning QA", icon: ThermometerSun },
  { href: "/graph", label: "Knowledge Graph", icon: Share2 },
];

function Brand() {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-4 py-5">
      <span
        className="grid h-7 w-7 place-items-center rounded text-[1.1rem] font-bold leading-none"
        style={{
          color: "#0B0F14",
          background: "var(--accent)",
          boxShadow: "0 0 16px -2px var(--accent-glow)",
        }}
        aria-hidden
      >
        ▣
      </span>
      <span className="font-display text-lg font-semibold tracking-tight text-text-hi">
        SiteMind
      </span>
    </Link>
  );
}

function NavRail({ live }: { live: boolean }) {
  const pathname = usePathname();
  return (
    <nav className="flex w-60 shrink-0 flex-col border-r border-line bg-bg-800">
      <Brand />
      <div className="px-3">
        <div className="overline px-2 pb-2 pt-1">Command Center</div>
        <ul className="flex flex-col gap-1">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  className={cn(
                    "group relative flex items-center gap-3 rounded px-3 py-2 text-sm transition-colors duration-150",
                    active
                      ? "bg-bg-700 text-text-hi"
                      : "text-text-mid hover:bg-bg-700/60 hover:text-text-hi",
                  )}
                >
                  {active && (
                    <span className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-accent" />
                  )}
                  <Icon
                    size={18}
                    strokeWidth={1.5}
                    style={{ color: active ? "var(--accent)" : undefined }}
                  />
                  <span className={active ? "font-medium" : ""}>{label}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="mt-auto px-5 py-4">
        <div className="overline pb-1">Mode</div>
        <div className="flex items-center gap-2 text-xs text-text-mid">
          <span
            className={cn(
              "h-2 w-2 rounded-full",
              live ? "bg-pass shadow-[0_0_8px_var(--pass)]" : "bg-warning shadow-[0_0_8px_var(--warning)]",
            )}
          />
          <span className="font-mono">
            {live ? "Backend live" : "Mock fallback (backend unreachable)"}
          </span>
        </div>
      </div>
    </nav>
  );
}

function SettingsPanel({ health, live, onClose }: { health: HealthState | null; live: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [onClose]);

  const rows: [string, string][] = [
    ["Backend", live ? "Reachable" : "Unreachable — showing bundled mock data"],
    ["API URL", API_URL],
    ["LLM provider", health?.provider ?? "unknown"],
    ["Offline mode", health?.offline_mode ? "On — deterministic, no live LLM calls" : "Off"],
    ["Langfuse tracing", health?.langfuse_enabled ? "Enabled — traces mirrored to Langfuse" : "Disabled (local trace log only)"],
  ];

  return (
    <div
      ref={ref}
      className="absolute right-6 top-14 z-50 w-80 rounded border border-line bg-bg-800 p-4 shadow-xl"
    >
      <div className="overline pb-2">System status</div>
      <dl className="flex flex-col gap-2 text-xs">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-start justify-between gap-3">
            <dt className="text-text-lo">{k}</dt>
            <dd className="text-right font-mono text-text-hi">{v}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-3 border-t border-line pt-3 text-[0.7rem] leading-relaxed text-text-lo">
        Every clause citation and pass/fail decision is deterministic Python regardless of provider —
        the provider above only affects narrative prose. Project documents and schedule are
        REPRESENTATIVE synthetic data; standards citations and decision logic are REAL. See{" "}
        <span className="font-mono text-text-mid">README.md</span> for the full breakdown.
      </div>
    </div>
  );
}

function ClockPanel({ clock, onChange, onClose }: { clock: ClockState | null; onChange: (c: ClockState) => void; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [onClose]);

  async function step(days: number) {
    setBusy(true);
    const next = days === 0 ? await resetClock() : await advanceClock(days);
    setBusy(false);
    if (next) {
      onChange(next);
      // Every page reads schedule/supply-chain data via its own useEffect —
      // a full refresh is the simplest reliable way to make ALL of them
      // reflect the new simulated day at once.
      window.location.reload();
    }
  }

  return (
    <div
      ref={ref}
      className="absolute right-6 top-14 z-50 w-72 rounded border border-line bg-bg-800 p-4 shadow-xl"
    >
      <div className="overline pb-1">Simulated demo clock</div>
      <p className="mt-1 text-[0.7rem] leading-relaxed text-text-lo">
        Advances &quot;today&quot; and re-runs every real computation against it — schedule
        risk, alert lead time, alternative-supplier viability. Nothing in the underlying
        data changes; only time passing does.
      </p>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-text-lo">Current day</span>
        <span className="font-mono text-text-hi">
          {clock ? `${clock.current_day} (base ${clock.base_day} +${clock.offset_days}d)` : "—"}
        </span>
      </div>
      <div className="mt-3 flex gap-2">
        <button
          disabled={busy}
          onClick={() => step(7)}
          className="flex-1 rounded border border-line px-2 py-1.5 text-xs text-text-mid transition-colors hover:border-accent hover:text-text-hi disabled:opacity-50"
        >
          +7 days
        </button>
        <button
          disabled={busy}
          onClick={() => step(14)}
          className="flex-1 rounded border border-line px-2 py-1.5 text-xs text-text-mid transition-colors hover:border-accent hover:text-text-hi disabled:opacity-50"
        >
          +14 days
        </button>
        <button
          disabled={busy || !clock?.offset_days}
          onClick={() => step(0)}
          className="flex-1 rounded border border-line px-2 py-1.5 text-xs text-text-mid transition-colors hover:border-warning hover:text-text-hi disabled:opacity-50"
        >
          Reset
        </button>
      </div>
    </div>
  );
}

function TopBar({ health, live }: { health: HealthState | null; live: boolean }) {
  const [open, setOpen] = useState(false);
  const [clockOpen, setClockOpen] = useState(false);
  const [clockState, setClockState] = useState<ClockState | null>(null);

  useEffect(() => {
    getClockState().then((c) => c && setClockState(c));
  }, []);

  return (
    <header className="relative flex h-14 shrink-0 items-center justify-between border-b border-line bg-bg-900/80 px-6 backdrop-blur">
      <div className="flex items-center gap-3 text-sm">
        <span className="font-display font-medium text-text-hi">SiteMind</span>
        <span className="text-text-lo">▸</span>
        <span className="font-mono text-[0.82rem] text-text-mid">
          {projectLabel}
        </span>
      </div>
      <div className="flex items-center gap-4">
        <span className="hidden items-center gap-2 text-xs text-text-mid md:flex">
          <span
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              live ? "bg-accent animate-pulse" : "bg-warning",
            )}
          />
          {live ? "Agents online" : "Fallback mode"}
        </span>
        {clockState && (
          <button
            aria-label="Simulated clock"
            onClick={() => setClockOpen((o) => !o)}
            className={cn(
              "flex items-center gap-1.5 rounded border px-2.5 py-1.5 font-mono text-xs text-text-mid transition-colors hover:border-text-lo hover:text-text-hi",
              clockOpen ? "border-accent text-text-hi" : "border-line",
            )}
          >
            <Clock size={14} strokeWidth={1.5} />
            Day {clockState.current_day}
            {clockState.offset_days > 0 && (
              <span className="text-accent">+{clockState.offset_days}d</span>
            )}
          </button>
        )}
        <button
          aria-label="Settings"
          onClick={() => setOpen((o) => !o)}
          className={cn(
            "grid h-8 w-8 place-items-center rounded border text-text-mid transition-colors hover:border-text-lo hover:text-text-hi",
            open ? "border-accent text-text-hi" : "border-line",
          )}
        >
          <Settings size={16} strokeWidth={1.5} />
        </button>
      </div>
      {clockOpen && (
        <ClockPanel clock={clockState} onChange={setClockState} onClose={() => setClockOpen(false)} />
      )}
      {open && <SettingsPanel health={health} live={live} onClose={() => setOpen(false)} />}
    </header>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { health, live } = useHealth();
  return (
    <div className="flex h-screen overflow-hidden">
      <NavRail live={live} />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar health={health} live={live} />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[1280px] px-6 py-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
