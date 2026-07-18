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
  ReferenceLine,
  ResponsiveContainer,
  LabelList,
} from "recharts";
import { Clock, AlertTriangle, ShieldCheck, Route, Zap, ArrowRight, Check, X, Users } from "lucide-react";
import { getClockState, getGantt, getRisks } from "@/lib/api";
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
  predicted_slip_days: number;
  drivers: string[];
}

// Short causal phrase for the Gantt label — the full driver list still lives
// in the risk card below; this is just enough to name the cause on the chart.
function shortenDriver(d: string, max = 26): string {
  const cleaned = d.replace(/^Long-lead /, "").replace(/^Progress /, "Progress lags plan");
  return cleaned.length > max ? `${cleaned.slice(0, max - 1)}…` : cleaned;
}

// Recharts' default LabelList renderer auto-wraps long text into one <tspan>
// PER WORD when it infers a narrow available width — unusable for a causal
// phrase. This draws a single plain <text> line instead, positioned just
// right of the bar segment it labels.
function SlipLabelContent(props: any) {
  const { x, y, width, height, value } = props;
  if (!value) return null;
  return (
    <text
      x={x + width + 6}
      y={y + height / 2}
      dy={3}
      fontSize={10}
      fill="var(--critical)"
    >
      {value}
    </text>
  );
}

function GanttTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d: TipDatum = payload[payload.length - 1].payload;
  const baselineEnd = d.start_day + d.duration_days;
  const predictedEnd = baselineEnd + (d.predicted_slip_days || 0);
  return (
    <div className="rounded border border-line bg-bg-700 px-3 py-2 text-xs shadow-glow">
      <div className="font-medium text-text-hi">{d.task}</div>
      <div className="font-mono text-text-lo">{d.wbs_id}</div>
      <div className="mt-1 text-text-mid">
        Baseline: Day <span className="font-mono">{d.start_day}</span> →{" "}
        <span className="font-mono">{baselineEnd}</span> · {d.duration_days}d
      </div>
      {d.at_risk && d.predicted_slip_days > 0 && (
        <div className="mt-0.5 text-critical">
          Predicted: Day <span className="font-mono">{d.start_day}</span> →{" "}
          <span className="font-mono">{predictedEnd}</span>{" "}
          <span className="font-mono font-semibold">(+{d.predicted_slip_days}d slip)</span>
        </div>
      )}
      <div className="mt-1 flex gap-2">
        {d.on_critical_path && (
          <span className="text-accent">● critical path</span>
        )}
        {d.at_risk && <span className="text-critical">● at-risk</span>}
      </div>
      {d.at_risk && d.drivers.length > 0 && (
        <div className="mt-1 max-w-[220px] text-text-mid">{d.drivers[0]}</div>
      )}
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

function truncate(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

// Name-first row labels: the task name is the primary, legible text; the WBS
// ID is small/muted secondary text underneath. Previously the WBS ID alone
// was the primary label and got clipped in a narrow axis column (e.g.
// "DC1-01-EN-010" rendering as ":1-01-EN-010") — IDs are secondary everywhere.
function PhaseAwareYTick({
  x,
  y,
  payload,
  firstInPhase,
  phaseByWbs,
  taskByWbs,
}: any) {
  const wbsId = payload.value as string;
  const isFirst = firstInPhase.has(wbsId);
  const taskName = truncate(taskByWbs[wbsId] || wbsId, 22);
  return (
    <g transform={`translate(${x},${y})`}>
      {isFirst && (
        <text
          x={-136}
          y={-16}
          textAnchor="start"
          fontSize={9}
          fill="var(--accent)"
          style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}
        >
          {phaseByWbs[wbsId]}
        </text>
      )}
      <text x={-8} y={-2} textAnchor="end" fontSize={10.5} fill="var(--text-hi)">
        {taskName}
      </text>
      <text x={-8} y={11} textAnchor="end" fontSize={9} fontFamily="var(--font-mono)" fill="var(--text-lo)">
        {wbsId}
      </text>
    </g>
  );
}

export default function SchedulePage() {
  const [gantt, setGantt] = useState<GanttBar[] | null>(null);
  const [risks, setRisks] = useState<RiskItem[] | null>(null);
  const [todayDay, setTodayDay] = useState<number | null>(null);

  useEffect(() => {
    getGantt().then((r) => setGantt(r.data));
    getRisks().then((r) => setRisks(r.data));
    getClockState().then((c) => c && setTodayDay(c.current_day));
  }, []);

  const chartData = gantt?.map((b) => {
    const slipExtension = b.at_risk ? b.predicted_slip_days : 0;
    const slipLabel =
      b.at_risk && b.predicted_slip_days > 0
        ? `+${b.predicted_slip_days}d${b.drivers[0] ? " · " + shortenDriver(b.drivers[0]) : ""}`
        : "";
    return {
      ...b,
      label: `${b.wbs_id}`,
      offset: b.start_day,
      slipExtension,
      slipLabel,
    };
  });
  const totalDays = gantt
    ? Math.max(
        ...gantt.map((b) => b.start_day + b.duration_days + (b.at_risk ? b.predicted_slip_days : 0)),
        todayDay ?? 0
      )
    : 0;
  const earliestWarning = risks?.length
    ? risks.reduce((a, b) => (b.detected_lead_time_days > a.detected_lead_time_days ? b : a))
    : null;

  const phaseByWbs: Record<string, string> = {};
  const taskByWbs: Record<string, string> = {};
  const firstInPhase = new Set<string>();
  let lastPhase = "";
  (chartData ?? []).forEach((b) => {
    phaseByWbs[b.wbs_id] = b.phase;
    taskByWbs[b.wbs_id] = b.task;
    if (b.phase !== lastPhase) {
      firstInPhase.add(b.wbs_id);
      lastPhase = b.phase;
    }
  });

  return (
    <div>
      <PageHeader
        eyebrow="Predictive Schedule Risk"
        title="Schedule & Risk"
        subtitle="For the planning engineer — critical path in lime, at-risk activities in red. SiteMind flags slips weeks before the baseline does."
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
            <span className="flex items-center gap-1.5">
              <span
                className="h-2.5 w-3 rounded-sm"
                style={{ background: "var(--critical)", opacity: 0.35, border: "1px dashed var(--critical)" }}
              />{" "}
              predicted slip
            </span>
          </div>
        </div>
        {chartData ? (
          <div className="mt-4" style={{ height: chartData.length * 46 + 40 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 10, right: 160, left: 8, bottom: 8 }}
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
                  width={150}
                  tick={<PhaseAwareYTick firstInPhase={firstInPhase} phaseByWbs={phaseByWbs} taskByWbs={taskByWbs} />}
                  stroke="var(--line)"
                />
                <Tooltip
                  content={<GanttTooltip />}
                  cursor={{ fill: "var(--bg-700)", opacity: 0.4 }}
                />
                {todayDay !== null && (
                  <ReferenceLine
                    x={todayDay}
                    stroke="var(--accent)"
                    strokeDasharray="4 3"
                    label={{
                      value: `Day ${todayDay} — today`,
                      position: "top",
                      fill: "var(--accent)",
                      fontSize: 10,
                    }}
                  />
                )}
                <Bar dataKey="offset" stackId="a" fill="transparent" />
                <Bar dataKey="duration_days" stackId="a" radius={3}>
                  {chartData.map((d, i) => (
                    <Cell key={i} fill={barColor(d)} />
                  ))}
                </Bar>
                <Bar
                  dataKey="slipExtension"
                  stackId="a"
                  radius={3}
                  fill="var(--critical)"
                  fillOpacity={0.35}
                  stroke="var(--critical)"
                  strokeDasharray="3 2"
                >
                  <LabelList dataKey="slipLabel" content={<SlipLabelContent />} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <Skeleton className="mt-4 h-72" />
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
