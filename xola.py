#!/usr/bin/env python3
"""Usage: python xola.py [--smoke] [--once] [--daemon] [--status] [--think PROMPT] [--voice TEXT] [--nudge NAME] [--submit TASK] [--interval SECONDS] [--json] [--manage-execute-audit] [--hours HOURS] [--round10] [--r10-once] # Xola Autonomous Service Loop — single unified orchestrator (formerly jarvis.py + xola_loop.py + lh10_loop.py) 🦋

Consolidation note (single orchestration name: xola):
  - This file IS the old jarvis.py (daemon/voice/think/nudge/telemetry core), renamed.
    No persona, agent spec, or persona_engine logic was touched or removed.
  - --manage-execute-audit folds in the old loop/xola_loop.py Manage->Execute->Audit
    cycle (scout/builder/guard/memory phases via agy/opencode fallback chain).
  - --round10 / --r10-once fold in the old loop/lh10_loop.py 10-agent parallel wave
    (scout, builder, guard, memory, ears, hands, sentinel, workbench, tester, scribe).
  - loop/xola_loop.py and loop/lh10_loop.py are removed; their state/log/outbox
    directories under loop/ and loop/lh10/ are left in place and still used by
    the folded-in modes below.
"""

import argparse
import contextvars
from tools.runtime import approvals
from tools.runtime.runtime_io import atomic_write, write_json, transaction
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
VERSION = "1.0.0"
_TASK_DEPTH = contextvars.ContextVar("xola_task_depth", default=0)

JARVIS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis")
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# =====================================================================
# Auto-Allow Gate — irreversible-action confirmation system
# ---------------------------------------------------------------------
# Default: OFF. Any step classified HIGH-STAKES (deleting files, spending
# money/API credits) writes a notification + logs PENDING, then SKIPS
# that step and moves on — it never blocks the loop. Xola picks the
# answer back up on a later cycle if one has been given by then.
# Toggle persistently via loop/auto_allow.json, or per-run via --auto-allow
# / --no-auto-allow on the CLI (CLI flag wins for that run only).
# =====================================================================
AUTO_ALLOW_STATE_FILE = os.path.join(PROJECT_ROOT, "loop", "auto_allow.json")
PENDING_QUESTIONS_FILE = os.path.join(PROJECT_ROOT, "loop", "pending_questions.json")
NOTIFICATIONS_LOG = os.path.join(PROJECT_ROOT, "loop", "notifications.log")

# Keywords/patterns that mark a step HIGH-STAKES regardless of auto-allow.
# Kept intentionally narrow per spec: irreversible file deletion and
# spend/credit-consuming actions only — not every risky-sounding action.
_HIGH_STAKES_PATTERNS = (
    "os.remove", "os.unlink", "shutil.rmtree", "send2trash",
    "rm -rf", "rm -f", "del /f", "del /s", "format ", "DROP TABLE", "DROP DATABASE",
    "--dangerously-skip-permissions",  # agy/opencode calls that spend API credits
    "charge", "purchase", "buy ", "payment", "invoice", "billing",
    "api credits", "spend", "top up", "top-up", "code change",
)


def _auto_allow_load_state() -> dict:
    try:
        with open(AUTO_ALLOW_STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"auto_allow": False, "updated": None, "mark": WATERMARK}


def _auto_allow_save_state(enabled: bool) -> None:
    os.makedirs(os.path.dirname(AUTO_ALLOW_STATE_FILE), exist_ok=True)
    state = {
        "auto_allow": bool(enabled),
        "updated": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }
    with open(AUTO_ALLOW_STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)


def is_auto_allow_enabled(cli_override: Optional[bool] = None) -> bool:
    """CLI flag wins for this run only; otherwise fall back to the
    persistent state file (default OFF if the file doesn't exist yet)."""
    if cli_override is not None:
        return cli_override
    return bool(_auto_allow_load_state().get("auto_allow", False))


def is_high_stakes(description: str) -> bool:
    """Classify a step/action description as HIGH-STAKES: irreversible
    file deletion or anything that spends money/API credits. This check
    ALWAYS applies, even with auto-allow ON — auto-allow only skips the
    ordinary confirm-before-acting step, never this category."""
    text = (description or "").lower()
    return any(pat.lower() in text for pat in _HIGH_STAKES_PATTERNS)


def _notify(question: str, context: str = "") -> str:
    """Write a non-blocking notification for a pending question. Returns
    the question id. The loop does NOT wait for an answer — it logs
    PENDING, skips the step, and moves on. A later cycle checks
    pending_questions.json for an answer and resumes if one was given."""
    qid = uuid.uuid4().hex[:10]
    os.makedirs(os.path.dirname(PENDING_QUESTIONS_FILE), exist_ok=True)
    try:
        with open(PENDING_QUESTIONS_FILE, encoding="utf-8") as fh:
            pending = json.load(fh)
    except Exception:
        pending = {}
    pending[qid] = {
        "id": qid,
        "question": question,
        "context": context[:2000],
        "asked_at": datetime.datetime.now().isoformat(),
        "answer": None,
        "answered_at": None,
        "mark": WATERMARK,
    }
    with open(PENDING_QUESTIONS_FILE, "w", encoding="utf-8") as fh:
        json.dump(pending, fh, indent=2, ensure_ascii=False)
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} NOTIFY [{qid}] {question}"
    print(f"🦋 {line}", flush=True)
    try:
        with open(NOTIFICATIONS_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    return qid


def check_pending_answer(qid: str) -> Optional[str]:
    """Non-blocking check: has this question been answered yet? Returns
    the answer string if yes, else None. Never waits."""
    try:
        with open(PENDING_QUESTIONS_FILE, encoding="utf-8") as fh:
            pending = json.load(fh)
    except Exception:
        return None
    entry = pending.get(qid)
    if entry and entry.get("answer"):
        return entry["answer"]
    return None


def gate_action(description: str, context: str = "", auto_allow: Optional[bool] = None) -> Tuple[bool, Optional[str]]:
    return approvals.request(description, context, high_stakes=is_high_stakes(description),
                             auto_allow=is_auto_allow_enabled(auto_allow), path=PENDING_QUESTIONS_FILE)


# =====================================================================
# Self-Proposing Evolution — never self-modifying
# ---------------------------------------------------------------------
# Xola can look at its own recent history (logs, telemetry, guard
# findings) and DRAFT a proposed code/config change with reasoning.
# It never applies that change itself. The proposal is:
#   1. written to loop/evolution_proposals.json (a diff/patch, not a
#      live edit)
#   2. scanned by tools.guard against the proposed new content, same as
#      any other code in this repo
#   3. always routed through gate_action() as its own HIGH-STAKES
#      category ("code change") — auto-allow can NEVER skip this,
#      exactly like deletes/spend
#   4. only written to the real file, and only after you approve it
#      with --approve-evolution <id>, at which point a vault snapshot
#      is taken FIRST so there's a one-line rollback if it turns out bad
# =====================================================================
EVOLUTION_PROPOSALS_FILE = os.path.join(PROJECT_ROOT, "loop", "evolution_proposals.json")
EVOLUTION_LOG = os.path.join(PROJECT_ROOT, "loop", "evolution.log")


def _evo_log(msg: str) -> None:
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(f"🦋 {line}", flush=True)
    try:
        os.makedirs(os.path.dirname(EVOLUTION_LOG), exist_ok=True)
        with open(EVOLUTION_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _evo_load_proposals() -> dict:
    try:
        with open(EVOLUTION_PROPOSALS_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _evo_save_proposals(proposals: dict) -> None:
    os.makedirs(os.path.dirname(EVOLUTION_PROPOSALS_FILE), exist_ok=True)
    with open(EVOLUTION_PROPOSALS_FILE, "w", encoding="utf-8") as fh:
        json.dump(proposals, fh, indent=2, ensure_ascii=False)


def _evo_scan_proposed_content(target_file: str, new_content: str) -> dict:
    """Run the real guard.py checks against the PROPOSED new content,
    without touching the real file. Writes to a throwaway temp copy so
    guard.audit_file's existing file-based API can be reused as-is."""
    from tools.guard import audit_file
    tmp_dir = os.path.join(PROJECT_ROOT, "loop", "_evo_scan_tmp")
    os.makedirs(tmp_dir, exist_ok=True)
    tmp_path = os.path.join(tmp_dir, os.path.basename(target_file))
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(new_content)
        return audit_file(tmp_path, strict=False, fix=False, smoke=False)
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


def propose_evolution(target_file: str, new_content: str, reasoning: str, evidence: str = "") -> str:
    """Draft a self-proposed change. NEVER applies it. Returns proposal id.

    target_file: path relative to PROJECT_ROOT of the file being proposed
                 for change (must already exist).
    new_content: the FULL proposed new content of that file (not a diff
                 format on disk, to keep this dependency-free — the diff
                 is computed and shown for review).
    reasoning:   why Xola thinks this change is an improvement — required,
                 never optional. A proposal with no reasoning is rejected
                 at write time.
    evidence:    what observation (log lines, telemetry, guard findings,
                 test failures) motivated this — for your review, not
                 taken on faith.
    """
    if not reasoning or not reasoning.strip():
        raise ValueError("propose_evolution requires non-empty reasoning — no silent proposals")

    abs_target = os.path.realpath(os.path.join(PROJECT_ROOT, target_file))
    if os.path.commonpath([os.path.realpath(PROJECT_ROOT), abs_target]) != os.path.realpath(PROJECT_ROOT):
        raise ValueError("Evolution target must be inside the project")
    try:
        with open(abs_target, encoding="utf-8") as fh:
            old_content = fh.read()
    except Exception as exc:
        raise ValueError(f"propose_evolution: cannot read target_file {target_file}: {exc}")

    import difflib
    diff_lines = list(difflib.unified_diff(
        old_content.splitlines(keepends=True),
        new_content.splitlines(keepends=True),
        fromfile=f"a/{target_file}", tofile=f"b/{target_file}",
    ))
    if not diff_lines:
        raise ValueError("propose_evolution: new_content is identical to current content, nothing to propose")

    guard_result = _evo_scan_proposed_content(abs_target, new_content)
    guard_verdict = guard_result.get("status", "UNKNOWN")

    pid = uuid.uuid4().hex[:10]
    proposals = _evo_load_proposals()
    proposals[pid] = {
        "id": pid,
        "target_file": target_file,
        "old_content": old_content,
        "new_content": new_content,
        "diff": "".join(diff_lines),
        "reasoning": reasoning,
        "evidence": evidence[:3000],
        "guard_verdict": guard_verdict,
        "guard_findings": guard_result.get("findings", []),
        "proposed_at": datetime.datetime.now().isoformat(),
        "status": "PENDING",  # PENDING -> APPROVED -> APPLIED, or REJECTED
        "decided_at": None,
        "applied_at": None,
        "mark": WATERMARK,
    }
    _evo_save_proposals(proposals)

    # Route through the gate as its own always-gated HIGH-STAKES category.
    # This call's only purpose here is the notification side-effect —
    # code changes are gated at --approve-evolution time regardless of
    # what this returns, so we don't act on (ok, qid) here.
    gate_action(
        description=f"code change proposed for {target_file}",
        context=f"[HIGH-STAKES: code change] proposal {pid}: {reasoning[:150]}",
    )
    _evo_log(f"PROPOSED [{pid}] target={target_file} guard={guard_verdict} reasoning={reasoning[:100]!r}")
    return pid


def list_evolution_proposals(status: Optional[str] = None) -> List[dict]:
    proposals = _evo_load_proposals()
    items = list(proposals.values())
    if status:
        items = [p for p in items if p.get("status") == status.upper()]
    return sorted(items, key=lambda p: p.get("proposed_at", ""), reverse=True)


def approve_evolution(pid: str) -> Tuple[bool, str]:
    """Apply a proposal — the ONLY path by which Xola's own code can
    change. Always: (1) snapshot the vault first for one-line rollback,
    (2) re-verify the proposal still parses/matches guard expectations,
    (3) write new_content to target_file, (4) record APPLIED with the
    snapshot id attached."""
    proposals = _evo_load_proposals()
    if pid not in proposals:
        return False, f"no proposal with id {pid}"
    p = proposals[pid]
    if p["status"] != "PENDING":
        return False, f"proposal {pid} is already {p['status']}, not PENDING"

    if p.get("guard_verdict") == "KILL":
        return False, f"proposal {pid} failed guard scan (verdict=KILL) — refusing to apply even on manual approval; findings: {p.get('guard_findings')}"

    try:
        from tools.vault import snapshot as vault_snapshot
        snap_id = vault_snapshot()
    except Exception as exc:
        return False, (
            f"refusing to apply {pid}: could not take a vault snapshot for rollback first ({exc}). "
            f"Fix the vault (see tools/vault.py) or accept the risk explicitly by re-running with "
            f"vault repaired — this system does not apply code changes without a rollback point."
        )

    abs_target = os.path.join(PROJECT_ROOT, p["target_file"]) if not os.path.isabs(p["target_file"]) else p["target_file"]
    try:
        with open(abs_target, encoding="utf-8") as fh:
            current = fh.read()
    except Exception as exc:
        return False, f"cannot re-read target_file before apply: {exc}"
    if current != p["old_content"]:
        return False, (
            f"target_file {p['target_file']} has changed since this proposal was drafted "
            f"(old_content no longer matches) — refusing to apply a stale diff, re-propose instead"
        )

    abs_target = os.path.realpath(abs_target)
    if os.path.commonpath([os.path.realpath(PROJECT_ROOT), abs_target]) != os.path.realpath(PROJECT_ROOT):
        return False, "Evolution target escaped the project"
    fresh_scan = _evo_scan_proposed_content(abs_target, p["new_content"])
    if not fresh_scan.get("passed", fresh_scan.get("status") in ("PASS", "WARN")):
        return False, "Proposal failed revalidation immediately before apply"
    backup = os.path.join(PROJECT_ROOT, "loop", "evolution_backups", pid + ".txt")
    atomic_write(backup, current)
    atomic_write(abs_target, p["new_content"])
    p["code_backup"] = backup

    p["status"] = "APPLIED"
    p["decided_at"] = datetime.datetime.now().isoformat()
    p["applied_at"] = p["decided_at"]
    p["snapshot_id"] = snap_id
    proposals[pid] = p
    _evo_save_proposals(proposals)
    _evo_log(f"APPLIED [{pid}] target={p['target_file']} snapshot={snap_id}")
    return True, f"applied {pid} to {p['target_file']} (rollback snapshot: {snap_id})"


def reject_evolution(pid: str, reason: str = "") -> Tuple[bool, str]:
    proposals = _evo_load_proposals()
    if pid not in proposals:
        return False, f"no proposal with id {pid}"
    if proposals[pid]["status"] != "PENDING":
        return False, f"proposal {pid} is already {proposals[pid]['status']}"
    proposals[pid]["status"] = "REJECTED"
    proposals[pid]["decided_at"] = datetime.datetime.now().isoformat()
    proposals[pid]["reject_reason"] = reason
    _evo_save_proposals(proposals)
    _evo_log(f"REJECTED [{pid}] reason={reason!r}")
    return True, f"rejected {pid}"
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

INBOX_DIR = os.path.join(JARVIS_DIR, "inbox")
OUTBOX_DIR = os.path.join(JARVIS_DIR, "outbox")
ARCHIVE_DIR = os.path.join(INBOX_DIR, "archive")
DONE_DIR = os.path.join(INBOX_DIR, "done")  # Round149: text-queue done dir (stdlib-only) 🦋
EARS_DIR = os.path.join(JARVIS_DIR, "ears")
TELEMETRY_FILE = os.path.join(JARVIS_DIR, "telemetry.jsonl")
STATE_FILE = os.path.join(JARVIS_DIR, "jarvis_state.json")
SENTINEL_LOG_FILE = os.path.join(JARVIS_DIR, "sentinel.log")
VOICE_LOG_FILE = os.path.join(JARVIS_DIR, "voice.log")

# Internal imports from XOLA ecosystem
from jarvis.sentinel import (
    Sentinel,
    SentinelCheck,
    get_system_health,
    run_sentinel_once,
    execute_scheduled_nudges,
    nudge_health_monitor,
    nudge_guard_audit,
    nudge_scout_probe,
    run_nudge_by_name,
)
from jarvis.hands import OSHands, capture_screenshot, list_processes, disk_space
from jarvis.brain import AutonomousBrain, BrainPlan, BrainExecutionResult, think, think_and_execute
from jarvis.voice import VoiceEngine, EarsQueue, speak, enqueue_utterance, process_ears_queue
import tools.skills as skills_tool
import tools.scout as scout_tool
import tools.guard as guard_tool
import tools.memory as memory_tool


# =====================================================================
# 1) Task & Response Dataclasses
# =====================================================================

@dataclass
class JarvisTask:
    """Incoming task representation from inbox 🦋."""
    task_id: str
    action: str = "skill"
    skill: Optional[str] = None
    prompt: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    chain: Optional[List[Dict[str, Any]]] = None
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    source_file: Optional[str] = None
    mark: str = WATERMARK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class JarvisResponse:
    """Structured response artifact written to outbox."""
    task_id: str
    status: str  # SUCCESS, ERROR, REJECTED
    action: str
    skill_used: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    latency_s: float = 0.0
    processed_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    telemetry: Dict[str, Any] = field(default_factory=dict)
    mark: str = WATERMARK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =====================================================================
# 2) Jarvis Harness State & Telemetry
# =====================================================================

class JarvisHarness:
    """Core Jarvis Execution Engine, Cognitive Coordinator & Service Loop."""

    def __init__(
        self,
        inbox_dir: str = INBOX_DIR,
        outbox_dir: str = OUTBOX_DIR,
        ears_dir: str = EARS_DIR,
    ):
        self.inbox_dir = inbox_dir
        self.outbox_dir = outbox_dir
        self.ears_dir = ears_dir
        self.archive_dir = os.path.join(inbox_dir, "archive")
        self.telemetry_file = TELEMETRY_FILE
        self.state_file = STATE_FILE
        self.hands = OSHands()
        self.sentinel = Sentinel()
        self.brain = AutonomousBrain()
        self.voice = VoiceEngine()
        self.ears = EarsQueue(ears_dir=self.ears_dir)
        self.mark = WATERMARK

        # Ensure directory structure exists
        os.makedirs(self.inbox_dir, exist_ok=True)
        os.makedirs(self.outbox_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)
        os.makedirs(os.path.join(inbox_dir, "done"), exist_ok=True)  # Round149: done queue 🦋
        os.makedirs(self.ears_dir, exist_ok=True)
        self._init_state()

    def _init_state(self) -> None:
        """Initialize or load persistent state."""
        if not os.path.exists(self.state_file):
            init_state = {
                "version": VERSION,
                "initialized_at": datetime.datetime.now().isoformat(),
                "tasks_processed": 0,
                "tasks_succeeded": 0,
                "tasks_failed": 0,
                "total_latency_s": 0.0,
                "last_task_id": None,
                "last_task_time": None,
                "daemon_status": "STOPPED",
                "mark": self.mark,
            }
            try:
                with open(self.state_file, "w", encoding="utf-8") as f:
                    json.dump(init_state, f, indent=2)
            except Exception:
                pass

    def load_state(self) -> Dict[str, Any]:
        """Load current Jarvis runtime state."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"tasks_processed": 0, "mark": self.mark}

    def update_state(self, task_id: str, success: bool, latency: float) -> None:
        """Update runtime state with newly completed task + live heartbeat 🦋."""
        state = self.load_state()
        now_iso = datetime.datetime.now().isoformat()
        state["tasks_processed"] = state.get("tasks_processed", 0) + 1
        if success:
            state["tasks_succeeded"] = state.get("tasks_succeeded", 0) + 1
        else:
            state["tasks_failed"] = state.get("tasks_failed", 0) + 1
        state["total_latency_s"] = round(state.get("total_latency_s", 0.0) + latency, 4)
        state["last_task_id"] = task_id
        state["last_task_time"] = now_iso
        state["daemon_status"] = "RUNNING"
        state["last_heartbeat"] = now_iso
        state["mark"] = self.mark

        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception:
            pass

    def record_telemetry(self, response: JarvisResponse) -> None:
        """Record structured task execution telemetry event to jarvis/telemetry.jsonl 🦋."""
        event = {
            "task_id": response.task_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "status": response.status,
            "action": response.action,
            "skill_used": response.skill_used,
            "latency_s": response.latency_s,
            "telemetry": response.telemetry,
            "error": response.error,
            "result_summary": str(response.result)[:200] if response.result is not None else None,
            "mark": response.mark,
        }
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.telemetry_file)), exist_ok=True)
            with open(self.telemetry_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"🦋 Telemetry recording error: {e}", file=sys.stderr)

    def record_task_to_memory(self, task: JarvisTask, response: JarvisResponse) -> None:
        """Auto-record completed Jarvis task execution into dated episodic memory markdown 🦋."""
        try:
            mem_dir = os.path.join(PROJECT_ROOT, "memory")
            step_desc = task.prompt or task.skill or task.action or f"Jarvis Task {task.task_id}"
            res_str = str(response.result)[:250] if response.result is not None else "(none)"
            ev_desc = f"Action: {response.action} | Skill: {response.skill_used} | Status: [{response.status}] | Latency: {response.latency_s:.4f}s | Result: {res_str}"
            verdict_str = "PASS" if response.status == "SUCCESS" else "KILL"
            tag_list = ["jarvis", task.action]
            if response.skill_used:
                tag_list.append(str(response.skill_used))

            memory_tool.append_round(
                step=f"Jarvis autonomous task: {step_desc}",
                evidence=ev_desc,
                verdict=verdict_str,
                lessons="Autonomous Jarvis harness processed task with stdlib OS hands / skills pipeline.",
                next_step="Continue persistent service monitoring loop.",
                tags=tag_list,
                lane="jarvis-harness",
                latency=response.latency_s,
                memory_dir=mem_dir,
            )
        except Exception:
            # Non-blocking error containment for memory recording
            pass

    # =================================================================
    # 3) Task Ingestion & Action Dispatcher
    # =================================================================

    def parse_task_file(self, file_path: str) -> Optional[JarvisTask]:
        """Parse raw task file from inbox with multi-step chain support 🦋."""
        if not os.path.isfile(file_path):
            return None

        filename = os.path.basename(file_path)
        base_id, _ = os.path.splitext(filename)
        # Clean prefix if named task_xxx
        task_id = base_id if base_id else f"task_{uuid.uuid4().hex[:8]}"

        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                raw_content = f.read().strip()

            if not raw_content:
                return None

            # Try parsing JSON
            if raw_content.startswith("{") and raw_content.endswith("}"):
                try:
                    payload = json.loads(raw_content)
                    chain_data = payload.get("chain") or payload.get("steps")
                    action_val = payload.get("action", "chain" if chain_data else "skill")
                    return JarvisTask(
                        task_id=payload.get("task_id", task_id),
                        action=action_val,
                        skill=payload.get("skill"),
                        prompt=payload.get("prompt", payload.get("task", "")),
                        args=payload.get("args", {}),
                        chain=chain_data,
                        created_at=payload.get("created_at", datetime.datetime.now().isoformat()),
                        source_file=file_path,
                        mark=WATERMARK,
                    )
                except json.JSONDecodeError:
                    pass

            # Fallback to plain text task prompt
            return JarvisTask(
                task_id=task_id,
                action="auto",
                prompt=raw_content,
                source_file=file_path,
                mark=WATERMARK,
            )
        except Exception as e:
            print(f"🦋 Error parsing task file {file_path}: {e}", file=sys.stderr)
            return None

    def execute_task(self, task: JarvisTask) -> JarvisResponse:
        if _TASK_DEPTH.get() >= 6:
            return JarvisResponse(task_id=task.task_id, status="ERROR", action=task.action,
                                  error="Maximum nested task depth exceeded")
        depth_token = _TASK_DEPTH.set(_TASK_DEPTH.get() + 1)
        token = approvals.SCOPE.set(task.task_id)
        try:
            response = self._execute_task(task)
            if isinstance(response.result, dict):
                nested = response.result.get("status")
                if nested in ("ERROR", "FAILED", "DENIED", "PENDING_APPROVAL", "UNSUPPORTED"):
                    response.status = nested
                    response.error = response.result.get("error", nested)
            return response
        finally:
            approvals.SCOPE.reset(token)
            _TASK_DEPTH.reset(depth_token)

    def _execute_task(self, task: JarvisTask) -> JarvisResponse:
        """Dispatch task through task chaining, dynamic skills registry, OS hands, brain reasoning, or subsystems 🦋."""
        t0 = time.perf_counter()
        skill_target = task.skill or task.prompt.strip()
        action_type = task.action.lower().strip() if task.action else "skill"

        # Step 1: Health snapshot for telemetry
        health_check = get_system_health()
        telemetry_snap = {
            "cpu_load_pct": health_check.cpu.get("used_percent", 0.0),
            "ram_used_pct": health_check.ram.get("used_percent", 0.0),
            "disk_used_pct": health_check.disk.get("max_used_percent", 0.0),
            "sentinel_status": health_check.status,
        }

        try:
            # Route -1: Multi-step Task Chaining
            chain_steps = task.chain or (task.args.get("chain") if isinstance(task.args, dict) else None) or (task.args.get("steps") if isinstance(task.args, dict) else None)
            if action_type in ("chain", "pipeline", "multi_step") or (chain_steps and isinstance(chain_steps, list)):
                steps = chain_steps or []
                if not steps or len(steps) > 25:
                    raise ValueError("A chain must contain 1 to 25 steps")
                chain_path = os.path.join(self.outbox_dir, ".chain_" + __import__("hashlib").sha256(
                    (task.task_id + json.dumps(steps, sort_keys=True)).encode()).hexdigest() + ".json")
                try:
                    with open(chain_path, encoding="utf-8") as stream:
                        completed = json.load(stream)
                except FileNotFoundError:
                    completed = {}
                step_responses = []
                all_succeeded = True
                chain_error = None
                prev_output = None

                for i, step_def in enumerate(steps, start=1):
                    step_id = f"{task.task_id}_s{i}"
                    step_act = step_def.get("action", "skill")
                    step_skill = step_def.get("skill")
                    step_prompt = step_def.get("prompt", step_def.get("task", ""))
                    step_args = dict(step_def.get("args", {}))

                    if prev_output is not None and "_pipe_prev" in step_args:
                        step_args["previous_result"] = prev_output

                    sub_task = JarvisTask(
                        task_id=step_id,
                        action=step_act,
                        skill=step_skill,
                        prompt=step_prompt,
                        args=step_args,
                        mark=WATERMARK,
                    )
                    if step_id in completed:
                        sub_resp = JarvisResponse(**completed[step_id])
                    else:
                        sub_resp = self.execute_task(sub_task)
                        if sub_resp.status == "SUCCESS":
                            completed[step_id] = sub_resp.to_dict()
                            write_json(chain_path, completed)
                    if sub_resp.status == "PENDING_APPROVAL":
                        sub_resp.task_id = task.task_id
                        return sub_resp
                    step_responses.append(sub_resp.to_dict())

                    if sub_resp.status != "SUCCESS":
                        all_succeeded = False
                        chain_error = f"Step {i} ({sub_resp.action}) failed: {sub_resp.error}"
                        if step_def.get("abort_on_error", True):
                            break
                    else:
                        prev_output = sub_resp.result

                if os.path.exists(chain_path):
                    os.unlink(chain_path)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status="SUCCESS" if all_succeeded else "ERROR",
                    action="chain",
                    skill_used="task_chain",
                    result={
                        "total_steps": len(steps),
                        "completed_steps": len(step_responses),
                        "step_results": step_responses,
                        "final_output": prev_output,
                    },
                    error=chain_error,
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 0: Autonomous Brain Thinking (natural language or explicit 'auto' / 'brain')
            elif action_type in ("auto", "brain", "think"):
                prompt_to_plan = task.prompt or skill_target
                brain_res = self.brain.think_and_execute(prompt_to_plan, task.args)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status=brain_res.status,
                    action=brain_res.plan.action,
                    skill_used=brain_res.plan.skill or brain_res.plan.action,
                    result=brain_res.output if brain_res.output is not None else brain_res.formatted_response,
                    error=brain_res.error,
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 1: OS Hands Actions
            elif action_type.startswith("hands") or skill_target.startswith("hands."):
                hands_act = action_type.replace("hands.", "").replace("hands", "").strip()
                if not hands_act and skill_target.startswith("hands."):
                    hands_act = skill_target.replace("hands.", "").strip()
                if not hands_act:
                    hands_act = "ps"
                res_data = self.hands.execute_action(hands_act, task.args)
                lat = round(time.perf_counter() - t0, 4)
                is_err = "error" in res_data and res_data.get("status") == "ERROR"
                return JarvisResponse(
                    task_id=task.task_id,
                    status="SUCCESS" if not is_err else "ERROR",
                    action=f"hands.{hands_act}",
                    skill_used=f"hands.{hands_act}",
                    result=res_data,
                    error=res_data.get("error"),
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 2: Subsystem Scout Probes
            elif action_type in ("scout", "probe") or skill_target in ("scout", "probe_lanes"):
                py_info = scout_tool.probe_python()
                agy_info = scout_tool.probe_agy(quick=True)
                op_info = scout_tool.probe_opencode(quick=True)
                lanes = {"python": py_info, "agy": agy_info, "opencode": op_info}
                recs = scout_tool.recommend_execution_plan(lanes)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status="SUCCESS",
                    action="scout",
                    skill_used="tools.scout",
                    result={"lanes": lanes, "recommendations": recs},
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 3: Subsystem Guard Audit
            elif action_type == "guard" or skill_target == "guard_audit":
                target_dir = task.args.get("target", PROJECT_ROOT) if isinstance(task.args, dict) else PROJECT_ROOT
                audit_res = guard_tool.audit(target=target_dir, strict=False, fix=False, smoke=False)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status="SUCCESS",
                    action="guard",
                    skill_used="tools.guard",
                    result=audit_res,
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 4: Subsystem Memory Query / Stats
            elif action_type == "memory" or skill_target in ("memory_stats", "memory_query"):
                mem_dir = os.path.join(PROJECT_ROOT, "memory")
                loop_dir = os.path.join(PROJECT_ROOT, "loop")
                mem_stats = memory_tool.compute_stats(memory_dir=mem_dir, loop_dir=loop_dir)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status="SUCCESS",
                    action="memory",
                    skill_used="tools.memory",
                    result=mem_stats,
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 5: Voice Speech Synthesis
            elif action_type in ("voice", "speak") or skill_target in ("voice", "speak"):
                text_to_speak = (task.args.get("text") if isinstance(task.args, dict) else None) or task.prompt
                v_res = self.voice.speak(text_to_speak)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status="SUCCESS" if v_res.get("status") in ("SUCCESS", "ASYNC_QUEUED", "MUTED") else "ERROR",
                    action="voice",
                    skill_used="jarvis.voice",
                    result=v_res,
                    error=v_res.get("error"),
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 6: Scheduled Nudge Trigger
            elif action_type in ("nudge", "sentinel_nudge"):
                nudge_type = task.args.get("name", "all") if isinstance(task.args, dict) else "all"
                if nudge_type == "all":
                    n_res = self.sentinel.check_and_run_nudges(force=True)
                else:
                    n_res = run_nudge_by_name(nudge_type)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status="SUCCESS",
                    action="nudge",
                    skill_used=f"sentinel.nudge.{nudge_type}",
                    result=n_res,
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

            # Route 7: Dynamic Skills Registry Execution with Multi-Tier Fallback
            else:
                registry = skills_tool.GLOBAL_REGISTRY
                skill_obj = registry.get(skill_target) or registry.find_matching_skill(skill_target)

                if skill_obj:
                    call_args = task.args if isinstance(task.args, dict) else {}
                    if skill_obj.handler and callable(skill_obj.handler):
                        try:
                            import inspect
                            sig = inspect.signature(skill_obj.handler)
                            has_varkw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values())
                            if not has_varkw:
                                accepted_params = set(sig.parameters.keys())
                                call_args = {k: v for k, v in call_args.items() if k in accepted_params}
                        except Exception:
                            pass

                    exec_res = registry.execute(
                        name_or_query=skill_obj.name,
                        args=call_args,
                        auto_approve_red=False,
                    )
                    lat = round(time.perf_counter() - t0, 4)
                    is_ok = exec_res.get("status") == "SUCCESS"
                    return JarvisResponse(
                        task_id=task.task_id,
                        status=exec_res.get("status", "ERROR"),
                        action="skill",
                        skill_used=skill_obj.name,
                        result=exec_res.get("output") if is_ok else exec_res,
                        error=exec_res.get("error"),
                        latency_s=lat,
                        telemetry=telemetry_snap,
                        mark=WATERMARK,
                    )

                # Fallback A: Check if skill matches a Sentinel nudge (e.g. scout_probe, guard_audit, health_monitor)
                nudge_clean = skill_target.lower().replace("-", "_").strip()
                if nudge_clean in ("scout_probe", "guard_audit", "health_monitor", "scout", "guard", "health"):
                    n_res = run_nudge_by_name(nudge_clean)
                    lat = round(time.perf_counter() - t0, 4)
                    return JarvisResponse(
                        task_id=task.task_id,
                        status="SUCCESS" if n_res.get("status") not in ("ERROR", "KILL") else "ERROR",
                        action="skill",
                        skill_used=f"sentinel.{n_res.get('nudge', nudge_clean)}",
                        result=n_res,
                        error=n_res.get("error"),
                        latency_s=lat,
                        telemetry=telemetry_snap,
                        mark=WATERMARK,
                    )

                # Fallback B: Check if skill matches OS Hands action
                hands_clean = skill_target.lower().strip()
                if hands_clean in ("ps", "disk", "tree", "read", "write", "tail", "screenshot", "windows", "focus", "kill", "spawn", "info"):
                    h_res = self.hands.execute_action(hands_clean, task.args)
                    lat = round(time.perf_counter() - t0, 4)
                    is_err = "error" in h_res and h_res.get("status") == "ERROR"
                    return JarvisResponse(
                        task_id=task.task_id,
                        status="SUCCESS" if not is_err else "ERROR",
                        action="skill",
                        skill_used=f"hands.{hands_clean}",
                        result=h_res,
                        error=h_res.get("error"),
                        latency_s=lat,
                        telemetry=telemetry_snap,
                        mark=WATERMARK,
                    )

                # Fallback C: Autonomous Brain Heuristic / LLM Reasoning
                brain_res = self.brain.think_and_execute(task.prompt or skill_target, task.args)
                lat = round(time.perf_counter() - t0, 4)
                return JarvisResponse(
                    task_id=task.task_id,
                    status=brain_res.status,
                    action=brain_res.plan.action,
                    skill_used=brain_res.plan.skill or brain_res.plan.action,
                    result=brain_res.output or brain_res.formatted_response,
                    error=brain_res.error,
                    latency_s=lat,
                    telemetry=telemetry_snap,
                    mark=WATERMARK,
                )

        except Exception as exc:
            lat = round(time.perf_counter() - t0, 4)
            return JarvisResponse(
                task_id=task.task_id,
                status="ERROR",
                action=action_type,
                skill_used=skill_target,
                error=str(exc),
                latency_s=lat,
                telemetry=telemetry_snap,
                mark=WATERMARK,
            )

    def write_outbox_response(self, response: JarvisResponse) -> str:
        """Write structured response file into outbox."""
        ts_clean = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_id = __import__("re").sub(r"[^A-Za-z0-9_-]", "_", response.task_id)[:100]
        out_filename = f"response_{safe_id}_{ts_clean}.json"
        out_path = os.path.join(self.outbox_dir, out_filename)

        write_json(out_path, response.to_dict())

        # Round149: also drop stdlib text reply into inbox/done for *.txt queue 🦋
        try:
            done_dir = os.path.join(self.inbox_dir, "done")
            os.makedirs(done_dir, exist_ok=True)
            reply_path = os.path.join(done_dir, f"{safe_id}_reply.txt")
            with open(reply_path, "w", encoding="utf-8") as rf:
                rf.write(f"[{response.status}] {response.task_id} -> {response.skill_used}\n")
                rf.write(f"result: {str(response.result)[:500]}\n")
                if response.error:
                    rf.write(f"error: {response.error}\n")
        except Exception:
            pass

        return out_path

    def archive_task_file(self, task_file_path: str) -> None:
        """Move processed task file into archive directory."""
        if not os.path.exists(task_file_path):
            return
        filename = os.path.basename(task_file_path)
        dest_path = os.path.join(self.archive_dir, filename)
        try:
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(task_file_path, dest_path)
            # Round149: mirror to inbox/done for text-queue verify 🦋
            try:
                done_dir = os.path.join(self.inbox_dir, "done")
                os.makedirs(done_dir, exist_ok=True)
                shutil.copy2(dest_path, os.path.join(done_dir, filename))
            except Exception:
                pass
        except Exception:
            try:
                os.remove(task_file_path)
            except Exception:
                pass

    def process_single_task_file(self, task_file: str) -> Optional[JarvisResponse]:
        # Serialize duplicate consumers of one queue item.
        claim = os.path.join(self.outbox_dir, ".claims", __import__("hashlib").sha256(
            os.path.abspath(task_file).encode()).hexdigest())
        with transaction(claim):
            if not os.path.isfile(task_file):
                return None
            return self._process_single_task_file(task_file)

    def _process_single_task_file(self, task_file: str) -> Optional[JarvisResponse]:
        """Ingest, execute, log, record memory, archive, and respond to one task file 🦋."""
        task = self.parse_task_file(task_file)
        if not task:
            return None

        # Execute
        response = self.execute_task(task)

        # Write outbox response
        self.write_outbox_response(response)

        if response.status == "PENDING_APPROVAL":
            return response

        # Record telemetry
        self.record_telemetry(response)

        if task.args.get("speak_response"):
            text = response.error or str(response.result)
            if isinstance(response.result, dict):
                text = response.result.get("text", response.result.get("message", text))
            self.voice.speak(str(text)[:1500], wait=True)

        # Auto-record completed task into episodic memory
        self.record_task_to_memory(task, response)

        # Update state
        is_ok = response.status == "SUCCESS"
        self.update_state(task.task_id, success=is_ok, latency=response.latency_s)

        # Sentinel log entry
        self.sentinel.check_and_log()

        # Archive task
        self.archive_task_file(task_file)

        return response

    def process_pending_inbox(self) -> List[JarvisResponse]:
        """Poll and process all pending task files queued in inbox, ears queue, and periodic nudges. 🦋"""
        responses = []

        # 1. Process inbox tasks (robust: auto-create inbox, empty-safe, stdlib-only)
        try:
            os.makedirs(self.inbox_dir, exist_ok=True)
        except Exception:
            pass
        try:
            files = sorted(os.listdir(self.inbox_dir))
        except (FileNotFoundError, NotADirectoryError, OSError):
            files = []
        for f in files:
            fpath = os.path.join(self.inbox_dir, f)
            try:
                if os.path.isfile(fpath) and not f.startswith("."):
                    resp = self.process_single_task_file(fpath)
                    if resp:
                        responses.append(resp)
            except Exception:
                continue

        # 2. Process ears queue if pending utterances exist
        # Persist a deterministic inbox task before archiving the utterance.
        def submit_voice(utt):
            if utt.source == "mic_wake_word":
                return {"status": "IGNORED", "reason": "Wake word without command"}
            task_id = "voice_" + __import__("hashlib").sha256(utt.id.encode()).hexdigest()[:20]
            path = os.path.join(self.inbox_dir, task_id + ".json")
            if not os.path.exists(path) and not os.path.exists(os.path.join(self.archive_dir, task_id + ".json")):
                write_json(path, {"task_id": task_id, "action": "auto", "prompt": utt.text,
                                  "args": {"speak_response": True}})
            return {"status": "QUEUED", "task_id": task_id}
        self.ears.process_queue(handler=submit_voice)

        # 3. Check and run scheduled periodic nudges
        self.sentinel.check_and_run_nudges(force=False)

        # 4. Empty-inbox heartbeat (hardening): guarantee sentinel log touch on idle 🦋
        if not responses:
            try:
                self.sentinel.check_and_log()
            except Exception:
                pass

        return responses

    def submit_task(
        self,
        prompt_or_skill: str,
        args: Optional[Dict[str, Any]] = None,
        action: str = "skill",
        skill: Optional[str] = None,
        chain: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Helper to drop a new task request into the inbox 🦋."""
        t_id = f"task_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        act = "chain" if chain else action
        task_data = {
            "task_id": t_id,
            "action": act,
            "skill": skill or (prompt_or_skill if act != "chain" else None),
            "prompt": prompt_or_skill,
            "args": args or {},
            "chain": chain,
            "created_at": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }
        task_path = os.path.join(self.inbox_dir, f"{t_id}.json")
        with open(task_path, "w", encoding="utf-8") as f:
            json.dump(task_data, f, indent=2, ensure_ascii=False)
        return task_path


# =====================================================================
# 4) Standalone API Helpers & Smoke Runner
# =====================================================================

def process_inbox_task(task_file_path: str) -> Optional[JarvisResponse]:
    """Top-level functional entrypoint to process one task."""
    harness = JarvisHarness()
    return harness.process_single_task_file(task_file_path)


def run_jarvis_loop(interval: float = 2.0) -> None:
    """Run continuous persistent polling daemon loop."""
    harness = JarvisHarness()
    print(f"🦋 Starting Jarvis Autonomous Service Loop (polling interval: {interval}s)...")
    print(f"   • Inbox  : {harness.inbox_dir}")
    print(f"   • Outbox : {harness.outbox_dir}")
    print(f"   • Ears   : {harness.ears_dir}")
    print(f"   • Press Ctrl+C to terminate.")

    try:
        while True:
            try:
                responses = harness.process_pending_inbox()
            except Exception as exc:
                print(f"🦋 loop iteration contained (empty/inbox safe): {exc}", file=sys.stderr)
                responses = []
            for r in responses:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Processed {r.task_id} -> [{r.status}] {r.skill_used} ({r.latency_s:.4f}s) {WATERMARK}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print(f"\n🦋 Jarvis Service Loop stopped gracefully.")


def get_jarvis_status() -> Dict[str, Any]:
    """Inspect holistic Jarvis harness status with live heartbeat 🦋."""
    harness = JarvisHarness()
    state = harness.load_state()
    # Live heartbeat touch (stdlib-only): --status proves harness alive
    now_iso = datetime.datetime.now().isoformat()
    try:
        state["daemon_status"] = "RUNNING"
        state["last_heartbeat"] = now_iso
        state["mark"] = WATERMARK
        with open(harness.state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception:
        pass
    health = get_system_health()

    inbox_files = [f for f in os.listdir(harness.inbox_dir) if os.path.isfile(os.path.join(harness.inbox_dir, f))] if os.path.exists(harness.inbox_dir) else []
    outbox_files = [f for f in os.listdir(harness.outbox_dir) if os.path.isfile(os.path.join(harness.outbox_dir, f))] if os.path.exists(harness.outbox_dir) else []
    ears_files = harness.ears.peek()

    return {
        "status": "HEALTHY" if health.status != "CRITICAL" else "CRITICAL",
        "timestamp": datetime.datetime.now().isoformat(),
        "inbox_queue_count": len(inbox_files),
        "outbox_total_count": len(outbox_files),
        "ears_queue_count": len(ears_files),
        "tasks_processed_total": state.get("tasks_processed", 0),
        "tasks_succeeded": state.get("tasks_succeeded", 0),
        "tasks_failed": state.get("tasks_failed", 0),
        "last_task_id": state.get("last_task_id"),
        "last_task_time": state.get("last_task_time"),
        "daemon_status": state.get("daemon_status", "UNKNOWN"),
        "last_heartbeat": state.get("last_heartbeat"),
        "sentinel_health": health.to_dict(),
        "mark": WATERMARK,
    }


def run_smoke_test() -> Dict[str, Any]:
    """Execute end-to-end smoke test creating and processing an inbox task, voice synthesis, brain plan, and scheduled nudge."""
    t0 = time.perf_counter()
    harness = JarvisHarness()

    # Step 1: Submit synthetic test task
    task_args = {"drive": "D:"}
    task_file = harness.submit_task(
        prompt_or_skill="sys_info",
        args=task_args,
        action="skill",
    )

    # Step 2: Process pending task
    responses = harness.process_pending_inbox()

    # Step 3: Verify outbox response
    if not responses:
        return {
            "smoke_test": "FAILED",
            "error": "No response generated from inbox task processing",
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }

    resp = responses[0]
    outbox_files = os.listdir(harness.outbox_dir)
    matched_outbox = [f for f in outbox_files if resp.task_id in f]
    outbox_file_path = os.path.join(harness.outbox_dir, matched_outbox[0]) if matched_outbox else None

    # Step 4: Test Brain Thinking Engine directly
    brain_res = harness.brain.think_and_execute("check storage for drive D:")

    # Step 5: Test Voice & Ears Queue
    ears_id = harness.ears.enqueue(text="Jarvis online smoke check", source="smoke_test").id

    # Step 6: Test Scheduled Nudge Execution
    nudges_res = harness.sentinel.check_and_run_nudges(force=True)

    # Step 7: Sentinel log entry check
    sentinel_lines = []
    if os.path.exists(SENTINEL_LOG_FILE):
        with open(SENTINEL_LOG_FILE, "r", encoding="utf-8") as f:
            sentinel_lines = [l.strip() for l in f.readlines() if l.strip()]

    all_ok = (
        resp.status == "SUCCESS"
        and brain_res.status == "SUCCESS"
        and bool(nudges_res)
    )

    return {
        "smoke_test": "PASSED" if all_ok else "FAILED",
        "task_id": resp.task_id,
        "task_status": resp.status,
        "skill_used": resp.skill_used,
        "brain_test": brain_res.status,
        "brain_thought": brain_res.plan.thought,
        "ears_utterance_id": ears_id,
        "nudges_executed": len(nudges_res),
        "result_sample": str(resp.result)[:150] + "..." if len(str(resp.result)) > 150 else resp.result,
        "outbox_file": outbox_file_path,
        "sentinel_log_latest": sentinel_lines[-1] if sentinel_lines else None,
        "latency_s": round(time.perf_counter() - t0, 4),
        "mark": WATERMARK,
    }


run_smoke = run_smoke_test


# =====================================================================
# 5) Terminal Rendering & CLI
# =====================================================================

def render_jarvis_status(status_data: Dict[str, Any]) -> str:
    """Render terminal status banner for Jarvis harness."""
    st = status_data.get("status", "UNKNOWN")
    lines = [
        f"🦋 Jarvis Autonomous Harness Status [{st}] 🦋",
        "=" * 72,
        f"Timestamp         : {status_data.get('timestamp')}",
        f"Inbox Pending     : {status_data.get('inbox_queue_count', 0)} task(s)",
        f"Outbox Generated  : {status_data.get('outbox_total_count', 0)} response(s)",
        f"Ears Queue        : {status_data.get('ears_queue_count', 0)} utterance(s)",
        f"Total Processed   : {status_data.get('tasks_processed_total', 0)} ({status_data.get('tasks_succeeded', 0)} pass / {status_data.get('tasks_failed', 0)} fail)",
        f"Last Task ID      : {status_data.get('last_task_id') or '(none)'}",
        f"Last Task Time    : {status_data.get('last_task_time') or '(never)'}",
        "-" * 72,
        "Sentinel System Metrics:",
    ]
    sent = status_data.get("sentinel_health", {})
    lines.append(f"  • Sentinel State : [{sent.get('status', 'UNKNOWN')}]")
    lines.append(f"  • CPU Load       : {sent.get('cpu', {}).get('used_percent', 0.0):.1f}%")
    lines.append(f"  • RAM Load       : {sent.get('ram', {}).get('used_percent', 0.0):.1f}%")
    lines.append(f"  • Max Disk Load  : {sent.get('disk', {}).get('max_used_percent', 0.0):.1f}%")
    lines.append("=" * 72)
    return "\n".join(lines)


# ============================================================================
# --manage-execute-audit  (folded in from old loop/xola_loop.py, unchanged logic)
# ============================================================================
_MEA_ROOT = PROJECT_ROOT
_MEA_LOOP = os.path.join(_MEA_ROOT, "loop")
_MEA_AGENTS = os.path.join(_MEA_ROOT, "agents")
_MEA_TOOLS = os.path.join(_MEA_ROOT, "tools")
_MEA_REPORTS = os.path.join(_MEA_ROOT, "reports")
_MEA_MEMORY = os.path.join(_MEA_ROOT, "memory")
_MEA_LOG = os.path.join(_MEA_LOOP, "loop.log")
_MEA_STATE = os.path.join(_MEA_LOOP, "state.json")
_MEA_MISSION = os.path.join(_MEA_LOOP, "mission.md")

_MEA_AGY = os.environ.get("XOLA_AGY_BIN") or shutil.which("agy") or "agy"
_MEA_OPENCODE = os.environ.get("XOLA_OPENCODE_BIN") or shutil.which("opencode") or "opencode"
_MEA_AGY_MODEL = os.environ.get("XOLA_MODEL", "gemini-3.8-flash-high")
_MEA_AGY_PRO = "gemini-3.1-pro-high"
_MEA_SPARK_MODEL = "opencode/muse-spark-1.3-contributor-free"
_MEA_CHAIN = (
    ("agy", _MEA_AGY_MODEL),
    ("agy", _MEA_AGY_PRO),
    ("opencode", _MEA_SPARK_MODEL),
)
_MEA_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.environ.get("XOLA_LH_SRC", os.path.join(os.path.dirname(PROJECT_ROOT), "LongHorizon-Harness", "src")))
try:
    from lh_harness.agent_logs import visible_output as _mea_extract_opencode_text  # noqa: E402
    from lh_harness.adapters.agy import extract_agy_visible_output as _mea_extract_agy_visible_output  # noqa: E402
except Exception:
    def _mea_extract_opencode_text(s): return s
    def _mea_extract_agy_visible_output(s):
        try:
            d = json.loads(s)
            return d.get("response", s)
        except Exception:
            return s


def _mea_log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with open(_MEA_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _mea_run(cmd, input_text=None, timeout=300, cwd=PROJECT_ROOT):
    try:
        proc = subprocess.run(
            cmd, input=input_text, capture_output=True, text=True,
            timeout=timeout, cwd=cwd, creationflags=_MEA_NO_WINDOW,
        )
        out = proc.stdout or ""
        err = (proc.stderr or "")[-1500:]
        return proc.returncode == 0, out, err
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as exc:
        return False, "", f"LAUNCH-FAIL: {exc}"


def _mea_read_agent(name):
    try:
        with open(os.path.join(_MEA_AGENTS, name), encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def _mea_opencode_ask(prompt, model=_MEA_SPARK_MODEL, timeout=300):
    ok, out, err = _mea_run(
        [_MEA_OPENCODE, "run", "--format", "json", "--yolo", "--model", model],
        input_text=prompt, timeout=timeout,
    )
    if not ok:
        return False, "", f"opencode rc!=0: {err}"
    text = _mea_extract_opencode_text(out).strip()
    if not text or '"type":"error"' in out.replace(" ", ""):
        return False, "", f"opencode server failing: {(err or out)[-160:]}"
    return True, text, ""


def _mea_agy_ask(prompt, model=_MEA_AGY_MODEL, timeout=900):
    path = os.path.join(_MEA_LOOP, "prompt_tmp.txt")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(prompt)
    try:
        ok, out, err = _mea_run(
            [_MEA_AGY, "-p", f"@{path}", "--model", model,
             "--output-format", "json", "--print-timeout", f"{timeout}s",
             ],
            timeout=timeout + 60,
        )
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    if not ok:
        return False, "", f"agy rc!=0: {err}"
    return True, _mea_extract_agy_visible_output(out).strip(), ""


def _mea_ask_lane(prompt, timeout, lane="manager"):
    last_err = "no lanes tried"
    for backend, model in _MEA_CHAIN:
        if backend == "agy":
            ok, text, err = _mea_agy_ask(prompt, model=model, timeout=timeout)
            via = f"agy/{model}"
        else:
            ok, text, err = _mea_opencode_ask(prompt, model=model, timeout=timeout)
            via = f"opencode/{model}"
        if ok and text:
            if via != f"agy/{_MEA_AGY_MODEL}":
                _mea_log(f"CHAIN {lane} fell through to {via}")
            return True, text, via
        last_err = err
        _mea_log(f"CHAIN {lane} {via} down ({str(err)[:100]}), trying next")
    _mea_log(f"WARN {lane} all lanes down ({str(last_err)[:120]}), round skipped")
    return False, "", "none"


def _mea_load_state():
    try:
        with open(_MEA_STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"round": 0, "started": time.time(), "notes": [], "mark": WATERMARK}


def _mea_save_state(state):
    state["mark"] = WATERMARK
    to_write = {k: v for k, v in state.items() if k != "_auto_allow_override"}
    with open(_MEA_STATE, "w", encoding="utf-8") as fh:
        json.dump(to_write, fh, indent=2, ensure_ascii=False)


def _mea_mission_text():
    try:
        with open(_MEA_MISSION, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return "Analyse hermes/agy/opencode/deepseek-harness, create agents, loop to perfect."


def _mea_split_step(reply):
    try:
        start = reply.index("{")
        data = json.loads(reply[start:reply.rindex("}") + 1])
        if isinstance(data, dict) and data.get("executor_prompt"):
            return str(data["executor_prompt"])[:6000], str(data.get("verify", ""))[:2000]
    except Exception:
        pass
    return reply[:6000], ""


def _mea_one_round(state, smoke=False):
    from tools.scout import probe_python, probe_agy, probe_opencode, recommend_execution_plan
    from tools.builder import validate_all_tools
    from tools.guard import audit as guard_audit
    from tools.memory import append_round

    state["round"] += 1
    rnd = state["round"]
    _mea_log(f"=== ROUND {rnd} ===")

    py_info = probe_python()
    op_info = probe_opencode(quick=True, timeout=10.0)
    agy_info = probe_agy(quick=True, timeout=15.0)
    lanes = {"python": py_info, "agy": agy_info, "opencode": op_info}
    topology = recommend_execution_plan(lanes)
    _mea_log(f"SCOUT: python={py_info['status']} | agy={agy_info['status']} | opencode={op_info['status']} -> topology: exec={topology['executor']}")

    try:
        builder_res = validate_all_tools(tools_dir=_MEA_TOOLS, run_test=False)
        _mea_log(f"BUILDER: {builder_res['passed_count']}/{builder_res['total']} tools standard compliant (all_passed={builder_res['all_passed']})")
    except Exception as exc:
        _mea_log(f"BUILDER-WARN: {exc}")

    history = "\n".join(state["notes"][-6:])
    if state.get("pending_step"):
        step, hint = state["pending_step"]
    elif smoke:
        step, hint = "Reply with exactly: PONG", "check string PONG in result"
    else:
        mgr_prompt = (
            f"You are Xola's loop manager. Mission:\n{_mea_mission_text()[:4000]}\n\n"
            f"Pack: scout/builder/guard/memory discipline applies.\n"
            f"History:\n{history}\n\n"
            f"Round {rnd}. Reply JSON only: "
            f'{{"executor_prompt": "<one bounded step for the agy executor>", '
            f'"verify": "<how to check it>"}}'
        )
        ok, reply, via = _mea_ask_lane(mgr_prompt, 300)
        _mea_log(f"MANAGER via={via} ok={ok} chars={len(reply)}")
        if not ok or not reply:
            append_round(
                round_idx=rnd, step="Manager step planning",
                evidence="Manager lane unreachable", verdict="KILL",
                lessons="Manager lane failed to return valid JSON step",
                next_step="Retry manager inquiry on alternate lane",
                tags=["lane:manager", "status:down"], memory_dir=_MEA_MEMORY,
            )
            return False
        step, hint = _mea_split_step(reply)

    t0_exec = time.perf_counter()
    step_gate_ok, step_gate_qid = gate_action(
        description=step, context="MEA executor step", auto_allow=state.get("_auto_allow_override"),
    )
    if not step_gate_ok:
        state["pending_step"] = [step, hint]
        _mea_log(f"GATE-SKIP round={rnd} qid={step_gate_qid} step={step[:80]!r} (awaiting confirmation)")
        state["notes"].append(f"r{rnd}: skipped, awaiting confirmation ({step_gate_qid})")
        _mea_save_state(state)
        return False
    state.pop("pending_step", None)
    ok, result, via = _mea_ask_lane(
        f"You are Xola's executor hands. Do this bounded step, then report "
        f"exactly what you did with tool evidence:\n{step}",
        240 if smoke else 900, lane="executor",
    )
    exec_latency = time.perf_counter() - t0_exec
    _mea_log(f"EXECUTOR ok={ok} chars={len(result)} latency={exec_latency:.2f}s")
    if not ok or not result:
        append_round(
            round_idx=rnd, step=step,
            evidence=f"Execution failed or timed out: {result[:200]}",
            verdict="KILL", lessons="Executor did not complete cleanly; check prompt bounds",
            next_step="Refine executor prompt to smaller atomic sub-task",
            tags=["lane:agy", "verdict:kill"], memory_dir=_MEA_MEMORY,
        )
        state["notes"].append(f"r{rnd}: executor failed")
        return False

    guard_res = guard_audit(target=_MEA_ROOT, strict=False, smoke=smoke)
    guard_verdict = guard_res.get("verdict", "WARN")
    critical_count = guard_res.get("summary", {}).get("critical_count", 0)
    warning_count = guard_res.get("summary", {}).get("warning_count", 0)
    _mea_log(f"GUARD-AUTO: verdict={guard_verdict} (scanned={guard_res['summary']['files_scanned']}, critical={critical_count}, warnings={warning_count})")

    if smoke:
        verdict_ok = ok and ("PONG" in result or "pong" in result.lower()) and (critical_count == 0)
        audit_evidence = f"Smoke executor answered with PONG ({exec_latency:.2f}s); guard auto-verdict: {guard_verdict}"
    else:
        guard_agent_spec = _mea_read_agent("xola-guard.md")[:2000]
        guard_findings_snip = ""
        if guard_res.get("findings"):
            guard_findings_snip = f"\nAutomated Guard Scan Findings ({len(guard_res['findings'])} issues):\n" + "\n".join(
                [f"- [{f['severity']}] {os.path.basename(f['file'])}:L{f['line']} {f['message']}" for f in guard_res["findings"][:5]]
            )
        auditor_prompt = (
            f"{guard_agent_spec}\n\n"
            f"Step asked: {step[:2000]}\nVerify hint: {hint[:1000]}\n"
            f"Executor reported:\n{result[:5000]}\n"
            f"{guard_findings_snip}\n\n"
            f"Verdict JSON only: "
            f'{{"verdict": "PASS" or "KILL", "evidence": "<one line>"}}'
        )
        ok_audit, audit_reply, via_audit = _mea_ask_lane(auditor_prompt, 300, lane="auditor")
        llm_pass = ok_audit and ('"PASS"' in audit_reply.upper() or 'VERDICT: PASS' in audit_reply.upper())
        verdict_ok = llm_pass and (critical_count == 0)
        audit_evidence = f"LLM Audit via {via_audit} (pass={llm_pass}) | Guard auto-scan: {guard_verdict}"
        _mea_log(f"AUDIT ok={ok_audit} pass={verdict_ok} via={via_audit}")

    final_verdict = "PASS" if verdict_ok else "KILL"
    state["notes"].append(f"r{rnd}: {final_verdict} {step[:80]}")

    append_round(
        round_idx=rnd, step=step,
        evidence=f"{audit_evidence} | Executor chars={len(result)}",
        verdict=final_verdict,
        lessons=f"Round {rnd} completed via {topology['executor']}; guard auto-verdict: {guard_verdict}",
        next_step="Advance to next mission objective" if verdict_ok else "Fix audit findings and re-verify",
        tags=["lane:agy", f"verdict:{final_verdict.lower()}", "loop:xola"],
        memory_dir=_MEA_MEMORY,
    )
    _mea_save_state(state)
    return verdict_ok


def run_manage_execute_audit(hours: float = 10.0, smoke: bool = False, auto_allow: Optional[bool] = None) -> int:
    """Manage -> Execute -> Audit long loop (folded in from old xola_loop.py)."""
    os.makedirs(_MEA_REPORTS, exist_ok=True)
    os.makedirs(_MEA_MEMORY, exist_ok=True)
    state = _mea_load_state()
    state["_auto_allow_override"] = auto_allow
    if state["round"] == 0:
        state["started"] = time.time()
    budget = hours * 3600
    _mea_log(f"XOLA LOOP start hours={hours} round={state['round'] + 1} {WATERMARK}")

    if smoke:
        ok = _mea_one_round(state, smoke=True)
        _mea_save_state(state)
        _mea_log(f"SMOKE {'PASS' if ok else 'FAIL'} {WATERMARK}")
        return 0 if ok else 2

    while time.time() - state["started"] < budget:
        try:
            _mea_one_round(state)
        except Exception as exc:
            _mea_log(f"ROUND-ERROR: {exc}")
            time.sleep(60)
        _mea_save_state(state)
        time.sleep(60)
    _mea_log(f"BUDGET SPENT — loop done. History stands. {WATERMARK}")
    return 0


# ============================================================================
# --round10 / --r10-once  (folded in from old loop/lh10_loop.py, unchanged logic)
# ============================================================================
_R10_ROOT = PROJECT_ROOT
_R10_BASE = os.path.join(_R10_ROOT, "loop", "lh10")
_R10_INBOX = os.path.join(_R10_BASE, "inbox")
_R10_OUTBOX = os.path.join(_R10_BASE, "outbox")
_R10_LOG = os.path.join(_R10_BASE, "lh10.log")
_R10_STATE = os.path.join(_R10_BASE, "lh10_state.json")
_R10_AGY = _MEA_AGY
_R10_FAST = "gemini-3.8-flash-low"
_R10_FALLBACK = "gemini-3.1-pro-high"
_R10_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_R10_AGENTS = (
    ("scout", "Probe lanes: run `python ./tools/scout.py --quick` and report UP/DOWN per lane plus recommended executor. Keep under 15 lines.", 180),
    ("builder", "Validate tool forge: run `python ./tools/builder.py --validate` (or cli.py build) and report passed/total. Keep under 15 lines.", 180),
    ("guard", "Red-team audit: run `python ./tools/guard.py --target ./jarvis/inbox` and report verdict + findings count. Keep under 15 lines.", 180),
    ("memory", "Summarize last 10 lines of ./loop/loop.log into 5 bullet lessons. Keep under 15 lines.", 180),
    ("ears", "Check Jarvis ears queue: list ./jarvis/ears (top-level only) and report pending vs archived counts. Keep under 10 lines.", 120),
    ("hands", "Report disk free space for C: and D: drives (GB + %) and flag any drive over 90% used. Keep under 10 lines.", 120),
    ("sentinel", "Tail last 10 lines of ./jarvis/sentinel.log and report latest HEALTH state + any WARN. Keep under 10 lines.", 120),
    ("workbench", "Check Mission Control health at http://127.0.0.1:8101/api/health and report UP/DOWN + latency. Keep under 10 lines.", 120),
    ("tester", "Run `python -m unittest tests.test_scout -v` inside the project directory and report tests run, failures, errors. Keep under 15 lines.", 240),
    ("scribe", "Write a 5-line status note for the 10-agent loop: which lanes are up, what needs attention. Plain text, no fluff.", 120),
)


def _r10_log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with open(_R10_LOG, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass


def _r10_agy_ask(prompt, model, timeout, tag="solo"):
    tmp = os.path.join(_R10_BASE, f"prompt_tmp_{tag}.txt")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(prompt)
        proc = subprocess.run(
            [_R10_AGY, "-p", f"@{tmp}", "--model", model,
             "--output-format", "json", "--print-timeout", f"{timeout}s",
             ],
            capture_output=True, text=True, timeout=timeout + 60,
            cwd=PROJECT_ROOT, creationflags=_R10_NO_WINDOW,
        )
        out = proc.stdout or ""
        if proc.returncode != 0:
            return False, "", (proc.stderr or "")[-300:]
        try:
            d = json.loads(out)
            return True, str(d.get("response", out)).strip(), ""
        except Exception:
            return True, out.strip(), ""
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT"
    except Exception as exc:
        return False, "", f"LAUNCH-FAIL: {exc}"
    finally:
        try:
            os.remove(tmp)
        except Exception:
            pass


def _r10_ask(agent, job, timeout, tag="solo"):
    for model in (_R10_FAST, _R10_FALLBACK):
        ok, text, err = _r10_agy_ask(
            f"You are {agent}, one of 10 LH agents working IN PARALLEL with 9 others. Do this bounded job with real tool output, then report:\n{job}",
            model, timeout, tag)
        if ok and text:
            if model != _R10_FAST:
                _r10_log(f"CHAIN {agent} fell through to {model}")
            return True, text, model
        _r10_log(f"CHAIN {agent} {model} down ({str(err)[:100]})")
    return False, "", "none"


def _r10_load_state():
    try:
        with open(_R10_STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {"wave": 0, "done": {}, "started": time.time(), "mark": WATERMARK}


def _r10_save_state(s):
    s["mark"] = WATERMARK
    with open(_R10_STATE, "w", encoding="utf-8") as fh:
        json.dump(s, fh, indent=2, ensure_ascii=False)


def _r10_one_job(args):
    name, job, timeout, w = args
    gate_ok, gate_qid = gate_action(description=job, context=f"round10 agent={name}")
    if not gate_ok:
        _r10_log(f"GATE-SKIP {name}_w{w} qid={gate_qid} (awaiting confirmation)")
        return f"{name}_w{w}", {"ok": False, "via": "gated", "latency_s": 0.0, "chars": 0, "gate_qid": gate_qid}
    t0 = time.perf_counter()
    ok, text, via = _r10_ask(name, job, timeout, tag=f"{name}_w{w}")
    lat = round(time.perf_counter() - t0, 1)
    key = f"{name}_w{w}"
    fn = os.path.join(_R10_OUTBOX, f"{key}.txt")
    try:
        with open(fn, "w", encoding="utf-8") as fh:
            fh.write(f"agent={name} wave={w} ok={ok} via={via} latency={lat}s {WATERMARK}\n{text[:3000]}")
    except Exception as exc:
        _r10_log(f"WRITE-FAIL {key}: {exc}")
    _r10_log(f"JOB {name}: ok={ok} via={via} {lat}s chars={len(text)}")
    return key, {"ok": ok, "via": via, "latency_s": lat, "chars": len(text)}


def _r10_wave(state):
    state["wave"] += 1
    w = state["wave"]
    _r10_log(f"=== WAVE {w} — 10 jobs IN PARALLEL ===")
    with ThreadPoolExecutor(max_workers=10) as pool:
        for key, res in pool.map(_r10_one_job, [(n, j, t, w) for n, j, t in _R10_AGENTS]):
            state["done"][key] = res
    _r10_save_state(state)
    _r10_log(f"WAVE {w} complete {WATERMARK}")


def run_round10(hours: float = 1.0, once: bool = False) -> None:
    """10-agent parallel wave loop (folded in from old lh10_loop.py)."""
    os.makedirs(_R10_INBOX, exist_ok=True)
    os.makedirs(_R10_OUTBOX, exist_ok=True)
    state = _r10_load_state()
    if state["wave"] == 0:
        state["started"] = time.time()
    budget = hours * 3600
    _r10_log(f"LH10 start hours={hours} wave={state['wave'] + 1} {WATERMARK}")
    if once:
        _r10_wave(state)
        _r10_log(f"ONCE done — 10 jobs handed. {WATERMARK}")
        return
    while time.time() - state["started"] < budget:
        try:
            _r10_wave(state)
        except Exception as exc:
            _r10_log(f"WAVE-ERROR: {exc}")
            time.sleep(30)
        _r10_save_state(state)
        time.sleep(20)
    _r10_log(f"BUDGET SPENT — LH10 done. {WATERMARK}")


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for Xola service (single unified orchestrator)."""
    parser = argparse.ArgumentParser(
        prog="xola",
        description="Xola Autonomous Service Loop, Cognitive Brain & Inbox/Outbox Dispatcher — unified orchestrator 🦋",
        epilog="Usage: python xola.py [--smoke] [--once] [--daemon] [--status] [--think PROMPT] [--voice TEXT] [--nudge NAME] [--submit TASK] [--manage-execute-audit] [--round10] [--json]",
    )
    parser.add_argument("--doctor", action="store_true", help="Check installation without running tools or model calls")
    parser.add_argument("--remember", nargs=2, metavar=("KEY", "VALUE"), help="Store an explicit non-secret fact")
    parser.add_argument("--recall", metavar="QUERY", help="Search remembered facts")
    parser.add_argument("--pending", action="store_true", help="List pending tool approvals")
    parser.add_argument("--listen", action="store_true", help="Start Windows wake-word and command listener")
    parser.add_argument("--screen", action="store_true", help="Include an on-demand screen OCR observation with --think")
    parser.add_argument("--smoke", action="store_true", help="Execute complete end-to-end smoke test")
    parser.add_argument("--once", action="store_true", help="Process all currently queued inbox tasks and exit")
    parser.add_argument("--daemon", action="store_true", help="Run continuous background inbox polling loop")
    parser.add_argument("--status", action="store_true", help="Inspect current Jarvis harness state and queue health")
    parser.add_argument("--think", "-p", metavar="PROMPT", help="Process natural language prompt with Autonomous Brain")
    parser.add_argument("--voice", "-v", metavar="TEXT", help="Synthesize and speak text via voice engine")
    parser.add_argument("--nudge", metavar="NAME", help="Trigger scheduled nudge ('all', 'health', 'guard', 'scout')")
    parser.add_argument("--submit", metavar="TASK", help="Submit new task request string or skill name into inbox")
    parser.add_argument("--args", default="{}", help="JSON arguments for submitted task (default: '{}')")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds for daemon (default: 2.0)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON format")
    parser.add_argument("--manage-execute-audit", action="store_true", help="Run Manage->Execute->Audit long loop (formerly xola_loop.py)")
    parser.add_argument("--hours", type=float, default=10.0, help="Duration in hours for --manage-execute-audit or --round10 (default: 10.0, round10 default: 1.0)")
    parser.add_argument("--round10", action="store_true", help="Run 10-agent parallel wave loop (formerly lh10_loop.py)")
    parser.add_argument("--r10-once", action="store_true", help="With --round10, hand all 10 jobs exactly once, then exit")
    parser.add_argument("--auto-allow", action="store_true", help="For this run only: skip confirmation for non-high-stakes actions (high-stakes = irreversible deletes / spend, still always gated)")
    parser.add_argument("--no-auto-allow", action="store_true", help="For this run only: require confirmation for every action, overriding a persistent auto-allow=on state")
    parser.add_argument("--set-auto-allow", choices=["on", "off"], help="Persistently set the auto-allow default (writes loop/auto_allow.json) and exit")
    parser.add_argument("--answer", nargs=2, metavar=("QID", "ANSWER"), help="Answer a pending gated question by id, e.g. --answer a1b2c3d4e5 yes")
    parser.add_argument("--list-proposals", action="store_true", help="List self-proposed code changes (Xola never applies these itself)")
    parser.add_argument("--show-proposal", metavar="PID", help="Show the full diff and reasoning for one proposal")
    parser.add_argument("--approve-evolution", metavar="PID", help="Apply a proposed code change (snapshots the vault first for rollback)")
    parser.add_argument("--reject-evolution", metavar="PID", help="Reject a proposed code change")
    parser.add_argument("--reject-reason", default="", help="Optional reason text, used with --reject-evolution")
    return parser


def main():
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    # Default action if no flags provided: status
    if not (args.smoke or args.once or args.daemon or args.status or args.submit or args.think
            or args.voice or args.nudge or args.manage_execute_audit or args.round10
            or args.set_auto_allow or args.answer or args.list_proposals
            or args.show_proposal or args.approve_evolution or args.reject_evolution or args.pending or args.listen or args.doctor or args.remember or args.recall):
        args.status = True

    cli_auto_allow_override = None
    if args.auto_allow and args.no_auto_allow:
        print("🦋 ERROR: --auto-allow and --no-auto-allow are mutually exclusive", file=sys.stderr)
        sys.exit(1)
    elif args.auto_allow:
        cli_auto_allow_override = True
    elif args.no_auto_allow:
        cli_auto_allow_override = False

    try:
        if args.doctor:
            from tools.runtime.doctor import diagnose
            print(json.dumps(diagnose(), indent=2, ensure_ascii=False))
            sys.exit(0)

        elif args.remember:
            from tools.vault import remember
            print(json.dumps(remember(*args.remember), indent=2, ensure_ascii=False))
            sys.exit(0)

        elif args.recall:
            from tools.vault import recall
            print(json.dumps(recall(args.recall), indent=2, ensure_ascii=False))
            sys.exit(0)

        elif args.set_auto_allow:
            _auto_allow_save_state(args.set_auto_allow == "on")
            msg = f"🦋 Auto-allow persistently set to: {args.set_auto_allow.upper()} (high-stakes actions — deletes, spend — always still confirmed)"
            if args.json:
                print(json.dumps({"auto_allow": args.set_auto_allow == "on", "mark": WATERMARK}))
            else:
                print(msg)
            sys.exit(0)

        elif args.pending:
            print(json.dumps({k: v for k, v in approvals.read_records(PENDING_QUESTIONS_FILE).items()
                              if not v.get("consumed_at")}, indent=2, ensure_ascii=False))
            sys.exit(0)

        elif args.listen:
            if sys.platform != "win32":
                parser.error("Microphone listener requires Windows and Windows PowerShell")
            sys.exit(subprocess.call(["powershell", "-NoProfile", "-File",
                os.path.join(JARVIS_DIR, "ears_listener.ps1")]))

        elif args.answer:
            approvals.answer(*args.answer, path=PENDING_QUESTIONS_FILE)
            print("Answer recorded. Queued tasks resume on the next daemon cycle; retry a one-off command explicitly.")
            sys.exit(0)

        elif args.list_proposals:
            items = list_evolution_proposals()
            if args.json:
                print(json.dumps(items, indent=2, ensure_ascii=False))
            else:
                if not items:
                    print("🦋 No evolution proposals on file.")
                for p in items:
                    print(f"[{p['status']:9s}] {p['id']}  target={p['target_file']}  guard={p['guard_verdict']}  {p['reasoning'][:70]}")
            sys.exit(0)

        elif args.show_proposal:
            proposals = _evo_load_proposals()
            p = proposals.get(args.show_proposal)
            if not p:
                print(f"🦋 No proposal with id {args.show_proposal}", file=sys.stderr)
                sys.exit(1)
            if args.json:
                print(json.dumps(p, indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Proposal [{p['id']}] status={p['status']} target={p['target_file']}")
                print(f"Guard verdict: {p['guard_verdict']}")
                print(f"Reasoning: {p['reasoning']}")
                if p.get("evidence"):
                    print(f"Evidence: {p['evidence']}")
                print("=" * 72)
                print(p["diff"])
                print("=" * 72)
            sys.exit(0)

        elif args.approve_evolution:
            ok, msg = approve_evolution(args.approve_evolution)
            print(f"🦋 {msg}")
            sys.exit(0 if ok else 1)

        elif args.reject_evolution:
            ok, msg = reject_evolution(args.reject_evolution, reason=args.reject_reason)
            print(f"🦋 {msg}")
            sys.exit(0 if ok else 1)

        elif args.smoke:
            smoke_res = run_smoke_test()
            if args.json:
                print(json.dumps(smoke_res, indent=2, ensure_ascii=False))
            else:
                st = smoke_res.get("smoke_test", "UNKNOWN")
                print(f"🦋 Jarvis Smoke Test [{st}] 🦋")
                print("=" * 72)
                print(f"Task ID         : {smoke_res.get('task_id')}")
                print(f"Status          : {smoke_res.get('task_status')}")
                print(f"Skill Used      : {smoke_res.get('skill_used')}")
                print(f"Brain Status    : {smoke_res.get('brain_test')} ({smoke_res.get('brain_thought')})")
                print(f"Nudges Run      : {smoke_res.get('nudges_executed')}")
                print(f"Outbox File     : {smoke_res.get('outbox_file')}")
                print(f"Sentinel Log    : {smoke_res.get('sentinel_log_latest')}")
                print(f"Latency         : {smoke_res.get('latency_s')}s")
                print("=" * 72)
            sys.exit(0 if smoke_res.get("smoke_test") == "PASSED" else 1)

        elif args.think:
            res = think_and_execute(args.think, context={"include_screen": args.screen})
            if args.json:
                print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
            else:
                p = res.plan
                print(f"🦋 Jarvis Brain Execution [{res.status}] 🦋")
                print("=" * 72)
                print(f"Prompt   : {p.prompt}")
                print(f"Thought  : {p.thought}")
                print(f"Action   : {p.action} -> {p.skill}")
                print(f"Response : {res.formatted_response}")
                print(f"Latency  : {res.latency_s:.4f}s")
                print("=" * 72)
            sys.exit(0 if res.status == "SUCCESS" else 1)

        elif args.voice:
            v_res = speak(args.voice)
            if args.json:
                print(json.dumps(v_res, indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Voice synthesis: \"{args.voice}\" [{v_res.get('status')}] ({v_res.get('latency_s', 0.0)}s) 🦋")
            sys.exit(0)

        elif args.nudge:
            if args.nudge.lower() == "all":
                nudges = execute_scheduled_nudges(force=True)
                if args.json:
                    print(json.dumps(nudges, indent=2, ensure_ascii=False))
                else:
                    print(f"🦋 Executed {len(nudges)} Scheduled Nudges 🦋")
                    for n in nudges:
                        print(f"  • [{n.get('status')}] {n.get('nudge')} -> {n.get('log_line')}")
            else:
                n_res = run_nudge_by_name(args.nudge)
                if args.json:
                    print(json.dumps(n_res, indent=2, ensure_ascii=False))
                else:
                    print(f"🦋 Nudge '{args.nudge}' [{n_res.get('status')}]: {n_res.get('log_line')}")
            sys.exit(0)

        elif args.status:
            stat_res = get_jarvis_status()
            if args.json:
                print(json.dumps(stat_res, indent=2, ensure_ascii=False))
            else:
                print(render_jarvis_status(stat_res))
            sys.exit(0)

        elif args.submit:
            try:
                task_args = json.loads(args.args)
            except Exception:
                task_args = {}
            harness = JarvisHarness()
            task_path = harness.submit_task(prompt_or_skill=args.submit, args=task_args)
            if args.json:
                print(json.dumps({"submitted": True, "task_file": task_path, "mark": WATERMARK}, indent=2))
            else:
                print(f"🦋 Submitted task into inbox: {task_path}")
            sys.exit(0)

        elif args.once:
            harness = JarvisHarness()
            resps = harness.process_pending_inbox()
            if args.json:
                print(json.dumps([r.to_dict() for r in resps], indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Processed {len(resps)} pending task(s) from inbox 🦋")
                for r in resps:
                    print(f"  • [{r.status}] {r.task_id} -> {r.skill_used} ({r.latency_s}s)")
            sys.exit(0)

        elif args.daemon:
            run_jarvis_loop(interval=args.interval)

        elif args.manage_execute_audit:
            rc = run_manage_execute_audit(hours=args.hours, smoke=args.smoke, auto_allow=cli_auto_allow_override)
            sys.exit(rc)

        elif args.round10:
            r10_hours = args.hours if args.hours != 10.0 else 1.0  # round10 default differs from MEA default
            run_round10(hours=r10_hours, once=args.r10_once)
            sys.exit(0)

    except KeyboardInterrupt:
        print(f"\n🦋 Jarvis execution stopped by user.", file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        if args.json:
            print(json.dumps({"status": "ERROR", "error": str(exc), "mark": WATERMARK}, indent=2))
        else:
            print(f"🦋 ERROR in jarvis: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
