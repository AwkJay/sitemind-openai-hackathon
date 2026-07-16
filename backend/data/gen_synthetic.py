#!/usr/bin/env python3
"""
gen_synthetic.py — SiteMind DATA layer generator.

Emits all synthetic project documents for the fictional project:
    "Hyperscale DC — Chennai, 48 MW, Tier III (Concurrently Maintainable, N+1)"

Chennai = coastal -> SEVERE exposure (IS 456) + cyclonic wind k4 (IS 875) ->
natural, REAL IS-code compliance checks.

Standards (backend/data/standards/clauses.json) are REAL manak-cached clauses and
are NEVER touched by this script — they are only READ to align violating values to
real clause thresholds. Everything else here is clearly synthetic sample data.

Run:  python gen_synthetic.py
Reproducible (RNG seeded). Writes CSV/JSON/MD into this directory tree.
"""
from __future__ import annotations

import csv
import json
import os
import random

random.seed(42)  # reproducibility

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DOCS = os.path.join(DATA_DIR, "project_docs")
SCHEDULE_DIR = os.path.join(DATA_DIR, "schedule")
FIXTURES_DIR = os.path.join(DATA_DIR, "fixtures")
STANDARDS = os.path.join(DATA_DIR, "standards", "clauses.json")

for d in (PROJECT_DOCS, SCHEDULE_DIR, FIXTURES_DIR):
    os.makedirs(d, exist_ok=True)

# Sanity-check we can read (not edit) the real clauses so violating values stay aligned.
with open(STANDARDS, encoding="utf-8") as fh:
    CLAUSES = {c["key"]: c for c in json.load(fh)["clauses"]}

PROJECT = "Hyperscale DC — Chennai, 48 MW, Tier III (Concurrently Maintainable, N+1)"


def write_csv(path: str, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------------------
# 1 + 2. DESIGN BASIS  (prose General Notes  +  structured params JSON)
#    Each param is authored ONCE here as (note_no, sentence, structured-record)
#    so the prose and the JSON can never drift apart.
# ---------------------------------------------------------------------------
# Each entry: note_no, the quotable sentence, and the structured param dict.
DESIGN_PARAMS = [
    {
        "note": 3,
        "sentence": (
            "Site exposure category is classified as SEVERE per IS 456:2000 Table 3 "
            "(coastal Chennai, marine/chloride-laden atmosphere) and shall govern all "
            "durability provisions below."
        ),
        "param": None,  # context-setting note, not a checkable param
    },
    {
        "note": 5,
        "sentence": (
            "Nominal cover to reinforcement for transformer-yard footing F-12 is "
            "specified as 30 mm."
        ),
        "param": {
            "id": "DBP-01",
            "element": "Footing F-12",
            "element_type": "footing",
            "param": "nominal_cover",
            "value": 30,
            "unit": "mm",
            "context": {"exposure": "severe", "marine": True, "city_basic_vb": 50},
            "source_location": "General Note 5",
        },
    },
    {
        "note": 6,
        "sentence": (
            "Nominal cover to longitudinal reinforcement for primary column C-08 is "
            "specified as 45 mm."
        ),
        "param": {
            "id": "DBP-02",
            "element": "Column C-08",
            "element_type": "column",
            "param": "nominal_cover",
            "value": 45,
            "unit": "mm",
            "context": {"exposure": "severe", "marine": False, "city_basic_vb": 50},
            "source_location": "General Note 6",
        },
    },
    {
        "note": 7,
        "sentence": (
            "Concrete grade for all marine/transformer-yard RCC (rafts, footings and "
            "plinths in the transformer and DRUPS yard) is specified as M25."
        ),
        "param": {
            "id": "DBP-03",
            "element": "Transformer-yard RCC (raft/footings/plinths)",
            "element_type": "general",
            "param": "concrete_grade",
            "value": 25,
            "unit": "MPa",
            "context": {"exposure": "severe", "marine": True, "city_basic_vb": 50},
            "source_location": "General Note 7",
        },
    },
    {
        "note": 8,
        "sentence": (
            "The free water-cement ratio for severe-exposure structural concrete is "
            "specified as 0.55."
        ),
        "param": {
            "id": "DBP-04",
            "element": "Severe-exposure structural concrete (mix design)",
            "element_type": "general",
            "param": "wc_ratio",
            "value": 0.55,
            "unit": "ratio",
            "context": {"exposure": "severe", "marine": True, "city_basic_vb": 50},
            "source_location": "General Note 8",
        },
    },
    {
        "note": 9,
        "sentence": (
            "Longitudinal reinforcement for column C-08 is provided at 0.6 percent of "
            "the gross cross-sectional area of the column."
        ),
        "param": {
            "id": "DBP-05",
            "element": "Column C-08",
            "element_type": "column",
            "param": "long_steel_pct",
            "value": 0.6,
            "unit": "%",
            "context": {"exposure": "severe", "marine": False, "city_basic_vb": 50},
            "source_location": "General Note 9",
        },
    },
    {
        "note": 11,
        "sentence": (
            "The seismic Importance Factor I is adopted as 1.0 for the data-centre "
            "buildings (Seismic Zone III, Z = 0.16)."
        ),
        "param": {
            "id": "DBP-06",
            "element": "Data-centre buildings (global seismic basis)",
            "element_type": "general",
            "param": "importance_factor",
            "value": 1.0,
            "unit": "factor",
            "context": {"exposure": "severe", "marine": False, "city_basic_vb": 50},
            "source_location": "General Note 11",
        },
    },
    {
        "note": 13,
        "sentence": (
            "Design wind speed for the Chennai site is taken as 50 m/s basic wind speed "
            "(IS 875 Part 3 Zone, cyclonic east coast, k4 applied)."
        ),
        "param": {
            "id": "DBP-07",
            "element": "Roof cladding & lateral system (wind basis)",
            "element_type": "general",
            "param": "design_wind_speed",
            "value": 50,
            "unit": "m/s",
            "context": {"exposure": "severe", "marine": True, "city_basic_vb": 50},
            "source_location": "General Note 13",
        },
    },
    {
        "note": 15,
        "sentence": (
            "The span-to-effective-depth ratio for the typical white-space suspended "
            "slab is 24, against a permissible limit of 26."
        ),
        "param": {
            "id": "DBP-08",
            "element": "White-space suspended slab (typical bay)",
            "element_type": "slab",
            "param": "span_depth_ratio",
            "value": 24,
            "unit": "ratio",
            "context": {"exposure": "severe", "marine": False, "city_basic_vb": 50,
                        "limit": 26},
            "source_location": "General Note 15",
        },
    },
]


def gen_design_basis_md() -> None:
    notes = []
    # Intro / fixed front-matter notes
    fixed = {
        1: "This Structural Design Basis Report governs the civil and structural design of the "
           f"\"{PROJECT}\" project and shall be read with the latest revision of the project drawings.",
        2: "All structural design conforms to IS 456:2000 (Plain and Reinforced Concrete), "
           "IS 875 (Part 3):2015 (Wind Loads) and IS 1893 (Part 1):2016 (Earthquake Resistant Design), "
           "unless a more stringent project specification governs.",
        4: "Concrete grades adopted on the project are M25, M30 and M40; reinforcement is TMT Fe 550D "
           "conforming to IS 1786.",
        10: "Foundations are isolated and combined RCC footings on medium-stiff sandy clay, with a net "
            "safe bearing capacity of 180 kN/m2 at founding level.",
        12: "Seismic Zone Factor Z is taken as 0.16 (Zone III, Chennai) with Response Reduction Factor "
            "R = 5.0 for the special moment-resisting frames.",
        14: "Importance Factor for wind (k1, risk coefficient) is taken for a structure with a 100-year "
            "mean return period given the mission-critical, concurrently-maintainable nature of the facility.",
        16: "Deflection of all flexural members is limited to span/250 (final) and span/350 or 20 mm "
            "(post-partition) per IS 456:2000 Clause 23.2 to protect raised access floors and cable trays.",
    }
    by_note = {d["note"]: d["sentence"] for d in DESIGN_PARAMS}
    by_note.update(fixed)
    max_note = max(by_note)

    lines = [
        f"# Structural Design Basis Report — General Notes",
        "",
        f"**Project:** {PROJECT}  ",
        "**Document No:** DC1-02-DBR-0001-R2  ",
        "**Discipline:** Civil / Structural  ",
        "**Status:** Issued for Construction (IFC)  ",
        "",
        "> SAMPLE / SYNTHETIC DATA — generated for the SiteMind demo. Engineering values are "
        "fictional but internally consistent; standards citations are real (see standards/clauses.json).",
        "",
        "## General Notes",
        "",
    ]
    for n in range(1, max_note + 1):
        if n in by_note:
            lines.append(f"**Note {n}.** {by_note[n]}")
            lines.append("")
    with open(os.path.join(PROJECT_DOCS, "design_basis.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))


def gen_design_basis_params_json() -> None:
    records = []
    for d in DESIGN_PARAMS:
        if d["param"] is None:
            continue
        p = dict(d["param"])
        p["source_quote"] = d["sentence"]
        # canonical field order
        rec = {
            "id": p["id"],
            "element": p["element"],
            "element_type": p["element_type"],
            "param": p["param"],
            "value": p["value"],
            "unit": p["unit"],
            "context": p["context"],
            "source_quote": p["source_quote"],
            "source_location": p["source_location"],
        }
        records.append(rec)
    with open(os.path.join(PROJECT_DOCS, "design_basis_params.json"), "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------------------
# 3. SUBMITTAL REGISTER
# ---------------------------------------------------------------------------
def gen_submittals() -> None:
    header = ["Submittal No", "Rev", "Title", "Spec Section", "Discipline", "Type",
              "Contractor", "Date Submitted", "Status", "Days in Review"]
    rows = [
        ["DC1-02-DBR-0001-R2", "R2", "Structural Design Basis Report",
         "03 30 00", "Structural", "PD", "L&T Construction", "2026-03-02",
         "A – Approved", 9],
        ["DC1-02-SD-0142-R1", "R1", "Foundation shop drawing — footing F-12 transformer yard (cover 30mm, M25, severe)",
         "03 30 00", "Structural", "SD", "L&T Construction", "2026-04-18",
         "C – Revise & Resubmit", 14],
        ["DC1-02-MOS-0210-R0", "R0", "Method statement — concrete mix for severe-exposure raft (w/c 0.55)",
         "03 31 00", "Structural", "MOS", "L&T Construction", "2026-04-22",
         "C – Revise & Resubmit", 11],
        ["DC1-02-SD-0156-R0", "R0", "Reinforcement detailing — column C-08 (0.6% long. steel, cover 45mm)",
         "03 21 00", "Structural", "SD", "L&T Construction", "2026-04-25",
         "Pending", 6],
        ["DC1-02-MAT-0044-R1", "R1", "TMT Fe-550D reinforcement — mill test certificates",
         "03 21 00", "Structural", "MAT", "L&T Construction", "2026-03-28",
         "A – Approved", 7],
        ["DC1-09-SD-0508-R0", "R0", "Anti-static raised access floor — layout & point-load calc",
         "09 65 00", "Architecture", "SD", "Tata Projects", "2026-05-10",
         "B – Approved as Noted", 8],
        ["DC1-15-PD-0712-R1", "R1", "CRAH unit 150kW EC-fan (N+1) — product data & psychrometrics",
         "23 65 00", "Mechanical", "PD", "Voltas Ltd", "2026-05-14",
         "B – Approved as Noted", 10],
        ["DC1-16-PD-0905-R0", "R0", "DRUPS 2.5MW (2N) — product data & single-line",
         "26 32 13", "Electrical", "PD", "Sterling & Wilson", "2026-05-18",
         "Pending", 12],
        ["DC1-16-SD-0931-R0", "R0", "LV switchgear 415V Form-4b — GA & busway routing",
         "26 24 13", "Electrical", "SD", "Sterling & Wilson", "2026-05-21",
         "C – Revise & Resubmit", 13],
        ["DC1-01-SD-0301-R0", "R0", "Roof cladding — design wind pressure & fastener schedule",
         "07 41 13", "Architecture", "SD", "Tata Projects", "2026-05-06",
         "B – Approved as Noted", 9],
        ["DC1-21-MAT-0120-R0", "R0", "Fire-stopping system — material data & UL listing",
         "07 84 00", "Fire", "MAT", "Tata Projects", "2026-05-24",
         "A – Approved", 5],
        ["DC1-16-SMP-0140-R0", "R0", "Busway 4000A sandwich — sample & type-test report",
         "26 25 00", "Electrical", "SMP", "Sterling & Wilson", "2026-05-27",
         "Pending", 4],
    ]
    write_csv(os.path.join(PROJECT_DOCS, "submittals.csv"), header, rows)


# ---------------------------------------------------------------------------
# 4. RFI LOG
# ---------------------------------------------------------------------------
def gen_rfi_log() -> None:
    header = ["RFI No", "Date", "Discipline", "Subject", "Question", "Ref",
              "Status", "Cost Impact", "Schedule Impact (days)"]
    rows = [
        ["RFI-CIV-061", "2026-02-11", "Civil/Structural",
         "M30 vs M35 for severe exposure raft",
         "Design basis lists M30 for the severe-exposure raft; should we upgrade to M35 to improve "
         "chloride resistance at the coastal site?",
         "DBR-0001 Note 4 / IS456 8.2.4.1",
         "Closed", "INR 12,40,000", 0,
         ],
        ["RFI-CIV-072", "2026-04-26", "Civil/Structural",
         "M25 vs M30 for marine/transformer-yard RCC",
         "Note 7 of the design basis specifies M25 for marine/transformer-yard RCC. IS 456 Cl 8.2.8 "
         "requires RCC in/near sea-water to be at least M30. Please confirm grade for footing F-12 and "
         "the transformer-yard raft before casting.",
         "DBR-0001 Note 7 / IS456 8.2.8 / SUB-0142",
         "Open", "TBC", 0,
         ],
        ["RFI-CIV-073", "2026-04-20", "Civil/Structural",
         "Nominal cover to footing F-12",
         "Shop drawing SUB-0142 shows 30 mm nominal cover to footing F-12. Confirm required cover for "
         "footings in severe coastal exposure.",
         "SUB-0142 / IS456 26.4.2.2",
         "Open", "TBC", 0,
         ],
        ["RFI-CIV-074", "2026-04-23", "Civil/Structural",
         "w/c ratio for severe-exposure concrete",
         "MOS-0210 states free w/c ratio 0.55 for the severe-exposure raft. Please confirm the maximum "
         "permissible w/c ratio for severe exposure per Table 5.",
         "MOS-0210 / IS456 8.2.4.1",
         "Open", "TBC", 0,
         ],
        ["RFI-STR-068", "2026-04-28", "Civil/Structural",
         "Importance factor for data-centre buildings",
         "Design basis adopts seismic Importance Factor I = 1.0. Given the Tier-III lifeline nature of the "
         "facility, should I = 1.5 be adopted per IS 1893 Pt1 Table 8?",
         "DBR-0001 Note 11 / IS1893 7.2.3",
         "Open", "TBC", 0,
         ],
        ["RFI-CIV-055", "2026-02-02", "Civil/Structural",
         "Net safe bearing capacity confirmation",
         "Confirm net SBC of 180 kN/m2 at founding level against the geotechnical report.",
         "DBR-0001 Note 10",
         "Closed", "Nil", 0,
         ],
        ["RFI-ARC-031", "2026-05-08", "Architecture",
         "Raised floor finished floor height",
         "Confirm FFH of 900 mm for the anti-static raised access floor in white space.",
         "SUB-0508",
         "Answered", "Nil", 0,
         ],
        ["RFI-MEP-090", "2026-05-15", "Mechanical",
         "CRAH chilled-water supply temperature",
         "Confirm CHW supply temperature of 18 degC for the N+1 CRAH selection.",
         "SUB-0712",
         "Answered", "Nil", 0,
         ],
        ["RFI-EL-110", "2026-05-20", "Electrical",
         "DRUPS short-circuit withstand coordination",
         "Confirm fault level 50 kA for 1s at the 415V LV board for DRUPS/switchgear coordination.",
         "SUB-0905 / SUB-0931",
         "Open", "TBC", 0,
         ],
        ["RFI-EL-112", "2026-05-22", "Electrical",
         "LV switchgear delivery vs critical path",
         "Vendor indicates LV switchgear lead time slipping by ~6 weeks. Confirm impact on commissioning "
         "L4 milestone and any acceleration option.",
         "SUB-0931 / Schedule DC1-04-EL-030",
         "Open", "Potential", 28,
         ],
        ["RFI-CIV-066", "2026-04-02", "Civil/Structural",
         "Construction joint location in raft",
         "Propose construction joint location for the 1240 cum raft pour sequencing.",
         "BOQ 2.04",
         "Answered", "Nil", 0,
         ],
        ["RFI-FIRE-020", "2026-05-26", "Fire",
         "Fire-stopping rating at busway penetrations",
         "Confirm 2-hour fire-stopping rating at busway floor penetrations.",
         "SUB-0120 / SUB-0140",
         "Open", "Nil", 0,
         ],
        ["RFI-ARC-035", "2026-05-09", "Architecture",
         "Roof cladding fastener pull-out for cyclonic wind",
         "Confirm fastener pull-out capacity adequate for 50 m/s cyclonic design wind speed.",
         "SUB-0301 / IS875 5.3",
         "Answered", "Nil", 0,
         ],
        ["RFI-MEP-095", "2026-05-30", "Mechanical",
         "Hot-aisle containment clearance to sprinklers",
         "Confirm minimum clearance from hot-aisle containment roof to sprinkler heads.",
         "White-space layout",
         "Open", "Nil", 0,
         ],
    ]
    write_csv(os.path.join(PROJECT_DOCS, "rfi_log.csv"), header, rows)


# ---------------------------------------------------------------------------
# 5. BILL OF QUANTITIES
# ---------------------------------------------------------------------------
def gen_boq() -> None:
    header = ["Item No", "Code", "Description", "Unit", "Qty", "Rate_INR", "Amount_INR"]
    rows = [
        ["2.04", "CPWD 4.1.8", "PCC 1:1.5:3 (M25) in raft foundation incl shuttering/curing",
         "cum", 1240, 7850, 9734000],
        ["2.11", "CSI 03 30 00", "RCC M40 in columns & shear walls",
         "cum", 860.5, 9420, 8105910],
        ["2.14", "CSI 03 30 00", "RCC M30 in transformer-yard raft, footings & plinths (severe exposure)",
         "cum", 540, 8650, 4671000],
        ["2.18", "-", "TMT Fe-550D reinforcement cut/bent/placed",
         "MT", 312, 78500, 24492000],
        ["7.12", "CSI 07 41 13", "Insulated roof cladding system, cyclonic-rated fasteners",
         "sqm", 9600, 2150, 20640000],
        ["9.06", "CSI 09 65 00", "Anti-static raised access floor 600x600 1250kg point load 900mm FFH",
         "sqm", 4800, 6250, 30000000],
        ["15.41", "CSI 23 65 00", "CRAH unit 150kW sensible EC fans (N+1) supply/install/test",
         "nos", 24, 2850000, 68400000],
        ["16.19", "CSI 26 32 13", "DRUPS 2.5MW (2N) incl commissioning",
         "nos", 4, 62000000, 248000000],
        ["16.24", "CSI 26 24 13", "LV switchgear 415V Form-4b, 4000A, 50kA/1s",
         "nos", 8, 9650000, 77200000],
        ["16.31", "CSI 26 25 00", "Sandwich busway 4000A incl tap-off & fittings",
         "RM", 640, 42500, 27200000],
    ]
    write_csv(os.path.join(PROJECT_DOCS, "boq.csv"), header, rows)


# ---------------------------------------------------------------------------
# 6. PROJECT SCHEDULE  (latent slip driver = LV switchgear / DRUPS)
# ---------------------------------------------------------------------------
def gen_schedule() -> None:
    header = ["wbs_id", "task", "phase", "planned_start_day", "duration_days",
              "predecessors", "pct_complete", "procurement_item", "lead_time_days",
              "vendor_status", "weather_sensitive"]
    # rows: wbs_id, task, phase, start, dur, preds(list), pct, proc_item, lead, vendor, weather
    R = [
        ("DC1-01-EN-010", "Site mobilisation & enabling works", "Enabling", 0, 15, [], 100, "", 0, "na", False),
        ("DC1-01-EN-020", "Site clearing, fencing & temporary power", "Enabling", 5, 12, ["DC1-01-EN-010"], 100, "", 0, "na", True),
        ("DC1-01-EN-030", "Bulk earthwork & cut/fill to formation", "Enabling", 15, 20, ["DC1-01-EN-020"], 100, "", 0, "na", True),
        ("DC1-01-EN-040", "Dewatering & ground improvement", "Enabling", 30, 18, ["DC1-01-EN-030"], 90, "", 0, "na", True),

        ("DC1-02-CS-010", "Piling / raft excavation", "Civil/Structural", 45, 22, ["DC1-01-EN-040"], 80, "", 0, "na", True),
        ("DC1-02-CS-020", "PCC & raft foundation (1240 cum)", "Civil/Structural", 60, 25, ["DC1-02-CS-010"], 60, "", 0, "na", True),
        ("DC1-02-CS-030", "Transformer-yard footings & plinths (F-12 etc.)", "Civil/Structural", 78, 18, ["DC1-02-CS-020"], 40, "", 0, "na", True),
        ("DC1-02-CS-040", "RCC columns C-08 etc. up to plinth", "Civil/Structural", 85, 20, ["DC1-02-CS-020"], 35, "", 0, "na", False),
        ("DC1-02-CS-050", "Superstructure RCC frame & shear walls", "Civil/Structural", 100, 40, ["DC1-02-CS-040"], 20, "", 0, "na", False),
        ("DC1-02-CS-060", "Suspended white-space slabs", "Civil/Structural", 130, 30, ["DC1-02-CS-050"], 10, "", 0, "na", False),
        ("DC1-02-CS-070", "Roof structure & cyclonic-rated cladding", "Civil/Structural", 150, 25, ["DC1-02-CS-050"], 5, "", 0, "na", True),

        ("DC1-03-AF-010", "Block work & internal partitions", "Architecture/Finishes", 160, 30, ["DC1-02-CS-060"], 0, "", 0, "na", False),
        ("DC1-03-AF-020", "Waterproofing & screed", "Architecture/Finishes", 175, 20, ["DC1-02-CS-070"], 0, "", 0, "na", False),
        ("DC1-03-AF-030", "Anti-static raised access floor (white space)", "Architecture/Finishes", 195, 25, ["DC1-03-AF-010"], 0, "Raised access floor", 70, "on-track", False),
        ("DC1-03-AF-040", "Painting, doors & architectural finishes", "Architecture/Finishes", 210, 30, ["DC1-03-AF-010"], 0, "", 0, "na", False),

        ("DC1-04-EL-010", "Primary cable containment & earthing grid", "MEP", 170, 28, ["DC1-02-CS-050"], 0, "", 0, "na", False),
        ("DC1-04-EL-020", "DRUPS 2.5MW (2N) — procurement & delivery", "MEP", 120, 30, ["DC1-02-CS-040"], 0, "DRUPS 2.5MW", 180, "slipping", False),
        ("DC1-04-EL-030", "LV switchgear 415V — procurement & delivery", "MEP", 130, 25, ["DC1-02-CS-040"], 0, "LV switchgear 4000A", 150, "slipping", False),
        ("DC1-04-EL-040", "DRUPS installation & internal alignment", "MEP", 215, 20, ["DC1-04-EL-020", "DC1-03-AF-020"], 0, "", 0, "na", False),
        ("DC1-04-EL-050", "LV switchgear installation & busway", "MEP", 220, 22, ["DC1-04-EL-030", "DC1-04-EL-010"], 0, "Busway 4000A", 90, "slipping", False),
        ("DC1-04-EL-060", "rPDU / RPP / busway fit-out", "MEP", 240, 18, ["DC1-04-EL-050"], 0, "", 0, "na", False),
        ("DC1-04-ME-010", "Chilled-water plant & piping", "MEP", 180, 35, ["DC1-02-CS-060"], 0, "Chiller plant", 120, "on-track", False),
        ("DC1-04-ME-020", "CRAH units (N+1) install & pipe-up", "MEP", 225, 25, ["DC1-04-ME-010", "DC1-03-AF-030"], 0, "CRAH 150kW", 100, "on-track", False),
        ("DC1-04-FI-010", "Fire detection, suppression & fire-stopping", "MEP", 230, 22, ["DC1-03-AF-040"], 0, "", 0, "na", False),

        ("DC1-05-WS-010", "Hot/cold-aisle containment & cabinet install", "White-Space Fit-out", 250, 20, ["DC1-04-EL-060", "DC1-04-ME-020"], 0, "", 0, "na", False),
        ("DC1-05-WS-020", "BMS / EPMS integration & wiring", "White-Space Fit-out", 255, 18, ["DC1-04-EL-060"], 0, "", 0, "na", False),

        ("DC1-06-CX-010", "L1 FAT — DRUPS & switchgear (factory)", "Commissioning L1-L5", 110, 10, ["DC1-04-EL-020"], 0, "", 0, "na", False),
        ("DC1-06-CX-020", "L2 installation verification", "Commissioning L1-L5", 260, 12, ["DC1-05-WS-010", "DC1-05-WS-020"], 0, "", 0, "na", False),
        ("DC1-06-CX-030", "L3 pre-functional / SAT", "Commissioning L1-L5", 272, 12, ["DC1-06-CX-020"], 0, "", 0, "na", False),
        ("DC1-06-CX-040", "L4 functional testing (per system)", "Commissioning L1-L5", 284, 15, ["DC1-06-CX-030"], 0, "", 0, "na", False),
        ("DC1-06-CX-050", "L5 integrated systems test (IST, load-bank, pull-the-plug)", "Commissioning L1-L5", 299, 14, ["DC1-06-CX-040"], 0, "", 0, "na", False),

        ("DC1-07-SN-010", "Snagging / punch-list close-out", "Snagging", 313, 14, ["DC1-06-CX-050"], 0, "", 0, "na", False),
        ("DC1-07-SN-020", "Handover & as-built documentation", "Snagging", 327, 10, ["DC1-07-SN-010"], 0, "", 0, "na", False),
    ]
    rows = []
    for (wid, task, phase, start, dur, preds, pct, proc, lead, vendor, weather) in R:
        rows.append([wid, task, phase, start, dur, ",".join(preds), pct, proc, lead,
                     vendor, str(weather).lower()])
    write_csv(os.path.join(SCHEDULE_DIR, "schedule.csv"), header, rows)


# ---------------------------------------------------------------------------
# 7a. FIXTURES — compliance prose (offline LLM fallback)
# ---------------------------------------------------------------------------
def gen_compliance_prose() -> None:
    prose = {
        "DBP-01": {
            "finding": "The structural design basis specifies 30 mm nominal cover to reinforcement for "
                       "transformer-yard footing F-12.",
            "why_it_matters": "30 mm cover in a severe coastal (chloride-laden) exposure accelerates rebar "
                              "corrosion, shortening the service life of a foundation carrying a 2.5 MVA "
                              "transformer — a single-point uptime risk for a concurrently-maintainable Tier-III DC.",
            "corrective_action": "Revise the design basis and shop drawing SUB-0142 to 50 mm nominal cover for "
                                 "footing F-12 and re-issue for approval before casting.",
        },
        "DBP-03": {
            "finding": "Marine/transformer-yard RCC (rafts, footings and plinths) is specified at grade M25.",
            "why_it_matters": "Concrete in or near sea-water must be at least M30 for reinforced concrete; M25 "
                              "leaves insufficient density and cover-quality to resist chloride ingress at a "
                              "coastal site, risking premature durability failure of power-block foundations.",
            "corrective_action": "Upgrade the marine/transformer-yard RCC grade to a minimum of M30 (M35 "
                                 "recommended per the precedent in RFI-CIV-061) and revise the mix design and BoQ.",
        },
        "DBP-04": {
            "finding": "The free water-cement ratio for severe-exposure structural concrete is specified as 0.55.",
            "why_it_matters": "Table 5 caps the free w/c ratio for severe exposure to limit chloride and "
                              "moisture ingress; 0.55 produces a more permeable matrix that undermines the "
                              "durability and 50-year design life expected of mission-critical infrastructure.",
            "corrective_action": "Revise the mix design (MOS-0210) to a maximum free w/c ratio of 0.45 for "
                                 "severe exposure and re-submit the method statement.",
        },
        "DBP-05": {
            "finding": "Column C-08 is detailed with 0.6 percent longitudinal reinforcement of the gross "
                       "cross-sectional area.",
            "why_it_matters": "Below the 0.8 percent minimum, the column has inadequate reserve capacity and "
                              "ductility for the seismic and equipment loads of a data hall, reducing structural "
                              "robustness under the design earthquake.",
            "corrective_action": "Increase column C-08 longitudinal steel to at least 0.8 percent of the gross "
                                 "section and revise reinforcement drawing SUB-0156 before fabrication.",
        },
        "DBP-06": {
            "finding": "The seismic design adopts Importance Factor I = 1.0 for the data-centre buildings.",
            "why_it_matters": "IS 1893 Table 8 places lifeline/critical facilities (power stations, telephone "
                              "exchanges) at I = 1.5, and Note 1 lets the owner adopt a higher I. A Tier-III data "
                              "centre is a textbook modern lifeline facility, so I = 1.0 may under-design the "
                              "lateral system relative to its true criticality.",
            "corrective_action": "Review the seismic basis with the EOR and consider adopting I = 1.5 for the "
                                 "mission-critical blocks; document the agreed value in the design basis.",
            "recommendation": "Recommend adopting Importance Factor I = 1.5 for the data-centre buildings, "
                              "treating the Tier-III facility as a lifeline structure.",
            "confirm_with": "Engineer of Record (EOR) — IS 1893 Pt1:2016 Cl 7.2.3 Note 1 permits a higher I at the "
                            "owner's/engineer's discretion.",
        },
    }
    with open(os.path.join(FIXTURES_DIR, "compliance_prose.json"), "w", encoding="utf-8") as fh:
        json.dump(prose, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------------------
# 7b. FIXTURES — copilot golden answers (offline RAG fallback)
# ---------------------------------------------------------------------------
def gen_copilot_answers() -> None:
    answers = {
        "transformer-yard-footing-grade-cover": {
            "answer": "For transformer-yard footings (e.g. F-12) in Chennai's severe coastal exposure, the design "
                      "basis currently specifies M25 with 30 mm cover — both non-conforming. IS 456 requires RCC "
                      "in/near sea-water to be at least M30 (Cl 8.2.8) and footing cover to be at least 50 mm "
                      "(Cl 26.4.2.2). The footings should be M30 (M35 recommended) with 50 mm nominal cover.",
            "sources": [
                {"label": "IS 456:2000 Cl 8.2.8", "detail": "RCC in/near sea-water shall be at least M30.",
                 "verify_url": "http://gaudi.local/manak/#is456_2000/clause:8.2.8"},
                {"label": "IS 456:2000 Cl 26.4.2.2", "detail": "For footings minimum cover shall be 50 mm.",
                 "verify_url": "http://gaudi.local/manak/#is456_2000/clause:26.4.2"},
                {"label": "Design Basis Note 5 & 7", "detail": "Specifies 30 mm cover and M25 for transformer-yard RCC."},
                {"label": "SUB-0142 R1", "detail": "Foundation shop drawing for footing F-12 — Revise & Resubmit."},
            ],
        },
        "open-rfis-marine-cooling-rcc": {
            "answer": "There are open RFIs on the marine RCC: RFI-CIV-072 questions M25 vs M30 for the marine/"
                      "transformer-yard RCC (links to IS 456 Cl 8.2.8 and SUB-0142), RFI-CIV-073 questions the 30 mm "
                      "cover to footing F-12, and RFI-CIV-074 questions the 0.55 w/c ratio for severe exposure. All "
                      "three are currently Open and tied to the same coastal-durability compliance issue.",
            "sources": [
                {"label": "RFI-CIV-072 (Open)", "detail": "M25 vs M30 for marine/transformer-yard RCC."},
                {"label": "RFI-CIV-073 (Open)", "detail": "Nominal cover to footing F-12."},
                {"label": "RFI-CIV-074 (Open)", "detail": "w/c ratio 0.55 for severe-exposure concrete."},
            ],
        },
        "design-wind-speed-chennai": {
            "answer": "The design basis adopts a basic wind speed of 50 m/s for the Chennai site (cyclonic east "
                      "coast, k4 applied), which is consistent with IS 875 (Part 3):2015. The design wind speed "
                      "Vz = Vb·k1·k2·k3·k4 must not fall below this city basic value. The 50 m/s basis is conforming.",
            "sources": [
                {"label": "IS 875 (Part 3):2015 Cl 5.3", "detail": "Vz = Vb·k1·k2·k3·k4; includes cyclonic k4.",
                 "verify_url": "http://gaudi.local/manak/#is875_part3_2015/clause:5.3"},
                {"label": "Design Basis Note 13", "detail": "Design wind speed taken as 50 m/s (cyclonic, k4)."},
            ],
        },
        "m30-vs-m35-severe-exposure-seen-before": {
            "answer": "Yes — this exact question was resolved before. RFI-CIV-061 (Closed) asked whether to upgrade "
                      "the severe-exposure raft from M30 to M35, and the resolution was to upgrade to M35 to improve "
                      "chloride resistance at the coastal site. The same precedent supports upgrading the current "
                      "M25 marine RCC (now under RFI-CIV-072) to at least M30, ideally M35.",
            "sources": [
                {"label": "RFI-CIV-061 (Closed)", "detail": "M30 vs M35 for severe exposure raft — upgraded to M35."},
                {"label": "IS 456:2000 Cl 8.2.4.1", "detail": "Free w/c ratio / cement content governed by exposure (Table 5).",
                 "verify_url": "http://gaudi.local/manak/#is456_2000/clause:8.2.4.1"},
            ],
            "seen_before": {
                "rfi_id": "RFI-CIV-061",
                "summary": "M30 vs M35 for severe-exposure raft at the coastal Chennai site.",
                "resolution": "Upgraded to M35 to improve chloride resistance for severe coastal exposure.",
            },
        },
        "which-submittals-non-conforming": {
            "answer": "Three submittals are non-conforming against real IS 456 clauses: SUB-0142 (footing F-12 — "
                      "30 mm cover vs 50 mm required, and M25 vs M30 marine RCC), MOS-0210 (severe-exposure mix at "
                      "w/c 0.55 vs 0.45 max), and SUB-0156 (column C-08 at 0.6% longitudinal steel vs 0.8% minimum). "
                      "All three are in Revise & Resubmit / Pending status pending correction.",
            "sources": [
                {"label": "SUB-0142 R1 (C – Revise & Resubmit)", "detail": "30 mm cover & M25 — violates IS456 26.4.2.2 / 8.2.8."},
                {"label": "MOS-0210 R0 (C – Revise & Resubmit)", "detail": "w/c 0.55 — violates IS456 8.2.4.1 / Table 5."},
                {"label": "SUB-0156 R0 (Pending)", "detail": "0.6% column steel — violates IS456 26.5.3.1."},
            ],
        },
        "importance-factor-data-centre": {
            "answer": "A Tier-III/IV data centre is arguably a lifeline facility. IS 1893 (Part 1):2016 Cl 7.2.3 "
                      "Table 8 lists power-station and telephone-exchange buildings at I = 1.5, and Note 1 lets the "
                      "owner adopt a higher I. The design basis currently uses I = 1.0 (advisory flag); SiteMind "
                      "recommends adopting I = 1.5 for the mission-critical blocks — confirm with the EOR.",
            "sources": [
                {"label": "IS 1893 (Part 1):2016 Cl 7.2.3 + Table 8", "detail": "Lifeline/critical buildings take I = 1.5; Note 1 permits higher I.",
                 "verify_url": "http://gaudi.local/manak/#is1893_part1_2016/clause:7.2.3"},
                {"label": "Design Basis Note 11", "detail": "Adopts I = 1.0 (Zone III, Z = 0.16)."},
                {"label": "RFI-STR-068 (Open)", "detail": "Questions whether I = 1.5 should be adopted for the DC."},
            ],
        },
    }
    with open(os.path.join(FIXTURES_DIR, "copilot_answers.json"), "w", encoding="utf-8") as fh:
        json.dump(answers, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


# ---------------------------------------------------------------------------
# README
# ---------------------------------------------------------------------------
def gen_readme() -> None:
    txt = f"""# SiteMind — DATA layer

Synthetic-but-realistic project documents for the fictional project:

> **{PROJECT}**

Chennai = coastal -> **severe exposure** (IS 456) + **cyclonic wind k4** (IS 875),
which makes the real IS-code compliance checks natural. All values below are
**sample data**; the only REAL artefact is `standards/clauses.json` (manak-cached
IS clauses — the ground truth for every citation, never edited).

Regenerate everything reproducibly with:

```bash
python gen_synthetic.py
```

## Files

| File | Description |
|---|---|
| `gen_synthetic.py` | Seeded generator that emits every file below. |
| `standards/clauses.json` | REAL manak-cached IS 456 / 875 / 1893 clauses (read-only ground truth). |
| `project_docs/design_basis.md` | Structural Design Basis Report as numbered General Notes; each design parameter is a quotable sentence (for extract-with-source). |
| `project_docs/design_basis_params.json` | The same parameters as STRUCTURED data so the backend needs no OCR. |
| `project_docs/submittals.csv` | Submittal register (~12 rows) incl. the violating foundation drawing. |
| `project_docs/rfi_log.csv` | RFI log (~14 rows) incl. open marine-RCC RFI + closed seen-before RFI-CIV-061. |
| `project_docs/boq.csv` | Bill of Quantities (~10 rows) — PCC raft, RCC, TMT, raised floor, CRAH, DRUPS, switchgear. |
| `schedule/schedule.csv` | ~33 activities across all phases; latent slip driver = LV switchgear / DRUPS on critical path, `vendor_status=slipping`, long lead time. |
| `fixtures/compliance_prose.json` | Offline pre-written NCR prose per violating/advisory param id. |
| `fixtures/copilot_answers.json` | Offline answers for ~6 golden copilot questions, with sources + seen-before. |

## Schemas

**design_basis_params.json** — array of:
`{{ id, element, element_type (footing|column|slab|general), param (nominal_cover|concrete_grade|wc_ratio|long_steel_pct|importance_factor|design_wind_speed|span_depth_ratio), value (number), unit, context:{{ exposure, marine:bool, city_basic_vb }}, source_quote, source_location }}`

**submittals.csv** — `Submittal No,Rev,Title,Spec Section,Discipline,Type,Contractor,Date Submitted,Status,Days in Review`
Status codes: `A – Approved`, `B – Approved as Noted`, `C – Revise & Resubmit`, `Pending`.

**rfi_log.csv** — `RFI No,Date,Discipline,Subject,Question,Ref,Status,Cost Impact,Schedule Impact (days)`

**boq.csv** — `Item No,Code,Description,Unit,Qty,Rate_INR,Amount_INR`

**schedule.csv** — `wbs_id,task,phase,planned_start_day,duration_days,predecessors,pct_complete,procurement_item,lead_time_days,vendor_status,weather_sensitive`

**fixtures/compliance_prose.json** — `{{ <param_id>: {{ finding, why_it_matters, corrective_action, recommendation?, confirm_with? }} }}`

**fixtures/copilot_answers.json** — `{{ <slug>: {{ answer, sources:[{{ label, detail, verify_url? }}], seen_before?:{{ rfi_id, summary, resolution }} }} }}`

## Built-in compliance signal (aligned to real clauses.json)

| Param id | Element | Specified | Verdict | Clause |
|---|---|---|---|---|
| DBP-01 | Footing F-12 | cover 30 mm | NON-CONFORM | IS 456 26.4.2.2 (≥50 mm) |
| DBP-02 | Column C-08 | cover 45 mm | CONFORM | IS 456 26.4.2.1 (≥40 mm) |
| DBP-03 | Marine RCC | M25 | NON-CONFORM | IS 456 8.2.8 (≥M30) |
| DBP-04 | Severe mix | w/c 0.55 | NON-CONFORM | IS 456 8.2.4.1 / Table 5 (≤0.45) |
| DBP-05 | Column C-08 | 0.6% steel | NON-CONFORM | IS 456 26.5.3.1 (≥0.8%) |
| DBP-06 | DC buildings | I = 1.0 | ADVISORY | IS 1893 7.2.3 Table 8 (lifeline → 1.5) |
| DBP-07 | Wind basis | 50 m/s | CONFORM | IS 875 Pt3 5.3 |
| DBP-08 | White-space slab | span/depth 24 ≤ 26 | CONFORM | IS 456 23.2 |
"""
    with open(os.path.join(DATA_DIR, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(txt)


def main() -> None:
    gen_design_basis_md()
    gen_design_basis_params_json()
    gen_submittals()
    gen_rfi_log()
    gen_boq()
    gen_schedule()
    gen_compliance_prose()
    gen_copilot_answers()
    gen_readme()
    print("SiteMind synthetic data generated.")


if __name__ == "__main__":
    main()
