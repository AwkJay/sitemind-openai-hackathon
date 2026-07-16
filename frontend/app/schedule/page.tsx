"use client";

import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Cell,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Clock, AlertTriangle, ShieldCheck, Route, Zap, ArrowRight, Check, X, Users } from "lucide-react";
import { getGantt, getRisks } from "@/lib/api";
import type { GanttBar, RiskItem, MitigationOption } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Skeleton } from "@/components/ui/primitives";
import { mitigationAgentMeta } from "@/lib/format";

function barColor(b: GanttBar) {
  if (b.at_risk) return "var(--critical)";
  if (b.on_critical_path) return "var(--accent)";
  return "var(--data)";
}

interface TipDatum {
  task: string;
  wbs_id: string;
  phase: string;
  start_day: number;
  duration_days: number;
  on_critical_path: boolean;
  at_risk: boolean;
}

function GanttTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d: TipDatum = payload[payload.length - 1].payload;
  return (
    <div className="rounded border border-line bg-bg-700 px-3 py-2 text-xs shadow-glow">
      <div className="font-mono text-text-lo">{d.wbs_id}</div>
      <div className="font-medium text-text-hi">{d.task}</div>
      <div className="mt-1 text-text-mid">
        Day <span className="font-mono">{d.start_day}</span> →{" "}
        <span className="font-mono">{d.start_day + d.duration_days}</span> ·{" "}
        {d.duration_days}d
      </div>
      <div className="mt-1 flex gap-2">
        {d.on_critical_path && (
          <span className="text-accent">● critical path</span>
        )}
        {d.at_risk && <span className="text-critical">● at-risk</span>}
      </div>
    </div>
  );
}

// Renders the 3 specialist agents' grounded findings for one risk — the brief's
// only explicit "multi-agent system" ask (generate options, not just one alert).
// Each row is a real computation (agents/mitigation.py), never LLM reasoning.
function MitigationOptionsPanel({ options }: { options: MitigationOption[] }) {
  if (!options.length) return null;
  return (
    <div className="mt-2 space-y-1.5">
      <div className="flex items-center gap-1.5 text-[0.68rem] uppercase tracking-wide text-text-lo">
        <Users size={11} /> Mitigation options · 3 specialist agents
      </div>
      {options.map((o) => {
        const meta = mitigationAgentMeta[o.agent];
        return (
          <div
            key={o.agent}
            title={o.detail}
            className="flex items-start gap-2 rounded px-2.5 py-1.5 text-[0.78rem]"
            style={{
              background: o.viable ? "rgba(34,197,94,0.08)" : "rgba(159,176,191,0.06)",
              opacity: o.viable ? 1 : 0.75,
            }}
          >
            {o.viable ? (
              <Check size={13} className="mt-0.5 shrink-0 text-pass" />
            ) : (
              <X size={13} className="mt-0.5 shrink-0 text-text-lo" />
            )}
            <div className="min-w-0">
              <span className="font-mono text-[0.68rem] text-text-lo">{meta.label}</span>
              <p className={o.viable ? "text-text-hi" : "text-text-mid"}>{o.summary}</p>
            </div>
            {o.viable && o.days_recovered > 0 && (
              <span className="ml-auto shrink-0 font-mono text-[0.7rem] font-semibold text-pass">
                −{o.days_recovered}d
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function SchedulePage() {
  const [gantt, setGantt] = useState<GanttBar[] | null>(null);
  const [risks, setRisks] = useState<RiskItem[] | null>(null);

  useEffect(() => {
    getGantt().then((r) => setGantt(r.data));
    getRisks().then((r) => setRisks(r.data));
  }, []);

  const chartData = gantt?.map((b) => ({
    ...b,
    label: `${b.wbs_id}`,
    offset: b.start_day,
  }));
  const totalDays = gantt
    ? Math.max(...gantt.map((b) => b.start_day + b.duration_days))
    : 0;
  const earliestWarning = risks?.length
    ? risks.reduce((a, b) => (b.detected_lead_time_days > a.detected_lead_time_days ? b : a))
    : null;

  return (
    <div>
      <PageHeader
        eyebrow="Pillar 3 · Predictive schedule risk"
        title="Schedule & Risk"
        subtitle="Critical path in lime, at-risk activities in red. SiteMind flags slips weeks before the baseline does."
      />

      {/* Gantt */}
      <Card className="px-5 py-4">
        <div className="flex items-center justify-between">
          <Overline>Programme · WBS gantt</Overline>
          <div className="flex items-center gap-4 text-xs text-text-mid">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-3 rounded-sm bg-accent" /> critical path
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-3 rounded-sm bg-critical" /> at-risk
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-3 rounded-sm bg-data" /> nominal
            </span>
          </div>
        </div>
        {chartData ? (
          <div className="mt-4" style={{ height: chartData.length * 46 + 40 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 0, right: 24, left: 8, bottom: 8 }}
                barCategoryGap={10}
              >
                <CartesianGrid
                  horizontal={false}
                  stroke="var(--line)"
                  strokeOpacity={0.4}
                />
                <XAxis
                  type="number"
                  domain={[0, totalDays]}
                  tick={{ fill: "var(--text-lo)", fontSize: 11 }}
                  tickFormatter={(v) => `D${v}`}
                  stroke="var(--line)"
                />
                <YAxis
                  type="category"
                  dataKey="label"
                  width={84}
                  tick={{ fill: "var(--text-mid)", fontSize: 11, fontFamily: "var(--font-mono)" }}
                  stroke="var(--line)"
                />
                <Tooltip
                  content={<GanttTooltip />}
                  cursor={{ fill: "var(--bg-700)", opacity: 0.4 }}
                />
                <Bar dataKey="offset" stackId="a" fill="transparent" />
                <Bar dataKey="duration_days" stackId="a" radius={3}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={barColor(d)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <Skeleton className="mt-4 h-72" />
        )}
        {gantt && (
          <div className="mt-2 flex flex-wrap gap-x-6 gap-y-1 font-mono text-[0.68rem] text-text-lo">
            {gantt.map((b) => (
              <span key={b.wbs_id}>
                {b.wbs_id} · {b.task}
              </span>
            ))}
          </div>
        )}
      </Card>

      {/* Earliest-warning hero */}
      {earliestWarning && (
        <Card className="mt-6 px-5 py-4" glow>
          <div className="flex items-start gap-3">
            <Zap size={18} className="mt-0.5 shrink-0 text-warning" />
            <div className="min-w-0">
              <Overline>Biggest early warning · this cycle</Overline>
              <p className="mt-1 text-sm text-text-hi">
                <span className="font-medium">{earliestWarning.activity}</span> ({earliestWarning.wbs_id})
                is flagged{" "}
                <span className="font-mono font-semibold text-warning">
                  {earliestWarning.detected_lead_time_days} days
                </span>{" "}
                before a &ldquo;flag only once visibly behind&rdquo; baseline would catch it.
              </p>
              {earliestWarning.project_impact_days > 0 ? (
                <p className="mt-1 text-sm text-text-mid">
                  Re-running CPM with the predicted {earliestWarning.predicted_slip_days}d slip pushes the
                  project finish date out by{" "}
                  <span className="font-mono font-semibold text-critical">
                    {earliestWarning.project_impact_days} days
                  </span>
                  {earliestWarning.downstream_activities.length > 0 && (
                    <>
                      {" "}
                      via{" "}
                      {earliestWarning.downstream_activities.map((d, i) => (
                        <span key={d} className="font-mono text-text-hi">
                          {i > 0 && ", "}
                          {d}
                        </span>
                      ))}
                    </>
                  )}
                  .
                </p>
              ) : (
                <p className="mt-1 text-sm text-text-mid">
                  Not on the critical path — schedule float absorbs the predicted slip, so project finish is
                  unaffected unless the delay grows.
                </p>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Top risks */}
      <div className="mt-6">
        <Overline className="mb-3">Top schedule risks · earliest warning first</Overline>
        {risks && risks.length === 0 && (
          <Card className="px-5 py-8 text-center text-sm text-text-mid">
            No activities are currently flagged — no leading-indicator rule fired against the current
            schedule state.
          </Card>
        )}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {risks
            ? risks.map((r) => (
                <Card key={r.wbs_id} className="px-5 py-4">
                  <div
                    className="rounded-card"
                    style={{
                      borderLeft: `3px solid ${r.on_critical_path ? "var(--accent)" : "var(--warning)"}`,
                      paddingLeft: 12,
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          {r.on_critical_path && (
                            <Route size={14} className="text-accent" />
                          )}
                          <span className="font-medium text-text-hi">
                            {r.activity}
                          </span>
                        </div>
                        <span className="font-mono text-xs text-text-lo">
                          {r.wbs_id}
                          {r.on_critical_path && " · critical path"}
                        </span>
                      </div>
                      <span
                        className="inline-flex shrink-0 items-center gap-1 rounded-chip px-2 py-1 font-mono text-xs font-semibold"
                        style={{
                          color: "var(--warning)",
                          background: "var(--warning-bg)",
                          border: "1px solid #ffb02033",
                        }}
                      >
                        <Clock size={12} /> {r.detected_lead_time_days} days
                        before baseline
                      </span>
                    </div>

                    <div className="mt-3 flex items-center gap-2 text-sm">
                      <AlertTriangle size={14} className="text-critical" />
                      <span className="text-text-mid">
                        Predicted slip{" "}
                        <span className="font-mono font-semibold text-critical">
                          {r.predicted_slip_days} days
                        </span>
                      </span>
                    </div>

                    <div className="mt-2">
                      <div className="overline mb-1">Drivers</div>
                      <ul className="space-y-1">
                        {r.drivers.map((d, i) => (
                          <li
                            key={i}
                            className="flex gap-2 text-sm text-text-mid"
                          >
                            <span className="text-text-lo">·</span> {d}
                          </li>
                        ))}
                      </ul>
                    </div>

                    {r.downstream_activities.length > 0 && (
                      <div className="mt-2 flex items-center gap-1.5 flex-wrap text-xs text-text-lo">
                        <ArrowRight size={12} />
                        <span>feeds</span>
                        {r.downstream_activities.map((d) => (
                          <span
                            key={d}
                            className="rounded-chip border border-line px-2 py-0.5 font-mono text-[0.68rem] text-text-mid"
                          >
                            {d}
                          </span>
                        ))}
                        {r.project_impact_days > 0 ? (
                          <span className="ml-auto font-mono text-[0.7rem] font-semibold text-critical">
                            +{r.project_impact_days}d to project finish
                          </span>
                        ) : (
                          <span className="ml-auto text-[0.7rem] text-text-lo">absorbed by float</span>
                        )}
                      </div>
                    )}

                    <div
                      className="mt-3 flex items-start gap-2 rounded bg-bg-700 px-3 py-2"
                    >
                      <ShieldCheck
                        size={15}
                        className="mt-0.5 shrink-0 text-pass"
                      />
                      <p className="text-sm text-text-hi">{r.mitigation}</p>
                    </div>

                    <MitigationOptionsPanel options={r.mitigation_options ?? []} />
                  </div>
                </Card>
              ))
            : [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-48" />)}
        </div>
      </div>
    </div>
  );
}
