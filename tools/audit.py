#!/usr/bin/env python3
"""Usage: python audit.py [--smoke] [--json] # xola-audit: neutral routing audit & verification contracts 🦋

tools/audit.py — Neutral Routing Audit & Correction Telemetry 🦋

Layer 1/4 Extension:
Provides immutable append-only routing telemetry, correction resolution,
and the base verification contracts for Layer 4 tools.
Pure stdlib. Zero external dependencies. 🦋
"""

import argparse
import json
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"

# =====================================================================
# SECTION 1: ROUTING AUDIT & CORRECTION DETECTION
# =====================================================================

_this_dir = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(_this_dir).lower() == "tools":
    PROJECT_ROOT = os.path.dirname(_this_dir)
else:
    PROJECT_ROOT = _this_dir

AUDIT_LOG_PATH = os.path.join(PROJECT_ROOT, "memory", "routing_audit.jsonl")

CORRECTION_PATTERNS = [
    r"^(?:no|nope|wait|hold on|stop)\b",
    r"^(?:not that|wrong|incorrect)\b",
    r"^(?:i meant|i wanted|actually)\b",
    r"\b(?:don'?t do that|that'?s wrong|try again)\b",
]
_COMPILED_CORRECTIONS = [re.compile(p, re.IGNORECASE) for p in CORRECTION_PATTERNS]


def detect_user_correction(user_input: str) -> bool:
    """Deterministically checks if the user input represents a correction or rejection."""
    cleaned = user_input.strip()
    return any(regex.search(cleaned) for regex in _COMPILED_CORRECTIONS)


def log_routing_event(
    prompt: str,
    tier: int,
    confidence: float,
    threshold: float,
    handler: str,
    escalated_to_llm: bool,
    audit_file: str = AUDIT_LOG_PATH,
) -> str:
    """Appends an immutable routing event record to the audit log."""
    event_id = f"evt_{int(time.time() * 1000)}"
    record = {
        "event_id": event_id,
        "timestamp": time.time(),
        "prompt_snippet": prompt[:80],
        "tier": tier,
        "confidence": round(confidence, 4),
        "threshold": threshold,
        "handler": handler,
        "escalated_to_llm": escalated_to_llm,
        "mark": WATERMARK,
    }

    os.makedirs(os.path.dirname(audit_file), exist_ok=True)
    with open(audit_file, "a", encoding="utf-8") as f:
        _lock_file(f)
        try:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            _unlock_file(f)

    return event_id


def mark_last_event_corrected(
    event_id: Optional[str] = None, audit_file: str = AUDIT_LOG_PATH
) -> str:
    """Appends a new correction-flag record referencing a prior event."""
    correction_event_id = f"evt_{int(time.time() * 1000)}_correction"
    record = {
        "event_id": correction_event_id,
        "timestamp": time.time(),
        "type": "correction_flag",
        "refers_to": event_id if event_id is not None else "LAST",
        "mark": WATERMARK,
    }

    os.makedirs(os.path.dirname(audit_file), exist_ok=True)
    with open(audit_file, "a", encoding="utf-8") as f:
        _lock_file(f)
        try:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())
        finally:
            _unlock_file(f)

    return correction_event_id


def resolve_corrections(audit_file: str = AUDIT_LOG_PATH) -> Dict[str, bool]:
    """Reads the audit log and resolves which routing events were flagged as corrected."""
    if not os.path.exists(audit_file):
        return {}

    corrected: Dict[str, bool] = {}
    last_real_event_id: Optional[str] = None

    with open(audit_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # Tolerate torn or partially flushed records cleanly

            if record.get("type") == "correction_flag":
                target = record.get("refers_to")
                if target == "LAST":
                    if last_real_event_id is not None:
                        corrected[last_real_event_id] = True
                else:
                    corrected[target] = True
            else:
                last_real_event_id = record.get("event_id")

    return corrected


# =====================================================================
# SECTION 2: CROSS-PLATFORM FILE LOCKING HELPERS
# =====================================================================

def _lock_file(f) -> None:
    """Acquires an OS-level exclusive lock on an open file handle."""
    if sys.platform == "win32":
        import msvcrt
        f.seek(0)
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
        except Exception:
            pass
    else:
        try:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass


def _unlock_file(f) -> None:
    """Releases an OS-level exclusive lock."""
    try:
        if sys.platform == "win32":
            import msvcrt
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


# =====================================================================
# SECTION 3: PROTOCOL-LEVEL VERIFICATION CONTRACTS
# =====================================================================

class VerificationFailedError(Exception):
    """Raised when a VerifiableTool's post-condition check fails."""


class VerifiableTool(ABC):
    """Base class for tools whose effects are verified through an orthogonal channel."""

    name: str
    schema: dict
    permission_tier: str  # "READ_ONLY", "SAFE_WRITE", "SENSITIVE_WRITE", "SYSTEM_MUTATION"

    @abstractmethod
    def capture_before_state(self, params: dict) -> dict:
        """Snapshots orthogonal state required for post-execution verification."""
        ...

    @abstractmethod
    def execute(self, params: dict) -> Any:
        """Performs the primary action."""
        ...

    @abstractmethod
    def verify(self, params: dict, before_state: dict, result: Any) -> bool:
        """Verifies the actual outcome through an independent side channel."""
        ...

    def run_verified(self, params: dict) -> Any:
        """Executes the tool with autonomous pre-state capture and post-verification."""
        before_state = self.capture_before_state(params)
        result = self.execute(params)
        if not self.verify(params, before_state, result):
            raise VerificationFailedError(
                f"{self.name}: post-condition failed independent orthogonal verification"
            )
        return result


class UnverifiableTool(ABC):
    """Base class for tools whose effects cannot be independently verified."""

    name: str
    schema: dict
    permission_tier: str

    @abstractmethod
    def execute(self, params: dict) -> Any:
        """Performs the primary action without a verification guarantee."""
        ...


# =====================================================================
# SECTION 4: SMOKE TEST & CLI
# =====================================================================

def smoke() -> Dict[str, Any]:
    """Self-test for audit and verification module."""
    test_log = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "memory",
        "routing_audit_smoke.jsonl",
    )
    if os.path.exists(test_log):
        try:
            os.remove(test_log)
        except Exception:
            pass

    # Test 1: Log routing event
    eid = log_routing_event(
        prompt="verify disk health",
        tier=1,
        confidence=0.95,
        threshold=0.75,
        handler="gateway.cascade",
        escalated_to_llm=False,
        audit_file=test_log,
    )

    # Test 2: Detect user correction
    corr_true = detect_user_correction("no, that's wrong do drive D instead")
    corr_false = detect_user_correction("please show me disk space")

    # Test 3: Mark last corrected
    cid = mark_last_event_corrected(event_id=eid, audit_file=test_log)
    resolved = resolve_corrections(audit_file=test_log)

    # Test 4: VerifiableTool lifecycle
    class MockFileTool(VerifiableTool):
        name = "mock_file"
        schema = {"type": "object"}
        permission_tier = "SAFE_WRITE"

        def capture_before_state(self, params: dict) -> dict:
            p = params.get("path", "")
            return {"exists": os.path.exists(p)}

        def execute(self, params: dict) -> Any:
            p = params.get("path", "")
            with open(p, "w", encoding="utf-8") as f:
                f.write(params.get("content", ""))
            return {"written": True}

        def verify(self, params: dict, before_state: dict, result: Any) -> bool:
            p = params.get("path", "")
            return os.path.exists(p) and os.path.getsize(p) > 0

    tmp_target = test_log + ".tmp"
    tool = MockFileTool()
    res = tool.run_verified({"path": tmp_target, "content": "verified content"})

    # Clean up smoke artifacts
    for p in (test_log, tmp_target):
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    passed = (
        bool(eid)
        and corr_true is True
        and corr_false is False
        and resolved.get(eid) is True
        and res.get("written") is True
    )

    return {
        "status": "PASS" if passed else "FAIL",
        "logged_event_id": eid,
        "correction_detected": corr_true,
        "resolved": resolved,
        "mark": WATERMARK,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="X.O.L.A. Neutral Routing Audit & Verification Contracts 🦋")
    ap.add_argument("--smoke", action="store_true", help="Run the audit module smoke self-check")
    ap.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    args = ap.parse_args()

    result = smoke()
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(f"🦋 Audit Module Smoke: {result['status']} (Event: {result.get('logged_event_id')}) 🦋")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
