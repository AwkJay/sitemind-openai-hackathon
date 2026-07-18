"""Structure-aware chunking for the standalone retrieval package (Phase 3).

Tries structure-aware chunking FIRST: markdown headings (`#`..`######`) or a
relaxed numbered-clause-heading pattern ("4.2.1 Title", "Section 4:",
"Clause 5.1") at line starts. This is loosely inspired, as a DESIGN
REFERENCE ONLY, by manak-dev's `HEADING_RE`/`CLAUSE_ID_RE`
(`/home/awni/Documents/Project_hackathon/manak-dev/app/backend/indexer.py`)
— that code is read-only reference, never imported, never modified; this is
an independent, deliberately looser implementation because company-uploaded
documents won't follow manak's house formatting style.

If zero headings are detected, falls back to paragraph splitting
(blank-line delimited), then sentence splitting for oversized paragraphs —
the same "detect, don't assume" two-tier cascade proven in
`app/ingest.py`'s `_BLOCK_SPLIT`/`_SENTENCE_SPLIT`, written fresh here (no
import from `app/ingest.py` — this package stays fully self-contained).

Every chunk keeps the EXACT verbatim source text in `raw_text`; `text` is
only whitespace-normalized (collapsed runs of whitespace) for scoring —
never paraphrased, never reworded. `start_char`/`end_char` let any consumer
re-slice the original document and get back `raw_text` exactly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# --------------------------------------------------------------------------- #
# Heading detection
# --------------------------------------------------------------------------- #
_MD_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(\S.*?)\s*$")

# "Section 4:", "Clause 5.1", "Chapter 2", "Article 9.3" — keyword + a numeric
# id, colon/period optional.
_KEYWORD_HEADING_RE = re.compile(
    r"^(Section|Clause|Chapter|Article)\s+(\d+(?:\.\d+)*)\s*[:.]?\s*(.*)$",
    re.IGNORECASE,
)

# Bare multi-level numeric heading, e.g. "4.2.1 Title" or "1.2.3: Title". A
# SINGLE bare number ("3. Do this") is deliberately NOT matched — that's
# indistinguishable from an ordinary numbered list item in free prose, and
# treating every such line as a heading would badly over-segment normal text.
_NUMERIC_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){1,4})\s*[:.]?\s+([A-Z].{0,120})$")


@dataclass
class _Heading:
    line_idx: int  # 0-based line index into the original (unnormalized) lines
    level: int  # inferred depth; used to build breadcrumb trails via a stack
    title: str


def _detect_headings(lines: list[str]) -> list[_Heading]:
    headings: list[_Heading] = []
    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        m = _MD_HEADING_RE.match(line)
        if m:
            headings.append(_Heading(i, len(m.group(1)), m.group(2).strip()))
            continue
        m = _KEYWORD_HEADING_RE.match(line)
        if m:
            kw, num, rest = m.group(1), m.group(2), m.group(3).strip()
            level = num.count(".") + 1
            title = f"{kw} {num}" + (f": {rest}" if rest else "")
            headings.append(_Heading(i, level, title))
            continue
        m = _NUMERIC_HEADING_RE.match(line)
        if m:
            num, rest = m.group(1), m.group(2).strip()
            level = num.count(".") + 1
            headings.append(_Heading(i, level, f"{num} {rest}".strip()))
    return headings


# --------------------------------------------------------------------------- #
# Char-offset bookkeeping
# --------------------------------------------------------------------------- #
def _line_start_offsets(text: str) -> list[int]:
    """offsets[i] = char offset where line i (0-indexed) starts;
    offsets[N] == len(text) — a sentinel for "one past the last line"."""
    keepends = text.splitlines(keepends=True)
    offsets = [0]
    pos = 0
    for ln in keepends:
        pos += len(ln)
        offsets.append(pos)
    return offsets


def _normalize(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip()


# --------------------------------------------------------------------------- #
# Structure-aware chunking
# --------------------------------------------------------------------------- #
def _structured_chunks(text: str) -> Optional[list[dict]]:
    lines = text.splitlines()
    headings = _detect_headings(lines)
    if not headings:
        return None

    offsets = _line_start_offsets(text)
    chunks: list[dict] = []

    # Preamble before the first heading, if any — keep it rather than
    # silently dropping real document text.
    if headings[0].line_idx > 0:
        start_char, end_char = offsets[0], offsets[headings[0].line_idx]
        raw_text = text[start_char:end_char]
        norm = _normalize(raw_text)
        if norm:
            chunks.append(
                {
                    "text": norm,
                    "raw_text": raw_text,
                    "heading": None,
                    "breadcrumb": None,
                    "start_char": start_char,
                    "end_char": end_char,
                    "structured": True,
                }
            )

    stack: list[_Heading] = []
    for hi, h in enumerate(headings):
        while stack and stack[-1].level >= h.level:
            stack.pop()
        breadcrumb = " > ".join([s.title for s in stack] + [h.title])
        stack.append(h)

        end_line = headings[hi + 1].line_idx if hi + 1 < len(headings) else len(lines)
        start_char, end_char = offsets[h.line_idx], offsets[end_line]
        raw_text = text[start_char:end_char]
        norm = _normalize(raw_text)
        if not norm:
            continue
        chunks.append(
            {
                "text": norm,
                "raw_text": raw_text,
                "heading": h.title,
                "breadcrumb": breadcrumb,
                "start_char": start_char,
                "end_char": end_char,
                "structured": True,
            }
        )
    return chunks or None


# --------------------------------------------------------------------------- #
# Fallback: paragraph splitting, then sentence splitting for oversized blocks.
# --------------------------------------------------------------------------- #
_BLOCK_SPLIT = re.compile(r"\n\s*\n+")
_SENTENCE_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-Z0-9])")

# A paragraph longer than this (normalized chars) is split further into
# sentence-level chunks, so one giant undifferentiated block of prose doesn't
# become a single oversized, hard-to-cite retrieval unit. Chosen as a round
# number comfortably larger than a typical paragraph (2-4 sentences) but
# small enough that a multi-page block of unstructured prose still gets
# split into several independently-citable pieces.
_MAX_PARAGRAPH_CHARS = 600


def _iter_paragraphs(text: str):
    """Yield (start_char, end_char, raw_text) for each blank-line-delimited
    block, preserving exact char offsets into the original text."""
    pos = 0
    for m in _BLOCK_SPLIT.finditer(text):
        if m.start() > pos:
            yield pos, m.start(), text[pos : m.start()]
        pos = m.end()
    if pos < len(text):
        yield pos, len(text), text[pos : len(text)]


def _locate_in_raw(raw: str, normalized_snippet: str, start_hint: int) -> tuple[int, int]:
    """Find `normalized_snippet`'s span inside `raw` (whitespace-flexible),
    searching forward from `start_hint` so repeated near-duplicate sentences
    resolve to their correct, later occurrence. Falls back to the remaining
    span if no exact match is found (rare — only when normalization altered
    something beyond whitespace)."""
    words = normalized_snippet.split()
    if not words:
        return start_hint, start_hint
    pattern = r"\s+".join(re.escape(w) for w in words)
    m = re.search(pattern, raw[start_hint:], flags=re.DOTALL)
    if not m:
        return start_hint, len(raw)
    return start_hint + m.start(), start_hint + m.end()


def _fallback_chunks(text: str) -> list[dict]:
    chunks: list[dict] = []
    for p_start, p_end, raw_para in _iter_paragraphs(text):
        norm_para = _normalize(raw_para)
        if not norm_para:
            continue
        if len(norm_para) <= _MAX_PARAGRAPH_CHARS:
            chunks.append(
                {
                    "text": norm_para,
                    "raw_text": raw_para,
                    "heading": None,
                    "breadcrumb": None,
                    "start_char": p_start,
                    "end_char": p_end,
                    "structured": False,
                }
            )
            continue

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(norm_para) if s.strip()]
        cursor = 0
        for sent in sentences:
            s_rel, e_rel = _locate_in_raw(raw_para, sent, cursor)
            cursor = e_rel
            chunks.append(
                {
                    "text": sent,
                    "raw_text": raw_para[s_rel:e_rel],
                    "heading": None,
                    "breadcrumb": None,
                    "start_char": p_start + s_rel,
                    "end_char": p_start + e_rel,
                    "structured": False,
                }
            )
    return chunks


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #
def chunk_document(text: str, file_type: str, doc_prefix: str = "doc") -> list[dict]:
    """Chunk `text` (already-extracted plain text from a .pdf/.docx/.txt/.md
    upload). `file_type` is carried through onto each chunk for provenance —
    heading/paragraph detection itself is generic across extracted text
    regardless of source format, so it is not currently branched on.

    Returns a list of chunk dicts (fields: text, raw_text, heading,
    breadcrumb, start_char, end_char, structured, chunk_id, file_type).
    `corpus_name`/`document_id`/`filename` are added by ingest.py once the
    corpus/document identity is known.
    """
    chunks = _structured_chunks(text) or _fallback_chunks(text)
    for i, c in enumerate(chunks):
        c["chunk_id"] = f"{doc_prefix}:{i:04d}"
        c["file_type"] = file_type
    return chunks
