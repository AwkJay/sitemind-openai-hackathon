// Mirrors backend/app/schemas.py — keep in sync with CONTRACT.md

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "ADVISORY";
export type NcrStatus = "OPEN" | "CLOSED";

// Mirrors backend/app/schemas.py Citation.source_type — the honest provenance
// disclosure. "manak_verified" (displayed to users as "Codebook") is the
// default/gold standard; the other three are non-Codebook primary-source
// extractions, each with a different reliability caveat, and must never be
// presented as equivalent to a Codebook citation.
export type SourceType =
  | "manak_verified"
  | "cross_source_unverified"
  | "primary_scan_ocr"
  | "primary_native_pdf";

export interface Citation {
  standard: string; // e.g. "IS 456:2000"
  clause: string; // e.g. "26.4.2.2"
  text: string; // exact clause text
  verify_url: string;
  source_type?: SourceType; // defaults to "manak_verified" server-side
}

export interface SourceSpan {
  quote: string;
  location: string; // e.g. "General Note 7"
}

export interface NCR {
  id: string;
  item: string;
  severity: Severity;
  finding: string;
  source?: SourceSpan | null;
  citation?: Citation | null;
  why_it_matters: string;
  corrective_action: string;
  recommendation?: string | null; // ADVISORY
  confirm_with?: string | null; // ADVISORY, e.g. "EOR"
  governing_note?: string | null; // set when >1 clause governs this parameter
  status?: NcrStatus;
  domain?: "structural" | "electrical" | "mechanical"; // from the real Check.domain (compliance) or commissioning.py, defaults structural
}

export interface OverlapNote {
  item: string;
  param: string;
  clauses: string[]; // clause refs that all govern this param
  governing: string; // the binding (strictest) clause ref
  note: string;
}

export interface CoverageStat {
  standards: string[];
  clauses_cited: number;
  checks_run: number;
  library_clauses: number;
  standards_by_domain?: Record<string, string[]>; // e.g. { structural: [...], electrical: [...] }
}

export interface ComplianceResult {
  document: string;
  checked_params: number;
  ncrs: NCR[];
  conforming: string[];
  overlaps?: OverlapNote[];
  coverage?: CoverageStat | null;
}

export type DocType = "design_basis" | "submittal" | "mix_design" | "rfi";

export interface DocItem {
  id: string;
  title: string;
  type: DocType;
  status: string; // "A – Approved" | "B – Approved as Noted" | "C – Revise & Resubmit" | "Pending"
  discipline: string;
}

export interface RFISource {
  label: string;
  detail: string;
  verify_url?: string;
}

export interface SeenBefore {
  rfi_id: string;
  summary: string;
  resolution: string;
}

export interface RFIAnswer {
  answer: string;
  sources: RFISource[];
  seen_before?: SeenBefore | null;
}

export type MitigationAgent = "procurement_alternative" | "resequencing_float" | "resource_recovery";

export interface MitigationOption {
  agent: MitigationAgent;
  viable: boolean;
  days_recovered: number;
  cost_premium_pct?: number | null;
  summary: string;
  detail: string;
}

export interface RiskItem {
  activity: string;
  wbs_id: string;
  on_critical_path: boolean;
  predicted_slip_days: number;
  detected_lead_time_days: number;
  drivers: string[];
  mitigation: string;
  downstream_activities: string[];
  project_impact_days: number;
  mitigation_options?: MitigationOption[];
}

// ── Supply Chain Visibility ─────────────────────────────────────────────────

export interface SupplyPoint {
  name: string;
  city: string;
  country: string;
  lat: number;
  lon: number;
}

export interface ShipmentMilestone {
  stage: string;
  tier: number;
  planned_day: number;
  actual_day: number | null;
  projected_day: number | null;
}

export interface ProcurementAlternative {
  supplier: string;
  city: string;
  country: string;
  lat: number;
  lon: number;
  lead_time_days: number;
  cost_premium_pct: number;
  viable: boolean;
  projected_arrival_day: number;
}

// Equipment-spec compliance (IS 8623-1:1993-derived subset) — only LV switchgear
// is covered by a real standard today; every other category is honestly
// NOT_APPLICABLE rather than force-fit. See supply_chain.py.
export interface DeclaredSpec {
  rated_operational_voltage_v: number | null;
  rated_insulation_voltage_v: number | null;
}

export interface EquipmentSpecCheck {
  standard_applicable: boolean;
  status: "MATCH" | "MISMATCH" | "SPEC_NOT_PROVIDED" | "NOT_APPLICABLE";
  declared_spec?: DeclaredSpec | null;
  citation?: Citation | null;
  note: string;
}

export interface Shipment {
  id: string;
  procurement_item: string;
  wbs_id: string;
  tier1_supplier: SupplyPoint;
  tier2_suppliers: SupplyPoint[];
  milestones: ShipmentMilestone[];
  current_stage: string;
  required_on_site_by: number;
  projected_arrival_day: number;
  days_at_risk: number;
  on_critical_path: boolean;
  root_cause: string | null;
  alternatives: ProcurementAlternative[];
  equipment_spec: EquipmentSpecCheck;
  linked_rfi?: LinkedRFI | null;
  linked_activity?: AffectedActivity | null;
}

export type AlertSeverity = "INFO" | "WARNING" | "CRITICAL";

export interface SupplyChainAlert {
  id: string;
  shipment_id: string;
  procurement_item: string;
  severity: AlertSeverity;
  message: string;
  detected_at_day: number;
  /** FIXED at detection (required_on_site_by - detected_at_day) — the brief's lead-time metric. */
  lead_time_at_detection_days: number;
  /** GROWS daily (today - detected_at_day) — "flagged N days ago" caption only, not the same metric. */
  advance_warning_days: number;
  days_at_risk: number;
  on_critical_path: boolean;
}

export interface SupplyChainMeta {
  as_of_day: number;
  as_of_date: string;
  note: string;
}

export interface SupplyChainRisk {
  shipment_id: string;
  procurement_item: string;
  wbs_id: string;
  days_at_risk: number;
  detected_at_day?: number | null;
  /** Same FIXED metric as SupplyChainAlert.lead_time_at_detection_days. */
  lead_time_at_detection_days: number;
  /** SHRINKS daily (required_on_site_by - today) — "runway remaining", a different concept. */
  days_until_required: number;
  root_cause: string | null;
  recommended_alternative: ProcurementAlternative | null;
  on_critical_path: boolean;
  linked_rfi?: LinkedRFI | null;
  linked_activity?: AffectedActivity | null;
}

export interface MapPoint {
  id: string;
  kind: "site" | "tier1" | "tier2";
  shipment_id: string | null;
  label?: string;
  name?: string;
  city: string;
  country?: string;
  lat: number;
  lon: number;
  at_risk: boolean;
  equipment_spec_status?: EquipmentSpecCheck["status"]; // present on tier1 points only
}

export interface MapRoute {
  shipment_id: string;
  from: { lat: number; lon: number };
  to: { lat: number; lon: number };
  tier: number;
  at_risk: boolean;
}

export interface SupplyChainMap {
  points: MapPoint[];
  routes: MapRoute[];
}

export interface GanttBar {
  wbs_id: string;
  task: string;
  phase: string;
  start_day: number;
  duration_days: number;
  on_critical_path: boolean;
  at_risk: boolean;
  /** Joined from /schedule/risks; 0 when not at risk. Baseline bar never moves — this extends it. */
  predicted_slip_days: number;
  /** Joined from /schedule/risks; [] when not at risk. */
  drivers: string[];
}

export type ImpactPillar =
  | "compliance"
  | "schedule"
  | "supply_chain"
  | "commissioning";

export interface PillarImpact {
  pillar: ImpactPillar;
  hours_saved: number;
  inr_saved: number;
  basis: string;
}

export interface CostRiskComponent {
  label: string;
  inr: number;
  basis: string;
}

export interface CostRisk {
  total_inr: number;
  components: CostRiskComponent[];
  data_note: string;
}

export interface MachineScaleStats {
  documents_read: number;
  clauses_checked: number;
  cross_references_found: number;
  conflicts_surfaced: number;
}

export interface OverviewStats {
  project: string;
  issues_caught: number;
  engineer_hours_saved: number;
  rework_avoided_inr: number;
  open_ncrs_by_severity: Record<string, number>;
  schedule_at_risk: number;
  by_pillar: PillarImpact[];
  machine_scale?: MachineScaleStats | null;
}

// ── Project Timeline (P0) — pure aggregation, mirrors backend/app/schemas.py ──

export type TimelinePillar = "compliance" | "copilot" | "schedule" | "supply_chain" | "commissioning";
export type TimelineSeverity = "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";

export interface PhaseBand {
  phase: string;
  start_day: number;
  end_day: number;
}

export interface TimelineEvent {
  id: string;
  day: number;
  pillar: TimelinePillar;
  kind: string;
  severity: TimelineSeverity;
  title: string;
  detail: string;
  link_route: string;
  linked_event_ids: string[];
}

export interface TimelineData {
  project_start: string;
  today_day: number;
  phase_bands: PhaseBand[];
  events: TimelineEvent[];
}

export type KgNodeType = "equipment" | "spec" | "standard" | "rfi";
export interface KgNode {
  id: string;
  label: string;
  type: KgNodeType;
}
export interface KgEdge {
  source: string;
  target: string;
  label: string;
}
export interface KgGraph {
  nodes: KgNode[];
  edges: KgEdge[];
}

// SSE event shapes for the streaming compliance/copilot endpoints
export type StreamEvent =
  | { type: "reasoning"; text: string }
  | { type: "result"; data: ComplianceResult };

// Real document upload — POST /api/compliance/ingest. No mock fallback: this
// endpoint reads an actual uploaded file, so if the backend is unreachable the
// UI must say so rather than fabricate an extraction.
export interface ExtractedParamPreview {
  param: string;
  element: string;
  value: number;
  unit: string;
  source_quote: string;
}

export interface AbstainedParam {
  param: string;
  reason: string;
}

export interface IngestResult {
  document_id: string;
  title: string;
  extracted: ExtractedParamPreview[];
  abstained: AbstainedParam[];
  checkable_params: number;
}

// Action Brief — GET /api/compliance/action-brief/{document_id}. Every field is
// extracted-with-span, cited, or deterministic; confidence is an enum, never a
// fabricated %; computed_impact stays null unless a transparent formula exists.
export interface BriefParameter {
  name: string;
  value: string;
  source?: SourceSpan | null;
}

export interface BriefCheck {
  clause?: Citation | null;
  requirement: string;
  result: "FAIL" | "ADVISORY";
  engine: "deterministic";
}

export interface LinkedRFI {
  id: string;
  status: string;
  match: "curated" | "retrieved";
  subject?: string;
  question?: string;
}

export interface AffectedActivity {
  id: string;
  name: string;
  on_critical_path: boolean;
}

export interface RecommendedAction {
  owner_role: string;
  action: string;
  note: string;
}

export interface Confidence {
  level: "high" | "medium" | "low";
  basis: string;
}

export interface ActionBrief {
  finding_id: string;
  parameter: BriefParameter;
  check: BriefCheck;
  status: "NCR" | "REVIEW_REQUIRED";
  linked_rfi?: LinkedRFI | null;
  affected_activity?: AffectedActivity | null;
  recommended_action?: RecommendedAction | null;
  confidence: Confidence;
  evidence: string[];
  computed_impact?: Record<string, unknown> | null;
}

// ── Commissioning QA (Pillar 5, cooling-only slice) ─────────────────────────
// Mirrors backend/app/schemas.py. The envelope corpus is cross_source_unverified
// (see Citation.source_type) — every finding/package must show that limitation,
// never presented as Codebook-grade.

export type CommissioningVerdict =
  | "PASS"
  | "OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE"
  | "FAIL"
  | "NOT_CHECKABLE";

export interface CommissioningFinding {
  test_id: string;
  location_zone: string;
  parameter: string;
  measured_value: number;
  unit: string;
  verdict: CommissioningVerdict;
  recommended_range?: string | null;
  allowable_range?: string | null;
  citation?: Citation | null;
  ncr?: NCR | null;
}

export interface QualityPackage {
  run_id: string;
  generated_at: string;
  corpus_limitation: string;
  total_records: number;
  pass_count: number;
  within_allowable_count: number;
  fail_count: number;
  not_checkable_count: number;
  findings: CommissioningFinding[];
}

export interface CommissioningIngestResult {
  run_id: string;
  parsed: number;
  parse_errors: string[];
  package: QualityPackage;
}

// ── Knowledge Base (Phase 3 standalone retrieval package,
// backend/app/retrieval/) ────────────────────────────────────────────────────
// Deliberately independent of the SourceType above (mirrors
// backend/app/retrieval/models.py, which is itself deliberately independent of
// schemas.py — see IMPROVEMENTS.md PHASE 3). "company_uploaded" is the only
// tag the package currently returns; "manak_indexed" / "sitemind_indexed" are
// Phase 3b's planned read-only cross-corpus tags — the UI must keep working
// whether or not those exist yet, and must not crash on any other
// unrecognized string either, since this is not a closed union on the wire.
export type RetrievalSourceType = "company_uploaded" | "manak_indexed" | "sitemind_indexed" | string;

export interface RetrievalCitation {
  chunk_id: string;
  document_id: string;
  filename: string;
  heading?: string | null;
  breadcrumb?: string | null;
  text: string;
  source_type: RetrievalSourceType;
  score: number;
}

export interface RetrievalQueryResult {
  question: string;
  corpus_name: string;
  abstained: boolean;
  floor: number;
  citations: RetrievalCitation[];
}

export interface RetrievalIngestManifest {
  document_id: string;
  corpus_name: string;
  filename: string;
  chunk_count: number;
  structured: boolean;
  provenance_tag: string;
}

export interface RetrievalCorpusSummary {
  corpus_name: string;
  document_count: number;
  chunk_count: number;
  source: string;
  provenance_tag?: string | null;
}

// ── Codebook (standards-service, a separate MCP-serving process; SiteMind's
// backend is an MCP *client* of it — backend/app/codebook_router.py, gated
// behind CODEBOOK_ENABLED) ──────────────────────────────────────────────────
// Codebook's 4 MCP tools (standards-service/app/mcp_server.py) each return
// ONE human-readable text block, not a structured payload — see
// backend/app/codebook_client.py's module docstring for why (mcp==1.9.4 has
// no structured_output passthrough, and re-parsing prose into fields
// client-side would risk silently drifting from what Codebook actually
// said). These types mirror codebook_client.py's returned dicts exactly: a
// `text` field carrying the real rendered block, plus whatever the caller
// already knows about the call (query/corpus/ids) — never a guessed
// structured breakdown of the prose.
export interface CodebookCorporaResult {
  text: string;
}

export interface CodebookSearchResult {
  query: string;
  corpus_name: string | null;
  k: number;
  text: string;
}

export interface CodebookClauseResult {
  document_id: string;
  chunk_id: string;
  text: string;
}

export interface CodebookCheckResult {
  document_path: string;
  corpus_name: string;
  k: number;
  text: string;
}
