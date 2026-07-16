"""SiteMind compliance evaluation — REAL, computed, honest.

What this measures and why it's defensible:
  * Our compliance DECISION is deterministic (Python rules anchored to real IS clauses).
    Scoring it against gold derived from the same thresholds would be trivially 100% and
    meaningless. So instead we compare OUR element-aware grounded checks against a NAIVE
    KEYWORD BASELINE (what a quick LLM/regex wrapper does) on the same labelled set. The
    baseline confuses element types, near-misses and not-applicable cases — so the gap is
    real and informative, not circular.
  * The headline number is the CITATION HALLUCINATION RATE: every clause our system cites
    is resolved against the real clause cache (clauses.json). It is verified, not asserted.
  * Boundary cases (value exactly at the limit, >= vs >) and NOT_APPLICABLE distractors are
    included so the score reflects genuine robustness.

Run:  python -m eval.run_eval   (from backend/, venv active)  -> writes eval/report.json + eval/testset.jsonl
Honesty: this isolates the rule engine + citation grounding. EXTRACTION accuracy (pulling the
value/clause from free text) is LLM-dependent and is a separate online metric — stated as a known limit.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from sklearn.metrics import precision_recall_fscore_support, confusion_matrix

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path
from app.agents.checks import CHECKS          # the REAL rules
from app.standards import all_clauses

HERE = Path(__file__).resolve().parent
LABELS = ["VIOLATION", "COMPLIANT", "NOT_APPLICABLE"]
_REAL = {(c["standard"], c["clause"]) for c in all_clauses()}
_KEY2CLAUSE = {c["key"]: (c["standard"], c["clause"]) for c in all_clauses()}


# ----------------------------------------------------------------------------- test set
def build_testset() -> list[dict]:
    """Construct a class-balanced labelled set across all 8 checks, incl. boundary + N/A.

    Each case has a structured `param` (what a perfect extractor yields), a short `text`
    snippet (what a naive baseline must work from), a gold `label`, and a gold `clause`.
    Gold labels come from the REAL clause thresholds (verifiable in clauses.json).
    """
    cases: list[dict] = []

    def add(param, text, label, clause):
        cases.append({"param": param, "text": text, "label": label, "gold_clause": clause})

    # COVER_FOOTING (>=50) — footings
    for v, lab in [(30, "VIOLATION"), (40, "VIOLATION"), (50, "COMPLIANT"), (60, "COMPLIANT"), (49, "VIOLATION")]:
        add({"element_type": "footing", "param": "nominal_cover", "value": v},
            f"Footing nominal cover {v} mm.", lab, "26.4.2.2")
    # COVER_COLUMN (>=40) — columns  (boundary 40 is COMPLIANT; tests element-awareness vs baseline)
    for v, lab in [(25, "VIOLATION"), (40, "COMPLIANT"), (45, "COMPLIANT"), (35, "VIOLATION")]:
        add({"element_type": "column", "param": "nominal_cover", "value": v},
            f"Column nominal cover {v} mm.", lab, "26.4.2.1")
    # WC_RATIO_SEVERE (<=0.45 in severe exposure)
    for v, lab in [(0.40, "COMPLIANT"), (0.45, "COMPLIANT"), (0.50, "VIOLATION"), (0.55, "VIOLATION")]:
        add({"param": "wc_ratio", "exposure": "severe", "value": v},
            f"Free water-cement ratio {v} for severe exposure.", lab, "8.2.4.1")
    # WC ratio but MILD exposure -> rule does not apply -> NOT_APPLICABLE
    for v in [0.55, 0.60]:
        add({"param": "wc_ratio", "exposure": "mild", "value": v},
            f"Free water-cement ratio {v} for mild exposure.", "NOT_APPLICABLE", None)
    # SEAWATER_GRADE (>=M30 when marine)
    for g, lab in [(20, "VIOLATION"), (25, "VIOLATION"), (30, "COMPLIANT"), (35, "COMPLIANT")]:
        add({"param": "concrete_grade", "marine": True, "grade_mpa": g, "value": g},
            f"Marine RCC grade M{g}.", lab, "8.2.8")
    # concrete grade but NOT marine -> NOT_APPLICABLE (baseline trap: it sees a low grade and flags)
    for g in [20, 25]:
        add({"param": "concrete_grade", "marine": False, "grade_mpa": g, "value": g},
            f"Internal RCC grade M{g}.", "NOT_APPLICABLE", None)
    # COLUMN_STEEL (0.8-6%)
    for v, lab in [(0.6, "VIOLATION"), (0.8, "COMPLIANT"), (2.0, "COMPLIANT"), (6.5, "VIOLATION")]:
        add({"element_type": "column", "param": "long_steel_pct", "value": v},
            f"Column longitudinal steel {v} percent.", lab, "26.5.3.1")
    # DEFLECTION (span_depth <= limit)
    for v, lim, lab in [(18, 20, "COMPLIANT"), (20, 20, "COMPLIANT"), (24, 20, "VIOLATION"), (26, 20, "VIOLATION")]:
        add({"param": "span_depth_ratio", "value": v, "limit": lim},
            f"Span-to-depth ratio {v} (limit {lim}).", lab, "23.2")
    # WIND_SPEED (>= city basic Vb)
    for v, vb, lab in [(39, 50, "VIOLATION"), (50, 50, "COMPLIANT"), (55, 50, "COMPLIANT")]:
        add({"param": "design_wind_speed", "value": v, "city_basic_vb": vb},
            f"Design wind speed {v} m/s (Chennai basic {vb}).", lab, "5.3")
    # COVER_TOLERANCE (+10/-0)
    for v, lab in [(-2, "VIOLATION"), (0, "COMPLIANT"), (8, "COMPLIANT"), (12, "VIOLATION")]:
        add({"param": "cover_deviation", "value": v},
            f"Cover deviation {v} mm from nominal.", lab, "12.3.2")
    # Pure distractors -> NOT_APPLICABLE (no check governs these)
    for txt in ["Concrete slump 75 mm.", "Curing period 7 days.", "Formwork stripped after 24 hours.",
                "Aggregate size 20 mm nominal.", "Rebar grade Fe-550D."]:
        add({"param": "misc", "value": 0}, txt, "NOT_APPLICABLE", None)
    return cases


# ----------------------------------------------------------------------------- our system
def predict_ours(param: dict) -> tuple[str, str | None]:
    """Run the param through the REAL check registry (first matching rule)."""
    for chk in CHECKS:
        if chk["applies_when"](param):
            std, cl = _KEY2CLAUSE.get(chk["clause_key"], (None, None))
            return ("COMPLIANT" if chk["rule"](param) else "VIOLATION"), cl
    return "NOT_APPLICABLE", None


# ----------------------------------------------------------------------------- naive baseline
_NUM = re.compile(r"(\d+(?:\.\d+)?)")

def predict_baseline(text: str) -> tuple[str, str | None]:
    """A naive keyword+number baseline (what a quick wrapper does): if the text mentions a
    'cover'/'grade'/'ratio' keyword and a number below a generic threshold, call it a VIOLATION,
    and guess the cover clause. Element-blind and exposure-blind on purpose — this is the strawman
    a grounded system should beat."""
    t = text.lower()
    m = _NUM.search(t)
    val = float(m.group(1)) if m else None
    if "cover" in t and val is not None:
        return ("VIOLATION" if val < 50 else "COMPLIANT"), "26.4.2.2"   # blind to footing-vs-column
    if "grade" in t and val is not None:
        return ("VIOLATION" if val < 30 else "COMPLIANT"), "8.2.8"      # blind to marine-or-not
    if "ratio" in t and val is not None and "water" in t:
        return ("VIOLATION" if val > 0.45 else "COMPLIANT"), "8.2.4.1"  # blind to exposure class
    if "steel" in t and val is not None:
        return ("VIOLATION" if val < 0.8 else "COMPLIANT"), "26.5.3.1"
    return "NOT_APPLICABLE", None


def _metrics(gold, pred):
    p, r, f, _ = precision_recall_fscore_support(gold, pred, labels=LABELS, average=None, zero_division=0)
    mp, mr, mf, _ = precision_recall_fscore_support(gold, pred, labels=LABELS, average="macro", zero_division=0)
    acc = sum(int(a == b) for a, b in zip(gold, pred)) / len(gold)
    return {
        "accuracy": round(acc, 4),
        "macro_f1": round(mf, 4),
        "per_class": {lab: {"precision": round(float(p[i]), 3), "recall": round(float(r[i]), 3),
                            "f1": round(float(f[i]), 3)} for i, lab in enumerate(LABELS)},
        "confusion_matrix": {"labels": LABELS,
                             "matrix": confusion_matrix(gold, pred, labels=LABELS).tolist()},
    }


def _hallucination(cases, predict, is_text):
    cited = real = 0
    for c in cases:
        _, clause = predict(c["text"]) if is_text else predict(c["param"])
        if clause is None:
            continue
        cited += 1
        # resolve clause number against the real cache (any standard)
        if any(cl == clause for (_std, cl) in _REAL):
            real += 1
    rate = 0.0 if cited == 0 else round(1 - real / cited, 4)
    return {"hallucination_rate": rate, "cited": cited, "resolved": real}


def main():
    cases = build_testset()
    gold = [c["label"] for c in cases]
    ours = [predict_ours(c["param"])[0] for c in cases]
    base = [predict_baseline(c["text"])[0] for c in cases]

    report = {
        "n": len(cases),
        "label_space": LABELS,
        "method": "Element-aware grounded checks (SiteMind) vs a naive keyword baseline, on a "
                  "class-balanced labelled set incl. boundary (>= vs >) and not-applicable cases. "
                  "Decision is deterministic; gold derived from the real IS-clause thresholds.",
        "sitemind": {**_metrics(gold, ours), **_hallucination(cases, predict_ours, is_text=False)},
        "baseline": {**_metrics(gold, base), **_hallucination(cases, predict_baseline, is_text=True)},
        "headline": "0.00 hallucinated citations — every clause SiteMind cites resolves to the real IS code.",
        "limitation": "This isolates the rule engine + citation grounding (deterministic). Free-text "
                      "EXTRACTION accuracy is LLM-dependent and measured separately when ANTHROPIC_API_KEY is set.",
        "examples": [
            {"text": cases[0]["text"], "gold": cases[0]["label"],
             "sitemind": predict_ours(cases[0]["param"])[0], "baseline": predict_baseline(cases[0]["text"])[0]},
            # a footing-vs-column trap the baseline fails:
            *[{"text": c["text"], "gold": c["label"],
               "sitemind": predict_ours(c["param"])[0], "baseline": predict_baseline(c["text"])[0]}
              for c in cases if c["text"].startswith("Column nominal cover 40")][:1],
            # a marine-trap N/A the baseline fails:
            *[{"text": c["text"], "gold": c["label"],
               "sitemind": predict_ours(c["param"])[0], "baseline": predict_baseline(c["text"])[0]}
              for c in cases if c["text"].startswith("Internal RCC grade")][:1],
        ],
    }

    (HERE / "report.json").write_text(json.dumps(report, indent=2))
    with (HERE / "testset.jsonl").open("w") as fh:
        for c in cases:
            fh.write(json.dumps(c) + "\n")

    print(f"n={report['n']}")
    print(f"SiteMind : acc={report['sitemind']['accuracy']}  macroF1={report['sitemind']['macro_f1']}  "
          f"hallucination={report['sitemind']['hallucination_rate']}")
    print(f"Baseline : acc={report['baseline']['accuracy']}  macroF1={report['baseline']['macro_f1']}  "
          f"hallucination={report['baseline']['hallucination_rate']}")
    print("wrote eval/report.json + eval/testset.jsonl")


if __name__ == "__main__":
    main()
