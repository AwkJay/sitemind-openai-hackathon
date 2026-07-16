# SiteMind — DATA layer

Synthetic-but-realistic project documents for the fictional project:

> **Hyperscale DC — Chennai, 48 MW, Tier III (Concurrently Maintainable, N+1)**

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
`{ id, element, element_type (footing|column|slab|general), param (nominal_cover|concrete_grade|wc_ratio|long_steel_pct|importance_factor|design_wind_speed|span_depth_ratio), value (number), unit, context:{ exposure, marine:bool, city_basic_vb }, source_quote, source_location }`

**submittals.csv** — `Submittal No,Rev,Title,Spec Section,Discipline,Type,Contractor,Date Submitted,Status,Days in Review`
Status codes: `A – Approved`, `B – Approved as Noted`, `C – Revise & Resubmit`, `Pending`.

**rfi_log.csv** — `RFI No,Date,Discipline,Subject,Question,Ref,Status,Cost Impact,Schedule Impact (days)`

**boq.csv** — `Item No,Code,Description,Unit,Qty,Rate_INR,Amount_INR`

**schedule.csv** — `wbs_id,task,phase,planned_start_day,duration_days,predecessors,pct_complete,procurement_item,lead_time_days,vendor_status,weather_sensitive`

**fixtures/compliance_prose.json** — `{ <param_id>: { finding, why_it_matters, corrective_action, recommendation?, confirm_with? } }`

**fixtures/copilot_answers.json** — `{ <slug>: { answer, sources:[{ label, detail, verify_url? }], seen_before?:{ rfi_id, summary, resolution } } }`

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
