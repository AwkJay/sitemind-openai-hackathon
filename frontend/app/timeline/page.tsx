"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Info, Link2, X } from "lucide-react";
import { getTimeline } from "@/lib/api";
import type { PhaseBand, TimelineData, TimelineEvent, TimelinePillar } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Skeleton } from "@/components/ui/primitives";
import { timelinePillarMeta, timelineSeverityMeta } from "@/lib/format";

const LANES: TimelinePillar[] = ["compliance", "copilot", "schedule", "supply_chain", "commissioning"];
const AXIS_H = 32;
const ROW_H = 48;

// Draws the actual visual threads between a selected marker and its linked
// evidence markers across pillar lanes — the page's own subtitle promises
// "threads between them made visible"; before this, the connection only
// existed as a list in the detail card below, never on the chart itself.
// Straight lines only (no bezier): the SVG uses preserveAspectRatio="none" so
// day-percent (x, 0-100) and lane pixels (y) can share one viewBox despite
// their very different scales — a curve's control points would distort
// under that non-uniform stretch, but a straight line's endpoints don't.
function ConnectorLines({
  selected,
  events,
  laneIndexOf,
  pctFn,
  totalHeight,
}: {
  selected: TimelineEvent | null;
  events: TimelineEvent[];
  laneIndexOf: (p: TimelinePillar) => number;
  pctFn: (day: number) => number;
  totalHeight: number;
}) {
  if (!selected) return null;
  const y = (pillar: TimelinePillar) => AXIS_H + laneIndexOf(pillar) * ROW_H + ROW_H / 2;
  return (
    <svg
      className="pointer-events-none absolute inset-0"
      viewBox={`0 0 100 ${totalHeight}`}
      preserveAspectRatio="none"
      style={{ width: "100%", height: totalHeight }}
    >
      {selected.linked_event_ids.map((lid) => {
        const target = events.find((e) => e.id === lid);
        if (!target) return null;
        return (
          <line
            key={lid}
            x1={pctFn(selected.day)}
            y1={y(selected.pillar)}
            x2={pctFn(target.day)}
            y2={y(target.pillar)}
            stroke="var(--accent)"
            strokeWidth={1.5}
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
            opacity={0.85}
          />
        );
      })}
    </svg>
  );
}

function Dot({
  event,
  leftPct,
  jitterPx = 0,
  selected,
  linked,
  onSelect,
}: {
  event: TimelineEvent;
  leftPct: number;
  jitterPx?: number;
  selected: boolean;
  linked: boolean;
  onSelect: () => void;
}) {
  const meta = timelineSeverityMeta[event.severity];
  // CRITICAL/HIGH render larger than MEDIUM/LOW/INFO — severity is visually
  // legible at a glance, not just by colour, on a chart with 33+ markers.
  const prominent = event.severity === "CRITICAL" || event.severity === "HIGH";
  const base = prominent ? 12 : 9;
  const size = selected || linked ? base + 4 : base;
  return (
    <button
      type="button"
      onClick={onSelect}
      title={event.title}
      className="absolute top-1/2 rounded-full transition-all duration-150"
      style={{
        left: `calc(${leftPct}% + ${jitterPx}px)`,
        transform: "translate(-50%, -50%)",
        width: size,
        height: size,
        background: meta.color,
        boxShadow:
          selected || linked
            ? `0 0 0 3px ${meta.bg}, 0 0 12px -1px ${meta.color}`
            : `0 0 6px -2px ${meta.color}`,
        zIndex: selected || linked ? 5 : 2,
      }}
    />
  );
}

export default function TimelinePage() {
  const [data, setData] = useState<TimelineData | null>(null);
  const [live, setLive] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  useEffect(() => {
    getTimeline().then((r) => {
      setData(r.data);
      setLive(r.live);
    });
  }, []);

  const totalDays = useMemo(() => {
    if (!data) return 1;
    const candidates = [
      data.today_day,
      ...data.phase_bands.map((b) => b.end_day),
      ...data.events.map((e) => e.day),
    ];
    return Math.max(1, Math.max(...candidates) + 10);
  }, [data]);

  const pct = (day: number) => Math.max(0, Math.min(100, (day / totalDays) * 100));

  const ticks = useMemo(() => {
    const step = totalDays > 300 ? 50 : totalDays > 150 ? 25 : 10;
    const out: number[] = [];
    for (let d = 0; d <= totalDays; d += step) out.push(d);
    return out;
  }, [totalDays]);

  const selected = data?.events.find((e) => e.id === selectedId) ?? null;
  const linkedIds = new Set(selected?.linked_event_ids ?? []);

  return (
    <div>
      <PageHeader
        eyebrow="Project Timeline"
        title="One Data Centre, Being Built"
        subtitle="For anyone who wants the whole build at a glance — every finding SiteMind has caught, in time order, with the threads between them made visible."
      />

      <div className="mb-6 flex items-start gap-2.5 rounded border border-line bg-bg-800 px-4 py-3 text-xs text-text-mid">
        <Info size={14} strokeWidth={1.5} className="mt-0.5 shrink-0 text-text-lo" />
        <span>
          Every marker is aggregated live from the same pipelines each pillar page already runs
          (compliance checks, RFI log, schedule risk, supply-chain alerts, commissioning findings) —
          this page adds no new judgment, only a shared timeline. Phase bands are the real min/max of
          each phase&rsquo;s activities from the schedule DAG. Dataset is REPRESENTATIVE synthetic data;
          see README for what&rsquo;s real vs. representative.
          {!live && " (Showing bundled mock data — backend unreachable.)"}
        </span>
      </div>

      <Card className="px-5 py-4">
        <div className="mb-3 flex items-center justify-between">
          <Overline>Build lifecycle · groundbreaking → handover</Overline>
          <div className="flex items-center gap-3 text-[0.68rem] text-text-lo">
            {(Object.keys(timelineSeverityMeta) as (keyof typeof timelineSeverityMeta)[]).map((k) => (
              <span key={k} className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full" style={{ background: timelineSeverityMeta[k].color }} />
                {k}
              </span>
            ))}
          </div>
        </div>

        {!data ? (
          <Skeleton className="h-96" />
        ) : (
          <div className="flex">
            {/* Lane gutter */}
            <div className="w-32 shrink-0">
              <div style={{ height: AXIS_H }} />
              {LANES.map((lane) => (
                <div key={lane} style={{ height: ROW_H }} className="flex items-center">
                  <Link
                    href={timelinePillarMeta[lane].href}
                    className="text-[0.7rem] text-text-mid transition-colors hover:text-text-hi"
                  >
                    {timelinePillarMeta[lane].label}
                  </Link>
                </div>
              ))}
            </div>

            {/* Timeline column */}
            <div className="relative flex-1" style={{ height: AXIS_H + LANES.length * ROW_H }}>
              {/* day axis */}
              <div className="absolute inset-x-0 top-0 border-b border-line" style={{ height: AXIS_H }}>
                {ticks.map((t) => (
                  <span
                    key={t}
                    className="absolute top-1 -translate-x-1/2 font-mono text-[0.62rem] text-text-lo"
                    style={{ left: `${pct(t)}%` }}
                  >
                    D{t}
                  </span>
                ))}
              </div>

              {/* phase bands — boundary guidelines, not full-height fills, because
                  data-centre phases genuinely run in parallel (MEP and L1
                  commissioning both start well before Civil/Structural finishes);
                  overlapping colour washes would read as visual noise instead of
                  the real build sequence. */}
              <div className="absolute inset-x-0" style={{ top: AXIS_H, height: LANES.length * ROW_H }}>
                {data.phase_bands.map((b: PhaseBand, i: number) => {
                  const future = b.start_day > data.today_day;
                  return (
                    <div
                      key={b.phase}
                      className="absolute top-0 h-full border-l border-dashed"
                      style={{ left: `${pct(b.start_day)}%`, borderColor: "var(--line)", opacity: future ? 0.5 : 0.85 }}
                    >
                      <span
                        className="absolute left-1.5 whitespace-nowrap text-[0.58rem] uppercase tracking-wide text-text-lo"
                        style={{ top: (i % 3) * 11 + 2 }}
                      >
                        {b.phase}
                        {future && " · planned"}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* today line */}
              <div
                className="absolute top-0 w-px bg-accent"
                style={{ left: `${pct(data.today_day)}%`, height: AXIS_H + LANES.length * ROW_H }}
              >
                <span className="absolute -top-0.5 -translate-x-1/2 whitespace-nowrap rounded-chip bg-accent px-1.5 py-0.5 font-mono text-[0.6rem] font-semibold text-[#0B0F14]">
                  Day {data.today_day} — you are here
                </span>
              </div>

              {/* connector lines — behind the dots (rendered after, in a later
                  DOM position) so markers stay clickable and legible on top */}
              <ConnectorLines
                selected={selected}
                events={data.events}
                laneIndexOf={(p) => LANES.indexOf(p)}
                pctFn={pct}
                totalHeight={AXIS_H + LANES.length * ROW_H}
              />

              {/* lanes */}
              {LANES.map((lane, li) => {
                const laneEvents = data.events.filter((e) => e.pillar === lane);
                // Exact same-day duplicates (e.g. 3 commissioning findings that
                // all landed the same day) render on top of each other and
                // become uncklickable except the topmost — space them out with
                // a small pixel jitter so every marker stays independently
                // selectable, without disturbing their real day position.
                const sameDayIds: Record<number, string[]> = {};
                laneEvents.forEach((e) => {
                  (sameDayIds[e.day] ??= []).push(e.id);
                });
                return (
                  <div
                    key={lane}
                    className="absolute inset-x-0"
                    style={{ top: AXIS_H + li * ROW_H, height: ROW_H }}
                  >
                    {laneEvents.map((e) => {
                      const group = sameDayIds[e.day];
                      const idx = group.indexOf(e.id);
                      const jitterPx = group.length > 1 ? (idx - (group.length - 1) / 2) * 12 : 0;
                      return (
                        <Dot
                          key={e.id}
                          event={e}
                          leftPct={pct(e.day)}
                          jitterPx={jitterPx}
                          selected={e.id === selectedId}
                          linked={linkedIds.has(e.id)}
                          onSelect={() => setSelectedId(e.id === selectedId ? null : e.id)}
                        />
                      );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Card>

      {selected && (
        <Card className="mt-4 px-5 py-4" glow>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className="rounded-chip px-2 py-0.5 font-mono text-[0.65rem] font-semibold"
                  style={{
                    color: timelineSeverityMeta[selected.severity].color,
                    background: timelineSeverityMeta[selected.severity].bg,
                  }}
                >
                  {selected.severity}
                </span>
                <span className="text-[0.68rem] uppercase tracking-wide text-text-lo">
                  {timelinePillarMeta[selected.pillar].label} · Day {selected.day}
                </span>
              </div>
              <h3 className="mt-1.5 font-medium text-text-hi">{selected.title}</h3>
              <p className="mt-1 text-sm text-text-mid">{selected.detail}</p>

              {selected.linked_event_ids.length > 0 && (
                <div className="mt-3">
                  <div className="mb-1.5 flex items-center gap-1.5 text-[0.68rem] uppercase tracking-wide text-text-lo">
                    <Link2 size={11} /> Linked evidence · same underlying finding, seen from another pillar
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {selected.linked_event_ids.map((lid) => {
                      const target = data?.events.find((e) => e.id === lid);
                      if (!target) return null;
                      return (
                        <button
                          key={lid}
                          onClick={() => setSelectedId(lid)}
                          className="rounded-chip border border-accent/40 bg-bg-900/60 px-2.5 py-1 text-left text-[0.72rem] text-text-mid transition-colors hover:border-accent hover:text-text-hi"
                        >
                          <span className="font-mono text-text-lo">Day {target.day} · </span>
                          {target.title}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <Link
                href={selected.link_route}
                className="rounded border border-line px-3 py-1.5 text-xs font-medium text-text-mid transition-colors hover:border-accent hover:text-text-hi"
              >
                Open in {timelinePillarMeta[selected.pillar].label}
              </Link>
              <button
                onClick={() => setSelectedId(null)}
                className="grid h-7 w-7 shrink-0 place-items-center rounded border border-line text-text-lo transition-colors hover:border-text-lo hover:text-text-hi"
              >
                <X size={13} />
              </button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
