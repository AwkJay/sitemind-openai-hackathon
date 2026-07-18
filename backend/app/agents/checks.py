"""The CHECK REGISTRY — the core compliance asset.

Each check maps a checkable parameter to a REAL clause key (in clauses.json) and
a deterministic threshold function. The pass/fail decision lives here, in Python,
anchored to a real clause — never in the LLM. 6-8 solid checks beat 30 shaky ones.

A check dict has:
  id            : stable rule id
  applies_when  : (param) -> bool   does this rule govern this param?
  rule          : (param) -> bool   True = CONFORMS, False = NON-CONFORM
  clause_key    : key into clauses.json (the real Citation)
  severity      : NCR severity for a breach
  why           : why_it_matters seed (data-centre framing)
  rule_text     : human description of the requirement (for the explain prompt)
  corrective    : concrete corrective action seed
"""
from __future__ import annotations

from typing import Callable, TypedDict


class Check(TypedDict, total=False):
    id: str
    applies_when: Callable[[dict], bool]
    rule: Callable[[dict], bool]
    clause_key: str
    severity: str
    why: str
    rule_text: str
    corrective: str
    # Optional: other clause keys that ALSO govern this same parameter. When a
    # parameter is constrained by more than one clause, the overlap detector in
    # compliance.evaluate() surfaces all of them and names the binding (strictest)
    # one — senior-engineer behaviour, not a single-rule lookup.
    also_governed_by: list[str]
    # "structural" (default if omitted) or "electrical" — lets the UI/coverage stats
    # group checks by domain without restructuring the original structural registry.
    domain: str


# IS 732:2019 Table 15 minimum insulation resistance by nominal circuit voltage
# class (current edition — simpler methodology than the 1989 50/N formula, a
# genuinely different test approach, not a restatement of the same rule).
_TABLE15_MIN_INSULATION_MOHM = {
    "selv_pelv": 0.5,
    "up_to_500v": 1.0,
    "above_500v": 1.0,
}

CHECKS: list[Check] = [
    {
        "id": "COVER_FOOTING",
        "applies_when": lambda p: p.get("element_type") == "footing"
        and p.get("param") == "nominal_cover",
        "rule": lambda p: p["value"] >= 50,
        "clause_key": "IS456_26.4.2.2",
        "also_governed_by": ["IS456_26.5.1.1"],  # Table 16 durability cover (severe = 45 mm)
        "severity": "HIGH",
        "why": "Inadequate cover in severe coastal exposure accelerates rebar corrosion, "
        "shortening the service life of a foundation carrying transformer/genset loads — "
        "a single-point uptime risk for the data centre.",
        "rule_text": "For footings the minimum nominal cover shall be 50 mm.",
        "corrective": "Revise the shop drawing to 50 mm nominal cover and re-issue for approval before casting.",
    },
    {
        "id": "COVER_COLUMN",
        "applies_when": lambda p: p.get("element_type") == "column"
        and p.get("param") == "nominal_cover",
        "rule": lambda p: p["value"] >= 40,
        "clause_key": "IS456_26.4.2.1",
        "also_governed_by": ["IS456_26.5.1.1"],  # Table 16 durability cover (severe = 45 mm)
        "severity": "HIGH",
        "why": "Column cover below 40 mm violates minimum durability cover for primary "
        "load-bearing members supporting the white-space structure.",
        "rule_text": "Longitudinal bars in a column shall have nominal cover not less than 40 mm.",
        "corrective": "Increase nominal cover to at least 40 mm and re-detail the column schedule.",
    },
    {
        "id": "COVER_TOLERANCE",
        "applies_when": lambda p: p.get("param") == "cover_deviation",
        "rule": lambda p: 0 <= p["value"] <= 10,
        "clause_key": "IS456_12.3.2",
        "severity": "MEDIUM",
        "why": "Cover may deviate only +10/-0 mm; under-cover is never permitted and compromises durability.",
        "rule_text": "Actual cover shall not deviate from nominal cover by more than +10 mm and -0 mm.",
        "corrective": "Adjust cover blocks / fixing so deviation stays within +10/-0 mm before the pour.",
    },
    {
        "id": "WC_RATIO_SEVERE",
        "applies_when": lambda p: p.get("param") == "wc_ratio"
        and p.get("exposure") in ("severe", "very severe", "extreme"),
        "rule": lambda p: p["value"] <= 0.45,
        "clause_key": "IS456_8.2.4.1",
        "severity": "HIGH",
        "why": "Severe coastal exposure caps the free water-cement ratio (Table 5) to limit "
        "chloride ingress; an over-wet mix undermines the durability of mission-critical foundations.",
        "rule_text": "For severe exposure the maximum free water-cement ratio is 0.45 (Table 5).",
        "corrective": "Redesign the mix to a free water-cement ratio of 0.45 or lower and re-submit the MOS.",
    },
    {
        "id": "SEAWATER_GRADE",
        "applies_when": lambda p: p.get("param") == "concrete_grade" and p.get("marine"),
        "rule": lambda p: p.get("grade_mpa", 0) >= 30,
        "clause_key": "IS456_8.2.8",
        "severity": "HIGH",
        "why": "RCC in or near sea-water must be at least M30 to resist coastal attack.",
        "rule_text": "Reinforced concrete in/near sea-water shall be at least M30 grade.",
        "corrective": "Specify a minimum grade of M30 for all marine-exposed RCC.",
    },
    {
        "id": "COLUMN_STEEL",
        "applies_when": lambda p: p.get("element_type") == "column"
        and p.get("param") == "long_steel_pct",
        "rule": lambda p: 0.8 <= p["value"] <= 6.0,
        "clause_key": "IS456_26.5.3.1",
        "severity": "MEDIUM",
        "why": "Column longitudinal steel must be 0.8-6% (<=4% at laps) for adequate capacity and ductility.",
        "rule_text": "Column longitudinal reinforcement shall be 0.8% to 6% of gross area.",
        "corrective": "Revise the column reinforcement to fall within 0.8-6% of the gross section.",
    },
    {
        "id": "DEFLECTION",
        "applies_when": lambda p: p.get("param") == "span_depth_ratio",
        "rule": lambda p: p["value"] <= p.get("limit", 20),
        "clause_key": "IS456_23.2",
        "severity": "MEDIUM",
        "why": "Deflection limits (span/250 final) protect raised floors, cable trays and equipment alignment.",
        "rule_text": "Final deflection of floors/roofs should not exceed span/250.",
        "corrective": "Increase member depth or revise the span so the deflection check passes.",
    },
    {
        "id": "WIND_SPEED",
        "applies_when": lambda p: p.get("param") == "design_wind_speed",
        "rule": lambda p: p["value"] >= p.get("city_basic_vb", 0),
        "clause_key": "IS875_5.3",
        "severity": "HIGH",
        "why": "Design wind speed Vz = Vb·k1·k2·k3·k4 must not fall below the city basic wind speed; "
        "Chennai is cyclonic (k4) and under-speccing risks cladding loss in a storm.",
        "rule_text": "Design wind speed must not be below the city basic wind speed Vb.",
        "corrective": "Recompute Vz from the Chennai basic wind speed including k4 (cyclonic) and revise the cladding basis.",
    },
    {
        "id": "TIE_PITCH",
        "applies_when": lambda p: p.get("param") == "tie_spacing",
        # Pitch must not exceed the least of: least lateral dim, 16x smallest long bar dia, 300 mm.
        "rule": lambda p: p["value"]
        <= min(
            p.get("least_lateral_dim", 1e9),
            16 * p.get("long_bar_dia", 1e9),
            300,
        ),
        "clause_key": "IS456_26.5.3.2",
        "severity": "MEDIUM",
        "why": "Over-spaced lateral ties let longitudinal bars buckle under the seismic and "
        "equipment loads of a data hall, reducing column ductility exactly where a "
        "concurrently-maintainable facility can least afford a structural failure.",
        "rule_text": "Lateral-tie pitch shall not exceed the least of the column's least lateral "
        "dimension, 16x the smallest longitudinal bar diameter, and 300 mm.",
        "corrective": "Reduce the tie spacing to the governing value (the least of the three limits) "
        "and re-issue the column detailing drawing before fabrication.",
    },
    {
        "id": "WIND_PRESSURE",
        "applies_when": lambda p: p.get("param") == "design_wind_pressure",
        # pz must be at least 0.6*Vz^2 (within 2% rounding); under-specifying is non-conforming.
        "rule": lambda p: p["value"] >= 0.6 * (p.get("design_wind_speed_vz", 0) ** 2) * 0.98,
        "clause_key": "IS875_5.4",
        "severity": "HIGH",
        "why": "Design wind pressure pz = 0.6*Vz^2 sets the cladding and fastener demand; "
        "under-specifying it on a cyclonic east-coast site risks roof/cladding loss in a "
        "storm and a breach of the data hall envelope.",
        "rule_text": "Design wind pressure pz shall be not less than 0.6*Vz^2 (N/m2).",
        "corrective": "Recompute pz from the design wind speed Vz and revise the cladding/fastener schedule.",
    },
    # ---------------------------------------------------------------------- #
    # Electrical domain (IS 732:1989, Third Revision — a real BIS document, but
    # an OLDER edition extracted via OCR from a scanned copy, not Codebook. See
    # each clause's source_type="primary_scan_ocr" in clauses.json and
    # sitemind/docs/codes.txt. Only 2 checks so far: IS 3043 (earthing electrode
    # resistance thresholds) is still needed to check earthing itself.
    # ---------------------------------------------------------------------- #
    {
        "id": "INSULATION_RESISTANCE",
        "domain": "electrical",
        "applies_when": lambda p: p.get("param") == "insulation_resistance_megohm"
        and p.get("num_points") is not None,
        # Required minimum = 50 / num_points, but never more than 1 megohm (the
        # clause's own cap) — measured value must meet or exceed that minimum.
        "rule": lambda p: p["value"] >= min(50.0 / p["num_points"], 1.0),
        "clause_key": "IS732_1989_E-2.1.5b",
        "severity": "HIGH",
        "why": "Low insulation resistance on a data-hall wiring installation is an early "
        "indicator of insulation breakdown risk — a fire/electrocution hazard and a "
        "single-point availability risk for a facility that cannot tolerate an "
        "unplanned electrical trip.",
        "rule_text": "Insulation resistance (megohms) shall not be less than 50 divided "
        "by the number of points on the circuit, capped at a minimum requirement of 1 megohm.",
        "corrective": "Investigate and remediate the insulation fault before energising "
        "this circuit; re-test and re-measure before sign-off.",
    },
    {
        "id": "RCD_RATED_CURRENT",
        "domain": "electrical",
        "applies_when": lambda p: p.get("param") == "rcd_rated_current_ma"
        and p.get("circuit_type") == "socket_outlet",
        "rule": lambda p: p["value"] <= 30.0,
        "clause_key": "IS732_1989_5.1.3.2_RCD",
        "severity": "HIGH",
        "why": "An over-rated RCD on a socket-outlet circuit fails to trip within a safe "
        "touch-voltage duration, directly risking personnel safety during "
        "commissioning and O&M work in the electrical rooms.",
        "rule_text": "Every socket-outlet circuit (household/TT-system context) shall be "
        "protected by an RCD with rated residual operating current not exceeding 30 mA.",
        "corrective": "Replace with a 30 mA (or lower) rated RCD on this socket-outlet circuit.",
    },
    {
        "id": "EARTH_GRID_RESISTANCE",
        "domain": "electrical",
        "applies_when": lambda p: p.get("param") == "earth_grid_resistance_ohm",
        "rule": lambda p: p["value"] <= 1.0,
        "clause_key": "IS3043_1987_22.2.3",
        "severity": "HIGH",
        "why": "A high-resistance earth grid at the transformer yard/generator earthing system "
        "raises touch/step potential during a ground fault and slows protective-device "
        "operation — a direct personnel-safety and equipment-damage risk for the facility's "
        "HT infrastructure.",
        "rule_text": "The continuity resistance of the earth return path through the earth "
        "grid shall in no case be greater than one ohm.",
        "corrective": "Add earth electrodes / improve soil treatment at the earthing pit and "
        "re-measure the grid resistance before energising the HT switchgear.",
    },
    {
        "id": "GENERATOR_FRAME_EARTHING",
        "domain": "electrical",
        "applies_when": lambda p: p.get("param") == "frame_earth_connections_count",
        "rule": lambda p: p["value"] >= 2,
        "clause_key": "CEA_2010_41xii",
        "severity": "HIGH",
        "why": "An under-earthed generator/transformer frame is a direct touch-voltage safety "
        "hazard during O&M work in the generator/transformer yard, and a single-connection "
        "earth is a single point of failure if that one connection corrodes or breaks.",
        "rule_text": "The frame of every generator, transformer, and voltage-regulating "
        "apparatus (250-650 V) shall be earthed by two separate and distinct connections with earth.",
        "corrective": "Add a second, independent earth connection to the equipment frame before "
        "energising; verify continuity of both connections separately.",
    },
    {
        "id": "TRANSFORMER_NEUTRAL_EARTHING",
        "domain": "electrical",
        "applies_when": lambda p: p.get("param") == "neutral_earth_connections_count",
        "rule": lambda p: p["value"] >= 2,
        "clause_key": "CEA_2010_41xiii",
        "severity": "HIGH",
        "why": "A single-connection neutral earth removes the redundancy the regulation "
        "requires — if that connection fails, the neutral point can float, risking "
        "dangerous touch voltages across the installation.",
        "rule_text": "The neutral point of every generator and transformer shall be earthed "
        "by not less than two separate and distinct connections.",
        "corrective": "Add a second, independent neutral earth connection before energising; "
        "verify continuity of both connections separately.",
    },
    {
        "id": "RCD_TOUCH_VOLTAGE",
        "domain": "electrical",
        "applies_when": lambda p: p.get("param") == "rcd_touch_voltage_check"
        and p.get("earth_electrode_resistance_ohm") is not None
        and p.get("rcd_residual_current_a") is not None,
        "rule": lambda p: p["earth_electrode_resistance_ohm"] * p["rcd_residual_current_a"] <= 50.0,
        "clause_key": "IS732_2019_4.2.11.5.3",
        "severity": "HIGH",
        "why": "In a TT earthing system, if the earth-electrode resistance times the RCD's rated "
        "residual current exceeds 50V, the RCD will not limit touch voltage to a safe level on a "
        "fault — a direct personnel-safety risk during commissioning and O&M in the electrical rooms.",
        "rule_text": "Where an RCD is used for fault protection in a TT system, RA x I(delta n) "
        "shall not exceed 50 V (RA = earth electrode + protective conductor resistance in ohm, "
        "I(delta n) = the RCD's rated residual operating current in A).",
        "corrective": "Reduce earth-electrode resistance (additional rods/plates, chemical "
        "treatment) or select a lower-rated-current RCD so RA x I(delta n) <= 50V before energising.",
    },
    {
        "id": "INSULATION_RESISTANCE_TABLE15",
        "domain": "electrical",
        "applies_when": lambda p: p.get("param") == "insulation_resistance_voltage_class_megohm"
        and p.get("voltage_class") in _TABLE15_MIN_INSULATION_MOHM,
        "rule": lambda p: p["value"] > _TABLE15_MIN_INSULATION_MOHM[p["voltage_class"]],
        "clause_key": "IS732_2019_Table15",
        "severity": "HIGH",
        "why": "Insulation resistance below the Table 15 minimum for the circuit's voltage class "
        "indicates degraded conductor insulation — a fire/electrocution risk, and on a data-centre "
        "distribution circuit a precursor to an unplanned trip or arc fault under load.",
        "rule_text": "Per IS 732:2019 Table 15, measured insulation resistance shall exceed: "
        "SELV/PELV circuits > 0.5 Mohm (at 250V DC test voltage); circuits up to and including "
        "500V (incl. FELV) > 1.0 Mohm (at 500V DC); circuits above 500V > 1.0 Mohm (at 1000V DC).",
        "corrective": "Investigate and rectify the insulation fault (moisture ingress, damaged "
        "cable, degraded termination) and re-test before energising the circuit.",
    },
]


def applicable_checks(param: dict) -> list[Check]:
    """All checks whose applies_when matches this parameter."""
    return [c for c in CHECKS if c["applies_when"](param)]
