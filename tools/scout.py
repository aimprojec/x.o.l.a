#!/usr/bin/env python3
"""Usage: python scout.py [--quick] [--json] [--timeout SECONDS] # xola-scout: fast triage prober for free lanes 🦋"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

try:
    sys.stdout.reconfigure(encoding="utf-8")  # 🦋 prints everywhere, even cp1252 consoles
except Exception:
    pass

KNOWN_FALLBACKS = {
    "agy": [
        r"C:\Users\user\AppData\Local\agy\bin\agy.cmd",
        r"C:\Users\user\AppData\Local\agy\bin\agy_real.exe",
        r"C:\Users\user\AppData\Local\agy\bin\agy",
    ],
    "opencode": [
        r"C:\Users\user\AppData\Roaming\npm\opencode.CMD",
        r"C:\Users\user\AppData\Roaming\npm\opencode",
    ],
    "python": [
        sys.executable,
        r"C:\Python314\python.exe",
    ],
}


def find_executable(name: str) -> str | None:
    """Find binary path via shutil.which or known Windows fallbacks."""
    resolved = shutil.which(name)
    if resolved and os.path.exists(resolved):
        return resolved
    for fallback in KNOWN_FALLBACKS.get(name, []):
        if os.path.exists(fallback):
            return fallback
    return None


def run_cmd(cmd_list, timeout=15, cwd=None, input_text=None):
    """Run command safely returning (ok, stdout, stderr, latency_seconds)."""
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd_list,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or os.getcwd(),
            creationflags=NO_WINDOW,
        )
        latency = time.perf_counter() - t0
        return proc.returncode == 0, (proc.stdout or "").strip(), (proc.stderr or "").strip(), latency
    except subprocess.TimeoutExpired:
        return False, "", "TIMEOUT", time.perf_counter() - t0
    except Exception as exc:
        return False, "", f"LAUNCH-FAIL: {exc}", time.perf_counter() - t0


def probe_python() -> dict:
    """Probe Python runtime availability and performance."""
    t0 = time.perf_counter()
    py_path = sys.executable or find_executable("python")
    version_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    latency = time.perf_counter() - t0
    
    if not py_path or not os.path.exists(py_path):
        return {
            "lane": "python",
            "status": "DOWN",
            "path": py_path or "NOT_FOUND",
            "version": "unknown",
            "latency_s": round(latency, 4),
            "details": "Python executable not resolved",
        }

    status = "UP" if latency < 0.5 else "DEGRADED"
    return {
        "lane": "python",
        "status": status,
        "path": py_path,
        "version": f"Python {version_str}",
        "latency_s": round(latency, 4),
        "details": f"Platform: {sys.platform}, UTF-8 mode: {sys.flags.utf8_mode}",
    }


def probe_agy(quick: bool = False, model: str = "gemini-3.7-flash-low", timeout: float = 30.0) -> dict:
    """Probe AGY CLI availability and test free-tier health."""
    bin_path = find_executable("agy")
    if not bin_path:
        return {
            "lane": "agy",
            "status": "DOWN",
            "path": "NOT_FOUND",
            "version": "unknown",
            "latency_s": 0.0,
            "details": "agy binary not found in PATH or standard location",
        }

    # Version check
    ok_v, out_v, err_v, lat_v = run_cmd([bin_path, "--version"], timeout=10)
    if not ok_v:
        return {
            "lane": "agy",
            "status": "DOWN",
            "path": bin_path,
            "version": "error",
            "latency_s": round(lat_v, 4),
            "details": f"Version check failed: {err_v or out_v}",
        }

    version = out_v.splitlines()[0] if out_v else "unknown"

    if quick:
        return {
            "lane": "agy",
            "status": "UP",
            "path": bin_path,
            "version": version,
            "latency_s": round(lat_v, 4),
            "details": "CLI responsive (quick probe, LLM test skipped, live untested)",
            "live": False,
        }

    # Active LLM probe: feel free-tier health
    probe_cmd = [
        bin_path,
        "-p", "reply with: up",
        "--model", model,
        "--output-format", "json",
    ]
    ok_llm, out_llm, err_llm, lat_llm = run_cmd(probe_cmd, timeout=timeout)

    if not ok_llm:
        # If active probe fails, mark DEGRADED if version works, or DOWN if hard fail
        return {
            "lane": "agy",
            "status": "DEGRADED",
            "path": bin_path,
            "version": version,
            "latency_s": round(lat_llm, 4),
            "details": f"LLM probe failed ({model}): {err_llm or out_llm or 'non-zero exit'}",
            "live": False,
        }

    # Parse JSON output
    try:
        data = json.loads(out_llm)
        agy_status = data.get("status", "").upper()
        agy_duration = data.get("duration_seconds", lat_llm)
        resp_text = (data.get("response") or "").strip()

        if agy_status == "SUCCESS" and "up" in resp_text.lower():
            status = "UP" if lat_llm < 15.0 else "DEGRADED"
            details = f"Model: {model}, response: '{resp_text}', api_duration: {agy_duration:.2f}s"
            live = True
        else:
            status = "DEGRADED"
            details = f"Model: {model}, status: {agy_status}, raw_resp: '{resp_text}'"
            live = False
    except Exception as exc:
        status = "DEGRADED"
        details = f"JSON parse note: {exc}, raw output: {out_llm[:100]}"
        live = False

    return {
        "lane": "agy",
        "status": status,
        "path": bin_path,
        "version": version,
        "latency_s": round(lat_llm, 4),
        "details": details,
        "live": live,
    }


def probe_opencode(quick: bool = False, timeout: float = 15.0,
                   live_timeout: float = 120.0,
                   model: str = "opencode/deepseek-v4-flash-free") -> dict:
    """Probe OpenCode CLI availability AND live server health.

    --version only proves the CLI starts. The free-lane server can fail while
    the CLI is fine, so full mode sends one tiny PONG run through stdin.
    A lane is only recommended when its server actually answers.
    """
    bin_path = find_executable("opencode")
    if not bin_path:
        return {
            "lane": "opencode",
            "status": "DOWN",
            "path": "NOT_FOUND",
            "version": "unknown",
            "latency_s": 0.0,
            "details": "opencode binary not found in PATH or standard location",
            "live": False,
        }

    ok_v, out_v, err_v, lat_v = run_cmd([bin_path, "--version"], timeout=timeout)
    if not ok_v:
        return {
            "lane": "opencode",
            "status": "DOWN",
            "path": bin_path,
            "version": "error",
            "latency_s": round(lat_v, 4),
            "details": f"Version check failed: {err_v or out_v}",
            "live": False,
        }

    version = out_v.splitlines()[0] if out_v else "unknown"
    if quick:
        return {
            "lane": "opencode",
            "status": "UP",
            "path": bin_path,
            "version": version,
            "latency_s": round(lat_v, 4),
            "details": "OpenCode CLI responsive (quick probe, server untested)",
            "live": False,
        }

    # Live server test: one tiny run. Burns one small call to know the truth.
    ok_live, out_live, err_live, lat_live = run_cmd(
        [bin_path, "run", "--format", "json", "--yolo", "--model", model],
        input_text="Reply with exactly: PONG",
        timeout=live_timeout,
    )
    if '"type":"error"' in out_live.replace(" ", "") or '"type": "error"' in out_live:
        return {
            "lane": "opencode",
            "status": "DOWN",
            "path": bin_path,
            "version": version,
            "latency_s": round(lat_live, 4),
            "details": f"CLI up but SERVER FAILING ({model}): "
                       f"{(err_live or out_live)[-160:]}",
            "live": False,
        }
    if ok_live and "PONG" in out_live:
        status = "UP" if lat_live < 90.0 else "DEGRADED"
        return {
            "lane": "opencode",
            "status": status,
            "path": bin_path,
            "version": version,
            "latency_s": round(lat_live, 4),
            "details": f"Live server answered PONG ({model})",
            "live": True,
        }
    return {
        "lane": "opencode",
        "status": "DEGRADED",
        "path": bin_path,
        "version": version,
        "latency_s": round(lat_live, 4),
        "details": f"Live probe unclear ({model}): {(err_live or out_live)[-160:]}",
        "live": False,
    }


def recommend_execution_plan(lanes: dict) -> dict:
    """Recommend executor, manager, and auditor roles based on probe statuses.

    A lane only earns a seat when its server ANSWERED (live=True). A CLI that
    starts but whose server fails sends work into a hole — agy takes those
    seats instead.
    """
    agy = lanes.get("agy", {})
    op = lanes.get("opencode", {})
    agy_status = agy.get("status", "DOWN")
    op_live = op.get("status", "DOWN") == "UP" and bool(op.get("live"))

    if agy_status == "UP":
        executor = "agy (gemini-3.8-flash-high)"
    elif agy_status == "DEGRADED":
        executor = "agy (gemini-3.7-flash-low) [DEGRADED FALLBACK]"
    elif op_live:
        executor = "opencode (opencode/deepseek-v4-flash-free) [FALLBACK]"
    else:
        executor = "NONE (All executor lanes DOWN)"

    if op_live:
        manager = "opencode (opencode/deepseek-v4-flash-free)"
        auditor = "opencode (opencode/deepseek-v4-flash-free)"
    elif agy_status in ("UP", "DEGRADED"):
        manager = "agy (gemini-3.8-flash-high)"
        auditor = "agy (gemini-3.8-flash-high)"
    else:
        manager = "NONE (All manager lanes DOWN)"
        auditor = "NONE (All auditor lanes DOWN)"

    return {
        "executor": executor,
        "manager": manager,
        "auditor": auditor,
    }


def render_report(lanes: dict, recs: dict, quick: bool = False) -> str:
    """Format structured status report with butterfly marks."""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_str = "QUICK" if quick else "FULL"
    lines = [
        f"🦋 X.O.L.A. Scout — Lane Triage Report [{ts}] ({mode_str}) 🦋",
        "=" * 68,
    ]

    for name, data in lanes.items():
        st = data.get("status", "DOWN")
        lat = data.get("latency_s", 0.0)
        ver = data.get("version", "unknown")
        det = data.get("details", "")
        
        status_tag = f"[{st:^8}]"
        lines.append(f"{status_tag} {name:<10} | ver: {ver:<14} | lat: {lat:6.2f}s | {det}")

    lines.append("-" * 68)
    lines.append("🦋 Recommended Execution Topology:")
    lines.append(f"   • Executor : {recs['executor']}")
    lines.append(f"   • Manager  : {recs['manager']}")
    lines.append(f"   • Auditor  : {recs['auditor']}")
    lines.append("=" * 68)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="xola-scout — Fast triage prober for X.O.L.A. free-tier lanes 🦋",
        epilog="Usage: python scout.py [--quick] [--json] [--timeout SECONDS]",
    )
    parser.add_argument("--quick", action="store_true", help="Probe CLI versions only, skipping LLM test")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--model", default="gemini-3.7-flash-low", help="Model for AGY health probe")
    parser.add_argument("--timeout", type=float, default=30.0, help="Timeout in seconds for LLM probe")
    parser.add_argument("--live-timeout", type=float, default=120.0,
                        help="Timeout for the opencode live server test")
    args = parser.parse_args()

    # Execute all probes
    py_info = probe_python()
    op_info = probe_opencode(quick=args.quick, timeout=min(15.0, args.timeout),
                             live_timeout=args.live_timeout)
    agy_info = probe_agy(quick=args.quick, model=args.model, timeout=args.timeout)

    lanes = {
        "python": py_info,
        "agy": agy_info,
        "opencode": op_info,
    }

    recs = recommend_execution_plan(lanes)

    if args.json:
        payload = {
            "timestamp": datetime.datetime.now().isoformat(),
            "lanes": lanes,
            "recommendations": recs,
            "mark": "🦋",
        }
        print(json.dumps(payload, indent=2))
    else:
        print(render_report(lanes, recs, quick=args.quick))

    # Exit 0 if at least one execution lane and Python are available
    all_down = all(data.get("status") == "DOWN" for data in lanes.values())
    if all_down:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
