"""Local, honest provenance/trace logging for the three agent pipelines.

The local JSON log below is always written — it's the zero-dependency source
of truth that needs no external account, every pipeline run recorded with real
wall-clock step timings, the actual LLM provider used (or "offline" if none),
and a summary of what was produced. When LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY
are configured (config.LANGFUSE_ENABLED), `_persist` ALSO mirrors the same
record to a real Langfuse project via `langfuse_sink.send()` — see that module.
Both sinks record the same facts about the same execution; neither fabricates.

Traces are written to `backend/data/traces/<run_id>.json` and kept in an
in-memory ring buffer for the `/api/trace` list endpoint.
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

from . import langfuse_sink

_TRACE_DIR = Path(__file__).resolve().parent.parent / "data" / "traces"
_TRACE_DIR.mkdir(parents=True, exist_ok=True)

_lock = threading.Lock()
_RECENT: list[dict] = []
_MAX_RECENT = 200


class Run:
    """One pipeline invocation. Use as: `with trace.start("compliance.evaluate", {...}) as run:`"""

    def __init__(self, pipeline: str, input_summary: dict[str, Any]):
        self.id = f"TRC-{uuid.uuid4().hex[:10]}"
        self.pipeline = pipeline
        self.input_summary = input_summary
        self.started_at = time.time()
        self.steps: list[dict[str, Any]] = []
        self.output_summary: dict[str, Any] = {}
        self.error: Optional[str] = None

    @contextmanager
    def step(self, name: str, **meta: Any):
        t0 = time.time()
        try:
            yield
        except Exception as exc:  # record the failure, then re-raise — never swallow
            self.steps.append(
                {"name": name, "duration_ms": round((time.time() - t0) * 1000, 1), "meta": meta, "error": str(exc)}
            )
            raise
        else:
            self.steps.append(
                {"name": name, "duration_ms": round((time.time() - t0) * 1000, 1), "meta": meta}
            )

    def finish(self, output_summary: dict[str, Any]) -> dict:
        self.output_summary = output_summary
        finished_at = time.time()
        record = {
            "id": self.id,
            "pipeline": self.pipeline,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "duration_ms": round((finished_at - self.started_at) * 1000, 1),
            "input_summary": self.input_summary,
            "steps": self.steps,
            "output_summary": self.output_summary,
        }
        _persist(record)
        return record


def start(pipeline: str, input_summary: dict[str, Any]) -> Run:
    return Run(pipeline, input_summary)


def _persist(record: dict) -> None:
    with _lock:
        _RECENT.append(record)
        del _RECENT[: -_MAX_RECENT]
    path = _TRACE_DIR / f"{record['id']}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    langfuse_sink.send(record)  # no-op unless LANGFUSE_ENABLED; never raises


def recent(limit: int = 20) -> list[dict]:
    with _lock:
        return list(reversed(_RECENT[-limit:]))


def get(run_id: str) -> Optional[dict]:
    path = _TRACE_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
