from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import DATA_DIR

JOBS_FILE = DATA_DIR / "jobs.json"
_write_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_iso() -> str:
    return _now()


def ensure_jobs_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _empty_state() -> Dict[str, Any]:
    return {"jobs": {}}


def load_jobs_state() -> Dict[str, Any]:
    ensure_jobs_dir()
    if not JOBS_FILE.exists():
        return _empty_state()
    try:
        data = json.loads(JOBS_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("jobs"), dict):
            return data
    except Exception:
        pass
    return _empty_state()


def _save_jobs_state(state: Dict[str, Any]) -> None:
    JOBS_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def list_jobs() -> List[Dict[str, Any]]:
    state = load_jobs_state()
    jobs = list(state.get("jobs", {}).values())
    jobs.sort(key=lambda item: item.get("createdAt") or "", reverse=True)
    return jobs


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    state = load_jobs_state()
    return state.get("jobs", {}).get(job_id)


def create_job(job_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    with _write_lock:
        state = load_jobs_state()
        job_id = uuid.uuid4().hex
        job = {
            "id": job_id,
            "type": job_type,
            "status": "pending",
            "params": params or {},
            "logs": [],
            "createdAt": _now(),
            "updatedAt": _now(),
            "startedAt": "",
            "finishedAt": "",
            "result": None,
            "error": "",
        }
        state["jobs"][job_id] = job
        _save_jobs_state(state)
        return job


def update_job(job_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
    with _write_lock:
        state = load_jobs_state()
        job = state.get("jobs", {}).get(job_id)
        if not job:
            return None
        job.update(fields)
        job["updatedAt"] = _now()
        state["jobs"][job_id] = job
        _save_jobs_state(state)
        return job


def append_job_log(job_id: str, message: str) -> Optional[Dict[str, Any]]:
    with _write_lock:
        state = load_jobs_state()
        job = state.get("jobs", {}).get(job_id)
        if not job:
            return None
        logs = list(job.get("logs") or [])
        logs.append({"at": _now(), "message": message})
        job["logs"] = logs[-500:]
        job["updatedAt"] = _now()
        state["jobs"][job_id] = job
        _save_jobs_state(state)
        return job


def make_job_logger(job_id: str, echo: bool = True) -> Callable[[str], None]:
    def log(message: str) -> None:
        if echo:
            print(message)
        append_job_log(job_id, message)

    return log


def clear_jobs() -> None:
    with _write_lock:
        _save_jobs_state(_empty_state())


def delete_job(job_id: str) -> bool:
    with _write_lock:
        state = load_jobs_state()
        jobs_map = state.get("jobs", {})
        if job_id not in jobs_map:
            return False
        del jobs_map[job_id]
        _save_jobs_state(state)
        return True
