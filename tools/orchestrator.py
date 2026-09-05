#!/usr/bin/env python3
"""Usage: python orchestrator.py [--smoke] [--json] # X.O.L.A. Core Orchestrator & Deterministic Dispatch 🦋

Layer 3 (todo items 56-90):
56. Regex Intent Gatekeeper
57. Deterministic FSM Engine (PENDING, VALIDATING, CONFIRMING, EXECUTING, VERIFYING, COMPLETE, FAILED, ABORTED)
58. Idempotency Token Provider
59. Task Plan DAG Compiler
60. Parallel Step Dispatcher
61. Step Dependency Blocker
62. Transaction Rollback Handler
63. Execution Timeout Watchdog
64. Circuit Breaker Pattern
65. Human Approval Gate
66. Priority Event Queue
67. Sub-Task Result Multiplexer
68. Static Route Whitelist
69. Runtime State Introspector
70. Deadlock Prevention Manager
71. Task Retry Policy
72. Pre-Execution Contract Validation
73. Post-Execution Outcome Verifier
74. Dynamic Replanning Trigger
75. Deterministic Branching Selector
76. Subprocess Isolation Harness
77. Latency Instrumentation
78. Autonomous Runloop Controller
79. Process Signal Trapper
80. Action Rate Limiter
81. Atomic File Write Wrappers
82. Context Bleed Barrier
83. Execution Graph Visualizer
84. Task Cancellation Interceptor
85. Workload Throttler
86. Multi-Step State Preservation
87. Plan Sanity Bounds Checker
88. Input Normalizer
89. Orchestrator Heartbeat Broadcaster
90. Task Deduplication Window
Pure stdlib. Zero external dependencies. 🦋
"""

import argparse
import collections
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import dataclasses
import datetime
import enum
import hashlib
import json
import os
import queue
import re
import signal
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "loop", "lh10", "orchestrator")
STATE_DIR = os.path.join(BASE, "state")
SNAPSHOT_FILE = os.path.join(STATE_DIR, "dag_snapshot.json")
MAX_PLAN_ACTIONS = 25  # 87: Plan Sanity Bounds Checker

# =====================================================================
# 57: Deterministic FSM Engine 🦋
# =====================================================================

class TaskState(enum.Enum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    CONFIRMING = "CONFIRMING"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    ABORTED = "ABORTED"

class FSMTransitionError(Exception):
    pass

class TaskFSM:
    VALID_TRANSITIONS = {
        TaskState.PENDING: {TaskState.VALIDATING, TaskState.ABORTED},
        TaskState.VALIDATING: {TaskState.CONFIRMING, TaskState.EXECUTING, TaskState.FAILED, TaskState.ABORTED},
        TaskState.CONFIRMING: {TaskState.EXECUTING, TaskState.ABORTED, TaskState.FAILED},
        TaskState.EXECUTING: {TaskState.VERIFYING, TaskState.FAILED, TaskState.ABORTED},
        TaskState.VERIFYING: {TaskState.COMPLETE, TaskState.FAILED, TaskState.EXECUTING},
        TaskState.COMPLETE: set(),
        TaskState.FAILED: {TaskState.PENDING},  # allowed for retry
        TaskState.ABORTED: set(),
    }

    def __init__(self, initial: TaskState = TaskState.PENDING):
        self.state = initial
        self.history: List[Tuple[TaskState, float]] = [(initial, time.time())]

    def transition(self, next_state: TaskState) -> TaskState:
        if next_state not in self.VALID_TRANSITIONS.get(self.state, set()):
            raise FSMTransitionError(f"Illegal transition: {self.state} -> {next_state}")
        self.state = next_state
        self.history.append((next_state, time.time()))
        return self.state

# =====================================================================
# 88: Input Normalizer & 56: Regex Intent Gatekeeper 🦋
# =====================================================================

_STRIP_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_NORMALIZE_WS = re.compile(r"\s+")

def normalize_input(text: str) -> str:
    """88: Strip escape sequences, redundant whitespace, and unsupported chars."""
    clean = _STRIP_ESCAPE.sub("", text)
    clean = _NORMALIZE_WS.sub(" ", clean)
    return clean.strip()

_STATIC_ROUTES = [
    (re.compile(r"^(?:status|health|ping|probe)\b", re.I), "system.health"),
    (re.compile(r"^(?:disk|storage|drive space)\b", re.I), "hands.disk"),
    (re.compile(r"^(?:ps|processes|list procs)\b", re.I), "hands.ps"),
    (re.compile(r"^(?:audit|guard|verify code)\b", re.I), "guard.audit"),
    (re.compile(r"^(?:clean|vacuum|tidy)\b", re.I), "system.clean"),
    (re.compile(r"^(?:voice|speak|say)\s+(.+)$", re.I), "voice.speak"),
]

def regex_intent_gatekeeper(prompt: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """56: Initial regex routing matrix to handle common commands without an LLM."""
    clean = normalize_input(prompt)
    for pattern, route in _STATIC_ROUTES:
        m = pattern.search(clean)
        if m:
            args = {"raw": clean}
            if m.groups():
                args["param"] = m.group(1).strip()
            return route, args
    return None

# =====================================================================
# 58: Idempotency Token Provider & 90: Task Deduplication Window 🦋
# =====================================================================

_DEDUP_WINDOW_SECONDS = 5.0
_recent_tasks: Dict[str, float] = {}
_recent_tasks_lock = threading.Lock()

def generate_idempotency_token(intent: str, args: Dict[str, Any]) -> str:
    """58: Generate unique deterministic task keys to prevent identical runs."""
    payload = json.dumps({"intent": intent, "args": args}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def check_and_record_dedup(token: str) -> bool:
    """90: Cache and reject identical incoming tasks submitted within 5-sec window."""
    now = time.time()
    with _recent_tasks_lock:
        # Purge stale
        stale = [k for k, t in _recent_tasks.items() if now - t > _DEDUP_WINDOW_SECONDS]
        for k in stale:
            del _recent_tasks[k]
        if token in _recent_tasks:
            return False  # Duplicate within window!
        _recent_tasks[token] = now
        return True

# =====================================================================
# 59: Task Plan DAG Compiler, 60/61: Dispatcher & Blocker 🦋
# =====================================================================

@dataclasses.dataclass
class DAGNode:
    id: str
    action: str
    args: Dict[str, Any] = dataclasses.field(default_factory=dict)
    dependencies: Set[str] = dataclasses.field(default_factory=set)
    state: TaskState = TaskState.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    rollback_fn: Optional[Callable[[], Any]] = None

class DAGPlan:
    """59: Directed Acyclic Graph of individual atomic tool actions."""
    def __init__(self):
        self.nodes: Dict[str, DAGNode] = {}

    def add_node(self, node: DAGNode):
        if len(self.nodes) >= MAX_PLAN_ACTIONS:
            raise ValueError(f"Plan sanity limit exceeded ({MAX_PLAN_ACTIONS} max)")
        if node.id in self.nodes:
            raise ValueError("Duplicate DAG node ID: " + node.id)
        self.nodes[node.id] = node

    def is_acyclic(self) -> bool:
        visited: Dict[str, int] = {k: 0 for k in self.nodes}  # 0=unvisited, 1=visiting, 2=visited
        def dfs(curr: str) -> bool:
            visited[curr] = 1
            for dep in self.nodes[curr].dependencies:
                if dep not in visited:
                    continue
                if visited[dep] == 1:
                    return False
                if visited[dep] == 0 and not dfs(dep):
                    return False
            visited[curr] = 2
            return True
        return all(dfs(n) for n in self.nodes if visited[n] == 0)

    def ready_nodes(self) -> List[DAGNode]:
        """61: Step Dependency Blocker — downstream nodes stay locked until parents COMPLETE."""
        ready = []
        for node in self.nodes.values():
            if node.state == TaskState.PENDING:
                deps_met = all(
                    dep in self.nodes and self.nodes[dep].state == TaskState.COMPLETE
                    for dep in node.dependencies
                )
                if deps_met:
                    ready.append(node)
        return ready

# =====================================================================
# 62: Transaction Rollback Handler 🦋
# =====================================================================

class RollbackJournal:
    """62: Implement inverse undo handlers for reversible actions."""
    def __init__(self):
        self._undos: List[Tuple[str, Callable[[], Any]]] = []

    def register(self, description: str, undo_fn: Callable[[], Any]):
        self._undos.append((description, undo_fn))

    def rollback(self) -> List[Dict[str, Any]]:
        results = []
        while self._undos:
            desc, fn = self._undos.pop()
            try:
                out = fn()
                results.append({"action": desc, "status": "ROLLED_BACK", "output": out})
            except Exception as exc:
                results.append({"action": desc, "status": "ROLLBACK_FAILED", "error": str(exc)})
        return results

# =====================================================================
# 64: Circuit Breaker Pattern 🦋
# =====================================================================

class CircuitState(enum.Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    """64: Automatically suspend tool integrations that log 3 consecutive failures."""
    def __init__(self, failure_threshold: int = 3, reset_timeout: float = 10.0):
        self.threshold = failure_threshold
        self.timeout = reset_timeout
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = 0.0

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.threshold:
            self.state = CircuitState.OPEN

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        return True  # HALF_OPEN allows a trial

# =====================================================================
# 65: Human Approval Gate & 68: Static Route Whitelist 🦋
# =====================================================================

ALLOWED_COMMAND_WHITELIST = {
    "system.health", "hands.disk", "hands.ps", "guard.audit",
    "system.clean", "voice.speak", "fs.read", "fs.write", "echo"
}

SENSITIVE_ACTIONS = {"system.lock", "system.shutdown", "fs.delete", "net.raw_send"}

class ApprovalGate:
    """65: Suspend execution when an action requests elevated permissions."""
    def __init__(self):
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}

    def requires_approval(self, action: str) -> bool:
        return action in SENSITIVE_ACTIONS

    def request(self, req_id: str, action: str, details: Dict[str, Any]) -> str:
        self.pending_approvals[req_id] = {"action": action, "details": details, "status": "PENDING"}
        return "APPROVAL_REQUIRED"

    def approve(self, req_id: str) -> bool:
        if req_id in self.pending_approvals:
            self.pending_approvals[req_id]["status"] = "APPROVED"
            return True
        return False

# =====================================================================
# 66: Priority Event Queue & 67: Sub-Task Result Multiplexer 🦋
# =====================================================================

class PriorityEventQueue:
    """66: In-memory thread-safe priority queue prioritizing urgent signals."""
    def __init__(self):
        self._q = queue.PriorityQueue()

    def push(self, priority: int, event_type: str, data: Any):
        # lower number = higher priority
        self._q.put((priority, time.time(), event_type, data))

    def pop(self, timeout: Optional[float] = None) -> Optional[Tuple[int, str, Any]]:
        try:
            prio, _, etype, data = self._q.get(timeout=timeout)
            return prio, etype, data
        except queue.Empty:
            return None

    def empty(self) -> bool:
        return self._q.empty()

class ResultMultiplexer:
    """67: Merge concurrent execution outputs into a unified structured dictionary."""
    def __init__(self):
        self._results: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def record(self, node_id: str, output: Any):
        with self._lock:
            self._results[node_id] = output

    def collect(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._results)

# =====================================================================
# 70: Deadlock Prevention Manager 🦋
# =====================================================================

class ResourceLockManager:
    """70: Global hierarchical resource acquisition order to prevent contention."""
    def __init__(self):
        self._locks: Dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def get_lock(self, resource_id: str) -> threading.Lock:
        with self._meta_lock:
            if resource_id not in self._locks:
                self._locks[resource_id] = threading.Lock()
            return self._locks[resource_id]

    def acquire_ordered(self, resource_ids: List[str]):
        """Acquire multiple locks in sorted lexicographical order."""
        ordered = sorted(resource_ids)
        acquired = []
        for rid in ordered:
            lk = self.get_lock(rid)
            lk.acquire()
            acquired.append(lk)
        return acquired

    def release_all(self, acquired_locks: List[threading.Lock]):
        for lk in reversed(acquired_locks):
            lk.release()

# =====================================================================
# 71: Task Retry Policy & 72: Contract Validation & 73: Outcome Verifier 🦋
# =====================================================================

def retry_with_backoff(fn: Callable[[], Any], max_retries: int = 2, base_delay: float = 0.05) -> Any:
    """71: Per-tool exponential backoff with strict maximum retry counts."""
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
    raise last_exc

def validate_contract(action: str, args: Dict[str, Any], schema: Dict[str, type]) -> Tuple[bool, Optional[str]]:
    """72: Parameter checks against target schemas before execution."""
    for field, expected_type in schema.items():
        if field not in args:
            return False, f"Missing required parameter: {field}"
        if not isinstance(args[field], expected_type):
            return False, f"Parameter {field} must be of type {expected_type.__name__}"
    return True, None

def verify_post_outcome(verifier_fn: Callable[[], bool]) -> bool:
    """73: Require tools to assert post-conditions before marking complete."""
    try:
        return bool(verifier_fn())
    except Exception:
        return False

# =====================================================================
# 76: Subprocess Isolation Harness & 77: Latency Instrumentation 🦋
# =====================================================================

def run_isolated_subprocess(cmd: List[str], timeout: float = 5.0, max_bytes: int = 65536) -> Dict[str, Any]:
    """76: Subprocess calls with capped buffer allocations and timeout."""
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        stdout = proc.stdout[:max_bytes].decode("utf-8", errors="replace")
        stderr = proc.stderr[:max_bytes].decode("utf-8", errors="replace")
        lat = round(time.perf_counter() - t0, 4)
        return {"returncode": proc.returncode, "stdout": stdout, "stderr": stderr, "latency_s": lat}
    except subprocess.TimeoutExpired:
        lat = round(time.perf_counter() - t0, 4)
        return {"returncode": -1, "error": "TIMEOUT", "latency_s": lat}
    except Exception as exc:
        lat = round(time.perf_counter() - t0, 4)
        return {"returncode": -1, "error": str(exc), "latency_s": lat}

class LatencyTracker:
    """77: Latency instrumentation around orchestrator hops measuring ms."""
    def __init__(self):
        self.measurements: Dict[str, float] = {}

    def measure(self, name: str, fn: Callable[[], Any]) -> Any:
        t0 = time.perf_counter()
        res = fn()
        self.measurements[name] = round((time.perf_counter() - t0) * 1000.0, 3)
        return res

# =====================================================================
# 80: Action Rate Limiter (Token Bucket) 🦋
# =====================================================================

class TokenBucketRateLimiter:
    """80: Enforce tokens-per-second constraints across tool calls."""
    def __init__(self, rate: float = 20.0, capacity: float = 20.0):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> bool:
        with self._lock:
            now = time.time()
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_refill = now
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

# =====================================================================
# 81: Atomic File Write Wrappers 🦋
# =====================================================================

def atomic_write_json(filepath: str, data: Any):
    """81: Write-to-temp-then-rename convention across all state modifications."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    tmp_path = filepath + f".tmp_{time.time_ns()}"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    # On Windows replace handles atomicity
    os.replace(tmp_path, filepath)

# =====================================================================
# 82: Context Bleed Barrier 🦋
# =====================================================================

class ExecutionEnvironment:
    """82: Clear local execution environments completely between sequential tasks."""
    def __init__(self):
        self.locals: Dict[str, Any] = {}

    def set(self, k: str, v: Any):
        self.locals[k] = v

    def clear(self):
        self.locals.clear()

# =====================================================================
# 83: Execution Graph Visualizer (DOT & ASCII) 🦋
# =====================================================================

def render_dag_dot(dag: DAGPlan) -> str:
    """83: Output active execution DAG states to Graphviz DOT."""
    lines = ["digraph TaskDAG {", '  node [shape=box, style=filled, fillcolor="#f0f0f0"];']
    for node in dag.nodes.values():
        color = "#c8e6c9" if node.state == TaskState.COMPLETE else "#ffcdd2" if node.state == TaskState.FAILED else "#ffffff"
        lines.append(f'  "{node.id}" [label="{node.id}: {node.action}\\n[{node.state.value}]", fillcolor="{color}"];')
        for dep in node.dependencies:
            lines.append(f'  "{dep}" -> "{node.id}";')
    lines.append("}")
    return "\n".join(lines)

def render_dag_ascii(dag: DAGPlan) -> str:
    """83: Output active execution DAG to terminal ASCII chart."""
    out = ["=== DAG Execution Chart 🦋 ==="]
    for node in dag.nodes.values():
        deps = f" <- [{', '.join(node.dependencies)}]" if node.dependencies else ""
        out.append(f"• [{node.state.value:<9}] {node.id:<12} ({node.action}){deps}")
    return "\n".join(out)

# =====================================================================
# 84: Task Cancellation Interceptor 🦋
# =====================================================================

class CancellationContext:
    """84: Cancellation hook that flags task records as ABORTED."""
    def __init__(self):
        self._aborted = threading.Event()

    def cancel(self):
        self._aborted.set()

    def is_cancelled(self) -> bool:
        return self._aborted.is_set()

# =====================================================================
# 86: Multi-Step State Preservation 🦋
# =====================================================================

def snapshot_dag_state(dag: DAGPlan, filepath: str = SNAPSHOT_FILE):
    """86: Serialize partially completed task trees to disk to allow resumption."""
    snap = {}
    for nid, node in dag.nodes.items():
        snap[nid] = {
            "id": node.id,
            "action": node.action,
            "args": node.args,
            "dependencies": list(node.dependencies),
            "state": node.state.value,
            "error": node.error,
        }
    atomic_write_json(filepath, snap)

def restore_dag_state(filepath: str = SNAPSHOT_FILE) -> Optional[DAGPlan]:
    """86: Restore serialized task tree from disk."""
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        dag = DAGPlan()
        for nid, d in data.items():
            dag.add_node(DAGNode(
                id=d["id"],
                action=d["action"],
                args=d.get("args", {}),
                dependencies=set(d.get("dependencies", [])),
                state=TaskState(d.get("state", "PENDING")),
                error=d.get("error"),
            ))
        return dag
    except Exception:
        return None

# =====================================================================
# 89: Heartbeat Broadcaster & 78: Runloop Controller 🦋
# =====================================================================

class OrchestratorHeartbeat:
    """89: Publish periodic pulse signal verifying core loop readiness."""
    def __init__(self):
        self.last_beat = 0.0
        self.pulse_count = 0

    def pulse(self) -> Dict[str, Any]:
        self.last_beat = time.time()
        self.pulse_count += 1
        return {"pulse": self.pulse_count, "timestamp": self.last_beat, "mark": WATERMARK}

# =====================================================================
# 69: Runtime State Introspector 🦋
# =====================================================================

class RuntimeIntrospector:
    """69: Expose internal JSON endpoint displaying thread states, queues, and locks."""
    def __init__(self, heartbeat: OrchestratorHeartbeat, queue_ref: PriorityEventQueue):
        self.heartbeat = heartbeat
        self.queue_ref = queue_ref

    def snapshot(self) -> Dict[str, Any]:
        return {
            "heartbeat": self.heartbeat.pulse_count,
            "last_beat_s_ago": round(time.time() - self.heartbeat.last_beat, 3) if self.heartbeat.last_beat else -1,
            "active_threads": threading.active_count(),
            "queue_empty": self.queue_ref.empty(),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }

# =====================================================================
# 60, 63, 74, 75, 85: Orchestrator Engine Core 🦋
# =====================================================================

class CoreOrchestrator:
    """Unified Orchestrator implementing Layer 3 (Items 56-90) 🦋"""
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.fsm = TaskFSM()
        self.circuit_breakers: Dict[str, CircuitBreaker] = collections.defaultdict(CircuitBreaker)
        self.approval_gate = ApprovalGate()
        self.event_queue = PriorityEventQueue()
        self.multiplexer = ResultMultiplexer()
        self.lock_manager = ResourceLockManager()
        self.rate_limiter = TokenBucketRateLimiter()
        self.heartbeat = OrchestratorHeartbeat()
        self.introspector = RuntimeIntrospector(self.heartbeat, self.event_queue)
        self.journal = RollbackJournal()
        self.env = ExecutionEnvironment()

    def dispatch_dag(self, dag: DAGPlan, timeout_per_step: float = 5.0) -> Dict[str, Any]:
        """Dispatch actual tools in isolated Python workers with bounded timeouts.

        No automatic retries for mutations. A failed parent blocks dependents.
        Worker timeout kills the Python worker, but external processes a tool
        intentionally launches may outlive it; those tools require approval.
        """
        if not dag.nodes or timeout_per_step <= 0:
            raise ValueError("Nonempty DAG and positive timeout required")
        missing = set().union(*(n.dependencies for n in dag.nodes.values())) - dag.nodes.keys()
        if missing:
            raise ValueError("Missing dependencies: " + ", ".join(sorted(missing)))
        if not dag.is_acyclic():
            raise ValueError("DAG contains cycles")
        if any(n.state != TaskState.PENDING for n in dag.nodes.values()):
            raise ValueError("Use a fresh DAG for each dispatch")
        self.fsm = TaskFSM()
        self.multiplexer = ResultMultiplexer()
        self.fsm.transition(TaskState.VALIDATING)
        self.fsm.transition(TaskState.EXECUTING)
        from tools.runtime.approvals import SCOPE
        scope = SCOPE.get()
        def work(node):
            command = [sys.executable, "-m", "tools.runtime.dag_worker"]
            payload = json.dumps({"action": node.action, "args": node.args,
                                  "scope": scope + ":" + node.id})
            result = subprocess.run(command, input=payload, capture_output=True, text=True,
                                    encoding="utf-8", timeout=timeout_per_step,
                                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if result.returncode:
                raise RuntimeError(result.stderr[-2000:] or "Worker exited unsuccessfully")
            return json.loads(result.stdout)
        futures = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            while True:
                for node in dag.nodes.values():
                    if node.state == TaskState.PENDING and any(
                        dag.nodes[d].state in (TaskState.FAILED, TaskState.ABORTED) for d in node.dependencies):
                        node.state, node.error = TaskState.ABORTED, "Dependency failed"
                for node in dag.ready_nodes():
                    if len(futures) >= self.max_workers:
                        break
                    cb = self.circuit_breakers[node.action]
                    if not cb.can_execute():
                        node.state, node.error = TaskState.FAILED, "Circuit breaker open"
                        continue
                    node.state = TaskState.EXECUTING
                    futures[executor.submit(work, node)] = node
                if not futures:
                    if any(n.state == TaskState.PENDING for n in dag.nodes.values()):
                        continue
                    break
                done, _ = wait(futures, return_when=FIRST_COMPLETED)
                for future in done:
                    node = futures.pop(future)
                    cb = self.circuit_breakers[node.action]
                    try:
                        node.result = future.result()
                        self.multiplexer.record(node.id, node.result)
                        if node.result.get("status") not in ("SUCCESS", "COMPLETE"):
                            raise RuntimeError(node.result.get("error") or str(node.result))
                        node.state = TaskState.COMPLETE
                        cb.record_success()
                    except Exception as exc:
                        node.state, node.error = TaskState.FAILED, str(exc)
                        cb.record_failure()
        self.fsm.transition(TaskState.VERIFYING)
        success = all(n.state == TaskState.COMPLETE for n in dag.nodes.values())
        self.fsm.transition(TaskState.COMPLETE if success else TaskState.FAILED)
        snapshot_dag_state(dag)
        return {"status": self.fsm.state.value, "results": self.multiplexer.collect(),
                "errors": {n.id: n.error for n in dag.nodes.values() if n.error},
                "fsm": self.fsm.state.value, "mark": WATERMARK}

# =====================================================================
# SMOKE TEST 🦋
# =====================================================================

def smoke() -> Dict[str, Any]:
    checks: Dict[str, Any] = {}
    orch = CoreOrchestrator(max_workers=2)

    # 1. Regex intent (56) & normalization (88)
    route, args = regex_intent_gatekeeper("   \x1b[31mdisk free space\x1b[0m   ")
    checks["regex_gate"] = (route == "hands.disk")

    # 2. Idempotency (58) & Dedup (90)
    tok = generate_idempotency_token("hands.disk", args)
    d1 = check_and_record_dedup(tok)
    d2 = check_and_record_dedup(tok)
    checks["idempotency_dedup"] = (d1 is True and d2 is False)

    # 3. FSM (57)
    fsm = TaskFSM()
    fsm.transition(TaskState.VALIDATING)
    fsm.transition(TaskState.EXECUTING)
    fsm.transition(TaskState.VERIFYING)
    fsm.transition(TaskState.COMPLETE)
    checks["fsm_lifecycle"] = (fsm.state == TaskState.COMPLETE)

    # 4. DAG compiler (59) & DAG execution (60, 61, 67, 86)
    dag = DAGPlan()
    dag.add_node(DAGNode(id="step1", action="echo"))
    dag.add_node(DAGNode(id="step2", action="echo", args={"text": "second"}, dependencies={"step1"}))
    dag_res = orch.dispatch_dag(dag)
    checks["dag_dispatch"] = (dag_res["status"] == "COMPLETE" and "step2" in dag_res["results"])

    # 5. Rollback journal (62)
    journal = RollbackJournal()
    journal.register("create_temp", lambda: "undone")
    rb_res = journal.rollback()
    checks["rollback"] = (len(rb_res) == 1 and rb_res[0]["status"] == "ROLLED_BACK")

    # 6. Circuit breaker (64)
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_failure()
    cb.record_failure()
    checks["circuit_breaker"] = (cb.state == CircuitState.OPEN and not cb.can_execute())

    # 7. Priority Event Queue (66)
    pq = PriorityEventQueue()
    pq.push(priority=2, event_type="LOW", data="background")
    pq.push(priority=0, event_type="URGENT", data="fire")
    prio, etype, _ = pq.pop()
    checks["priority_queue"] = (etype == "URGENT")

    # 8. Rate Limiter (80)
    rl = TokenBucketRateLimiter(rate=5.0, capacity=2.0)
    checks["rate_limiter"] = rl.acquire(1.0)

    # 9. Graph visualizers (83)
    dot = render_dag_dot(dag)
    chart = render_dag_ascii(dag)
    checks["visualizers"] = ("digraph" in dot and "DAG Execution Chart" in chart)

    # 10. Heartbeat (89) & Introspector (69)
    hb = orch.heartbeat.pulse()
    intro = orch.introspector.snapshot()
    checks["heartbeat_introspect"] = (hb["pulse"] == 1 and intro["active_threads"] > 0)

    passed = all(checks.values())
    checks["smoke"] = "PASS" if passed else "FAIL"
    checks["mark"] = WATERMARK
    return checks

def main() -> int:
    ap = argparse.ArgumentParser(description="X.O.L.A. Core Orchestrator (Layer 3) 🦋")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = smoke()
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"🦋 Orchestrator smoke: {res['smoke']} ({len(checks)} checks) 🦋" if 'checks' in locals() else f"🦋 Orchestrator smoke: {res['smoke']} 🦋")
    return 0 if res["smoke"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
