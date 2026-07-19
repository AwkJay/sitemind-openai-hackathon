"""Shared data contracts for SiteMind. The frontend depends on these shapes — keep them stable."""
from __future__ import annotations
from typing import Literal, Optional
from pydantic import BaseModel


class Citation(BaseModel):
    standard: str            # e.g. "IS 456:2000"
    clause: str              # e.g. "26.4.2.2"
    text: str                # exact clause text (from clauses.json / the Codebook standards service)
    verify_url: str          # link to the real source clause
    # "codebook_verified": fetched verbatim via Codebook's digitised-standards index (IS/IRC/IRS
    # corpus) — the default and the project's normal integrity bar. "cross_source_unverified": NOT
    # fetched from a single verified primary document — compiled from convergent public
    # secondary sources because the primary standard is paywalled/inaccessible (e.g.
    # ASHRAE TC9.9's book). "primary_scan_ocr": IS the real primary document (a genuine
    # BIS/government standard), but extracted via OCR from an older scanned edition —
    # text is verbatim from the scan, but (a) the edition may not be current, and (b) OCR
    # can introduce transcription errors, so only sentences verified clean/legible are
    # used. "primary_native_pdf": IS the real primary document (genuine BIS/CEA text),
    # extracted directly from a clean NATIVE (non-scanned) PDF — no OCR-transcription risk
    # at all, and may be the current edition (unlike primary_scan_ocr, which is often an
    # older scanned reprint) — but still not fetched via Codebook, so it carries
    # whatever edition-currency caveat applies to that specific document (stated per-clause).
    # Must be disclosed in the UI whenever it's not codebook_verified; never silently
    # presented as equivalent to a Codebook-verified citation.
    source_type: Literal[
        "codebook_verified", "cross_source_unverified", "primary_scan_ocr", "primary_native_pdf"
    ] = "codebook_verified"


class SourceSpan(BaseModel):
    """Proves the extracted value came from the document, not the model's imagination."""
    quote: str               # the exact sentence the parameter was read from
    location: str            # e.g. "General Note 7" / "DBR §4.2" / "page 3"


class NCR(BaseModel):
    """Pillar 1 output. severity ADVISORY = a cited judgment call, not a binary fail."""
    id: str
    item: str
    severity: Literal["LOW", "MEDIUM", "HIGH", "ADVISORY"]
    finding: str
    source: Optional[SourceSpan] = None
    citation: Optional[Citation] = None
    why_it_matters: str
    corrective_action: str
    recommendation: Optional[str] = None     # for ADVISORY
    confirm_with: Optional[str] = None        # for ADVISORY, e.g. "EOR"
    governing_note: Optional[str] = None      # set when >1 clause governs this parameter
    status: Literal["OPEN", "CLOSED"] = "OPEN"
    domain: Literal["structural", "electrical", "mechanical"] = "structural"  # from Check.domain (checks.py); commissioning.py sets "mechanical" explicitly


class OverlapNote(BaseModel):
    """A parameter governed by more than one clause: surface all, name the binding one."""
    item: str
    param: str
    clauses: list[str]       # human-readable clause refs that all govern this param
    governing: str           # the binding (strictest) clause ref
    note: str                # plain-language explanation of the resolution


class CoverageStat(BaseModel):
    """Honest depth-of-review metric — derived from the run, never asserted."""
    standards: list[str]     # distinct standards touched, e.g. ["IS 456:2000", ...]
    clauses_cited: int       # distinct clauses cited in this review
    checks_run: int          # deterministic checks executed
    library_clauses: int     # total real clauses available in the digitised library
    standards_by_domain: dict[str, list[str]] = {}  # e.g. {"structural": [...], "electrical": [...]}


class ComplianceResult(BaseModel):
    document: str
    checked_params: int
    ncrs: list[NCR]
    conforming: list[str]    # human-readable list of params that passed
    overlaps: list[OverlapNote] = []
    coverage: Optional[CoverageStat] = None


class RFIAnswer(BaseModel):          # Pillar 2 output
    answer: str
    sources: list[dict]              # [{label, detail, verify_url?}]
    seen_before: Optional[dict] = None   # {rfi_id, summary, resolution}


# --------------------------------------------------------------------------- #
# Supply Chain Visibility (extends the schedule pillar's procurement fields)
# --------------------------------------------------------------------------- #
class SupplyPoint(BaseModel):
    name: str
    city: str
    country: str
    lat: float
    lon: float


class Milestone(BaseModel):
    stage: str
    tier: int
    planned_day: int
    actual_day: Optional[int] = None     # null = not yet reached (never asserted early)
    projected_day: Optional[int] = None  # computed: carries forward the observed delay; null if on/ahead of plan


class ProcurementAlternative(BaseModel):
    supplier: str
    city: str
    country: str
    lat: float
    lon: float
    lead_time_days: int
    cost_premium_pct: float
    viable: bool          # real arithmetic: would switching today still land by required_on_site_by?
    projected_arrival_day: int


class DeclaredSpec(BaseModel):
    """Vendor-submittal voltage rating, per IS 8623-1:1993 Cl 5.1 nameplate items g/h."""
    rated_operational_voltage_v: Optional[float] = None
    rated_insulation_voltage_v: Optional[float] = None


class EquipmentSpecCheck(BaseModel):
    """Pillar 4 extension: equipment-spec compliance (IS 8623-1:1993-derived subset).
    Only applies where a real primary standard in the corpus actually covers the
    equipment category — everything else is honestly NOT_APPLICABLE rather than
    force-fit against a standard that doesn't govern it."""
    standard_applicable: bool
    status: Literal["MATCH", "MISMATCH", "SPEC_NOT_PROVIDED", "NOT_APPLICABLE"]
    declared_spec: Optional[DeclaredSpec] = None
    citation: Optional[Citation] = None
    note: str


class Shipment(BaseModel):
    id: str
    procurement_item: str
    wbs_id: str
    tier1_supplier: SupplyPoint
    tier2_suppliers: list[SupplyPoint]
    milestones: list[Milestone]
    current_stage: str
    required_on_site_by: int          # derived from the schedule DAG, never hand-asserted
    projected_arrival_day: int        # computed by propagating the observed delay forward
    days_at_risk: int                 # max(0, projected_arrival_day - required_on_site_by)
    on_critical_path: bool
    root_cause: Optional[str] = None  # names the first slipped milestone (which tier), if any
    alternatives: list[ProcurementAlternative]
    equipment_spec: EquipmentSpecCheck
    # Evidence links (evidence_links.py) — computed from a real shared key
    # (wbs_id verbatim in an RFI's Ref text, or the real schedule DAG), never
    # hardcoded; None when no defensible match exists.
    linked_rfi: Optional[LinkedRFI] = None
    linked_activity: Optional[AffectedActivity] = None


class SupplyChainAlert(BaseModel):
    """An in-app, timestamped alert-log entry — NOT a push/email/SMS/webhook
    notification (no such delivery channel exists in this project; adding a fake
    'notification sent' claim would violate the no-asserted-numbers rule).
    `detected_at_day` is the REAL day the underlying delay first became visible
    in the milestone data — the day the system COULD have raised this alert.

    Two distinct, non-interchangeable time metrics live on this record (a UI
    review 2026-07-08 found both had been labelled "advance warning", which
    reads as a data bug when their values legitimately differ per shipment):
    - `lead_time_at_detection_days` is the brief's literal "schedule risk
      prediction lead time" metric — required_on_site_by - detected_at_day,
      FIXED at detection time, does not shrink as the clock advances. This is
      the headline number to show.
    - `advance_warning_days` is "how many days ago this was flagged"
      (today - detected_at_day) — grows every day, useful only as an
      "active since" caption, never billed as the same thing as the above."""
    id: str
    shipment_id: str
    procurement_item: str
    severity: Literal["INFO", "WARNING", "CRITICAL"]
    message: str
    detected_at_day: int
    lead_time_at_detection_days: int  # required_on_site_by - detected_at_day; FIXED, the brief's lead-time metric
    advance_warning_days: int      # today - detected_at_day; GROWS daily, "flagged N days ago" caption only
    days_at_risk: int
    on_critical_path: bool


class SupplyChainRisk(BaseModel):
    shipment_id: str
    procurement_item: str
    wbs_id: str
    days_at_risk: int
    detected_at_day: Optional[int] = None
    lead_time_at_detection_days: int  # same FIXED metric as SupplyChainAlert, mirrored here
    days_until_required: int          # required_on_site_by - today; SHRINKS daily ("runway remaining")
    root_cause: Optional[str] = None
    recommended_alternative: Optional[ProcurementAlternative] = None
    on_critical_path: bool
    linked_rfi: Optional[LinkedRFI] = None
    linked_activity: Optional[AffectedActivity] = None


class MitigationOption(BaseModel):
    """One specialist agent's grounded finding (agents/mitigation.py). Never
    free-form LLM reasoning — each field traces to a real computation (CPM float,
    a real supply-chain alternative, or real progress-rate arithmetic). Non-viable
    options are included too, transparently, same honesty discipline as Supply
    Chain's own 'no viable alternative' case."""
    agent: Literal["procurement_alternative", "resequencing_float", "resource_recovery"]
    viable: bool
    days_recovered: int                     # how much of predicted_slip_days this option addresses
    cost_premium_pct: Optional[float] = None  # only procurement_alternative sets this
    summary: str
    detail: str


class RiskItem(BaseModel):           # Pillar 3 output (CPM + rules)
    activity: str
    wbs_id: str
    on_critical_path: bool
    predicted_slip_days: int
    detected_lead_time_days: int     # vs naive baseline (the brief's metric)
    drivers: list[str]               # explainable reasons
    mitigation: str
    downstream_activities: list[str] = []   # direct CPM successors (real DAG edges)
    project_impact_days: int = 0            # re-run CPM with the predicted slip applied;
                                             # 0 if the slip is absorbed by float (not on critical path)
    # Multi-agent mitigation-option generation (added 2026-07-03) — the brief's ONLY
    # explicit "multi-agent system" ask (Predictive Schedule Risk Engine bullet):
    # several specialist agents, each a real computation, never LLM reasoning.
    mitigation_options: list[MitigationOption] = []


class BriefParameter(BaseModel):
    name: str
    value: str
    source: Optional[SourceSpan] = None


class BriefCheck(BaseModel):
    clause: Optional[Citation] = None
    requirement: str
    result: Literal["FAIL", "ADVISORY"]
    engine: Literal["deterministic"] = "deterministic"


class LinkedRFI(BaseModel):
    id: str
    status: str
    match: Literal["curated", "retrieved"]
    subject: str = ""
    question: str = ""


class AffectedActivity(BaseModel):
    id: str
    name: str
    on_critical_path: bool


class RecommendedAction(BaseModel):
    owner_role: str
    action: str
    note: str


class Confidence(BaseModel):
    level: Literal["high", "medium", "low"]
    basis: str


class ActionBrief(BaseModel):
    """Evidence-backed summary linking a compliance finding to related RFI/schedule
    evidence. Every field is extracted-with-span, cited, or a deterministic result —
    `confidence` is an enum tied to conditions (never a fabricated %), and
    `computed_impact` stays null unless a transparent formula with visible
    assumptions exists. Contract agreed in update_plan_draft.md."""
    finding_id: str
    parameter: BriefParameter
    check: BriefCheck
    status: Literal["NCR", "REVIEW_REQUIRED"]
    linked_rfi: Optional[LinkedRFI] = None
    affected_activity: Optional[AffectedActivity] = None
    recommended_action: Optional[RecommendedAction] = None
    confidence: Confidence
    evidence: list[str]
    computed_impact: Optional[dict] = None


# --------------------------------------------------------------------------- #
# Commissioning QA (Pillar 5, cooling-only slice — see docs/codes.txt for scope)
# --------------------------------------------------------------------------- #
class TestRecord(BaseModel):
    test_id: str
    system: str                       # "cooling" | "power" | "IT" (only "cooling" is checked)
    parameter: str                    # e.g. "supply_air_temp", "return_air_rh"
    measured_value: float
    unit: str
    timestamp: str
    location_zone: str
    equipment_class: str = "A1"       # ASHRAE class this zone is designed to, default A1


class CommissioningFinding(BaseModel):
    test_id: str
    location_zone: str
    parameter: str
    measured_value: float
    unit: str
    verdict: Literal["PASS", "OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE", "FAIL", "NOT_CHECKABLE"]
    recommended_range: Optional[str] = None
    allowable_range: Optional[str] = None
    citation: Optional[Citation] = None
    ncr: Optional[NCR] = None


class QualityPackage(BaseModel):
    """As-commissioned quality package: every test record + verdict, compiled into
    one exportable report. `corpus_limitation` must always be present and shown —
    this pillar checks ONLY the cooling/thermal envelope, and the envelope values
    are cross_source_unverified (see Citation.source_type)."""
    run_id: str
    generated_at: str
    corpus_limitation: str
    total_records: int
    pass_count: int
    within_allowable_count: int
    fail_count: int
    not_checkable_count: int
    findings: list[CommissioningFinding]


class PillarImpact(BaseModel):
    """One pillar's contribution to the platform-wide hours/₹ ROI (impact.py).
    `basis` states the exact computed inputs x documented per-unit assumption —
    shown in the UI so the number is defensible, never a bare figure."""
    pillar: Literal["compliance", "schedule", "supply_chain", "commissioning"]
    hours_saved: int
    inr_saved: int
    basis: str


class CostRiskComponent(BaseModel):
    """One term of the cost-at-risk formula (cost_risk.py). `basis` states the exact
    computed inputs x documented rate/base-cost so the number is defensible, never
    a bare figure — same transparency pattern as PillarImpact.basis."""
    label: str
    inr: int
    basis: str


class CostRisk(BaseModel):
    """Deterministic cost-at-risk = schedule_delay_cost + expedite_premium_cost +
    rework_exposure (see cost_risk.py). NOT probabilistic/ML — a transparent formula,
    matching the project's no-ML, explainable-decisions thesis. `data_note` discloses
    that the per-item base costs are REPRESENTATIVE synthetic data (see
    cost_basis.json), even though the formula and its live inputs are real."""
    total_inr: int
    components: list[CostRiskComponent]
    data_note: str


class PhaseBand(BaseModel):
    """One project build phase (Enabling, Civil/Structural, ...) as a lane on
    the Timeline. start_day/end_day are the real min/max of that phase's
    activities' CPM-scheduled windows -- taken from schedule.csv's own `phase`
    column, never a hardcoded date range."""
    phase: str
    start_day: int
    end_day: int


class TimelineEvent(BaseModel):
    """One event on the Project Timeline (timeline.py) -- pure aggregation of
    a finding/alert/risk/RFI that another pillar's module already computed.
    `day` always traces to a real field (a submittal's Date Submitted, an
    RFI's Date, a shipment's detected_at_day/projected_arrival_day, an
    activity's planned_start_day, a test record's timestamp) -- never
    invented. `linked_event_ids` are computed via evidence_links.py's shared
    real-key matching and are always symmetric (see eval/run_timeline_eval.py)."""
    id: str
    day: int
    pillar: Literal["compliance", "copilot", "schedule", "supply_chain", "commissioning"]
    kind: str
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]
    title: str
    detail: str
    link_route: str
    linked_event_ids: list[str] = []


class TimelineData(BaseModel):
    project_start: str
    today_day: int
    phase_bands: list[PhaseBand]
    events: list[TimelineEvent]


class MachineScaleStats(BaseModel):
    """Raw processing-scale counts for the Overview hero — deliberately NOT the
    same thing as issues_caught/hours_saved below (those are outcomes; these are
    inputs/throughput). Every count here is read from the same computations the
    pillar pages already display — never a typed constant — so a judge can check
    a number here against its pillar page and find them equal."""
    documents_read: int           # len(load_submittals()) — same source as the Compliance doc register
    clauses_checked: int          # sum of CoverageStat.clauses_cited across all evaluated documents
    cross_references_found: int   # shipments with a real linked_rfi (curated/TF-IDF match, evidence_links.py)
    conflicts_surfaced: int       # sum of OverlapNote entries across all evaluated documents


class OverviewStats(BaseModel):
    project: str
    issues_caught: int
    engineer_hours_saved: int
    rework_avoided_inr: int
    open_ncrs_by_severity: dict
    schedule_at_risk: int
    by_pillar: list[PillarImpact] = []
    machine_scale: Optional[MachineScaleStats] = None
