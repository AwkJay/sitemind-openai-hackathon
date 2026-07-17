"""SiteMind COMMISSIONING QA (cooling-only slice) evaluation — a SIXTH separate
metric, never blended with the other five.

What this measures and why it's scoped the way it is:
  * `app/commissioning.py`'s deterministic checker maps a measured value to
    PASS / OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE / FAIL / NOT_CHECKABLE against
    the cooling envelope corpus (commissioning_clauses.json). This is a correctness
    check on that arithmetic against a hand-built answer key — NOT a claim that the
    underlying ASHRAE numbers are verified against a primary document (they aren't;
    see commissioning_clauses.json's _note and every Citation's source_type field).
  * Cases cover: PASS inside recommended, OUT_OF_RECOMMENDED at each boundary,
    FAIL outside allowable, exact-boundary cases (recommended max, allowable max),
    both temperature and relative_humidity, both A1 and A2 classes, and
    NOT_CHECKABLE for a non-cooling system record (scope discipline, not a bug).

Run:  python -m eval.run_commissioning_eval   (from backend/, venv active)
      -> writes eval/commissioning_report.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.commissioning import check_record  # noqa: E402
from app.schemas import TestRecord  # noqa: E402


def _rec(test_id, system, parameter, measured_value, unit, zone, equipment_class="A1"):
    return TestRecord(
        test_id=test_id,
        system=system,
        parameter=parameter,
        measured_value=measured_value,
        unit=unit,
        timestamp="2026-07-01T10:00:00Z",
        location_zone=zone,
        equipment_class=equipment_class,
    )


CASES = [
    # id, record, expected_verdict
    ("temp-pass-recommended", _rec("T-01", "cooling", "supply_air_temp", 22.0, "degC", "Zone-1", "A1"), "PASS"),
    ("temp-pass-lower-boundary", _rec("T-02", "cooling", "supply_air_temp", 18.0, "degC", "Zone-1", "A1"), "PASS"),
    ("temp-pass-upper-boundary", _rec("T-03", "cooling", "supply_air_temp", 27.0, "degC", "Zone-1", "A1"), "PASS"),
    ("temp-out-of-recommended-a1", _rec("T-04", "cooling", "supply_air_temp", 30.0, "degC", "Zone-2", "A1"), "OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE"),
    ("temp-fail-above-allowable-a1", _rec("T-05", "cooling", "supply_air_temp", 34.0, "degC", "Zone-2", "A1"), "FAIL"),
    ("temp-fail-below-allowable-a1", _rec("T-06", "cooling", "supply_air_temp", 12.0, "degC", "Zone-3", "A1"), "FAIL"),
    # A2 has a wider allowable band (10-35) — the same 30C that fails nothing extra, still
    # out-of-recommended but within A2's allowable, and 34C (fails A1) is within A2 allowable.
    ("temp-out-of-recommended-a2", _rec("T-07", "cooling", "supply_air_temp", 34.0, "degC", "Zone-4", "A2"), "OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE"),
    ("temp-fail-above-allowable-a2", _rec("T-08", "cooling", "supply_air_temp", 36.0, "degC", "Zone-4", "A2"), "FAIL"),
    ("rh-pass-recommended", _rec("H-01", "cooling", "relative_humidity", 45.0, "%RH", "Zone-1", "A1"), "PASS"),
    ("rh-out-of-recommended", _rec("H-02", "cooling", "relative_humidity", 70.0, "%RH", "Zone-2", "A1"), "OUT_OF_RECOMMENDED_BUT_WITHIN_ALLOWABLE"),
    ("rh-fail-above-allowable", _rec("H-03", "cooling", "relative_humidity", 90.0, "%RH", "Zone-3", "A1"), "FAIL"),
    ("rh-fail-below-allowable", _rec("H-04", "cooling", "relative_humidity", 3.0, "%RH", "Zone-3", "A1"), "FAIL"),
    ("not-checkable-power-system", _rec("P-01", "power", "voltage", 415.0, "V", "LV-Board-1"), "NOT_CHECKABLE"),
    ("not-checkable-unmapped-cooling-param", _rec("T-09", "cooling", "duct_static_pressure", 250.0, "Pa", "Zone-1"), "NOT_CHECKABLE"),
]


def main() -> None:
    results = []
    n_pass = 0
    for case_id, record, expected in CASES:
        finding = check_record(record)
        ok = finding.verdict == expected
        n_pass += int(ok)
        results.append(
            {
                "case": case_id,
                "expected": expected,
                "got": finding.verdict,
                "pass": ok,
                "ncr_generated": finding.ncr is not None,
            }
        )
    report = {
        "n_cases": len(CASES),
        "n_pass": n_pass,
        "accuracy": round(n_pass / len(CASES), 3),
        "results": results,
        "note": "Correctness check on the deterministic PASS/allowable/FAIL threshold logic "
        "against a hand-built answer key. Does NOT validate the underlying ASHRAE envelope "
        "numbers themselves against a primary source — those are cross_source_unverified, "
        "see commissioning_clauses.json.",
    }
    out = Path(__file__).parent / "commissioning_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"n_cases={len(CASES)}  n_pass={n_pass}  accuracy={report['accuracy']}")
    print(f"wrote {out}")
    if n_pass != len(CASES):
        for r in results:
            if not r["pass"]:
                print(f"  FAIL: {r['case']} expected={r['expected']} got={r['got']}")


if __name__ == "__main__":
    main()
