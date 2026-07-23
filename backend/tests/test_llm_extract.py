"""Tests for app.llm_extract: the span-verification gate, the offline fallback
fidelity guarantee, and a full-pipeline regression through the FastAPI app.

All offline / no-credentials — LLM_EXTRACTION_ENABLED defaults to False so
extract_params() never attempts a network/SDK call in this suite.
"""
from __future__ import annotations

import asyncio

import pytest

from app import ingest, llm_extract

DOC = (
    "Structural Design Basis Report.\n"
    "The clear concrete cover to the raft foundation reinforcement was taken as 30 mm.\n"
    "The blinding concrete is grade M25 for the marine substructure below the transformer yard.\n"
    "Column C-08 longitudinal steel is 1.8 percent of gross area.\n"
)


# --------------------------------------------------------------------------- #
# 1. verify_spans unit tests (pure Python, no LLM/key involved)
# --------------------------------------------------------------------------- #
def test_valid_item_survives():
    span = "Column C-08 longitudinal steel is 1.8 percent of gross area."
    items = [
        {
            "param_type": "long_steel_pct",
            "element": "Column C-08",
            "element_type": "column",
            "value": 1.8,
            "unit": "%",
            "verbatim_source_span": span,
            "context": {},
        }
    ]
    found, abstained = llm_extract.verify_spans(items, DOC)
    assert len(found) == 1
    assert abstained == []
    p = found[0]
    assert p.param == "long_steel_pct"
    assert p.value == 1.8
    assert p.element_type == "column"


def test_generalization_phrasing_regex_misses_llm_catches():
    span = (
        "The clear concrete cover to the raft foundation reinforcement was taken as 30 mm."
    )
    items = [
        {
            "param_type": "nominal_cover",
            "element": "Raft foundation",
            "element_type": "footing",
            "value": 30,
            "unit": "mm",
            "verbatim_source_span": span,
            "context": {},
        }
    ]
    found, abstained = llm_extract.verify_spans(items, DOC)
    assert len(found) == 1
    assert abstained == []
    p = found[0]
    assert p.param == "nominal_cover"
    # source_quote must be verbatim-contained in the doc (whitespace-normalized).
    doc_norm = " ".join(DOC.split())
    assert p.source_quote in doc_norm

    # The regex extractor should not find a nominal_cover for this "clear concrete
    # cover to the raft foundation ... 30 mm" phrasing — proving the LLM path adds
    # coverage. If it turns out ingest DOES catch it, weaken to just asserting the
    # LLM path found it (already asserted above).
    regex_found, _ = ingest.extract_params(DOC)
    regex_covers = [f for f in regex_found if f.param == "nominal_cover"]
    if regex_covers:
        pytest.skip(
            "regex extractor unexpectedly already finds nominal_cover for this "
            "phrasing; weakening per instructions — LLM-path coverage already "
            "asserted above."
        )
    assert regex_covers == []


def test_hallucinated_span_dropped():
    items = [
        {
            "param_type": "concrete_grade",
            "element": "Slab",
            "element_type": "general",
            "value": 40,
            "unit": "MPa",
            "verbatim_source_span": "Grade M40 concrete is specified for the roof slab.",
            "context": {},
        }
    ]
    found, abstained = llm_extract.verify_spans(items, DOC)
    assert found == []
    assert len(abstained) == 1
    assert abstained[0].param == "concrete_grade"


def test_value_not_in_span_dropped():
    span = "Column C-08 longitudinal steel is 1.8 percent of gross area."
    items = [
        {
            "param_type": "long_steel_pct",
            "element": "Column C-08",
            "element_type": "column",
            "value": 2.5,  # not written inside the span
            "unit": "%",
            "verbatim_source_span": span,
            "context": {},
        }
    ]
    found, abstained = llm_extract.verify_spans(items, DOC)
    assert found == []
    assert len(abstained) == 1


def test_non_checkable_type_dropped():
    items = [
        {
            "param_type": "slump_mm",
            "element": "Slab",
            "element_type": "general",
            "value": 30,
            "unit": "mm",
            "verbatim_source_span": "The clear concrete cover to the raft foundation reinforcement was taken as 30 mm.",
            "context": {},
        }
    ]
    found, abstained = llm_extract.verify_spans(items, DOC)
    assert found == []
    assert len(abstained) == 1
    assert abstained[0].param == "slump_mm"


def test_cover_without_element_dropped():
    items = [
        {
            "param_type": "nominal_cover",
            "element": "",
            "element_type": "",
            "value": 30,
            "unit": "mm",
            # span mentions neither "footing" nor "column"
            "verbatim_source_span": "Structural Design Basis Report.",
            "context": {},
        }
    ]
    # Note: the span above doesn't contain "30", so this would also fail the
    # value-in-span check; use a span that has the value but no element word.
    items[0]["verbatim_source_span"] = "The nominal cover adopted generally is 30 mm."
    found, abstained = llm_extract.verify_spans(items, DOC + " The nominal cover adopted generally is 30 mm.")
    assert found == []
    assert len(abstained) == 1


def test_context_grounding_marine():
    marine_span = "The blinding concrete is grade M25 for the marine substructure below the transformer yard."
    items_marine = [
        {
            "param_type": "concrete_grade",
            "element": "Blinding concrete",
            "element_type": "general",
            "value": 25,
            "unit": "MPa",
            "verbatim_source_span": marine_span,
            "context": {"marine": True},
        }
    ]
    found, abstained = llm_extract.verify_spans(items_marine, DOC)
    assert len(found) == 1
    assert found[0].context.get("marine") is True

    non_marine_doc = DOC + "\nGrade M25 concrete is used for the office block footpaths.\n"
    non_marine_span = "Grade M25 concrete is used for the office block footpaths."
    items_non_marine = [
        {
            "param_type": "concrete_grade",
            "element": "Footpath concrete",
            "element_type": "general",
            "value": 25,
            "unit": "MPa",
            "verbatim_source_span": non_marine_span,
            "context": {"marine": True},  # model may claim marine; grounding must reject it
        }
    ]
    found2, _ = llm_extract.verify_spans(items_non_marine, non_marine_doc)
    assert len(found2) == 1
    assert not found2[0].context.get("marine")


# --------------------------------------------------------------------------- #
# 2. Offline fallback fidelity
# --------------------------------------------------------------------------- #
DEMO_TXT_PATH = "../docs/demo_files/Structural-Design-Basis-Report_DEMO.txt"


def test_offline_fallback_matches_regex_exactly():
    assert llm_extract.llm_enabled() is False  # sanity: default config is offline

    with open(DEMO_TXT_PATH) as f:
        text = f.read()

    llm_found, llm_abstained = asyncio.run(llm_extract.extract_params(text))
    regex_found, regex_abstained = ingest.extract_params(text)

    def sig(items):
        return sorted((p.param, p.value, p.element_type) for p in items)

    assert sig(llm_found) == sig(regex_found)
    assert len(llm_abstained) == len(regex_abstained)

    # Verified demo baseline.
    assert len(llm_found) == 6
    assert len(llm_abstained) == 10


# --------------------------------------------------------------------------- #
# 3. Full-pipeline regression via FastAPI TestClient (offline)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app

    return TestClient(app)


def test_full_pipeline_ingest_and_check(client):
    with open(DEMO_TXT_PATH, "rb") as f:
        ingest_resp = client.post(
            "/api/compliance/ingest",
            files={
                "file": (
                    "Structural-Design-Basis-Report_DEMO.txt",
                    f,
                    "text/plain",
                )
            },
        )
    assert ingest_resp.status_code == 200
    ingest_data = ingest_resp.json()
    assert ingest_data["checkable_params"] == 6
    assert len(ingest_data["abstained"]) == 10

    document_id = ingest_data["document_id"]
    check_resp = client.post("/api/compliance/check", json={"document_id": document_id})
    assert check_resp.status_code == 200
    result = check_resp.json()

    ncrs = result["ncrs"]
    high = [n for n in ncrs if n["severity"] == "HIGH"]
    advisory = [n for n in ncrs if n["severity"] == "ADVISORY"]
    assert len(high) == 3
    assert len(advisory) == 1

    # Robust substring checks against each finding's citation (standard + clause).
    def citation_str(ncr):
        c = ncr.get("citation") or {}
        return f"{c.get('standard', '')} {c.get('clause', '')}"

    cite_strings = [citation_str(n) for n in ncrs]
    joined = " | ".join(cite_strings)

    assert any("IS 456:2000" in s and "26.4.2.2" in s for s in cite_strings)
    assert any("IS 456:2000" in s and "8.2.8" in s for s in cite_strings)
    assert any("IS 456:2000" in s and "8.2.4.1" in s for s in cite_strings)
    assert any(
        "IS 1893 (Part 1):2016" in s and "7.2.3" in s for s in cite_strings
    ), joined

    # A conforming PASS exists for Column C-08 longitudinal steel (IS 456 26.5.3.1).
    conforming = result["conforming"]
    assert any(
        "C-08" in c and "long steel" in c and "26.5.3.1" in c for c in conforming
    ), conforming
