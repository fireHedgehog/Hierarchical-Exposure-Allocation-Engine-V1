"""Live progress tracking for a background pipeline run -- real, direct
user request: "show step 1 fetching 1/22... then 1 completed, 2 start."

Deliberately in-process, in-memory, single dict (this app is loopback-
only, single-operator, single uvicorn worker -- no need for a real task
queue/Redis/etc. for this). A run's progress lives only as long as the
server process does; a restart mid-run loses live progress (the run
itself, in a background thread, keeps writing real data to the DB
regardless -- only the live progress display is ephemeral).
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_runs: dict[str, dict[str, Any]] = {}

PIPELINE_STAGE_ORDER = [
    "fetch_data", "validate_data", "regime_filter",
    "factor_engine", "allocation_engine", "instrument_engine",
]


def start_run(run_id: str) -> None:
    with _lock:
        _runs[run_id] = {
            "run_id": run_id,
            "stage": None,
            "stage_index": 0,
            "total_stages": len(PIPELINE_STAGE_ORDER),
            "item_progress": None,
            "finished": False,
            "error": None,
            "result": None,
        }


def set_stage(run_id: str, stage_key: str) -> None:
    with _lock:
        entry = _runs.get(run_id)
        if entry is None:
            return
        entry["stage"] = stage_key
        entry["stage_index"] = (
            PIPELINE_STAGE_ORDER.index(stage_key) + 1 if stage_key in PIPELINE_STAGE_ORDER else entry["stage_index"]
        )
        entry["item_progress"] = None


def set_item_progress(run_id: str, done: int, total: int, current: str | None) -> None:
    with _lock:
        entry = _runs.get(run_id)
        if entry is None:
            return
        entry["item_progress"] = {"done": done, "total": total, "current": current}


def finish_run(run_id: str, result: dict[str, Any] | None, error: str | None = None) -> None:
    with _lock:
        entry = _runs.get(run_id)
        if entry is None:
            return
        entry["finished"] = True
        entry["result"] = result
        entry["error"] = error
        entry["item_progress"] = None


def get_progress(run_id: str) -> dict[str, Any] | None:
    with _lock:
        entry = _runs.get(run_id)
        return dict(entry) if entry is not None else None
