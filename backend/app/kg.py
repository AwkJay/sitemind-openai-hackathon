"""Knowledge Graph — equipment -> spec -> standard -> rfi.

Built in-memory with NetworkX from the structured synthetic data (no Neo4j for
the MVP). /api/kg/{element_id} returns the connected neighbourhood of the
requested element (a submittal id or element name); if it isn't found we return
the whole small graph so the panel always renders.
"""
from __future__ import annotations

from functools import lru_cache

import networkx as nx
from fastapi import APIRouter

from .agents.checks import applicable_checks
from .data_loader import load_rfi_log, load_submittal_params, load_submittals
from .standards import get_clause

router = APIRouter(prefix="/api/kg", tags=["kg"])


@lru_cache(maxsize=1)
def _graph() -> nx.DiGraph:
    g = nx.DiGraph()
    params_by_doc = load_submittal_params()
    titles = {s.get("Submittal No"): s.get("Title", "") for s in load_submittals()}

    for doc_id, params in params_by_doc.items():
        spec_node = doc_id
        g.add_node(spec_node, label=titles.get(doc_id, doc_id), type="spec")
        for p in params:
            elem = p.get("element", "element")
            g.add_node(elem, label=elem, type="equipment")
            g.add_edge(elem, spec_node, label="specified_in")
            # governing standard clauses for this param
            for check in applicable_checks(p):
                cit = get_clause(check["clause_key"])
                if cit is None:
                    continue
                std_node = f"{cit.standard} Cl. {cit.clause}"
                g.add_node(std_node, label=std_node, type="standard")
                g.add_edge(elem, std_node, label="governed_by")
            # the IS 1893 advisory standard for importance factor
            if p.get("param") == "importance_factor":
                cit = get_clause("IS1893_7.2.3")
                if cit:
                    std_node = f"{cit.standard} Cl. {cit.clause}"
                    g.add_node(std_node, label=std_node, type="standard")
                    g.add_edge(elem, std_node, label="governed_by")

    # RFIs link to docs/standards via their Ref field (e.g. "SUB-0142",
    # "DBR-0001 Note 7", "IS456 8.2.8"). Match by the 4-digit submittal sequence.
    import re

    def _seqs(text: str) -> set[str]:
        return set(re.findall(r"\d{3,4}", text or ""))

    doc_seqs = {doc_id: _seqs(doc_id) for doc_id in params_by_doc}
    for r in load_rfi_log():
        rfi_node = r.get("RFI No")
        g.add_node(rfi_node, label=r.get("Subject", rfi_node), type="rfi")
        ref = r.get("Ref") or r.get("Location/WBS") or ""
        ref_seqs = _seqs(ref)
        linked = False
        for doc_id, seqs in doc_seqs.items():
            if ref_seqs & seqs:
                g.add_edge(rfi_node, doc_id, label="references")
                linked = True
        # Link to any standard clause named in the Ref (e.g. "IS456 8.2.8").
        for n in list(g.nodes):
            if g.nodes[n].get("type") == "standard":
                clause_no = n.split("Cl. ")[-1]
                if clause_no and clause_no in ref:
                    g.add_edge(rfi_node, n, label="references")
                    linked = True
        if not linked and doc_seqs:
            g.add_edge(rfi_node, next(iter(doc_seqs)), label="references")
    return g


def _serialize(nodes) -> dict:
    g = _graph()
    sub = g.subgraph(nodes)
    return {
        "nodes": [
            {"id": n, "label": g.nodes[n].get("label", n), "type": g.nodes[n].get("type", "spec")}
            for n in sub.nodes
        ],
        "edges": [
            {"source": u, "target": v, "label": g.edges[u, v].get("label", "")}
            for u, v in sub.edges
        ],
    }


@router.get("/{element_id}")
def get_kg(element_id: str) -> dict:
    g = _graph()
    # Match by exact id or substring (element name / submittal no).
    matches = [n for n in g.nodes if element_id == n or element_id.lower() in str(n).lower()]
    if not matches:
        return _serialize(list(g.nodes))  # whole graph fallback
    # Neighbourhood (undirected) around the matched nodes.
    keep = set(matches)
    und = g.to_undirected()
    for m in matches:
        keep.update(nx.node_connected_component(und, m))
    return _serialize(list(keep))
