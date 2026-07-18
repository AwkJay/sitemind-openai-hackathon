// Bundled, demo-grade mock data. Every API call falls back to these so the UI
// always renders for a demo, even with no backend. Clauses are the REAL IS text
// from backend/data/standards/clauses.json (verbatim — do not edit the text).

import type {
  ComplianceResult,
  CostRisk,
  DocItem,
  GanttBar,
  KgGraph,
  OverviewStats,
  RFIAnswer,
  RiskItem,
  Shipment,
  SupplyChainAlert,
  SupplyChainMap,
  SupplyChainMeta,
  SupplyChainRisk,
  TimelineData,
} from "./types";

export const PROJECT_LABEL = "Hyperscale DC — Chennai · 48 MW · Tier III";

export const mockOverview: OverviewStats = {
  project: PROJECT_LABEL,
  issues_caught: 14,
  engineer_hours_saved: 320,
  rework_avoided_inr: 21000000, // ₹2.1 Cr
  open_ncrs_by_severity: { HIGH: 3, MEDIUM: 5, ADVISORY: 4, LOW: 2 },
  schedule_at_risk: 4,
  machine_scale: {
    documents_read: 12,
    clauses_checked: 12,
    cross_references_found: 5,
    conflicts_surfaced: 2,
  },
  by_pillar: [
    {
      pillar: "compliance",
      hours_saved: 280,
      inr_saved: 21000000,
      basis: "14 open NCR(s) x 20h manual cross-check/write-up avoided + Rs 1,500,000 rework avoided per issue caught pre-site.",
    },
    {
      pillar: "schedule",
      hours_saved: 24,
      inr_saved: 5050000,
      basis: "6 leading-indicator flag(s) x 4h manual root-cause/escalation avoided + 101d of critical-path impact caught early x Rs 50,000/day coordination overhead avoided.",
    },
    {
      pillar: "supply_chain",
      hours_saved: 12,
      inr_saved: 750000,
      basis: "2 at-risk shipment(s) x 6h manual root-cause/alternative-evaluation avoided + 10d at-risk mitigated early x Rs 75,000/day.",
    },
    {
      pillar: "commissioning",
      hours_saved: 18,
      inr_saved: 600000,
      basis: "2 FAIL x 8h re-test/re-commission avoided + 1 within-allowable-only x 2h O&M-review avoided (cooling slice only).",
    },
  ],
};

export const mockCostRisk: CostRisk = {
  total_inr: 135250000,
  components: [
    {
      label: "Schedule delay exposure",
      inr: 35350000,
      basis: "101d of critical-path project impact (CPM-recomputed, summed across findings) x Rs 350,000/day documented delay/liquidated-damages rate.",
    },
    {
      label: "Expedite-premium exposure",
      inr: 90900000,
      basis: "SHP-001 (DRUPS 2.5MW): 45% premium on Rs 180,000,000 base = Rs 81,000,000; SHP-002 (LV switchgear 4000A): 22% premium on Rs 9,900,000 base.",
    },
    {
      label: "Rework exposure (open NCRs)",
      inr: 9000000,
      basis: "6 open NCR(s) x Rs 1,500,000 avg rework cost per issue (same assumption the ROI ticker's Compliance pillar uses).",
    },
  ],
  data_note:
    "REPRESENTATIVE synthetic cost data — order-of-magnitude figures modelled on typical Indian data-centre EPC BOQ line items, not any real project's actual costs. The formula and its live inputs are real.",
};

export const mockDocuments: DocItem[] = [
  {
    id: "DC1-23-DBR-0001-R2",
    title: "Structural Design Basis Report — Substructure",
    type: "design_basis",
    status: "Pending",
    discipline: "Civil/Structural",
  },
  {
    id: "DC1-23-SD-0042-R1",
    title: "Foundation Shop Drawings — Transformer Yard",
    type: "submittal",
    status: "C – Revise & Resubmit",
    discipline: "Civil/Structural",
  },
  {
    id: "DC1-23-MX-0008-R0",
    title: "Concrete Mix Design — M30 Substructure",
    type: "mix_design",
    status: "B – Approved as Noted",
    discipline: "Civil/Structural",
  },
  {
    id: "DC1-23-SD-0117-R3",
    title: "Column Reinforcement Schedule — Gen Building",
    type: "submittal",
    status: "A – Approved",
    discipline: "Civil/Structural",
  },
  {
    id: "RFI-MECH-033",
    title: "CRAH Pad Anchorage Clarification",
    type: "rfi",
    status: "Pending",
    discipline: "Mechanical",
  },
];

// ── Per-document compliance results ───────────────────────────────────────────

const RESULT_DBR: ComplianceResult = {
  document: "DC1-23-DBR-0001-R2 · Structural Design Basis Report",
  checked_params: 11,
  conforming: [
    "Concrete grade M30 for RCC ≥ M30 (sea-coast exposure) — CONFORMS",
    "Max free water-cement ratio 0.45 ≤ 0.45 limit — CONFORMS",
    "Design wind speed Vz derived from basic 50 m/s with k1·k2·k3 — CONFORMS",
    "Column longitudinal steel 1.2% within 0.8–6% band — CONFORMS",
  ],
  ncrs: [
    {
      id: "NCR-CIV-019",
      item: "Nominal cover — isolated footings",
      severity: "HIGH",
      finding:
        "Design basis specifies 40 mm nominal cover to footing reinforcement. IS 456:2000 requires a minimum of 50 mm for footings.",
      source: {
        quote:
          "Clear cover to all footing reinforcement shall be 40 mm unless noted otherwise.",
        location: "DBR §4.2 General Note 7",
      },
      citation: {
        standard: "IS 456:2000",
        clause: "26.4.2.2",
        text: "For footings minimum cover shall be 50 mm.",
        verify_url:
          "http://gaudi.local/manak/#is456_2000/clause:26.4.2",
      },
      why_it_matters:
        "Footings sit against soil with chlorides from the nearby sea-coast. 10 mm of missing cover materially shortens time-to-corrosion of the bottom mat and risks durability of the entire transformer-yard substructure.",
      corrective_action:
        "Revise DBR General Note 7 and all footing details to specify 50 mm minimum nominal cover. Re-issue affected shop drawings (DC1-23-SD-0042) before any rebar is cut.",
      status: "OPEN",
    },
    {
      id: "NCR-CIV-022",
      item: "Seismic importance factor (I)",
      severity: "ADVISORY",
      finding:
        "DBR adopts importance factor I = 1.0. IS 1893 (Part 1):2016 Cl. 7.2.3 permits I = 1.5 for buildings whose post-event functionality is critical. A Tier III data centre is arguably a critical facility.",
      source: {
        quote:
          "Importance factor I taken as 1.0 for a normal industrial structure.",
        location: "DBR §6.1 Seismic Parameters",
      },
      citation: {
        standard: "IS 1893 (Part 1):2016",
        clause: "7.2.3",
        text: "The importance factor I is used to obtain the design seismic force. It depends upon the functional use of the structure, characterized by hazardous consequences of its failure, post-earthquake functional need, historic value, or economic importance.",
        verify_url:
          "http://gaudi.local/manak/#is1893_2016/clause:7.2.3",
      },
      why_it_matters:
        "If the owner classifies the facility as critical (continuous-operation Tier III), I = 1.5 increases the design base shear by 50%. Catching this now avoids a structural redesign after detailed design freeze.",
      corrective_action:
        "Obtain a formal facility-importance classification from the owner/EOR and re-run the seismic analysis with the agreed I before design freeze.",
      recommendation:
        "Recommend adopting I = 1.5 unless the owner formally accepts a normal-importance classification. Quantify the base-shear impact before EOR sign-off.",
      confirm_with: "EOR",
      status: "OPEN",
    },
    {
      id: "NCR-CIV-027",
      item: "Span/effective-depth ratio — yard slab",
      severity: "MEDIUM",
      finding:
        "Spanning slab over cable trench shows a span/effective-depth ratio of 28 against a basic limit of 20 for simply supported members under IS 456 Cl. 23.2, with no modification factor justified.",
      source: {
        quote: "Trench cover slab: span 4.2 m, effective depth 150 mm.",
        location: "DBR §5.4 Slab Schedule",
      },
      citation: {
        standard: "IS 456:2000",
        clause: "23.2",
        text: "The vertical deflection limits may generally be assumed to be satisfied provided that the span to depth ratios are not greater than the values obtained as below: (a) Basis values of span to effective depth ratios for spans up to 10 m: Cantilever 7, Simply supported 20, Continuous 26.",
        verify_url:
          "http://gaudi.local/manak/#is456_2000/clause:23.2",
      },
      why_it_matters:
        "Excess deflection of the trench cover can crack finishes and disturb cable supports. The ratio must be justified with the tension-steel modification factor or the depth increased.",
      corrective_action:
        "Increase effective depth to ≥ 210 mm or provide a documented modification-factor calculation per Fig. 4 of IS 456.",
      status: "OPEN",
    },
  ],
  overlaps: [
    {
      item: "Footing F-12",
      param: "nominal_cover",
      clauses: [
        "IS 456:2000 Cl 26.4.2.2 (footing min 50 mm)",
        "IS 456:2000 Cl 26.5.1.1 / Table 16 (severe exposure 45 mm)",
      ],
      governing: "IS 456:2000 Cl 26.4.2.2 (footing min 50 mm)",
      note: "Two clauses govern cover for Footing F-12: the footing minimum (50 mm) and the severe-exposure durability floor (Table 16, 45 mm). The binding requirement is 50 mm.",
    },
  ],
  coverage: {
    standards: [
      "IS 1893 (Part 1):2016",
      "IS 456:2000",
      "IS 875 (Part 3):2015",
    ],
    clauses_cited: 12,
    checks_run: 10,
    library_clauses: 13,
  },
};

const RESULT_SD42: ComplianceResult = {
  document: "DC1-23-SD-0042-R1 · Foundation Shop Drawings",
  checked_params: 8,
  conforming: [
    "Lap length 50d for M30 — CONFORMS",
    "Bar spacing 150 mm c/c within max spacing — CONFORMS",
  ],
  ncrs: [
    {
      id: "NCR-CIV-031",
      item: "Cover tolerance on detailed cover",
      severity: "MEDIUM",
      finding:
        "Cover callout reads '50 mm (-5/+15)'. IS 456 Cl. 12.3.2 permits +10/-0 mm only; a negative tolerance is not allowed.",
      source: {
        quote: "Bottom cover 50 mm (tol −5 / +15 mm).",
        location: "Drawing DC1-23-SD-0042-R1, Detail A",
      },
      citation: {
        standard: "IS 456:2000",
        clause: "12.3.2",
        text: "The actual concrete cover should not deviate from the required nominal cover by +10 mm and -0 mm.",
        verify_url:
          "http://gaudi.local/manak/#is456_2000/clause:12.3.2",
      },
      why_it_matters:
        "A −5 mm tolerance silently permits 45 mm cover on site, re-introducing the durability risk the 50 mm minimum exists to prevent.",
      corrective_action:
        "Change cover tolerance note to '+10 / −0 mm' on all foundation details.",
      status: "OPEN",
    },
  ],
};

const RESULT_GENERIC: ComplianceResult = {
  document: "Selected document",
  checked_params: 6,
  conforming: [
    "Concrete grade ≥ M30 for RCC in marine exposure — CONFORMS",
    "Column longitudinal steel within 0.8–6% — CONFORMS",
    "Lap and development lengths — CONFORMS",
  ],
  ncrs: [
    {
      id: "NCR-CIV-040",
      item: "Minimum cement content / w-c ratio",
      severity: "LOW",
      finding:
        "Mix narrative quotes cement content without stating the maximum free water-cement ratio used to verify durability for the exposure class.",
      source: {
        quote: "OPC 53 grade, 380 kg/m³ cement content.",
        location: "Mix design sheet, row 4",
      },
      citation: {
        standard: "IS 456:2000",
        clause: "8.2.4.1",
        text: "The free water-cement ratio is an important factor in governing the durability of concrete and should always be the lowest value. Appropriate values for minimum cement content and the maximum free water-cement ratio are given in Table 5 for different exposure conditions.",
        verify_url:
          "http://gaudi.local/manak/#is456_2000/clause:8.2.4.1",
      },
      why_it_matters:
        "Without the stated w-c ratio the durability check is incomplete for the severe sea-coast exposure class.",
      corrective_action:
        "Add the design free water-cement ratio (target ≤ 0.45) and reference Table 5 exposure class on the mix sheet.",
      status: "OPEN",
    },
  ],
};

export const mockComplianceByDoc: Record<string, ComplianceResult> = {
  "DC1-23-DBR-0001-R2": RESULT_DBR,
  "DC1-23-SD-0042-R1": RESULT_SD42,
};

export function mockComplianceFor(documentId: string): ComplianceResult {
  return (
    mockComplianceByDoc[documentId] ?? {
      ...RESULT_GENERIC,
      document:
        mockDocuments.find((d) => d.id === documentId)?.title ??
        RESULT_GENERIC.document,
    }
  );
}

// The reasoning trace the streaming endpoint would emit, token-ish chunks.
export function mockReasoningTrace(documentId: string): string[] {
  const r = mockComplianceFor(documentId);
  return [
    `Loading ${documentId} and the applicable standards set (IS 456:2000, IS 1893, IS 875)…`,
    "Parsing general notes, schedules and detail callouts. Extracting design parameters with source spans.",
    "Extracted: nominal cover, concrete grade, w-c ratio, importance factor, span/depth ratio, longitudinal steel %.",
    `Running ${r.checked_params} deterministic clause checks against the digitised IS text…`,
    "Cross-checking footing cover against IS 456:2000 Cl. 26.4.2.2 → required 50 mm.",
    "Comparing extracted 40 mm with the 50 mm minimum → NON-CONFORMING.",
    "Evaluating seismic importance factor against IS 1893 Cl. 7.2.3 → judgment call for critical facilities.",
    `Compiling ${r.ncrs.length} finding(s) with verified citations and corrective actions.`,
    "Done. Rendering NCR cards.",
  ];
}

// ── Copilot ───────────────────────────────────────────────────────────────────

export function mockCopilotAnswer(question: string): RFIAnswer {
  const q = question.toLowerCase();
  if (q.includes("cover") || q.includes("footing")) {
    return {
      answer:
        "For footings, IS 456:2000 requires a minimum nominal cover of 50 mm [1]. On site the actual cover may exceed the nominal by up to 10 mm but must never fall below it (tolerance +10 / −0 mm) [2]. For the Chennai sea-coast exposure this 50 mm is a durability floor, not a target — specifying 40 mm (as the current DBR draft does) is non-conforming.",
      sources: [
        {
          label: "IS 456:2000 · Cl. 26.4.2.2",
          detail: "For footings minimum cover shall be 50 mm.",
          verify_url: "http://gaudi.local/manak/#is456_2000/clause:26.4.2",
        },
        {
          label: "IS 456:2000 · Cl. 12.3.2",
          detail:
            "The actual concrete cover should not deviate from the required nominal cover by +10 mm and -0 mm.",
          verify_url: "http://gaudi.local/manak/#is456_2000/clause:12.3.2",
        },
      ],
      seen_before: {
        rfi_id: "RFI-CIV-014",
        summary:
          "Contractor asked whether 40 mm cover to pile caps was acceptable on the adjacent phase.",
        resolution:
          "EOR directed 50 mm minimum per IS 456 Cl. 26.4.2.2; drawings revised R2. Same answer applies here.",
      },
    };
  }
  if (q.includes("wind") || q.includes("vz") || q.includes("875")) {
    return {
      answer:
        "Design wind speed Vz is the basic wind speed Vb modified by risk, terrain and topography factors per IS 875 (Part 3):2015 Cl. 5.3: Vz = Vb·k1·k2·k3 [1]. For the Chennai cyclonic zone Vb = 50 m/s; apply k1 for a 100-year-class facility before deriving pressures.",
      sources: [
        {
          label: "IS 875 (Part 3):2015 · Cl. 5.3",
          detail:
            "Design wind speed Vz = Vb·k1·k2·k3 where k1 = risk coefficient, k2 = terrain/height factor, k3 = topography factor.",
          verify_url: "http://gaudi.local/manak/#is875_2015/clause:5.3",
        },
      ],
      seen_before: null,
    };
  }
  if (q.includes("seismic") || q.includes("importance") || q.includes("1893")) {
    return {
      answer:
        "The seismic importance factor I scales the design base shear by functional criticality [1]. IS 1893 (Part 1):2016 Cl. 7.2.3 allows I = 1.5 for facilities whose post-event functionality is critical. A Tier III data centre is a strong candidate — adopting I = 1.5 raises base shear ~50% versus the I = 1.0 currently in the DBR. This is flagged as an ADVISORY for EOR confirmation, not an automatic failure.",
      sources: [
        {
          label: "IS 1893 (Part 1):2016 · Cl. 7.2.3",
          detail:
            "Importance factor depends on functional use, hazardous consequences of failure and post-earthquake functional need.",
          verify_url: "http://gaudi.local/manak/#is1893_2016/clause:7.2.3",
        },
      ],
      seen_before: null,
    };
  }
  return {
    answer:
      "I cross-reference the project documents against the digitised IS/IRC standards. Ask about cover, concrete grade, water-cement ratio, wind speed, seismic importance factor, or any submittal — I cite the exact clause [1]. Try: \"What cover does IS 456 require for footings?\"",
    sources: [
      {
        label: "IS 456:2000 · Cl. 8.2.4.1",
        detail:
          "Durability governed by the free water-cement ratio; minimum cement content and max w-c ratio per Table 5 by exposure class.",
        verify_url: "http://gaudi.local/manak/#is456_2000/clause:8.2.4.1",
      },
    ],
    seen_before: null,
  };
}

// ── Schedule ──────────────────────────────────────────────────────────────────

export const mockRisks: RiskItem[] = [
  {
    activity: "Transformer-yard foundation rebar & pour",
    wbs_id: "WBS-3.2.1",
    on_critical_path: true,
    predicted_slip_days: 9,
    detected_lead_time_days: 21,
    drivers: [
      "Shop drawing DC1-23-SD-0042 in 'Revise & Resubmit' (cover NCR open)",
      "Rebar delivery lead time trending +4 days vs plan",
    ],
    mitigation:
      "Fast-track NCR-CIV-031 cover correction and pre-stage rebar for grids A–C to protect the pour window.",
    downstream_activities: [],
    project_impact_days: 0,
    mitigation_options: [
      { agent: "procurement_alternative", viable: false, days_recovered: 0, summary: "No tracked shipment feeds this activity.", detail: "This activity isn't a procurement/delivery item." },
      { agent: "resequencing_float", viable: false, days_recovered: 0, summary: "No schedule float — on the critical path.", detail: "CPM float is 0d." },
      { agent: "resource_recovery", viable: true, days_recovered: 9, summary: "Recoverable with ~18% added crew/overtime capacity.", detail: "Under the 30% documented threshold." },
    ],
  },
  {
    activity: "GIS hall switchgear installation",
    wbs_id: "WBS-5.4.0",
    on_critical_path: true,
    predicted_slip_days: 6,
    detected_lead_time_days: 14,
    drivers: [
      "Long-lead GIS bay delivery confirmation pending vendor",
      "Predecessor floor-flatness survey not yet closed",
    ],
    mitigation:
      "Escalate vendor delivery confirmation; schedule flatness survey this week to unblock anchoring.",
    downstream_activities: [],
    project_impact_days: 0,
    mitigation_options: [
      { agent: "procurement_alternative", viable: true, days_recovered: 6, cost_premium_pct: 15, summary: "Switch to an ex-stock GIS bay supplier — +15% cost.", detail: "Alternate supplier arrives on or before the required date." },
      { agent: "resequencing_float", viable: true, days_recovered: 6, summary: "6d absorbed by existing schedule float — fully covers the predicted slip.", detail: "CPM float covers the full slip." },
      { agent: "resource_recovery", viable: false, days_recovered: 2, summary: "Would need ~45% added capacity — not realistically recoverable via resourcing alone.", detail: "Over the 30% documented threshold." },
    ],
  },
  {
    activity: "Chilled-water primary loop pressure test",
    wbs_id: "WBS-6.1.3",
    on_critical_path: false,
    predicted_slip_days: 4,
    detected_lead_time_days: 10,
    drivers: ["RFI-MECH-033 (CRAH pad anchorage) open against this package"],
    mitigation:
      "Close RFI-MECH-033 using the prior resolution; no design change expected.",
    downstream_activities: [],
    project_impact_days: 0,
  },
  {
    activity: "Standby generator commissioning",
    wbs_id: "WBS-7.3.2",
    on_critical_path: false,
    predicted_slip_days: 3,
    detected_lead_time_days: 8,
    drivers: ["Fuel-polishing skid factory test slipping 2 days"],
    mitigation: "Parallel-path the fuel skid FAT with electrical pre-comm.",
    downstream_activities: [],
    project_impact_days: 0,
  },
  {
    activity: "White-space raised floor & containment",
    wbs_id: "WBS-8.2.0",
    on_critical_path: false,
    predicted_slip_days: 2,
    detected_lead_time_days: 6,
    drivers: ["Containment material approval (submittal) in review"],
    mitigation: "Approve the containment submittal to release procurement.",
    downstream_activities: [],
    project_impact_days: 0,
  },
];

export const mockGantt: GanttBar[] = [
  { wbs_id: "WBS-1.0", task: "Earthworks & piling", phase: "Substructure", start_day: 0, duration_days: 28, on_critical_path: true, at_risk: false, predicted_slip_days: 0, drivers: [] },
  { wbs_id: "WBS-3.2.1", task: "Yard foundations", phase: "Substructure", start_day: 26, duration_days: 24, on_critical_path: true, at_risk: true, predicted_slip_days: 5, drivers: ["Weather-sensitive activity scheduled during the monsoon window"] },
  { wbs_id: "WBS-2.1", task: "Gen-building superstructure", phase: "Superstructure", start_day: 44, duration_days: 40, on_critical_path: false, at_risk: false, predicted_slip_days: 0, drivers: [] },
  { wbs_id: "WBS-5.4.0", task: "GIS hall switchgear", phase: "Electrical", start_day: 70, duration_days: 30, on_critical_path: true, at_risk: true, predicted_slip_days: 25, drivers: ["Long-lead LV switchgear vendor status 'slipping' on the critical path"] },
  { wbs_id: "WBS-6.1.3", task: "Chilled-water primary loop", phase: "Mechanical", start_day: 82, duration_days: 26, on_critical_path: false, at_risk: true, predicted_slip_days: 6, drivers: ["Progress lags planned completion"] },
  { wbs_id: "WBS-7.3.2", task: "Generator commissioning", phase: "Electrical", start_day: 104, duration_days: 22, on_critical_path: false, at_risk: false, predicted_slip_days: 0, drivers: [] },
  { wbs_id: "WBS-8.2.0", task: "White-space fit-out", phase: "Fit-out", start_day: 120, duration_days: 28, on_critical_path: true, at_risk: false, predicted_slip_days: 0, drivers: [] },
  { wbs_id: "WBS-9.0", task: "Integrated systems test (IST)", phase: "Commissioning", start_day: 146, duration_days: 18, on_critical_path: true, at_risk: false, predicted_slip_days: 0, drivers: [] },
];

// ── Knowledge graph ───────────────────────────────────────────────────────────

export const mockKg: KgGraph = {
  nodes: [
    { id: "eq-tx", label: "33/11kV Transformer", type: "equipment" },
    { id: "eq-crah", label: "CRAH Unit (white-space)", type: "equipment" },
    { id: "spec-found", label: "Foundation Spec · M30", type: "spec" },
    { id: "spec-cover", label: "Cover Spec · 50 mm", type: "spec" },
    { id: "spec-anchor", label: "Anchorage Spec", type: "spec" },
    { id: "std-456-cover", label: "IS 456 · Cl. 26.4.2.2", type: "standard" },
    { id: "std-456-tol", label: "IS 456 · Cl. 12.3.2", type: "standard" },
    { id: "std-1893", label: "IS 1893 · Cl. 7.2.3", type: "standard" },
    { id: "rfi-033", label: "RFI-MECH-033", type: "rfi" },
    { id: "rfi-014", label: "RFI-CIV-014", type: "rfi" },
  ],
  edges: [
    { source: "eq-tx", target: "spec-found", label: "founded on" },
    { source: "spec-found", target: "spec-cover", label: "requires" },
    { source: "spec-cover", target: "std-456-cover", label: "governed by" },
    { source: "spec-cover", target: "std-456-tol", label: "tolerance per" },
    { source: "eq-tx", target: "std-1893", label: "seismic per" },
    { source: "spec-cover", target: "rfi-014", label: "raised in" },
    { source: "eq-crah", target: "spec-anchor", label: "fixed by" },
    { source: "spec-anchor", target: "rfi-033", label: "queried in" },
    { source: "rfi-033", target: "rfi-014", label: "similar to" },
  ],
};

// ── Supply Chain Visibility ─────────────────────────────────────────────────
// Mirrors real computed output from backend/app/supply_chain.py (verified during
// development) so the offline fallback tells the same story as the live backend.

const SITE_PT = { city: "Chennai", country: "India", lat: 13.0827, lon: 80.2707 };

// Real clause from backend/data/standards/clauses.json (verbatim) — the only
// procurement category currently covered by a real equipment-spec standard.
const IS8623_4_1_2_CITATION = {
  standard: "IS 8623 (Part 1):1993 (identical to IEC 439-1:1985)",
  clause: "4.1.2",
  text: "The maximum rated operational voltage of any circuit of the ASSEMBLY shall not exceed its rated insulation voltage. It is assumed that the operational voltage of any circuit of an ASSEMBLY will not, even temporarily, exceed 110% of its rated insulation voltage.",
  verify_url: "https://archive.org/details/gov.in.is.8623.1.1993",
  source_type: "primary_scan_ocr" as const,
};

const NOT_APPLICABLE_SPEC = {
  standard_applicable: false,
  status: "NOT_APPLICABLE" as const,
  declared_spec: null,
  citation: null,
  note: "No equipment-spec standard in the corpus yet covers this procurement category (only LV switchgear/controlgear assemblies, via IS 8623-1:1993, are covered so far).",
};

export const mockShipments: Shipment[] = [
  {
    id: "SHP-001",
    procurement_item: "DRUPS 2.5MW",
    wbs_id: "DC1-04-EL-020",
    tier1_supplier: { name: "Ashoka Power Systems", city: "Pune", country: "India", lat: 18.5204, lon: 73.8567 },
    tier2_suppliers: [
      { name: "Hanzhou Cell Works", city: "Shanghai", country: "China", lat: 31.2304, lon: 121.4737 },
    ],
    milestones: [
      { stage: "ordered", tier: 1, planned_day: 35, actual_day: 35, projected_day: null },
      { stage: "tier2_dispatched", tier: 2, planned_day: 60, actual_day: 60, projected_day: null },
      { stage: "tier2_customs_clearance", tier: 2, planned_day: 75, actual_day: 130, projected_day: null },
      { stage: "tier2_delivered_to_tier1", tier: 2, planned_day: 85, actual_day: 140, projected_day: null },
      { stage: "tier1_in_production", tier: 1, planned_day: 100, actual_day: 155, projected_day: null },
      { stage: "tier1_dispatched", tier: 1, planned_day: 140, actual_day: null, projected_day: 195 },
      { stage: "in_transit", tier: 1, planned_day: 150, actual_day: null, projected_day: 205 },
      { stage: "arrived_at_site", tier: 1, planned_day: 165, actual_day: null, projected_day: 220 },
    ],
    current_stage: "tier1_in_production",
    required_on_site_by: 215,
    projected_arrival_day: 220,
    days_at_risk: 5,
    on_critical_path: false,
    root_cause: "tier2 customs clearance slipped 55d (tier-2 sub-supplier)",
    alternatives: [
      { supplier: "Meridian DRUPS India", city: "Bengaluru", country: "India", lat: 12.9716, lon: 77.5946, lead_time_days: 200, cost_premium_pct: 18, viable: false, projected_arrival_day: 375 },
      { supplier: "NordPower EU", city: "Hamburg", country: "Germany", lat: 53.5511, lon: 9.9937, lead_time_days: 240, cost_premium_pct: 31, viable: false, projected_arrival_day: 415 },
      { supplier: "Uptime Bridge Rentals (interim containerized DRUPS)", city: "Mumbai", country: "India", lat: 19.0760, lon: 72.8777, lead_time_days: 30, cost_premium_pct: 45, viable: true, projected_arrival_day: 205 },
    ],
    equipment_spec: NOT_APPLICABLE_SPEC,
    linked_rfi: { id: "RFI-EL-110", status: "Open", match: "retrieved" },
    linked_activity: { id: "DC1-04-EL-020", name: "DRUPS 2.5MW (2N) — procurement & delivery", on_critical_path: false },
  },
  {
    id: "SHP-002",
    procurement_item: "LV switchgear 4000A",
    wbs_id: "DC1-04-EL-030",
    tier1_supplier: { name: "Kavery Switchgear Ltd", city: "Bengaluru", country: "India", lat: 12.9716, lon: 77.5946 },
    tier2_suppliers: [
      { name: "Rheinmetall Breaker Components", city: "Stuttgart", country: "Germany", lat: 48.7758, lon: 9.1829 },
    ],
    milestones: [
      { stage: "ordered", tier: 1, planned_day: 65, actual_day: 65, projected_day: null },
      { stage: "tier2_dispatched", tier: 2, planned_day: 90, actual_day: 90, projected_day: null },
      { stage: "tier2_customs_clearance", tier: 2, planned_day: 100, actual_day: 100, projected_day: null },
      { stage: "tier2_delivered_to_tier1", tier: 2, planned_day: 108, actual_day: 108, projected_day: null },
      { stage: "tier1_in_production", tier: 1, planned_day: 115, actual_day: 135, projected_day: null },
      { stage: "tier1_dispatched", tier: 1, planned_day: 190, actual_day: null, projected_day: 210 },
      { stage: "in_transit", tier: 1, planned_day: 198, actual_day: null, projected_day: 218 },
      { stage: "arrived_at_site", tier: 1, planned_day: 205, actual_day: null, projected_day: 225 },
    ],
    current_stage: "tier1_in_production",
    required_on_site_by: 220,
    projected_arrival_day: 225,
    days_at_risk: 5,
    on_critical_path: false,
    root_cause: "tier1 in production slipped 20d (tier-1 supplier)",
    alternatives: [
      { supplier: "Sundaram Electricals", city: "Chennai", country: "India", lat: 13.0827, lon: 80.2707, lead_time_days: 130, cost_premium_pct: 9, viable: false, projected_arrival_day: 305 },
      { supplier: "Vellore Panel Distributors (ex-stock unit)", city: "Chennai", country: "India", lat: 13.0827, lon: 80.2707, lead_time_days: 35, cost_premium_pct: 22, viable: true, projected_arrival_day: 210 },
    ],
    equipment_spec: {
      standard_applicable: true,
      status: "MATCH",
      declared_spec: { rated_operational_voltage_v: 415, rated_insulation_voltage_v: 1000 },
      citation: IS8623_4_1_2_CITATION,
      note: "Declared operational voltage (415V) is within the declared insulation voltage rating (1000V) per IS 8623-1:1993 Cl 4.1.2.",
    },
    linked_rfi: { id: "RFI-EL-112", status: "Open", match: "curated" },
    linked_activity: { id: "DC1-04-EL-030", name: "LV switchgear 415V — procurement & delivery", on_critical_path: false },
  },
  {
    id: "SHP-003",
    procurement_item: "Busway 4000A",
    wbs_id: "DC1-04-EL-050",
    tier1_supplier: { name: "Vaigai Busbar Fabricators", city: "Chennai", country: "India", lat: 13.0827, lon: 80.2707 },
    tier2_suppliers: [{ name: "Konkan Copper Traders", city: "Mumbai", country: "India", lat: 19.0760, lon: 72.8777 }],
    milestones: [
      { stage: "ordered", tier: 1, planned_day: 150, actual_day: 150, projected_day: null },
      { stage: "tier2_dispatched", tier: 2, planned_day: 160, actual_day: 166, projected_day: null },
      { stage: "tier2_delivered_to_tier1", tier: 2, planned_day: 165, actual_day: 174, projected_day: null },
      { stage: "tier1_in_production", tier: 1, planned_day: 170, actual_day: null, projected_day: 179 },
      { stage: "tier1_dispatched", tier: 1, planned_day: 195, actual_day: null, projected_day: 204 },
      { stage: "arrived_at_site", tier: 1, planned_day: 205, actual_day: null, projected_day: 214 },
    ],
    current_stage: "tier2_delivered_to_tier1",
    required_on_site_by: 220,
    projected_arrival_day: 214,
    days_at_risk: 0,
    on_critical_path: false,
    root_cause: null,
    alternatives: [
      { supplier: "Godavari Busbar Works", city: "Hyderabad", country: "India", lat: 17.3850, lon: 78.4867, lead_time_days: 45, cost_premium_pct: 12, viable: true, projected_arrival_day: 220 },
    ],
    equipment_spec: NOT_APPLICABLE_SPEC,
    linked_rfi: { id: "RFI-FIRE-020", status: "Open", match: "retrieved" },
    linked_activity: { id: "DC1-04-EL-050", name: "LV switchgear installation & busway", on_critical_path: false },
  },
  {
    id: "SHP-004",
    procurement_item: "Chiller plant",
    wbs_id: "DC1-04-ME-010",
    tier1_supplier: { name: "Neelkanth Thermal Systems", city: "Pune", country: "India", lat: 18.5204, lon: 73.8567 },
    tier2_suppliers: [],
    milestones: [
      { stage: "ordered", tier: 1, planned_day: 90, actual_day: 90, projected_day: null },
      { stage: "tier1_in_production", tier: 1, planned_day: 110, actual_day: 108, projected_day: null },
      { stage: "tier1_dispatched", tier: 1, planned_day: 165, actual_day: null, projected_day: null },
      { stage: "arrived_at_site", tier: 1, planned_day: 178, actual_day: null, projected_day: null },
    ],
    current_stage: "tier1_in_production",
    required_on_site_by: 225,
    projected_arrival_day: 178,
    days_at_risk: 0,
    on_critical_path: false,
    root_cause: null,
    alternatives: [],
    equipment_spec: NOT_APPLICABLE_SPEC,
    linked_rfi: null,
    linked_activity: { id: "DC1-04-ME-010", name: "Chilled-water plant & piping", on_critical_path: false },
  },
  {
    id: "SHP-005",
    procurement_item: "CRAH 150kW",
    wbs_id: "DC1-04-ME-020",
    tier1_supplier: { name: "Coromandel Coolair", city: "Bengaluru", country: "India", lat: 12.9716, lon: 77.5946 },
    tier2_suppliers: [],
    milestones: [
      { stage: "ordered", tier: 1, planned_day: 130, actual_day: 130, projected_day: null },
      { stage: "tier1_in_production", tier: 1, planned_day: 155, actual_day: 155, projected_day: null },
      { stage: "tier1_dispatched", tier: 1, planned_day: 205, actual_day: null, projected_day: null },
      { stage: "arrived_at_site", tier: 1, planned_day: 215, actual_day: null, projected_day: null },
    ],
    current_stage: "tier1_in_production",
    required_on_site_by: 250,
    projected_arrival_day: 215,
    days_at_risk: 0,
    on_critical_path: true,
    root_cause: null,
    alternatives: [],
    equipment_spec: NOT_APPLICABLE_SPEC,
    linked_rfi: { id: "RFI-MEP-090", status: "Answered", match: "retrieved" },
    linked_activity: { id: "DC1-04-ME-020", name: "CRAH units (N+1) install & pipe-up", on_critical_path: true },
  },
  {
    id: "SHP-006",
    procurement_item: "Raised access floor",
    wbs_id: "DC1-03-AF-030",
    tier1_supplier: { name: "Marina Floor Systems", city: "Chennai", country: "India", lat: 13.0827, lon: 80.2707 },
    tier2_suppliers: [],
    milestones: [
      { stage: "ordered", tier: 1, planned_day: 90, actual_day: 90, projected_day: null },
      { stage: "tier1_in_production", tier: 1, planned_day: 110, actual_day: 108, projected_day: null },
      { stage: "tier1_dispatched", tier: 1, planned_day: 165, actual_day: null, projected_day: null },
      { stage: "arrived_at_site", tier: 1, planned_day: 178, actual_day: null, projected_day: null },
    ],
    current_stage: "tier1_in_production",
    required_on_site_by: 225,
    projected_arrival_day: 178,
    days_at_risk: 0,
    on_critical_path: true,
    root_cause: null,
    alternatives: [],
    equipment_spec: NOT_APPLICABLE_SPEC,
    linked_rfi: { id: "RFI-ARC-031", status: "Answered", match: "retrieved" },
    linked_activity: { id: "DC1-03-AF-030", name: "Anti-static raised access floor (white space)", on_critical_path: true },
  },
];

// detected_at_day mirrors mockSupplyChainAlerts below (both derive from the
// same real _detected_at_day() milestone scan in backend/app/supply_chain.py).
const _MOCK_DETECTED_AT_DAY: Record<string, number> = { "SHP-001": 130, "SHP-002": 135 };

export const mockSupplyChainRisks: SupplyChainRisk[] = mockShipments
  .filter((s) => s.days_at_risk > 0)
  .map((s) => {
    const detectedAtDay = _MOCK_DETECTED_AT_DAY[s.id] ?? 175;
    return {
      shipment_id: s.id,
      procurement_item: s.procurement_item,
      wbs_id: s.wbs_id,
      days_at_risk: s.days_at_risk,
      detected_at_day: detectedAtDay,
      lead_time_at_detection_days: s.required_on_site_by - detectedAtDay,
      days_until_required: s.required_on_site_by - 175,
      root_cause: s.root_cause,
      recommended_alternative: s.alternatives.find((a) => a.viable) ?? null,
      on_critical_path: s.on_critical_path,
      linked_rfi: s.linked_rfi,
      linked_activity: s.linked_activity,
    };
  })
  .sort((a, b) => Number(b.on_critical_path) - Number(a.on_critical_path) || b.days_at_risk - a.days_at_risk);

// Severity + detected_at_day mirror the real rule in backend/app/supply_chain.py
// (_alert_severity / _detected_at_day) — an in-app alert log, not a push channel.
export const mockSupplyChainAlerts: SupplyChainAlert[] = [
  {
    id: "ALERT-SHP-001",
    shipment_id: "SHP-001",
    procurement_item: "DRUPS 2.5MW",
    severity: "WARNING",
    message: "DRUPS 2.5MW (SHP-001) is 5d at risk of missing its required-on-site date.",
    detected_at_day: 130,
    lead_time_at_detection_days: 85,
    advance_warning_days: 45,
    days_at_risk: 5,
    on_critical_path: false,
  },
  {
    id: "ALERT-SHP-002",
    shipment_id: "SHP-002",
    procurement_item: "LV switchgear 4000A",
    severity: "WARNING",
    message: "LV switchgear 4000A (SHP-002) is 5d at risk of missing its required-on-site date.",
    detected_at_day: 135,
    lead_time_at_detection_days: 85,
    advance_warning_days: 40,
    days_at_risk: 5,
    on_critical_path: false,
  },
];

export const mockSupplyChainMeta: SupplyChainMeta = {
  as_of_day: 175,
  as_of_date: "2026-06-29",
  note: "Shipment status and delay projections are computed by diffing a static milestone snapshot " +
    "against this as-of day — a point-in-time demo dataset, not a live carrier-tracking feed. The " +
    "arithmetic (delay propagation, root cause, alternative viability) is real; the underlying data " +
    "is REPRESENTATIVE synthetic input.",
};

export const mockSupplyChainMap: SupplyChainMap = {
  points: [
    { id: "site", kind: "site", shipment_id: null, city: SITE_PT.city, country: SITE_PT.country, lat: SITE_PT.lat, lon: SITE_PT.lon, at_risk: false },
    ...mockShipments.flatMap((s) => [
      { id: `${s.id}-tier1`, kind: "tier1" as const, shipment_id: s.id, label: s.tier1_supplier.name, city: s.tier1_supplier.city, lat: s.tier1_supplier.lat, lon: s.tier1_supplier.lon, at_risk: s.days_at_risk > 0, equipment_spec_status: s.equipment_spec.status },
      ...s.tier2_suppliers.map((t2) => ({ id: `${s.id}-tier2-${t2.name}`, kind: "tier2" as const, shipment_id: s.id, label: t2.name, city: t2.city, lat: t2.lat, lon: t2.lon, at_risk: s.days_at_risk > 0 })),
    ]),
  ],
  routes: mockShipments.flatMap((s) => [
    ...s.tier2_suppliers.map((t2) => ({ shipment_id: s.id, from: { lat: t2.lat, lon: t2.lon }, to: { lat: s.tier1_supplier.lat, lon: s.tier1_supplier.lon }, tier: 2, at_risk: s.days_at_risk > 0 })),
    { shipment_id: s.id, from: { lat: s.tier1_supplier.lat, lon: s.tier1_supplier.lon }, to: { lat: SITE_PT.lat, lon: SITE_PT.lon }, tier: 1, at_risk: s.days_at_risk > 0 },
  ]),
};

// Project Timeline (P0) — a small, representative slice of the real aggregation
// shape (7 phase bands, one event per pillar including a cross-pillar link),
// used only when the backend is unreachable.
export const mockTimeline: TimelineData = {
  project_start: "2026-01-05",
  today_day: 175,
  phase_bands: [
    { phase: "Enabling", start_day: 0, end_day: 48 },
    { phase: "Civil/Structural", start_day: 45, end_day: 175 },
    { phase: "Architecture/Finishes", start_day: 160, end_day: 240 },
    { phase: "MEP", start_day: 120, end_day: 258 },
    { phase: "White-Space Fit-out", start_day: 250, end_day: 273 },
    { phase: "Commissioning L1-L5", start_day: 110, end_day: 313 },
    { phase: "Snagging", start_day: 313, end_day: 337 },
  ],
  events: [
    {
      id: "tl-ncr-NCR-0002",
      day: 56,
      pillar: "compliance",
      kind: "ncr",
      severity: "HIGH",
      title: "Footing F-12 nominal cover — HIGH NCR",
      detail: "Nominal cover to reinforcement for footing F-12 does not meet the governing severe-exposure clause.",
      link_route: "/compliance",
      linked_event_ids: [],
    },
    {
      id: "tl-rfi-RFI-EL-112",
      day: 137,
      pillar: "copilot",
      kind: "rfi",
      severity: "MEDIUM",
      title: "RFI-EL-112 — LV switchgear delivery vs critical path",
      detail: "Vendor indicates LV switchgear lead time slipping by ~6 weeks. Confirm impact on commissioning L4 milestone.",
      link_route: "/copilot",
      linked_event_ids: ["tl-alert-ALERT-SHP-002", "tl-risk-DC1-04-EL-030"],
    },
    {
      id: "tl-risk-DC1-04-EL-030",
      day: 130,
      pillar: "schedule",
      kind: "risk",
      severity: "MEDIUM",
      title: "LV switchgear 415V — procurement & delivery — predicted 25d slip",
      detail: "Long-lead LV switchgear 4000A vendor status 'slipping' feeding the critical path.",
      link_route: "/schedule",
      linked_event_ids: ["tl-alert-ALERT-SHP-002", "tl-miss-SHP-002"],
    },
    {
      id: "tl-alert-ALERT-SHP-002",
      day: 135,
      pillar: "supply_chain",
      kind: "alert",
      severity: "MEDIUM",
      title: "LV switchgear 4000A — WARNING alert",
      detail: "LV switchgear 4000A (SHP-002) is at risk of missing its required-on-site date.",
      link_route: "/supply-chain",
      linked_event_ids: ["tl-rfi-RFI-EL-112", "tl-risk-DC1-04-EL-030"],
    },
    {
      id: "tl-cqa-CT-003",
      day: 174,
      pillar: "commissioning",
      kind: "finding",
      severity: "HIGH",
      title: "White Space Zone C — Fail",
      detail: "supply air temp: 34.0 degC",
      link_route: "/commissioning",
      linked_event_ids: [],
    },
  ],
};
