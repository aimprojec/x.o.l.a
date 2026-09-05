#!/usr/bin/env python3
"""Usage: python sentinel.py [--once] [--daemon] [--interval SECONDS] [--nudge NAME] [--status] [--tail N] [--json] # Jarvis System Sentinel & Health Watcher 🦋"""

import argparse
import ctypes
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
VERSION = "1.0.0"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

JARVIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(JARVIS_DIR)
SENTINEL_LOG_FILE = os.path.join(JARVIS_DIR, "sentinel.log")
INBOX_DIR = os.path.join(JARVIS_DIR, "inbox")
OUTBOX_DIR = os.path.join(JARVIS_DIR, "outbox")


# =====================================================================
# 1) Windows CTypes Memory Structure
# =====================================================================

class MEMORYSTATUSEX(ctypes.Structure):
    """Windows API GlobalMemoryStatusEx structure for instantaneous RAM queries."""
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _get_ram_windows() -> Dict[str, Any]:
    """Retrieve exact Windows RAM metrics via kernel32 GlobalMemoryStatusEx."""
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_bytes = stat.ullTotalPhys
            avail_bytes = stat.ullAvailPhys
            used_bytes = total_bytes - avail_bytes
            load_pct = float(stat.dwMemoryLoad)
            total_gb = round(total_bytes / (1024 ** 3), 2)
            used_gb = round(used_bytes / (1024 ** 3), 2)
            free_gb = round(avail_bytes / (1024 ** 3), 2)
            return {
                "total_gb": total_gb,
                "used_gb": used_gb,
                "free_gb": free_gb,
                "used_percent": load_pct,
                "source": "kernel32.GlobalMemoryStatusEx",
            }
    except Exception:
        pass

    # Fallback to estimated
    return {
        "total_gb": 16.0,
        "used_gb": 8.0,
        "free_gb": 8.0,
        "used_percent": 50.0,
        "source": "fallback",
    }


def _get_ram_unix() -> Dict[str, Any]:
    """Retrieve Unix/Linux RAM metrics via /proc/meminfo or sysconf."""
    try:
        if os.path.exists("/proc/meminfo"):
            mem_info = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        mem_info[key] = int(val) * 1024  # bytes
            total = mem_info.get("MemTotal", 0)
            avail = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
            used = total - avail
            pct = round((used / total) * 100.0, 1) if total > 0 else 0.0
            return {
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(avail / (1024 ** 3), 2),
                "used_percent": pct,
                "source": "/proc/meminfo",
            }
    except Exception:
        pass
    return {
        "total_gb": 8.0,
        "used_gb": 4.0,
        "free_gb": 4.0,
        "used_percent": 50.0,
        "source": "fallback",
    }


def probe_ram() -> Dict[str, Any]:
    """Probe system RAM usage metrics across platforms."""
    if sys.platform == "win32":
        return _get_ram_windows()
    return _get_ram_unix()


# =====================================================================
# 2) Disk & CPU Probing
# =====================================================================

def probe_disk(paths: Optional[List[str]] = None) -> Dict[str, Any]:
    """Probe disk storage usage across specified paths/mounts."""
    if not paths:
        if sys.platform == "win32":
            paths = ["D:\\", "C:\\"] if os.path.exists("D:\\") else ["C:\\"]
        else:
            paths = ["/", "/home"] if os.path.exists("/home") else ["/"]

    disks = {}
    highest_load = 0.0

    for p in paths:
        if os.path.exists(p):
            try:
                usage = shutil.disk_usage(p)
                total_gb = round(usage.total / (1024 ** 3), 2)
                used_gb = round(usage.used / (1024 ** 3), 2)
                free_gb = round(usage.free / (1024 ** 3), 2)
                pct = round((usage.used / usage.total) * 100.0, 1) if usage.total > 0 else 0.0
                disks[p] = {
                    "path": p,
                    "total_gb": total_gb,
                    "used_gb": used_gb,
                    "free_gb": free_gb,
                    "used_percent": pct,
                }
                if pct > highest_load:
                    highest_load = pct
            except Exception as e:
                disks[p] = {"path": p, "error": str(e)}

    return {
        "drives": disks,
        "max_used_percent": highest_load,
    }


def probe_cpu() -> Dict[str, Any]:
    """Probe CPU load percentage using zero-dep OS utilities."""
    cpu_pct = 0.0
    source = "unknown"

    if sys.platform == "win32":
        # Attempt 1: wmic cpu get loadpercentage (very quick)
        try:
            res = subprocess.run(
                ["wmic", "cpu", "get", "loadpercentage"],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=NO_WINDOW,
            )
            if res.returncode == 0:
                lines = [l.strip() for l in res.stdout.splitlines() if l.strip()]
                for l in lines:
                    if l.isdigit():
                        cpu_pct = float(l)
                        source = "wmic"
                        break
        except Exception:
            pass

        # Attempt 2: fallback to powershell Get-CimInstance Win32_Processor if wmic failed
        if source == "unknown":
            try:
                ps_cmd = "(Get-CimInstance Win32_Processor).LoadPercentage"
                res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=NO_WINDOW,
                )
                if res.returncode == 0 and res.stdout.strip().isdigit():
                    cpu_pct = float(res.stdout.strip())
                    source = "powershell"
            except Exception:
                pass
    else:
        # Unix load average
        try:
            load1, _, _ = os.getloadavg()
            cores = os.cpu_count() or 1
            cpu_pct = round(min(100.0, (load1 / cores) * 100.0), 1)
            source = "getloadavg"
        except Exception:
            pass

    if source == "unknown":
        cpu_pct = 5.0
        source = "estimated"

    return {
        "used_percent": cpu_pct,
        "cores": os.cpu_count() or 1,
        "source": source,
    }


# =====================================================================
# 3) Service Heartbeat Probes
# =====================================================================

def probe_services(server_url: str = "http://127.0.0.1:8101/api/health") -> Dict[str, Any]:  # 🦋
    """Probe heartbeats of active XOLA and Jarvis services."""
    services = {}

    # 1. Workbench REST Server (port fallback: 8101 real Workbench, then 8765 legacy) 🦋
    candidates = [server_url]
    if "127.0.0.1:8101" in server_url:
        candidates.append(server_url.replace("127.0.0.1:8101", "127.0.0.1:8765"))
    elif "127.0.0.1:8765" in server_url:
        candidates.append(server_url.replace("127.0.0.1:8765", "127.0.0.1:8101"))
    else:
        candidates.append("http://127.0.0.1:8765/api/health")
    probed_url = candidates[0]
    last_err = ""
    wb_result: Dict[str, Any] = {"status": "DOWN", "url": probed_url}
    for cand in candidates:
        probed_url = cand
        try:
            req = urllib.request.Request(cand, headers={"User-Agent": "XOLA-Sentinel/1.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                status_code = resp.getcode()
                body = resp.read().decode("utf-8", errors="ignore")
                wb_result = {
                    "status": "UP" if status_code == 200 else "DEGRADED",
                    "http_code": status_code,
                    "url": cand,
                }
                break
        except Exception as e:
            last_err = str(e)
            wb_result = {
                "status": "DOWN",
                "url": cand,
                "error": last_err,
            }
            continue
    services["workbench_server"] = wb_result

    # 2. Inbox Queue Backlog
    inbox_count = 0
    if os.path.exists(INBOX_DIR):
        try:
            inbox_count = len([
                f for f in os.listdir(INBOX_DIR)
                if os.path.isfile(os.path.join(INBOX_DIR, f)) and not f.startswith(".")
            ])
        except Exception:
            pass

    # 3. Outbox Queue Count
    outbox_count = 0
    if os.path.exists(OUTBOX_DIR):
        try:
            outbox_count = len([
                f for f in os.listdir(OUTBOX_DIR)
                if os.path.isfile(os.path.join(OUTBOX_DIR, f)) and not f.startswith(".")
            ])
        except Exception:
            pass

    services["jarvis_queues"] = {
        "status": "HEALTHY" if inbox_count < 50 else "BACKLOG_WARNING",
        "inbox_pending": inbox_count,
        "outbox_total": outbox_count,
    }

    # 4. Long-horizon Loop state file
    state_file = os.path.join(PROJECT_ROOT, "loop", "state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                s_data = json.load(f)
            services["loop_state"] = {
                "status": "ACTIVE",
                "current_round": s_data.get("round", 0),
                "phase": s_data.get("phase", "unknown"),
            }
        except Exception as e:
            services["loop_state"] = {"status": "ERROR", "error": str(e)}
    else:
        services["loop_state"] = {"status": "IDLE", "note": "state.json not found"}

    return services


# =====================================================================
# 4) Sentinel Health Evaluator Dataclass
# =====================================================================

@dataclass
class SentinelCheck:
    """Complete snapshot of system health, load, and service heartbeats."""
    timestamp: str
    status: str  # HEALTHY, WARNING, CRITICAL
    cpu: Dict[str, Any]
    ram: Dict[str, Any]
    disk: Dict[str, Any]
    services: Dict[str, Any]
    alerts: List[str] = field(default_factory=list)
    mark: str = WATERMARK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_log_line(self) -> str:
        """Format entry for sentinel.log."""
        cpu_p = self.cpu.get("used_percent", 0.0)
        ram_p = self.ram.get("used_percent", 0.0)
        disk_p = self.disk.get("max_used_percent", 0.0)
        srv_status = self.services.get("workbench_server", {}).get("status", "UNKNOWN")
        inbox_n = self.services.get("jarvis_queues", {}).get("inbox_pending", 0)
        alerts_str = f" | ALERTS: {'; '.join(self.alerts)}" if self.alerts else ""
        return (
            f"[{self.timestamp}] [{self.status}] CPU: {cpu_p:.1f}% | "
            f"RAM: {ram_p:.1f}% | DISK_MAX: {disk_p:.1f}% | "
            f"SRV: {srv_status} | INBOX: {inbox_n}{alerts_str} {self.mark}"
        )


def get_system_health() -> SentinelCheck:
    """Perform a holistic health check probe across all subsystems."""
    now_ts = datetime.datetime.now().isoformat()
    cpu_data = probe_cpu()
    ram_data = probe_ram()
    disk_data = probe_disk()
    services_data = probe_services()

    alerts = []
    status = "HEALTHY"

    # Evaluate RAM
    ram_pct = ram_data.get("used_percent", 0.0)
    if ram_pct >= 95.0:
        alerts.append(f"CRITICAL: RAM usage exceeds 95% ({ram_pct:.1f}%)")
        status = "CRITICAL"
    elif ram_pct >= 85.0:
        alerts.append(f"WARNING: High RAM usage ({ram_pct:.1f}%)")
        if status != "CRITICAL":
            status = "WARNING"

    # Evaluate Disk
    disk_pct = disk_data.get("max_used_percent", 0.0)
    if disk_pct >= 95.0:
        alerts.append(f"CRITICAL: Disk usage exceeds 95% ({disk_pct:.1f}%)")
        status = "CRITICAL"
    elif disk_pct >= 90.0:
        alerts.append(f"WARNING: Disk usage high ({disk_pct:.1f}%)")
        if status != "CRITICAL":
            status = "WARNING"

    # Evaluate CPU
    cpu_pct = cpu_data.get("used_percent", 0.0)
    if cpu_pct >= 98.0:
        alerts.append(f"WARNING: CPU load sustained near 100% ({cpu_pct:.1f}%)")
        if status != "CRITICAL":
            status = "WARNING"

    # Evaluate Services
    inbox_n = services_data.get("jarvis_queues", {}).get("inbox_pending", 0)
    if inbox_n >= 100:
        alerts.append(f"WARNING: Large inbox backlog ({inbox_n} pending tasks)")
        if status != "CRITICAL":
            status = "WARNING"

    return SentinelCheck(
        timestamp=now_ts,
        status=status,
        cpu=cpu_data,
        ram=ram_data,
        disk=disk_data,
        services=services_data,
        alerts=alerts,
        mark=WATERMARK,
    )


# =====================================================================
# 5) Scheduled Periodic Nudges Subsystem
# =====================================================================

@dataclass
class NudgeSchedule:
    """Configuration and state for a scheduled periodic nudge task."""
    name: str
    interval_s: float
    last_run: float = 0.0
    last_status: str = "PENDING"
    last_result: Optional[Dict[str, Any]] = None
    enabled: bool = True
    mark: str = WATERMARK

    def is_due(self, current_time: Optional[float] = None) -> bool:
        now = current_time if current_time is not None else time.time()
        return self.enabled and (now - self.last_run >= self.interval_s)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def append_nudge_log(line: str, log_path: str = SENTINEL_LOG_FILE) -> None:
    """Append formatted nudge line to sentinel.log safely."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line.strip() + "\n")
    except Exception as e:
        print(f"🦋 Sentinel nudge logging error: {e}", file=sys.stderr)


def nudge_health_monitor(log_path: str = SENTINEL_LOG_FILE) -> Dict[str, Any]:
    """Periodic Nudge: probe holistic vitals and append structured nudge log."""
    t0 = time.perf_counter()
    health = get_system_health()
    lat = round(time.perf_counter() - t0, 4)

    cpu_p = health.cpu.get("used_percent", 0.0)
    ram_p = health.ram.get("used_percent", 0.0)
    disk_p = health.disk.get("max_used_percent", 0.0)
    srv_st = health.services.get("workbench_server", {}).get("status", "UNKNOWN")
    inbox_n = health.services.get("jarvis_queues", {}).get("inbox_pending", 0)

    log_line = (
        f"[{datetime.datetime.now().isoformat()}] [NUDGE] [HEALTH_MONITOR] [{health.status}] "
        f"CPU: {cpu_p:.1f}% | RAM: {ram_p:.1f}% | DISK_MAX: {disk_p:.1f}% | SRV: {srv_st} | INBOX: {inbox_n} {WATERMARK}"
    )
    append_nudge_log(log_line, log_path=log_path)

    return {
        "nudge": "health_monitor",
        "status": health.status,
        "health": health.to_dict(),
        "log_line": log_line,
        "latency_s": lat,
        "mark": WATERMARK,
    }


def nudge_guard_audit(target_dir: Optional[str] = None, log_path: str = SENTINEL_LOG_FILE) -> Dict[str, Any]:
    """Periodic Nudge: run lightweight guard audit on codebase and log verdict."""
    t0 = time.perf_counter()
    tgt = target_dir or PROJECT_ROOT

    try:
        import tools.guard as guard_tool
        audit_res = guard_tool.audit(target=tgt, strict=False, fix=False, smoke=False)
        verdict = audit_res.get("verdict", "PASS")
        files_n = audit_res.get("summary", {}).get("files_scanned", 0)
        findings_n = audit_res.get("summary", {}).get("total_findings", 0)
        crit_n = audit_res.get("summary", {}).get("critical_count", 0)
        warn_n = audit_res.get("summary", {}).get("warning_count", 0)
    except Exception as e:
        verdict = "ERROR"
        files_n, findings_n, crit_n, warn_n = 0, 1, 1, 0
        audit_res = {"error": str(e)}

    lat = round(time.perf_counter() - t0, 4)
    log_line = (
        f"[{datetime.datetime.now().isoformat()}] [NUDGE] [GUARD_AUDIT] [{verdict}] "
        f"Files: {files_n} | Findings: {findings_n} (Crit: {crit_n}, Warn: {warn_n}) | Verdict: {verdict} {WATERMARK}"
    )
    append_nudge_log(log_line, log_path=log_path)

    return {
        "nudge": "guard_audit",
        "status": verdict,
        "verdict": verdict,
        "files_scanned": files_n,
        "findings_count": findings_n,
        "details": audit_res,
        "log_line": log_line,
        "latency_s": lat,
        "mark": WATERMARK,
    }


def nudge_scout_probe(log_path: str = SENTINEL_LOG_FILE) -> Dict[str, Any]:
    """Periodic Nudge: probe execution lanes (python, agy, opencode) and log status."""
    t0 = time.perf_counter()

    try:
        import tools.scout as scout_tool
        py_info = scout_tool.probe_python()
        agy_info = scout_tool.probe_agy(quick=True)
        op_info = scout_tool.probe_opencode(quick=True)
        lanes = {"python": py_info, "agy": agy_info, "opencode": op_info}
        overall = "UP" if any(l.get("status") == "UP" for l in lanes.values()) else "DOWN"
        py_st = py_info.get("status", "UNKNOWN")
        agy_st = agy_info.get("status", "UNKNOWN")
        op_st = op_info.get("status", "UNKNOWN")
    except Exception as e:
        lanes = {"error": str(e)}
        overall = "ERROR"
        py_st, agy_st, op_st = "ERR", "ERR", "ERR"

    lat = round(time.perf_counter() - t0, 4)
    log_line = (
        f"[{datetime.datetime.now().isoformat()}] [NUDGE] [SCOUT_PROBE] [{overall}] "
        f"Lanes: python={py_st}, agy={agy_st}, opencode={op_st} {WATERMARK}"
    )
    append_nudge_log(log_line, log_path=log_path)

    return {
        "nudge": "scout_probe",
        "status": overall,
        "lanes": lanes,
        "log_line": log_line,
        "latency_s": lat,
        "mark": WATERMARK,
    }


def run_nudge_by_name(name: str, log_path: str = SENTINEL_LOG_FILE) -> Dict[str, Any]:
    """Execute a single named periodic nudge."""
    clean = name.lower().strip()
    if clean in ("health", "health_monitor", "vitals"):
        return nudge_health_monitor(log_path=log_path)
    elif clean in ("guard", "guard_audit", "audit"):
        return nudge_guard_audit(log_path=log_path)
    elif clean in ("scout", "scout_probe", "lanes"):
        return nudge_scout_probe(log_path=log_path)
    else:
        return {
            "nudge": name,
            "status": "ERROR",
            "error": f"Unknown nudge type '{name}'",
            "mark": WATERMARK,
        }


# =====================================================================
# 6) Sentinel Daemon & Log Management
# =====================================================================

class Sentinel:
    """Jarvis Background Sentinel Watcher & Scheduled Nudges Engine."""

    def __init__(self, log_path: str = SENTINEL_LOG_FILE, interval: float = 5.0):
        self.log_path = log_path
        self.interval = interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Scheduled nudges with default intervals
        self.schedules: Dict[str, NudgeSchedule] = {
            "health_monitor": NudgeSchedule(name="health_monitor", interval_s=10.0),
            "guard_audit": NudgeSchedule(name="guard_audit", interval_s=60.0),
            "scout_probe": NudgeSchedule(name="scout_probe", interval_s=120.0),
        }

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)
        os.makedirs(INBOX_DIR, exist_ok=True)
        os.makedirs(OUTBOX_DIR, exist_ok=True)

    def log_entry(self, check: SentinelCheck) -> None:
        """Append health check entry to sentinel.log."""
        with self._lock:
            try:
                line = check.to_log_line() + "\n"
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception as e:
                print(f"🦋 Sentinel logging error: {e}", file=sys.stderr)

    def check_and_log(self) -> SentinelCheck:
        """Execute one health check and log the result."""
        check = get_system_health()
        self.log_entry(check)
        return check

    def check_and_run_nudges(self, force: bool = False) -> List[Dict[str, Any]]:
        """Evaluate scheduled nudges and execute due tasks."""
        results: List[Dict[str, Any]] = []
        now = time.time()

        for name, sched in self.schedules.items():
            if force or sched.is_due(now):
                with self._lock:
                    res = run_nudge_by_name(name, log_path=self.log_path)
                sched.last_run = now
                sched.last_status = res.get("status", "SUCCESS")
                sched.last_result = res
                results.append(res)

        return results

    def _loop(self) -> None:
        """Internal daemon loop checking vitals and running periodic nudges."""
        while self._running:
            self.check_and_log()
            self.check_and_run_nudges(force=False)
            time.sleep(self.interval)

    def start_daemon(self) -> None:
        """Start background sentinel watcher thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="JarvisSentinel", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background sentinel watcher thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


def run_sentinel_once(log_path: str = SENTINEL_LOG_FILE) -> SentinelCheck:
    """Perform a single sentinel health probe and record to log."""
    sentinel = Sentinel(log_path=log_path)
    return sentinel.check_and_log()


def read_sentinel_log(tail_n: int = 20, log_path: str = SENTINEL_LOG_FILE) -> List[str]:
    """Read the last N lines of the sentinel.log file."""
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return lines[-tail_n:] if tail_n > 0 else lines
    except Exception:
        return []


def execute_scheduled_nudges(
    force: bool = False,
    log_path: str = SENTINEL_LOG_FILE,
) -> List[Dict[str, Any]]:
    """Top-level helper to trigger all scheduled nudges."""
    sentinel = Sentinel(log_path=log_path)
    return sentinel.check_and_run_nudges(force=force)


# =====================================================================
# 7) Terminal Rendering & CLI
# =====================================================================

def render_sentinel_report(check: SentinelCheck) -> str:
    """Render structured terminal report for sentinel health check."""
    status_tag = f"[{check.status}]"
    cpu_p = check.cpu.get("used_percent", 0.0)
    ram_used = check.ram.get("used_gb", 0.0)
    ram_total = check.ram.get("total_gb", 0.0)
    ram_pct = check.ram.get("used_percent", 0.0)
    max_disk = check.disk.get("max_used_percent", 0.0)
    srv_data = check.services

    lines = [
        f"🦋 Jarvis Sentinel Health Status {status_tag} 🦋",
        "=" * 72,
        f"Timestamp    : {check.timestamp}",
        f"Health State : {check.status}",
        f"CPU Load     : {cpu_p:.1f}% ({check.cpu.get('cores', 1)} cores, source: {check.cpu.get('source')})",
        f"RAM Usage    : {ram_used:.1f} GB / {ram_total:.1f} GB ({ram_pct:.1f}%)",
        f"Max Disk Use : {max_disk:.1f}%",
        "-" * 72,
        "Storage Breakdown:",
    ]

    for drive, dinfo in check.disk.get("drives", {}).items():
        if "error" in dinfo:
            lines.append(f"  • {drive:<10} : Error ({dinfo['error']})")
        else:
            lines.append(
                f"  • {drive:<10} : {dinfo.get('used_gb', 0):.1f} GB used / "
                f"{dinfo.get('total_gb', 0):.1f} GB total ({dinfo.get('used_percent', 0):.1f}%) | "
                f"Free: {dinfo.get('free_gb', 0):.1f} GB"
            )

    lines.append("-" * 72)
    lines.append("Service Heartbeats:")
    wb_srv = srv_data.get("workbench_server", {})
    lines.append(f"  • Workbench Server : [{wb_srv.get('status', 'UNKNOWN')}] ({wb_srv.get('url', '')})")

    jq = srv_data.get("jarvis_queues", {})
    lines.append(f"  • Jarvis Queues    : [{jq.get('status', 'HEALTHY')}] Inbox: {jq.get('inbox_pending', 0)} | Outbox: {jq.get('outbox_total', 0)}")

    lp = srv_data.get("loop_state", {})
    lines.append(f"  • Long-Horizon Loop: [{lp.get('status', 'IDLE')}] Round: {lp.get('current_round', 0)}")

    if check.alerts:
        lines.append("-" * 72)
        lines.append(f"⚠️ Active Alerts ({len(check.alerts)}):")
        for alert in check.alerts:
            lines.append(f"  • {alert}")

    lines.append("=" * 72)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for sentinel health monitor."""
    parser = argparse.ArgumentParser(
        prog="sentinel",
        description="Jarvis Sentinel — Background System Health Watcher, Logger & Nudges 🦋",
        epilog="Usage: python sentinel.py [--once] [--daemon] [--interval SECONDS] [--nudge NAME] [--status] [--tail N] [--json]",
    )
    parser.add_argument("--once", "--check-once", dest="once", action="store_true", help="Perform single health check and record to log")
    parser.add_argument("--status", action="store_true", help="Inspect current system health without loop")
    parser.add_argument("--daemon", action="store_true", help="Run continuous background watcher and nudge loop")
    parser.add_argument("--interval", type=float, default=5.0, help="Check interval in seconds for daemon (default: 5.0)")
    parser.add_argument("--nudge", metavar="NAME", help="Trigger scheduled nudge ('all', 'health', 'guard', 'scout')")
    parser.add_argument("--tail", type=int, default=0, metavar="N", help="Display last N entries from sentinel.log")
    parser.add_argument("--json", action="store_true", help="Output result in machine-readable JSON format")
    return parser


def main():
    """Main CLI entrypoint for sentinel."""
    parser = build_parser()
    args = parser.parse_args()

    if args.tail > 0:
        lines = read_sentinel_log(tail_n=args.tail)
        if args.json:
            print(json.dumps({"log_lines": lines, "total": len(lines), "mark": WATERMARK}, indent=2))
        else:
            print(f"🦋 Jarvis Sentinel Log (Last {len(lines)} entries) 🦋")
            print("=" * 72)
            for l in lines:
                print(l)
            print("=" * 72)
        sys.exit(0)

    if args.nudge:
        if args.nudge.lower() == "all":
            results = execute_scheduled_nudges(force=True)
            if args.json:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Executed {len(results)} Scheduled Nudges 🦋")
                for r in results:
                    print(f"  • [{r.get('status')}] {r.get('nudge')} -> {r.get('log_line')}")
            sys.exit(0)
        else:
            res = run_nudge_by_name(args.nudge)
            if args.json:
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Executed Nudge '{args.nudge}' [{res.get('status')}]: {res.get('log_line')}")
            sys.exit(0 if res.get("status") not in ("ERROR", "KILL") else 1)

    if args.daemon:
        print(f"🦋 Starting Jarvis Sentinel Daemon (interval: {args.interval}s)... Press Ctrl+C to stop.")
        sentinel = Sentinel(interval=args.interval)
        try:
            while True:
                chk = sentinel.check_and_log()
                nudges = sentinel.check_and_run_nudges()
                print(chk.to_log_line())
                for n in nudges:
                    print(f"   ↳ Nudge: {n.get('nudge')} -> [{n.get('status')}]")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print(f"\n🦋 Jarvis Sentinel stopped cleanly.")
            sys.exit(0)

    # Default action: single check
    chk = run_sentinel_once()
    if args.json:
        print(json.dumps(chk.to_dict(), indent=2))
    else:
        print(render_sentinel_report(chk))
    sys.exit(0 if chk.status != "CRITICAL" else 1)


if __name__ == "__main__":
    main()
