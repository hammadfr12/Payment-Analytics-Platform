"""Lightweight structured logging + pipeline run summary.

Avoids a hard dependency on a logging framework; emits JSON-ish lines to stderr
and writes a machine-readable run summary to data/processed/pipeline_run_summary.json.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


_START: Optional[float] = None
_EVENTS: list = []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(event: str, **fields: Any) -> None:
    """Emit a single structured log line to stderr and record it."""
    payload = {"ts": _now_iso(), "event": event, **fields}
    line = json.dumps(payload, default=str)
    print(line, file=sys.stderr, flush=True)
    _EVENTS.append(payload)


def start_pipeline(name: str = "pipeline") -> None:
    global _START
    _START = time.time()
    log("pipeline_start", pipeline=name)


def end_pipeline(name: str = "pipeline", summary: Optional[Dict[str, Any]] = None,
                 out_path: Optional[Path] = None) -> Dict[str, Any]:
    elapsed = time.time() - _START if _START else 0.0
    payload = {
        "pipeline": name,
        "started_at": _EVENTS[0]["ts"] if _EVENTS else _now_iso(),
        "finished_at": _now_iso(),
        "elapsed_seconds": round(elapsed, 3),
        "events": _EVENTS,
        "summary": summary or {},
    }
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2, default=str))
    log("pipeline_end", pipeline=name, elapsed_seconds=round(elapsed, 3))
    return payload
