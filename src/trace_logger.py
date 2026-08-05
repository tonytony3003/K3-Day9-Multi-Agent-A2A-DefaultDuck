from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


class TraceLogger:
    def __init__(self, path: Path, run_id: str):
        self.path = path
        self.run_id = run_id
        self._lock = threading.Lock()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")

    def event(
        self,
        event_type: str,
        *,
        case_id: str | None = None,
        agent: str = "runner",
        status: str = "success",
        payload: Any = None,
        summary: dict | None = None,
        evidence_ids: list[str] | None = None,
        model: str | None = None,
        provider: str | None = None,
        usage: dict | None = None,
        latency_ms: int = 0,
        error: str | None = None,
    ) -> None:
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        record = {
            "timestamp": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "run_id": self.run_id,
            "case_id": case_id,
            "span_id": f"span_{uuid4().hex}",
            "agent": agent,
            "event_type": event_type,
            "model": model,
            "provider": provider,
            "input_hash": f"sha256:{hashlib.sha256(serialized.encode()).hexdigest()}",
            "decision_summary": summary or {},
            "evidence_ids": evidence_ids or [],
            "usage": usage or {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
            "latency_ms": latency_ms,
            "status": status,
            "error": error,
        }
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        with self._lock:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)

