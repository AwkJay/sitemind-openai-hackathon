"""SiteMind EXTRACTION evaluation — held out from the extractor's own regex authoring.

What this measures and why it is a separate, honest metric from `run_eval.py`:
  * `run_eval.py` scores the DETERMINISTIC RULE ENGINE (given a structured param, is the
    pass/fail + clause correct). That is deterministic Python and was always going to be
    accurate — it isn't a meaningful claim about reading a real document.
  * THIS file scores `app/ingest.py`'s regex extraction: given free-text document snippets,
    did it (a) find the planted parameter with the right value and element, (b) correctly
    ABSTAIN on parameter types genuinely absent from the text, and (c) avoid ever inventing
    a parameter/value that isn't in the text (a false positive here is the one failure mode
    that would let a hallucination back in — it is reported separately and must be near zero).
  * The test documents intentionally use DIFFERENT phrasing than the extractor's own
    docstrings/examples in `ingest.py`, so this is a genuine held-out check, not the
    extractor grading its own homework.

Run:  python -m eval.run_extraction_eval   (from backend/, venv active)
      -> writes eval/extraction_report.json
"""
from __future__ import annotations

import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.ingest import extract_params

HERE = Path(__file__).resolve().parent


# ----------------------------------------------------------------------------- held-out documents
# Each case: a short multi-sentence document with `expect` = the exact params that SHOULD be
# extracted (param type, optional element_type, value) and everything else in
# EXTRACTABLE_PARAM_TYPES not listed is expected to correctly ABSTAIN (nothing planted).
EXTRACTABLE_PARAM_TYPES = [
    "nominal_cover", "concrete_grade", "wc_ratio", "long_steel_pct", "importance_factor",
]


def _case(id_, text, expect):
    return {"id": id_, "text": text, "expect": expect}


CASES = [
    # -- nominal_cover, phrasing that does NOT mirror ingest.py's own docstring examples --
    _case(
        "cover-footing-1",
        "Footing F-9 shall be provided with a nominal cover to reinforcement of 55 mm, "
        "in accordance with the project's severe exposure classification.",
        [{"param": "nominal_cover", "element_type": "footing", "value": 55}],
    ),
    _case(
        "cover-column-1",
        "Provide 35 mm cover to the main longitudinal bars in Column C-14. Concrete grade "
        "for this member is M30.",
        [
            {"param": "nominal_cover", "element_type": "column", "value": 35},
            {"param": "concrete_grade", "value": 30},
        ],
    ),
    _case(
        "cover-no-element",
        "Reinforcement cover shall be 40 mm throughout unless noted otherwise on the drawings.",
        [],  # no footing/column keyword in the sentence — correct to abstain, not guess an element
    ),
    # -- concrete_grade + marine flag --
    _case(
        "grade-marine-1",
        "Concrete Grade M35 shall be used for all reinforced concrete cast in the marine "
        "splash zone adjoining the sea wall.",
        [{"param": "concrete_grade", "value": 35, "marine": True}],
    ),
    _case(
        "grade-internal-1",
        "Internal partition walls and non-structural blockwork backing shall use Grade M20 "
        "concrete for the fill.",
        [{"param": "concrete_grade", "value": 20, "marine": False}],
    ),
    # -- wc_ratio --
    _case(
        "wc-moderate-1",
        "For moderate exposure concrete elements, the maximum permissible free water-cement "
        "ratio shall not exceed 0.50 in any circumstance.",
        [{"param": "wc_ratio", "value": 0.50, "exposure": "moderate"}],
    ),
    _case(
        "wc-no-ratio",
        "Concrete shall be cured for a minimum of 7 days after placement.",
        [],  # no water-cement ratio mentioned at all
    ),
    # -- long_steel_pct --
    _case(
        "steel-column-1",
        "Column C-3 longitudinal reinforcement percentage is fixed at 1.2 percent of the "
        "gross cross-sectional area.",
        [{"param": "long_steel_pct", "element_type": "column", "value": 1.2}],
    ),
    _case(
        "steel-beam-no-match",
        "Beam B-7 longitudinal reinforcement is 3 bars of 20 mm diameter at the bottom face.",
        [],  # "longitudinal" present but element is a beam, no percent figure — must abstain
    ),
    # -- importance_factor --
    _case(
        "importance-1",
        "The seismic importance factor adopted for this facility, given its mission-critical "
        "role, is 1.2.",
        [{"param": "importance_factor", "value": 1.2}],
    ),
    _case(
        "importance-none",
        "Seismic design shall follow the zone factor and response reduction factor given in "
        "the structural design basis.",
        [],  # "importance factor" phrase never appears — must abstain, not assume 1.0
    ),
    # -- multi-parameter realistic mini-DBR excerpt --
    _case(
        "mixed-realistic-1",
        "General Note 4: Footing F-21 nominal cover shall be 45 mm. General Note 5: The "
        "concrete for footing F-21 is Grade M25, cast in a severe marine exposure "
        "environment. General Note 6: Free water-cement ratio for this severe-exposure mix "
        "shall be limited to 0.42.",
        [
            {"param": "nominal_cover", "element_type": "footing", "value": 45},
            {"param": "concrete_grade", "value": 25, "marine": True},
            {"param": "wc_ratio", "value": 0.42, "exposure": "severe"},
        ],
    ),
    # -- adversarial: a decoy number near a trigger word that should NOT be extracted --
    _case(
        "decoy-cover-charge",
        "The site security cover charge for after-hours access is INR 500 per visit.",
        [],  # "cover" appears but no "mm" unit — must not fabricate a cover value
    ),
    _case(
        "decoy-grade-unrelated",
        "Site grading and levelling works shall achieve a finished grade tolerance of 25 mm.",
        [],  # "grade" appears but not concrete grade (no M-number) — must abstain
    ),
]

# Categories this suite never plants — must always abstain (mirrors ingest.py's
# _ALWAYS_ABSTAIN design; verified once, not per-document, since it never varies by input).
_ALWAYS_ABSTAIN_TYPES = {"design_wind_speed", "design_wind_pressure", "tie_spacing"}


def _match(found: dict, expected: dict) -> bool:
    if found["param"] != expected["param"]:
        return False
    if "element_type" in expected and found.get("element_type") != expected["element_type"]:
        return False
    if abs(float(found["value"]) - float(expected["value"])) > 1e-6:
        return False
    if "marine" in expected and bool(found.get("context", {}).get("marine")) != expected["marine"]:
        return False
    if "exposure" in expected and found.get("context", {}).get("exposure") != expected["exposure"]:
        return False
    return True


def main():
    tp = 0        # planted param correctly extracted
    fn = 0        # planted param missed (incorrectly abstained or wrong value)
    fp = 0        # extracted a param that was NOT planted in that document (false positive — the dangerous class)
    correct_abstain = 0   # param type genuinely absent from doc AND system abstained on it
    wrong_abstain = 0     # should never happen alongside fp>0 for the same type; tracked for completeness

    per_case = []
    for case in CASES:
        found_list, abstained = extract_params(case["text"])
        found_dicts = [
            {
                "param": f.param,
                "element_type": f.element_type,
                "value": f.value,
                "context": f.context,
            }
            for f in found_list
        ]
        abstained_types = {a.param for a in abstained}

        matched_found_idx: set[int] = set()
        case_tp = 0
        case_fn = 0
        for expected in case["expect"]:
            hit = None
            for i, f in enumerate(found_dicts):
                if i in matched_found_idx:
                    continue
                if _match(f, expected):
                    hit = i
                    break
            if hit is not None:
                matched_found_idx.add(hit)
                case_tp += 1
            else:
                case_fn += 1

        # Anything extracted but not matched to an expectation is a false positive.
        case_fp = len(found_dicts) - len(matched_found_idx)

        expected_types = {e["param"] for e in case["expect"]}
        case_correct_abstain = 0
        for pt in EXTRACTABLE_PARAM_TYPES:
            if pt in expected_types:
                continue  # this type was supposed to be found — scored above, not an abstention case
            if pt in abstained_types:
                case_correct_abstain += 1
            # if a type not expected also wasn't in abstained_types, it means something WAS
            # extracted for it despite not being planted -> already counted in case_fp above.

        tp += case_tp
        fn += case_fn
        fp += case_fp
        correct_abstain += case_correct_abstain

        per_case.append(
            {
                "id": case["id"],
                "expected": len(case["expect"]),
                "correctly_extracted": case_tp,
                "missed": case_fn,
                "false_positive_extractions": case_fp,
                "correct_abstentions": case_correct_abstain,
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall and (precision + recall) else None

    total_abstain_opportunities = len(CASES) * len(EXTRACTABLE_PARAM_TYPES) - sum(
        len(c["expect"]) for c in CASES
    )
    abstention_accuracy = correct_abstain / total_abstain_opportunities if total_abstain_opportunities else None

    report = {
        "n_documents": len(CASES),
        "n_planted_params": tp + fn,
        "extraction": {
            "true_positives": tp,
            "false_negatives_missed": fn,
            "false_positives_fabricated": fp,
            "precision": round(precision, 4) if precision is not None else None,
            "recall": round(recall, 4) if recall is not None else None,
            "f1": round(f1, 4) if f1 is not None else None,
        },
        "abstention": {
            "correct_abstentions": correct_abstain,
            "total_opportunities": total_abstain_opportunities,
            "accuracy": round(abstention_accuracy, 4) if abstention_accuracy is not None else None,
        },
        "always_abstain_types_note": (
            f"design_wind_speed / design_wind_pressure / tie_spacing are hardcoded to always "
            f"abstain regardless of document content ({sorted(_ALWAYS_ABSTAIN_TYPES)}) — not "
            f"scored per-document here since the behaviour never varies by input; verified once "
            f"in unit tests."
        ),
        "method": "Held-out mini-documents with deliberately different phrasing than ingest.py's "
        "own regex/docstrings, including adversarial decoys (trigger word present, no valid "
        "value) that must NOT be extracted. A false-positive extraction (fabricating a value not "
        "in the text) is scored separately and is the metric that matters most for the "
        "no-hallucination claim.",
        "per_case": per_case,
    }

    (HERE / "extraction_report.json").write_text(json.dumps(report, indent=2))
    print(f"n_documents={report['n_documents']}  n_planted_params={report['n_planted_params']}")
    print(
        f"extraction: precision={report['extraction']['precision']} "
        f"recall={report['extraction']['recall']} f1={report['extraction']['f1']} "
        f"(fabricated/false-positive extractions={fp})"
    )
    print(f"abstention accuracy={report['abstention']['accuracy']} "
          f"({correct_abstain}/{total_abstain_opportunities})")
    print("wrote eval/extraction_report.json")


if __name__ == "__main__":
    main()
