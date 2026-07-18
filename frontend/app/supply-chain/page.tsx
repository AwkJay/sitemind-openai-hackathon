"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { AlertTriangle, ArrowRight, Bell, Info, MapPin, Route, ShieldCheck, Truck } from "lucide-react";
import { getShipments, getSupplyChainAlerts, getSupplyChainMap, getSupplyChainMeta, getSupplyChainRisks } from "@/lib/api";
import type { Shipment, SupplyChainAlert, SupplyChainMap, SupplyChainMeta, SupplyChainRisk } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Card, Overline, Skeleton, Chip } from "@/components/ui/primitives";
import { LinkedEvidence } from "@/components/LinkedEvidence";
import { alertSeverityMeta, equipmentSpecMeta } from "@/lib/format";

// Leaflet touches `window` at import time — must be client-only, no SSR.
const SupplyChainMapView = dynamic(
  () => import("@/components/SupplyChainMapView").then((m) => m.SupplyChainMapView),
  { ssr: false, loading: () => <Skeleton className="h-full w-full" /> },
);

export default function SupplyChainPage() {
  const [shipments, setShipments] = useState<Shipment[] | null>(null);
  const [risks, setRisks] = useState<SupplyChainRisk[] | null>(null);
  const [map, setMap] = useState<SupplyChainMap | null>(null);
  const [alerts, setAlerts] = useState<SupplyChainAlert[] | null>(null);
  const [meta, setMeta] = useState<SupplyChainMeta | null>(null);

  useEffect(() => {
    getShipments().then((r) => setShipments(r.data));
    getSupplyChainRisks().then((r) => setRisks(r.data));
    getSupplyChainMap().then((r) => setMap(r.data));
    getSupplyChainAlerts().then((r) => setAlerts(r.data));
    getSupplyChainMeta().then((r) => setMeta(r.data));
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Supply Chain Visibility & Risk"
        title="Supply Chain"
        subtitle="For the procurement lead — multi-tier shipment tracking extending the schedule pillar's own procurement data, real milestone delays, root-cause attribution across supplier tiers, and computed procurement alternatives."
      />

      {meta && (
        <div className="mb-6 flex items-start gap-2.5 rounded border border-line bg-bg-800 px-4 py-3 text-xs text-text-mid">
          <Info size={14} strokeWidth={1.5} className="mt-0.5 shrink-0 text-text-lo" />
          <span>
            <span className="font-mono text-text-hi">
              As of Day {meta.as_of_day} ({meta.as_of_date})
            </span>{" "}
            — {meta.note}
          </span>
        </div>
      )}

      {/* Alerts — an in-app, timestamped log (not a push/email channel). Answers
          the brief's "alerting timeliness" metric: detected_at_day is the real
          day the slip first became visible in the milestone data. */}
      <Card className="px-5 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell size={15} strokeWidth={1.5} className="text-warning" />
            <Overline>Alerts</Overline>
          </div>
          <span className="text-[0.68rem] text-text-lo">
            in-app alert log · timestamped, not a push notification
          </span>
        </div>
        {alerts ? (
          alerts.length === 0 ? (
            <p className="mt-3 text-sm text-text-mid">No active alerts — every tracked shipment is on track.</p>
          ) : (
            <div className="mt-3 space-y-2">
              {alerts.map((a) => {
                const m = alertSeverityMeta[a.severity];
                return (
                  <div key={a.id} className="flex items-center gap-3 rounded bg-bg-700 px-3 py-2 text-sm">
                    <Chip color={m.color} bg={m.bg}>{m.label}</Chip>
                    <span className="flex-1 text-text-hi">{a.message}</span>
                    <span className="shrink-0 font-mono text-[0.7rem] text-text-lo">
                      {a.lead_time_at_detection_days}d advance warning · flagged day {a.detected_at_day} ({a.advance_warning_days}d ago)
                    </span>
                  </div>
                );
              })}
            </div>
          )
        ) : (
          <Skeleton className="mt-3 h-16" />
        )}
      </Card>

      <Card className="mt-6 overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
          <div className="flex items-center gap-2">
            <MapPin size={15} strokeWidth={1.5} className="text-accent" />
            <Overline>Shipment map · tier-2 sub-suppliers → tier-1 assembly → site</Overline>
          </div>
          <div className="flex items-center gap-4 text-[0.68rem] text-text-mid">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: "#f0b429" }} /> site
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: "#38bdf8" }} /> tier-1
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full" style={{ background: "#94a3b8" }} /> tier-2
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-critical" /> at risk
            </span>
          </div>
        </div>
        <div style={{ height: 420 }}>
          {map ? <SupplyChainMapView data={map} /> : <Skeleton className="h-full w-full" />}
        </div>
      </Card>

      <div className="mt-6">
        <Overline className="mb-3">At-risk shipments · root cause + procurement alternative</Overline>
        {risks && risks.length === 0 && (
          <Card className="px-5 py-8 text-center text-sm text-text-mid">
            No shipments are currently projected to miss their required-on-site date.
          </Card>
        )}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {risks
            ? risks.map((r) => (
                <Card key={r.shipment_id} className="px-5 py-4">
                  <div
                    className="rounded-card"
                    style={{
                      borderLeft: `3px solid ${r.on_critical_path ? "var(--accent)" : "var(--critical)"}`,
                      paddingLeft: 12,
                    }}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          {r.on_critical_path && <Route size={14} className="text-accent" />}
                          <span className="font-medium text-text-hi">{r.procurement_item}</span>
                        </div>
                        <span className="font-mono text-xs text-text-lo">
                          {r.shipment_id} · feeds {r.wbs_id}
                          {r.on_critical_path && " · critical path"}
                        </span>
                      </div>
                      <span
                        className="inline-flex shrink-0 items-center gap-1 rounded-chip px-2 py-1 font-mono text-xs font-semibold"
                        style={{ color: "var(--critical)", background: "rgba(239,68,68,0.12)", border: "1px solid #ef444433" }}
                      >
                        <AlertTriangle size={12} /> {r.days_at_risk}d late
                      </span>
                    </div>

                    <div className="mt-3 flex items-center gap-2 text-sm">
                      <Truck size={14} className="text-text-lo" />
                      <span className="text-text-mid">
                        {r.lead_time_at_detection_days}d advance warning at detection · {r.days_until_required}d runway remaining
                      </span>
                    </div>

                    {r.root_cause && (
                      <div className="mt-2">
                        <div className="overline mb-1">Root cause</div>
                        <p className="text-sm text-text-mid">{r.root_cause}</p>
                      </div>
                    )}

                    <LinkedEvidence
                      linkedRfi={r.linked_rfi}
                      linkedActivity={r.linked_activity}
                      className="mt-3"
                    />

                    {r.recommended_alternative ? (
                      <div className="mt-3 rounded border-l-2 border-accent/40 bg-bg-900/50 px-3 py-2.5">
                        <div className="flex items-center gap-1.5 text-[0.68rem] font-medium uppercase tracking-wide text-text-lo">
                          <ShieldCheck size={12} className="text-pass" /> Viable alternative
                        </div>
                        <p className="mt-1 text-sm leading-relaxed text-text-hi">
                          {r.recommended_alternative.supplier} ({r.recommended_alternative.city}) — lead
                          time {r.recommended_alternative.lead_time_days}d, arrives day{" "}
                          {r.recommended_alternative.projected_arrival_day} at{" "}
                          <span className="font-mono text-warning">
                            +{r.recommended_alternative.cost_premium_pct}%
                          </span>{" "}
                          cost premium.
                        </p>
                      </div>
                    ) : (
                      <p className="mt-3 rounded border-l-2 border-critical/40 bg-bg-900/50 px-3 py-2.5 text-sm text-text-mid">
                        No alternative supplier can arrive by the required date — escalate for a schedule
                        replan rather than a procurement swap.
                      </p>
                    )}
                  </div>
                </Card>
              ))
            : [0, 1].map((i) => <Skeleton key={i} className="h-48" />)}
        </div>
      </div>

      <div className="mt-6">
        <Overline className="mb-3">All tracked shipments</Overline>
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[0.68rem] uppercase tracking-wide text-text-lo">
                <th className="px-4 py-2.5 font-medium">Item</th>
                <th className="px-4 py-2.5 font-medium">Tier-1 supplier</th>
                <th className="px-4 py-2.5 font-medium">Stage</th>
                <th className="px-4 py-2.5 font-medium">Required by</th>
                <th className="px-4 py-2.5 font-medium">Projected arrival</th>
                <th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Equipment spec</th>
              </tr>
            </thead>
            <tbody>
              {shipments
                ? shipments.map((s) => (
                    <tr key={s.id} className="border-b border-line/60 last:border-0">
                      <td className="px-4 py-3">
                        <div className="text-text-hi">{s.procurement_item}</div>
                        <div className="font-mono text-[0.66rem] text-text-lo">
                          {s.id} · feeds {s.wbs_id}
                          {s.on_critical_path && " · critical path"}
                        </div>
                        <LinkedEvidence
                          linkedRfi={s.linked_rfi}
                          linkedActivity={null}
                          className="mt-1.5"
                        />
                      </td>
                      <td className="px-4 py-3 text-text-mid">
                        {s.tier1_supplier.name}
                        <div className="font-mono text-[0.66rem] text-text-lo">{s.tier1_supplier.city}</div>
                      </td>
                      <td className="px-4 py-3 font-mono text-[0.72rem] text-text-mid">
                        {s.current_stage.replace(/_/g, " ")}
                      </td>
                      <td className="px-4 py-3 font-mono text-text-mid">day {s.required_on_site_by}</td>
                      <td className="px-4 py-3 font-mono text-text-mid">
                        day {s.projected_arrival_day}
                        {s.days_at_risk > 0 && (
                          <span className="ml-1.5 inline-flex items-center gap-1 text-critical">
                            <ArrowRight size={11} /> +{s.days_at_risk}d
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {s.days_at_risk > 0 ? (
                          <Chip color="var(--critical)" bg="rgba(239,68,68,0.12)">
                            at risk
                          </Chip>
                        ) : (
                          <Chip color="var(--pass)" bg="rgba(34,197,94,0.12)">
                            on track
                          </Chip>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {(() => {
                          const m = equipmentSpecMeta[s.equipment_spec.status];
                          return (
                            <span title={s.equipment_spec.note}>
                              <Chip color={m.color} bg={m.bg}>
                                {m.label}
                              </Chip>
                            </span>
                          );
                        })()}
                      </td>
                    </tr>
                  ))
                : [0, 1, 2].map((i) => (
                    <tr key={i}>
                      <td colSpan={7} className="px-4 py-3">
                        <Skeleton className="h-6" />
                      </td>
                    </tr>
                  ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
