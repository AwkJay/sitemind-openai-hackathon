"""SiteMind EQUIPMENT-SPEC COMPLIANCE evaluation — reported SEPARATELY from
run_supply_chain_eval.py's logistics/delay-propagation eval (8/8), never blended
into one number. Same discipline as every other pillar's eval in this project.

What this measures and why it's scoped the way it is:
  * `app/supply_chain.py`'s `_equipment_spec_check()` is grounded in IS 8623-1:1993
    Cl 4.1.2 (rated operational voltage must not exceed rated insulation voltage) —
    a real BIS "LV switchgear and controlgear assemblies" standard, OCR-extracted
    from a scanned reprint. Citation.source_type="primary_scan_ocr" throughout.
  * Only ONE procurement category (LV switchgear) is covered by a real primary
    standard in this corpus. The original ask ("voltage class/type-test cert/
    rating tolerance for UPS, generator, cooling tower, switchgear, transformer")
    was checked against `CEA_Safetycons.pdf` and found NOT to cover per-equipment
    procurement specs — that content lives in per-equipment BIS product standards
    (e.g. IS 8623 for switchgear), not CEA's safety-construction regulations. So
    this eval and the checker are honestly narrow to switchgear rather than
    force-fitting a standard onto equipment it doesn't govern. See PROGRESS.md.
  * This checks the THRESHOLD LOGIC (does op_v <= ins_v reach MATCH, does a
    missing declared_spec reach SPEC_NOT_PROVIDED, does an unmapped procurement
    category reach NOT_APPLICABLE) — not a re-verification of the OCR transcription
    of the underlying clause text (that was checked manually against the scan).

Run:  python -m eval.run_equipment_spec_eval   (from backend/, venv active)
      -> writes eval/equipment_spec_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.supply_chain import _equipment_spec_check  # noqa: E402


def _raw(procurement_item: str, declared_spec: dict | None = None) -> dict:
    d = {"procurement_item": procurement_item}
    if declared_spec is not None:
        d["declared_spec"] = declared_spec
    return d


CASES = [
    # MATCH: operational voltage within the declared insulation voltage rating.
    ("match-standard-lv-415-1000", _raw("LV switchgear 4000A", {"rated_operational_voltage_v": 415, "rated_insulation_voltage_v": 1000}), "MATCH"),
    ("match-boundary-equal", _raw("LV switchgear 4000A", {"rated_operational_voltage_v": 690, "rated_insulation_voltage_v": 690}), "MATCH"),
    ("match-well-under", _raw("LV switchgear 4000A", {"rated_operational_voltage_v": 230, "rated_insulation_voltage_v": 1000}), "MATCH"),
    # MISMATCH: operational voltage exceeds the declared insulation voltage rating.
    ("mismatch-op-exceeds-insulation", _raw("LV switchgear 4000A", {"rated_operational_voltage_v": 1100, "rated_insulation_voltage_v": 1000}), "MISMATCH"),
    ("mismatch-just-over-boundary", _raw("LV switchgear 4000A", {"rated_operational_voltage_v": 690.5, "rated_insulation_voltage_v": 690}), "MISMATCH"),
    # SPEC_NOT_PROVIDED: standard applies to this category, but the vendor submittal
    # is missing one or both declared voltage fields.
    ("missing-both-fields", _raw("LV switchgear 4000A"), "SPEC_NOT_PROVIDED"),
    ("missing-insulation-voltage-only", _raw("LV switchgear 4000A", {"rated_operational_voltage_v": 415}), "SPEC_NOT_PROVIDED"),
    ("missing-operational-voltage-only", _raw("LV switchgear 4000A", {"rated_insulation_voltage_v": 1000}), "SPEC_NOT_PROVIDED"),
    # NOT_APPLICABLE: no real standard in the corpus covers this procurement category —
    # must not silently guess or force-fit the switchgear rule onto unrelated equipment.
    ("not-applicable-drups", _raw("DRUPS 2.5MW", {"rated_operational_voltage_v": 415, "rated_insulation_voltage_v": 1000}), "NOT_APPLICABLE"),
    ("not-applicable-chiller", _raw("Chiller plant"), "NOT_APPLICABLE"),
    ("not-applicable-busway", _raw("Busway 4000A"), "NOT_APPLICABLE"),
    ("not-applicable-access-floor", _raw("Raised access floor"), "NOT_APPLICABLE"),
]


def main() -> None:
    results = []
    n_pass = 0
    for case_id, raw, expected_status in CASES:
        got = _equipment_spec_check(raw)
        ok = got.status == expected_status
        n_pass += int(ok)
        results.append({"case": case_id, "expected": expected_status, "got": got.status, "pass": ok})

    report = {
        "n_cases": len(CASES),
        "n_pass": n_pass,
        "accuracy": round(n_pass / len(CASES), 3),
        "results": results,
        "note": "Correctness check on the deterministic MATCH/MISMATCH/SPEC_NOT_PROVIDED/"
        "NOT_APPLICABLE logic in app/supply_chain.py's _equipment_spec_check(), grounded in "
        "IS 8623-1:1993 Cl 4.1.2 (primary_scan_ocr). Separate from run_supply_chain_eval.py's "
        "logistics eval (n=8) and every other pillar eval — never blended.",
    }
    out = Path(__file__).parent / "equipment_spec_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"n_cases={len(CASES)}  n_pass={n_pass}  accuracy={report['accuracy']}")
    print(f"wrote {out}")
    if n_pass != len(CASES):
        for r in results:
            if not r["pass"]:
                print(f"  FAIL: {r['case']} expected={r['expected']} got={r['got']}")


if __name__ == "__main__":
    main()
