"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Clock,
  IndianRupee,
  ArrowUpRight,
  Activity,
  FileText,
  ShieldAlert,
} from "lucide-react";
import { getCostRisk, getOverview, getRisks, getDocuments } from "@/lib/api";
import type { CostRisk, OverviewStats, RiskItem, DocItem } from "@/lib/types";
import { CountUp } from "@/components/CountUp";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Skeleton } from "@/components/ui/primitives";
import { impactPillarMeta, inrCompact, severityMeta, statusMeta } from "@/lib/format";

function TickerCard({
  icon,
  label,
  to,
  format,
  color,
  suffix,
}: {
  icon: React.ReactNode;
  label: string;
  to: number;
  format?: (v: number) => string;
  color: string;
  suffix?: string;
}) {
  return (
    <Card className="px-5 py-5">
      <div className="flex items-center gap-2">
        <span style={{ color }}>{icon}</span>
        <Overline>{label}</Overline>
      </div>
      <div className="mt-3 flex items-baseline gap-1.5">
        <span
          className="metric text-[2.6rem] font-semibold leading-none"
          style={{ color: "var(--text-hi)" }}
        >
          <CountUp to={to} format={format} />
        </span>
        {suffix && (
          <span className="metric text-lg text-text-mid">{suffix}</span>
        )}
      </div>
    </Card>
  );
}

export default function OverviewPage() {
  const [stats, setStats] = useState<OverviewStats | null>(null);
  const [risks, setRisks] = useState<RiskItem[] | null>(null);
  const [docs, setDocs] = useState<DocItem[] | null>(null);
  const [costRisk, setCostRisk] = useState<CostRisk | null>(null);

  useEffect(() => {
    getOverview().then((r) => setStats(r.data));
    getRisks().then((r) => setRisks(r.data));
    getDocuments().then((r) => setDocs(r.data));
    getCostRisk().then((r) => setCostRisk(r.data));
  }, []);

  const totalNcrs = stats
    ? Object.values(stats.open_ncrs_by_severity).reduce((a, b) => a + b, 0)
    : 0;

  return (
    <div>
      <PageHeader
        eyebrow="Command Center"
        title="Project Overview"
        subtitle="SiteMind is already catching code violations, schedule slips and rework before they reach the field."
      />

      {/* ROI ticker */}
      {stats ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <TickerCard
            icon={<AlertTriangle size={18} strokeWidth={1.5} />}
            color="var(--critical)"
            label="⚠ Issues caught pre-site"
            to={stats.issues_caught}
          />
          <TickerCard
            icon={<Clock size={18} strokeWidth={1.5} />}
            color="var(--accent)"
            label="⏱ Engineer-hours saved"
            to={stats.engineer_hours_saved}
            suffix="hrs"
          />
          <TickerCard
            icon={<IndianRupee size={18} strokeWidth={1.5} />}
            color="var(--pass)"
            label="₹ Rework avoided"
            to={stats.rework_avoided_inr}
            format={inrCompact}
          />
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      )}

      {/* Per-pillar impact breakdown — computed live from impact.py, not asserted */}
      <Card className="mt-4 px-5 py-4">
        <div className="flex items-center justify-between">
          <Overline>Where the ROI comes from — by pillar</Overline>
          <span className="text-[0.68rem] text-text-lo">
            hover a row for the exact computed basis
          </span>
        </div>
        {stats ? (
          <div className="mt-3 divide-y divide-bg-700">
            {stats.by_pillar.map((p) => {
              const meta = impactPillarMeta[p.pillar];
              return (
                <Link
                  key={p.pillar}
                  href={meta.href}
                  title={p.basis}
                  className="flex items-center justify-between gap-3 py-2.5 text-sm transition-colors hover:bg-bg-700/50"
                >
                  <span className="text-text-mid">{meta.label}</span>
                  <span className="flex items-baseline gap-3 font-mono text-text-hi">
                    <span>
                      {p.hours_saved}
                      <span className="text-text-lo"> hrs</span>
                    </span>
                    <span style={{ color: "var(--pass)" }}>
                      {inrCompact(p.inr_saved)}
                    </span>
                  </span>
                </Link>
              );
            })}
          </div>
        ) : (
          <Skeleton className="mt-3 h-32" />
        )}
      </Card>

      {/* Cost-at-Risk — deterministic cost_at_risk = schedule_delay_cost +
          expedite_premium_cost + rework_exposure (app/cost_risk.py). NOT ML/
          probabilistic; every term's inputs are real, only the per-item base
          costs are labelled REPRESENTATIVE (data_note below). */}
      <Card className="mt-4 px-5 py-4">
        <div className="flex items-center gap-2">
          <ShieldAlert size={16} strokeWidth={1.5} style={{ color: "var(--critical)" }} />
          <Overline>Cost at risk — schedule + supply-chain + rework</Overline>
        </div>
        {costRisk ? (
          <>
            <div className="mt-3 flex items-baseline gap-2">
              <span
                className="metric text-[2.2rem] font-semibold leading-none"
                style={{ color: "var(--text-hi)" }}
              >
                {inrCompact(costRisk.total_inr)}
              </span>
              <span className="text-sm text-text-mid">exposed today, computed live</span>
            </div>
            <div className="mt-3 space-y-2">
              {costRisk.components.map((c) => (
                <div
                  key={c.label}
                  title={c.basis}
                  className="flex items-center justify-between gap-3 rounded bg-bg-700 px-3 py-2 text-sm"
                >
                  <span className="text-text-mid">{c.label}</span>
                  <span className="font-mono text-text-hi">{inrCompact(c.inr)}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[0.7rem] leading-snug text-text-lo">{costRisk.data_note}</p>
          </>
        ) : (
          <Skeleton className="mt-3 h-32" />
        )}
      </Card>

      {/* Summary cards */}
      <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Open NCRs by severity */}
        <Card className="px-5 py-4">
          <div className="flex items-center justify-between">
            <Overline>Open NCRs by severity</Overline>
            <span className="font-mono text-sm text-text-mid">
              {totalNcrs} open
            </span>
          </div>
          <div className="mt-4 space-y-2.5">
            {stats ? (
              (["HIGH", "MEDIUM", "ADVISORY", "LOW"] as const).map((sev) => {
                const count = stats.open_ncrs_by_severity[sev] ?? 0;
                const meta = severityMeta[sev];
                const pct = totalNcrs ? (count / totalNcrs) * 100 : 0;
                return (
                  <div key={sev}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="flex items-center gap-2">
                        <span style={{ color: meta.color }} aria-hidden>
                          {meta.icon}
                        </span>
                        <span className="text-text-mid">{meta.label}</span>
                      </span>
                      <span className="font-mono text-text-hi">{count}</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-700">
                      <div
                        className="h-full rounded-full transition-all duration-700"
                        style={{ width: `${pct}%`, background: meta.color }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <Skeleton className="h-32" />
            )}
          </div>
          <Link
            href="/compliance"
            className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-data hover:text-[#7cd4fb]"
          >
            Open compliance <ArrowUpRight size={14} />
          </Link>
        </Card>

        {/* Schedule health */}
        <Card className="px-5 py-4">
          <Overline>Schedule health</Overline>
          {risks ? (
            <>
              <div className="mt-3 flex items-baseline gap-2">
                <Activity size={18} strokeWidth={1.5} className="text-warning" />
                <span className="metric text-3xl font-semibold text-text-hi">
                  {risks.filter((r) => r.on_critical_path).length}
                </span>
                <span className="text-sm text-text-mid">
                  critical-path risks
                </span>
              </div>
              <p className="mt-1 text-sm text-text-mid">
                {stats?.schedule_at_risk ?? risks.length} activities at-risk ·
                max{" "}
                <span className="font-mono text-warning">
                  {Math.max(...risks.map((r) => r.detected_lead_time_days))}d
                </span>{" "}
                early warning.
              </p>
              <div className="mt-4 space-y-2">
                {risks.slice(0, 3).map((r) => (
                  <div
                    key={r.wbs_id}
                    className="flex items-center justify-between rounded bg-bg-700 px-3 py-2 text-sm"
                  >
                    <span className="truncate text-text-mid">{r.activity}</span>
                    <span
                      className="ml-2 shrink-0 font-mono text-xs"
                      style={{
                        color: r.on_critical_path
                          ? "var(--critical)"
                          : "var(--warning)",
                      }}
                    >
                      −{r.predicted_slip_days}d
                    </span>
                  </div>
                ))}
              </div>
              <Link
                href="/schedule"
                className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-data hover:text-[#7cd4fb]"
              >
                View schedule <ArrowUpRight size={14} />
              </Link>
            </>
          ) : (
            <Skeleton className="mt-3 h-40" />
          )}
        </Card>

        {/* Recent documents / RFIs */}
        <Card className="px-5 py-4">
          <Overline>Recent submittals & RFIs</Overline>
          {docs ? (
            <div className="mt-3 space-y-2">
              {docs.slice(0, 5).map((d) => {
                const sm = statusMeta(d.status);
                return (
                  <div
                    key={d.id}
                    className="flex items-center justify-between gap-2 rounded bg-bg-700 px-3 py-2"
                  >
                    <div className="flex min-w-0 items-center gap-2">
                      <FileText
                        size={14}
                        strokeWidth={1.5}
                        className="shrink-0 text-text-lo"
                      />
                      <div className="min-w-0">
                        <div className="truncate text-sm text-text-hi">
                          {d.title}
                        </div>
                        <div className="font-mono text-[0.68rem] text-text-lo">
                          {d.id}
                        </div>
                      </div>
                    </div>
                    <span
                      className="shrink-0 rounded-chip px-1.5 py-0.5 font-mono text-[0.62rem] font-semibold"
                      style={{ color: sm.color, background: sm.bg }}
                    >
                      {d.status.split(" ")[0]}
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <Skeleton className="mt-3 h-40" />
          )}
          <Link
            href="/copilot"
            className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-data hover:text-[#7cd4fb]"
          >
            Ask the copilot <ArrowUpRight size={14} />
          </Link>
        </Card>
      </div>
    </div>
  );
}
