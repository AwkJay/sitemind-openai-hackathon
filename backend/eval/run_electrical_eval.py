"""SiteMind ELECTRICAL DOMAIN rule-decision evaluation — reported SEPARATELY from
the existing structural rule-decision eval (run_eval.py), never blended into one
number. Same discipline as every other pillar's eval in this project.

What this measures and why it's scoped the way it is:
  * `app/agents/checks.py`'s two electrical checks (INSULATION_RESISTANCE,
    RCD_RATED_CURRENT) are grounded in IS 732:1989 (Third Revision) — a real BIS
    document, extracted via OCR from an older scanned edition, NOT via Codebook, NOT the
    current 2019 edition. Every clause's Citation carries
    source_type="primary_scan_ocr" (schemas.py) so this is never presented as
    equivalent to a Codebook-verified structural clause.
  * This eval checks the THRESHOLD ARITHMETIC against a hand-built answer key
    (does the deterministic rule reach the correct CONFORMS/NON-CONFORMS verdict
    for a given measured value) — it does NOT re-verify the OCR transcription
    accuracy of the underlying clause text itself (that was done manually,
    page-by-page, cross-checked against column-aware re-extraction of the
    original scan; see PROGRESS.md for that process).
  * Smaller n than the structural eval (n=41) because the electrical domain has
    only 2 deterministic checks so far — IS 3043 (earthing electrode resistance)
    is still needed to build more; see sitemind/docs/codes.txt.

Run:  python -m eval.run_electrical_eval   (from backend/, venv active)
      -> writes eval/electrical_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.agents.checks import applicable_checks  # noqa: E402


def _param(**kw):
    return kw


CASES = [
    # Insulation resistance: required minimum = min(50/num_points, 1.0) megohm.
    # The clause's "need not be required to have an IR greater than 1 megohm" is a
    # CEILING on the requirement, not a floor: for small num_points (where 50/N > 1),
    # the requirement is capped DOWN to 1 megohm, not up.
    # N=50: 50/50 = 1.0 exactly -> no capping in effect, required = 1.0
    ("ir-pass-n50-exact-boundary", _param(param="insulation_resistance_megohm", value=1.0, num_points=50), True),
    ("ir-fail-n50-just-under", _param(param="insulation_resistance_megohm", value=0.99, num_points=50), False),
    # N=100: 50/100 = 0.5, well below the cap -> required = 0.5
    ("ir-pass-n100-boundary", _param(param="insulation_resistance_megohm", value=0.5, num_points=100), True),
    ("ir-fail-n100-below-required", _param(param="insulation_resistance_megohm", value=0.3, num_points=100), False),
    # N=10: raw 50/10 = 5.0, EXCEEDS the cap -> required is capped DOWN to 1.0
    ("ir-pass-n10-capped-requirement", _param(param="insulation_resistance_megohm", value=1.0, num_points=10), True),
    ("ir-fail-n10-below-capped-requirement", _param(param="insulation_resistance_megohm", value=0.9, num_points=10), False),
    # N=2: raw 50/2 = 25, heavily capped down to 1.0 -> a small installation only
    # needs 1 megohm, not the raw 25 the naive formula would imply.
    ("ir-pass-n2-heavily-capped", _param(param="insulation_resistance_megohm", value=1.5, num_points=2), True),
    ("ir-fail-n2-below-capped-requirement", _param(param="insulation_resistance_megohm", value=0.5, num_points=2), False),
    # RCD rated current: socket-outlet circuits must be <= 30 mA
    ("rcd-pass-standard-30ma", _param(param="rcd_rated_current_ma", value=30.0, circuit_type="socket_outlet"), True),
    ("rcd-pass-well-under", _param(param="rcd_rated_current_ma", value=10.0, circuit_type="socket_outlet"), True),
    ("rcd-fail-over-rated-100ma", _param(param="rcd_rated_current_ma", value=100.0, circuit_type="socket_outlet"), False),
    ("rcd-fail-just-over-boundary", _param(param="rcd_rated_current_ma", value=30.5, circuit_type="socket_outlet"), False),
    # Scope discipline: RCD check only applies to socket-outlet circuits — a
    # distribution-board RCD isn't governed by this specific clause, so no check
    # should fire at all (not a false PASS, not a false FAIL — not applicable).
    ("rcd-not-applicable-wrong-circuit-type", _param(param="rcd_rated_current_ma", value=100.0, circuit_type="distribution_board"), None),
    # Earth grid continuity resistance (IS 3043:1987 22.2.3): <= 1 ohm required
    ("earth-grid-pass-boundary", _param(param="earth_grid_resistance_ohm", value=1.0), True),
    ("earth-grid-pass-well-under", _param(param="earth_grid_resistance_ohm", value=0.4), True),
    ("earth-grid-fail-over-boundary", _param(param="earth_grid_resistance_ohm", value=1.2), False),
    # Generator/transformer frame earthing (CEA 41(xii)): >= 2 separate connections
    ("frame-earth-pass-two", _param(param="frame_earth_connections_count", value=2), True),
    ("frame-earth-pass-more-than-two", _param(param="frame_earth_connections_count", value=3), True),
    ("frame-earth-fail-single-connection", _param(param="frame_earth_connections_count", value=1), False),
    # Neutral point earthing (CEA 41(xiii)): >= 2 separate connections
    ("neutral-earth-pass-two", _param(param="neutral_earth_connections_count", value=2), True),
    ("neutral-earth-fail-single-connection", _param(param="neutral_earth_connections_count", value=1), False),
    # RCD touch-voltage limit (IS 732:2019 Cl 4.2.11.5.3, TT systems):
    # RA (earth electrode + protective conductor resistance, ohm) x I(delta n)
    # (RCD rated residual current, A) must not exceed 50V.
    ("rcd-touch-pass-typical-30ma", _param(param="rcd_touch_voltage_check", earth_electrode_resistance_ohm=10.0, rcd_residual_current_a=0.03), True),
    ("rcd-touch-pass-exact-boundary-100ma", _param(param="rcd_touch_voltage_check", earth_electrode_resistance_ohm=500.0, rcd_residual_current_a=0.1), True),
    ("rcd-touch-fail-just-over-boundary-30ma", _param(param="rcd_touch_voltage_check", earth_electrode_resistance_ohm=1700.0, rcd_residual_current_a=0.03), False),
    ("rcd-touch-pass-exact-boundary-500ma", _param(param="rcd_touch_voltage_check", earth_electrode_resistance_ohm=100.0, rcd_residual_current_a=0.5), True),
    ("rcd-touch-fail-500ma-high-earth-resistance", _param(param="rcd_touch_voltage_check", earth_electrode_resistance_ohm=101.0, rcd_residual_current_a=0.5), False),
    # IS 732:2019 Table 15 insulation resistance by voltage class (strict ">", not ">=").
    ("ins-table15-selv-pass", _param(param="insulation_resistance_voltage_class_megohm", value=0.6, voltage_class="selv_pelv"), True),
    ("ins-table15-selv-fail-at-boundary", _param(param="insulation_resistance_voltage_class_megohm", value=0.5, voltage_class="selv_pelv"), False),
    ("ins-table15-up-to-500v-pass", _param(param="insulation_resistance_voltage_class_megohm", value=1.5, voltage_class="up_to_500v"), True),
    ("ins-table15-up-to-500v-fail-at-boundary", _param(param="insulation_resistance_voltage_class_megohm", value=1.0, voltage_class="up_to_500v"), False),
    ("ins-table15-above-500v-pass", _param(param="insulation_resistance_voltage_class_megohm", value=2.0, voltage_class="above_500v"), True),
    ("ins-table15-above-500v-fail-below", _param(param="insulation_resistance_voltage_class_megohm", value=0.9, voltage_class="above_500v"), False),
]


def main() -> None:
    results = []
    n_pass = 0
    for case_id, param, expected_conforms in CASES:
        applied = applicable_checks(param)
        if expected_conforms is None:
            ok = len(applied) == 0
            got = "NOT_APPLICABLE" if not applied else f"APPLIED:{[c['id'] for c in applied]}"
        else:
            ok = len(applied) == 1 and applied[0]["rule"](param) == expected_conforms
            got = None
            if applied:
                got = "CONFORMS" if applied[0]["rule"](param) else "NON_CONFORMS"
        n_pass += int(ok)
        results.append({"case": case_id, "expected_conforms": expected_conforms, "got": got, "pass": ok})

    report = {
        "n_cases": len(CASES),
        "n_pass": n_pass,
        "accuracy": round(n_pass / len(CASES), 3),
        "results": results,
        "note": "Correctness check on the deterministic threshold arithmetic for the 2 "
        "electrical checks (IS 732:1989, primary_scan_ocr). Does not re-verify OCR "
        "transcription accuracy of the underlying clause text (done manually, see "
        "PROGRESS.md). Separate from run_eval.py's structural n=41 — never blended.",
    }
    out = Path(__file__).parent / "electrical_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"n_cases={len(CASES)}  n_pass={n_pass}  accuracy={report['accuracy']}")
    print(f"wrote {out}")
    if n_pass != len(CASES):
        for r in results:
            if not r["pass"]:
                print(f"  FAIL: {r['case']} expected={r['expected_conforms']} got={r['got']}")


if __name__ == "__main__":
    main()
