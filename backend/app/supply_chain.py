"""Supply Chain Visibility & Risk — extends the schedule pillar's procurement
data (`vendor_status`/`lead_time_days` on schedule.csv) into real multi-tier
shipment tracking: milestone-level delay detection, root-cause attribution
across supplier tiers, and a deterministic procurement-alternative evaluation.

Nothing here is asserted. `required_on_site_by` is derived from the schedule
dependency DAG (the real successor "install" activity), `projected_arrival_day`
is computed by propagating the OBSERVED delay at the last-reached milestone
forward (never invented), and each alternative supplier's `viable` flag is
plain arithmetic against that same required date — including the honest case
where no alternative is viable and the system says so instead of guessing.
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from typing import Optional

from . import clock
from .data_loader import load_schedule, load_supply_chain
from .evidence_links import link_activity, link_rfi
from .schedule import PROJECT_START, TODAY_DAY, _cpm
from .schemas import (
    DeclaredSpec,
    EquipmentSpecCheck,
    Milestone,
    NCR,
    ProcurementAlternative,
    Shipment,
    SupplyChainAlert,
    SupplyChainRisk,
    SupplyPoint,
)
from .standards import get_clause

router = APIRouter(prefix="/api/supply-chain", tags=["supply-chain"])

# Site coordinates match config.PROJECT_NAME's "Chennai" siting.
SITE = {"name": "Project site", "city": "Chennai", "country": "India", "lat": 13.0827, "lon": 80.2707}


# --------------------------------------------------------------------------- #
# required_on_site_by: derived from the real schedule DAG, never hand-asserted
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=1)
def _by_id() -> dict[str, dict]:
    return {r["wbs_id"]: r for r in load_schedule()}


def _required_on_site_by(wbs_id: str) -> int:
    rows = _by_id()
    row = rows.get(wbs_id)
    if row is None:
        return 0
    # Prefer a real downstream "install" activity's start day (the item is
    # actually consumed then); fall back to this row's own start day.
    candidates = []
    for r in rows.values():
        preds = [p.split("(")[0].strip() for p in (r.get("predecessors") or "").split(",")]
        if wbs_id in preds and "install" in (r.get("task") or "").lower():
            try:
                candidates.append(int(float(r.get("planned_start_day", 0))))
            except (TypeError, ValueError):
                continue
    if candidates:
        return min(candidates)
    try:
        return int(float(row.get("planned_start_day", 0)))
    except (TypeError, ValueError):
        return 0


def _on_critical_path(wbs_id: str) -> bool:
    return wbs_id in _cpm()["critical"]


# --------------------------------------------------------------------------- #
# Delay propagation: compute, never assert
# --------------------------------------------------------------------------- #
def _milestones(raw: list[dict]) -> tuple[list[Milestone], str, int, int]:
    """Returns (milestones-with-projected-day, current_stage, current_delay, final_planned_day)."""
    current_stage = raw[0]["stage"] if raw else "not_started"
    current_delay = 0
    for m in raw:
        if m.get("actual_day") is not None:
            current_stage = m["stage"]
            current_delay = max(0, int(m["actual_day"]) - int(m["planned_day"]))

    out: list[Milestone] = []
    final_planned = raw[-1]["planned_day"] if raw else 0
    for m in raw:
        projected = None
        if m.get("actual_day") is None and current_delay > 0:
            projected = int(m["planned_day"]) + current_delay
        out.append(
            Milestone(
                stage=m["stage"],
                tier=m["tier"],
                planned_day=m["planned_day"],
                actual_day=m.get("actual_day"),
                projected_day=projected,
            )
        )
    return out, current_stage, current_delay, final_planned


def _root_cause(raw: list[dict]) -> str | None:
    """Names the FIRST milestone that slipped (planned < actual) — the real
    upstream cause, which may be a tier-2 sub-supplier the tier-1 vendor_status
    flag alone would never explain."""
    for m in raw:
        if m.get("actual_day") is not None and int(m["actual_day"]) > int(m["planned_day"]):
            slip = int(m["actual_day"]) - int(m["planned_day"])
            tier_label = "tier-2 sub-supplier" if m["tier"] == 2 else "tier-1 supplier"
            return f"{m['stage'].replace('_', ' ')} slipped {slip}d ({tier_label})"
    return None


def _point(d: dict) -> SupplyPoint:
    return SupplyPoint(name=d["name"], city=d["city"], country=d["country"], lat=d["lat"], lon=d["lon"])


def _alternatives(raw: list[dict], required_on_site_by: int) -> list[ProcurementAlternative]:
    out = []
    for a in raw:
        arrival = clock.current_day() + int(a["lead_time_days"])
        out.append(
            ProcurementAlternative(
                supplier=a["supplier"],
                city=a["city"],
                country=a["country"],
                lat=a["lat"],
                lon=a["lon"],
                lead_time_days=a["lead_time_days"],
                cost_premium_pct=a["cost_premium_pct"],
                viable=arrival <= required_on_site_by,
                projected_arrival_day=arrival,
            )
        )
    return out


# --------------------------------------------------------------------------- #
# Equipment-spec compliance (IS 8623-1:1993-derived subset). Only LV switchgear/
# controlgear assemblies are covered by a real primary standard we hold — every
# other tracked procurement category honestly returns NOT_APPLICABLE rather than
# being force-fit against a standard that doesn't govern it. See PROGRESS.md for
# why this stayed narrow (searched CEA_Safetycons.pdf for the original voltage-
# class/type-test-cert/rating-tolerance ask, found it doesn't cover procurement
# specs; IS 8623-1:1993 — a genuine BIS "LV switchgear and controlgear assemblies"
# standard — does, but only for the switchgear category).
_EQUIPMENT_SPEC_CLAUSE_KEY = {
    "LV switchgear 4000A": "IS8623_1_1993_4.1.2",
}
_EQUIPMENT_SPEC_NAMEPLATE_CLAUSE_KEY = "IS8623_1_1993_5.1"


def _equipment_spec_check(raw: dict) -> EquipmentSpecCheck:
    clause_key = _EQUIPMENT_SPEC_CLAUSE_KEY.get(raw["procurement_item"])
    if clause_key is None:
        return EquipmentSpecCheck(
            standard_applicable=False,
            status="NOT_APPLICABLE",
            declared_spec=None,
            citation=None,
            note="No equipment-spec standard in the corpus yet covers this procurement category "
            "(only LV switchgear/controlgear assemblies, via IS 8623-1:1993, are covered so far).",
        )
    ds_raw = raw.get("declared_spec")
    op_v = (ds_raw or {}).get("rated_operational_voltage_v")
    ins_v = (ds_raw or {}).get("rated_insulation_voltage_v")
    if op_v is None or ins_v is None:
        return EquipmentSpecCheck(
            standard_applicable=True,
            status="SPEC_NOT_PROVIDED",
            declared_spec=DeclaredSpec(**ds_raw) if ds_raw else None,
            citation=get_clause(_EQUIPMENT_SPEC_NAMEPLATE_CLAUSE_KEY),
            note="Rated operational/insulation voltage not declared in the vendor submittal — "
            "cannot verify against IS 8623-1:1993 Cl 5.1's nameplate-information requirement.",
        )
    spec = DeclaredSpec(**ds_raw)
    citation = get_clause(clause_key)
    if op_v > ins_v:
        return EquipmentSpecCheck(
            standard_applicable=True,
            status="MISMATCH",
            declared_spec=spec,
            citation=citation,
            note=f"Declared operational voltage ({op_v:g}V) exceeds declared insulation voltage "
            f"({ins_v:g}V) — violates IS 8623-1:1993 Cl 4.1.2.",
        )
    return EquipmentSpecCheck(
        standard_applicable=True,
        status="MATCH",
        declared_spec=spec,
        citation=citation,
        note=f"Declared operational voltage ({op_v:g}V) is within the declared insulation voltage "
        f"rating ({ins_v:g}V) per IS 8623-1:1993 Cl 4.1.2.",
    )


def _equipment_spec_ncr(shipment_id: str, procurement_item: str, spec: EquipmentSpecCheck) -> NCR | None:
    if spec.status != "MISMATCH":
        return None
    return NCR(
        id=f"NCR-SC-{shipment_id}",
        item=procurement_item,
        severity="HIGH",
        finding=spec.note,
        source=None,
        citation=spec.citation,
        why_it_matters="An operational voltage rating that exceeds the assembly's insulation "
        "voltage rating risks dielectric breakdown under normal load — a data-centre LV "
        "switchboard failure here is an availability risk, not a paperwork gap.",
        corrective_action="Obtain a corrected vendor submittal / nameplate declaration with "
        "rated_insulation_voltage_v >= rated_operational_voltage_v before FAT sign-off.",
    )


def _build(raw: dict) -> Shipment:
    milestones, current_stage, delay, final_planned = _milestones(raw["milestones"])
    required = _required_on_site_by(raw["wbs_id"])
    projected_arrival = final_planned + delay if delay > 0 else final_planned
    days_at_risk = max(0, projected_arrival - required)
    alternatives = _alternatives(raw.get("alternatives", []), required)
    wbs_id = raw["wbs_id"]
    return Shipment(
        id=raw["id"],
        procurement_item=raw["procurement_item"],
        wbs_id=wbs_id,
        tier1_supplier=_point(raw["tier1_supplier"]),
        tier2_suppliers=[_point(t) for t in raw.get("tier2_suppliers", [])],
        milestones=milestones,
        current_stage=current_stage,
        required_on_site_by=required,
        projected_arrival_day=projected_arrival,
        days_at_risk=days_at_risk,
        on_critical_path=_on_critical_path(wbs_id),
        root_cause=_root_cause(raw["milestones"]) if days_at_risk > 0 else None,
        alternatives=alternatives,
        equipment_spec=_equipment_spec_check(raw),
        linked_rfi=link_rfi(wbs_id=wbs_id, query_text=raw["procurement_item"]),
        linked_activity=link_activity(wbs_id),
    )


@lru_cache(maxsize=1)
def shipments() -> list[Shipment]:
    return [_build(raw) for raw in load_supply_chain()]


def _best_alternative(s: Shipment) -> ProcurementAlternative | None:
    viable = [a for a in s.alternatives if a.viable]
    if not viable:
        return None
    return min(viable, key=lambda a: a.projected_arrival_day)


@lru_cache(maxsize=1)
def risks() -> list[SupplyChainRisk]:
    out = []
    for s in shipments():
        if s.days_at_risk <= 0:
            continue
        out.append(
            SupplyChainRisk(
                shipment_id=s.id,
                procurement_item=s.procurement_item,
                wbs_id=s.wbs_id,
                days_at_risk=s.days_at_risk,
                detected_lead_time_days=max(0, s.required_on_site_by - clock.current_day()),
                root_cause=s.root_cause,
                recommended_alternative=_best_alternative(s),
                on_critical_path=s.on_critical_path,
                linked_rfi=s.linked_rfi,
                linked_activity=s.linked_activity,
            )
        )
    out.sort(key=lambda r: (r.on_critical_path, r.days_at_risk), reverse=True)
    return out


# --------------------------------------------------------------------------- #
# Alerting (Evaluation Focus: "visibility depth AND alerting timeliness") — an
# in-app alert log, not a push/email/SMS channel (see SupplyChainAlert docstring).
# --------------------------------------------------------------------------- #
# Documented, deterministic severity rule: on-critical-path or a large at-risk
# gap is CRITICAL regardless of size; otherwise tiered by days_at_risk.
_ALERT_CRITICAL_DAYS = 14
_ALERT_WARNING_DAYS = 4
_SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}


def _detected_at_day(milestones: list[Milestone]) -> Optional[int]:
    """Real day the slip first became visible in the milestone data — the day the
    system COULD have raised this alert. Same first-slipped-milestone scan as
    _root_cause(), returned as a day number."""
    for m in milestones:
        if m.actual_day is not None and m.actual_day > m.planned_day:
            return m.actual_day
    return None


def _alert_severity(days_at_risk: int, on_critical_path: bool) -> str:
    if on_critical_path or days_at_risk > _ALERT_CRITICAL_DAYS:
        return "CRITICAL"
    if days_at_risk >= _ALERT_WARNING_DAYS:
        return "WARNING"
    return "INFO"


def _build_alert(s: Shipment) -> Optional[SupplyChainAlert]:
    if s.days_at_risk <= 0:
        return None
    detected = _detected_at_day(s.milestones)
    detected_at_day = detected if detected is not None else clock.current_day()
    severity = _alert_severity(s.days_at_risk, s.on_critical_path)
    critical_note = " — on the critical path" if s.on_critical_path else ""
    return SupplyChainAlert(
        id=f"ALERT-{s.id}",
        shipment_id=s.id,
        procurement_item=s.procurement_item,
        severity=severity,
        message=f"{s.procurement_item} ({s.id}) is {s.days_at_risk}d at risk of missing its "
        f"required-on-site date{critical_note}.",
        detected_at_day=detected_at_day,
        advance_warning_days=max(0, clock.current_day() - detected_at_day),
        days_at_risk=s.days_at_risk,
        on_critical_path=s.on_critical_path,
    )


@lru_cache(maxsize=1)
def alerts() -> list[SupplyChainAlert]:
    out = [a for s in shipments() if (a := _build_alert(s)) is not None]
    out.sort(key=lambda a: (_SEVERITY_ORDER[a.severity], -a.days_at_risk))
    return out


@router.get("/alerts", response_model=list[SupplyChainAlert])
def get_alerts() -> list[SupplyChainAlert]:
    return alerts()


@router.get("/meta")
def get_meta() -> dict:
    """Discloses the data provenance behind every 'status'/'at risk' figure on this
    page: a static milestone snapshot (backend/data/project_docs/supply_chain.json),
    diffed against a fixed as-of day — not a live carrier-tracking feed. Real
    computation over a point-in-time synthetic dataset, stated plainly rather than
    left to look mysteriously live."""
    import datetime as dt

    day = clock.current_day()
    as_of_date = PROJECT_START + dt.timedelta(days=day)
    note = (
        "Shipment status and delay projections are computed by diffing a static milestone "
        "snapshot against this as-of day — a point-in-time demo dataset, not a live carrier-tracking "
        "feed. The arithmetic (delay propagation, root cause, alternative viability) is real; the "
        "underlying data is REPRESENTATIVE synthetic input (see README 'What's REAL vs REPRESENTATIVE')."
    )
    if clock.get_offset() > 0:
        note += f" Clock advanced +{clock.get_offset()}d from the base day ({TODAY_DAY}) via /api/clock."
    return {
        "as_of_day": day,
        "as_of_date": as_of_date.isoformat(),
        "note": note,
    }


@router.get("/shipments", response_model=list[Shipment])
def get_shipments() -> list[Shipment]:
    return shipments()


@router.get("/shipments/{shipment_id}", response_model=Shipment)
def get_shipment(shipment_id: str) -> Shipment:
    for s in shipments():
        if s.id == shipment_id:
            return s
    raise HTTPException(status_code=404, detail=f"Unknown shipment_id: {shipment_id}")


@router.get("/risks", response_model=list[SupplyChainRisk])
def get_risks() -> list[SupplyChainRisk]:
    return risks()


@router.get("/equipment-spec-ncrs", response_model=list[NCR])
def get_equipment_spec_ncrs() -> list[NCR]:
    """Equipment-spec compliance (IS 8623-1:1993-derived subset) — MISMATCH shipments only,
    same NCR schema as the Compliance Agent. See PROGRESS.md for why this stays narrow to
    LV switchgear assemblies rather than force-fitting the other 5 procurement categories."""
    out = []
    for s in shipments():
        ncr = _equipment_spec_ncr(s.id, s.procurement_item, s.equipment_spec)
        if ncr:
            out.append(ncr)
    return out


@router.get("/map")
def get_map() -> dict:
    """Points + routes for the geospatial view — plain data, no external maps API needed."""
    points = [{"id": "site", "kind": "site", "shipment_id": None, **SITE, "at_risk": False}]
    routes = []
    for s in shipments():
        points.append(
            {
                "id": f"{s.id}-tier1",
                "kind": "tier1",
                "shipment_id": s.id,
                "label": s.tier1_supplier.name,
                "city": s.tier1_supplier.city,
                "lat": s.tier1_supplier.lat,
                "lon": s.tier1_supplier.lon,
                "at_risk": s.days_at_risk > 0,
                "equipment_spec_status": s.equipment_spec.status,
            }
        )
        for t2 in s.tier2_suppliers:
            points.append(
                {
                    "id": f"{s.id}-tier2-{t2.name}",
                    "kind": "tier2",
                    "shipment_id": s.id,
                    "label": t2.name,
                    "city": t2.city,
                    "lat": t2.lat,
                    "lon": t2.lon,
                    "at_risk": s.days_at_risk > 0,
                }
            )
            routes.append(
                {
                    "shipment_id": s.id,
                    "from": {"lat": t2.lat, "lon": t2.lon},
                    "to": {"lat": s.tier1_supplier.lat, "lon": s.tier1_supplier.lon},
                    "tier": 2,
                    "at_risk": s.days_at_risk > 0,
                }
            )
        routes.append(
            {
                "shipment_id": s.id,
                "from": {"lat": s.tier1_supplier.lat, "lon": s.tier1_supplier.lon},
                "to": {"lat": SITE["lat"], "lon": SITE["lon"]},
                "tier": 1,
                "at_risk": s.days_at_risk > 0,
            }
        )
    return {"points": points, "routes": routes}
