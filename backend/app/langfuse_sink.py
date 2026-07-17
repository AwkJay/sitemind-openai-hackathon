"""Real Langfuse tracing — a thin, best-effort mirror of trace.py's local log.

trace.py's local provenance log (`data/traces/*.json`, `/api/trace`) is always
written regardless of this module — it's the zero-dependency source of truth
that needs no external account. This module ADDS a second sink: when
LANGFUSE_SECRET_KEY/LANGFUSE_PUBLIC_KEY are set (config.LANGFUSE_ENABLED), every
finished Run is also mirrored to a real Langfuse project as one trace with one
child observation per pipeline step, carrying the exact same step timings/meta
already computed locally — nothing here is a second, separate measurement.
(API verified against the installed langfuse==4.13.0 client via a live round-trip
during development — `auth_check()` returned True and `get_trace_url()` returned
a real https://cloud.langfuse.com/... URL. Uses `start_as_current_observation()`
as a context manager for parent/child nesting: the flat `start_observation()` +
manual `.end()` chaining looks correct but silently produces UNLINKED spans
[confirmed by a "no active span in current context" warning + get_trace_url()
returning None during testing] — OTel context propagation needs the `with`
form, not manual start/end calls on returned objects.)

Same resilience contract as llm.py: any failure (package missing, bad keys,
network down, API shape mismatch on a future langfuse upgrade) is swallowed —
a Langfuse hiccup must never affect a request or crash the app.
"""
from __future__ import annotations

from typing import Any, Optional

from . import config

_client: Optional[Any] = None
_tried_init = False


def _get_client() -> Optional[Any]:
    global _client, _tried_init
    if _tried_init:
        return _client
    _tried_init = True
    if not config.LANGFUSE_ENABLED:
        return None
    try:
        from langfuse import Langfuse

        _client = Langfuse(
            secret_key=config.LANGFUSE_SECRET_KEY,
            public_key=config.LANGFUSE_PUBLIC_KEY,
            base_url=config.LANGFUSE_BASE_URL,
        )
    except Exception:
        _client = None
    return _client


def send(record: dict) -> None:
    """Mirror one finished trace.Run record to Langfuse. No-op if disabled/unavailable."""
    client = _get_client()
    if client is None:
        return
    try:
        with client.start_as_current_observation(
            name=record["pipeline"],
            input=record.get("input_summary"),
            metadata={"run_id": record.get("id"), "duration_ms": record.get("duration_ms")},
        ) as root:
            for step in record.get("steps", []):
                with client.start_as_current_observation(
                    name=step["name"],
                    metadata=step.get("meta"),
                    output={"duration_ms": step.get("duration_ms"), "error": step.get("error")},
                ):
                    pass
            root.update(output=record.get("output_summary"))
        client.flush()
    except Exception:
        pass  # a tracing hiccup must never affect the request
