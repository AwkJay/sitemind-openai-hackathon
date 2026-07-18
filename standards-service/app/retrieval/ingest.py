"""Company-upload ingestion pipeline for the standalone retrieval package
(Phase 3).

Mirrors `app/ingest.py`'s per-file-type dispatch and utf-8 discipline (see
CLAUDE.md's mojibake bug history — every read/decode here is explicit
utf-8) but does GENERAL-PURPOSE structure-aware chunking instead of narrow
compliance-parameter extraction: this package doesn't know about
design-basis parameters, checks, or clauses at all. No import from
`app/ingest.py` — this package stays fully self-contained.
"""
from __future__ import annotations

import io
import uuid
from pathlib import Path
from typing import Union

from .chunker import chunk_document
from .index import get_or_create_corpus
from .store import save_corpus

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md")


class UnsupportedFileType(ValueError):
    pass


def extract_text(filename: str, content: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        return _extract_pdf(content)
    if name.endswith(".docx"):
        return _extract_docx(content)
    if name.endswith((".txt", ".md")):
        return content.decode("utf-8", errors="replace")
    raise UnsupportedFileType(
        f"Unsupported file type for '{filename}'. Accepted: {', '.join(SUPPORTED_EXTENSIONS)}"
    )


def _extract_pdf(content: bytes) -> str:
    import pdfplumber  # imported lazily — only reached on an actual .pdf upload

    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)


def _extract_docx(content: bytes) -> str:
    import docx  # python-docx, imported lazily

    doc = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text)


def _file_type(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def ingest_document(
    file_path: Union[str, Path],
    corpus_name: str,
    provenance_tag: str = "company_uploaded",
) -> dict:
    """Extract, chunk, embed, and add ONE document (already saved to disk at
    `file_path`, e.g. by router.py's upload endpoint) to a named corpus,
    persisting the updated corpus to disk. Returns a manifest:
    `{document_id, corpus_name, filename, chunk_count, structured,
    provenance_tag}`. Never guesses at content — extraction is the same
    real per-file-type parsing as `app/ingest.py` (pdfplumber / python-docx
    / explicit utf-8 decode)."""
    path = Path(file_path)
    content = path.read_bytes()
    filename = path.name

    text = extract_text(filename, content)
    document_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
    file_type = _file_type(filename)

    chunks = chunk_document(text, file_type=file_type, doc_prefix=document_id)
    for c in chunks:
        c["document_id"] = document_id
        c["corpus_name"] = corpus_name
        c["filename"] = filename
        c["provenance_tag"] = provenance_tag

    structured = bool(chunks) and chunks[0]["structured"]

    corpus = get_or_create_corpus(corpus_name)
    corpus.add(chunks)
    save_corpus(corpus)

    return {
        "document_id": document_id,
        "corpus_name": corpus_name,
        "filename": filename,
        "chunk_count": len(chunks),
        "structured": structured,
        "provenance_tag": provenance_tag,
    }
