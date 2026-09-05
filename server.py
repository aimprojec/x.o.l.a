#!/usr/bin/env python3
"""Usage: python server.py [--port PORT] # X.O.L.A. Mission Control Workbench server 🦋

X.O.L.A. = the partner loop: two free brains, one long horizon.
  brain 1: agy (Antigravity CLI, Gemini, Google login — no key)
  brain 2: opencode + muse-spark (free lane, port 4096 server)
  loop   : LongHorizon-Harness Manage -> Execute -> Audit, agy lane patched in

Stdlib only. Serves the Mission Control workbench + JSON APIs on 127.0.0.1:8101.
State lives in tasks.json, loop/state.json, and memory/ (source of truth). 🦋
"""
import argparse
from tools.runtime.runtime_io import write_json, transaction
import datetime
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import time
import urllib.parse

# Ensure project root is in sys.path for tools package imports
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tools.guard as guard_tool
import tools.memory as memory_tool
import tools.scout as scout_tool
import tools.skills as skills_tool
import jarvis
from jarvis.jarvis import JarvisHarness, get_jarvis_status
from jarvis.sentinel import get_system_health, read_sentinel_log

PORT = 8101
TASKS = os.path.join(ROOT, "tasks.json")
LH_SRC = r"D:\alox\LongHorizon-Harness\src"
WATERMARK = "🦋"
AGY_FALLBACKS = (
    r"C:\Users\user\AppData\Local\agy\bin\agy.cmd",
    r"C:\Users\user\AppData\Local\agy\bin\agy_real.exe",
)


def load_tasks():
    try:
        with open(TASKS, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def save_tasks(tasks):
    write_json(TASKS, tasks)


def brain_status():
    agy = shutil.which("agy") or next(
        (p for p in AGY_FALLBACKS if os.path.isfile(p)), None
    )
    opencode = shutil.which("opencode")
    return {
        "agy": {"binary": agy, "free": True, "model": "gemini-3.8-flash-high"},
        "muse_spark": {
            "binary": opencode,
            "free": True,
            "model": "muse-spark",
            "via": "opencode",
        },
        "mark": WATERMARK,
    }


def lh_status():
    registry = os.path.join(LH_SRC, "lh_harness", "agent_registry.py")
    agy_adapter = os.path.join(LH_SRC, "lh_harness", "adapters", "agy.py")
    agy_lane = False
    try:
        with open(registry, encoding="utf-8") as fh:
            agy_lane = '"agy"' in fh.read() or "'agy'" in fh.read()
    except Exception:
        pass
    return {
        "present": os.path.isdir(LH_SRC),
        "agy_lane": agy_lane and os.path.isfile(agy_adapter),
        "workspace": "D:\\alox",
        "mark": WATERMARK,
    }


def loop_lane_evidence():
    """Who actually answered lately? Reads loop.log tail for CHAIN outcomes.

    --version probes can't see quota walls. The loop's own log can: repeated
    'fell through to opencode/...spark' with no agy success means agy is
    walled and spark is carrying the seats.
    """
    evidence = {"fallthrough": False, "agy_ok": False, "spark_ok": False}
    try:
        with open(os.path.join(ROOT, "loop", "loop.log"),
                  encoding="utf-8", errors="replace") as fh:
            tail = fh.readlines()[-100:]
    except Exception:
        return evidence
    for line in tail:
        if "fell through to opencode/" in line:
            evidence["fallthrough"] = True
        match = re.search(r"via=(opencode/\S+|agy\S*)", line)
        if match:
            via = match.group(1)
            if via.startswith("agy") and "ok=True" in line:
                evidence["agy_ok"] = True
            if "spark" in via and "ok=True" in line:
                evidence["spark_ok"] = True
    return evidence


# =====================================================================
# API Response TTL Cache (dashboard poll accelerator) 🦋
# =====================================================================

_API_CACHE: dict = {}


def _cached_json(key: str, ttl_s: float, producer):
    """Serve a cached API payload while fresh; recompute once per TTL window.

    The Mission Control dashboard polls heavy endpoints every few seconds;
    this turns repeated sub-second recomputes into dictionary lookups.
    Thread-safety note: ThreadingHTTPServer may race benignly — worst case
    two threads compute the same payload once. 🦋
    """
    now = time.time()
    hit = _API_CACHE.get(key)
    if hit is not None and (now - hit["t"]) <= ttl_s:
        out = dict(hit["data"])
        out["cache"] = {"hit": True, "age_s": round(now - hit["t"], 3), "ttl_s": ttl_s}
        return out
    data = producer()
    _API_CACHE[key] = {"t": now, "data": data}
    out = dict(data)
    out["cache"] = {"hit": False, "age_s": 0.0, "ttl_s": ttl_s}
    return out


def scout_status(quick: bool = True):
    try:
        py_info = scout_tool.probe_python()
        agy_info = scout_tool.probe_agy(quick=quick)
        op_info = scout_tool.probe_opencode(quick=quick)
        lanes = {
            "python": py_info,
            "agy": agy_info,
            "opencode": op_info,
        }
        recs = scout_tool.recommend_execution_plan(lanes)
        # Truth overlay: --version can't see quota walls, the loop log can.
        evidence = loop_lane_evidence()
        if evidence["fallthrough"] and not evidence["agy_ok"] and evidence["spark_ok"]:
            agy_info["details"] = (agy_info.get("details", "")
                                   + " | QUOTA-WALLED (loop falling through to spark)")
            spark = "opencode/opencode/muse-spark-1.3-contributor-free"
            recs = {"executor": spark, "manager": spark, "auditor": spark,
                    "note": "board overruled by loop evidence: agy walled, spark carrying"}
        return {
            "status": "ok",
            "timestamp": datetime.datetime.now().isoformat(),
            "lanes": lanes,
            "recommendations": recs,
            "loop_evidence": evidence,
            "quick": quick,
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }


def guard_status():
    try:
        return guard_tool.audit(ROOT, strict=False, fix=False, smoke=False)
    except Exception as exc:
        return {
            "auditor": "guard",
            "target": ROOT,
            "verdict": "ERROR",
            "error": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }


def memory_status():
    mem_dir = os.path.join(ROOT, "memory")
    loop_dir = os.path.join(ROOT, "loop")
    try:
        history = memory_tool.parse_all_memory(mem_dir)
        stats = memory_tool.compute_stats(mem_dir, loop_dir)
        timeline = memory_tool.generate_timeline(mem_dir, loop_dir)
        return {
            "status": "ok",
            "history": history,
            "stats": stats,
            "timeline": timeline.get("timeline", []),
            "total_records": len(history),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }


def loop_status():
    state_file = os.path.join(ROOT, "loop", "state.json")
    loop_log = os.path.join(ROOT, "loop", "loop.log")
    mission_file = os.path.join(ROOT, "loop", "mission.md")
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as exc:
            state = {"error": str(exc)}
    else:
        state = {"round": 0, "started": 0, "notes": []}

    mission_text = ""
    if os.path.exists(mission_file):
        try:
            with open(mission_file, "r", encoding="utf-8", errors="replace") as f:
                mission_text = f.read()
        except Exception:
            pass

    log_tail = []
    if os.path.exists(loop_log):
        try:
            with open(loop_log, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                log_tail = [line.strip() for line in lines[-35:] if line.strip()]
        except Exception:
            pass

    return {
        "status": "ok",
        "state": state,
        "round": state.get("round", 0),
        "started": state.get("started"),
        "notes": state.get("notes", []),
        "mission_snippet": mission_text[:400] if mission_text else "",
        "log_tail": log_tail,
        "timestamp": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }


def jarvis_status():
    try:
        stat = get_jarvis_status()
        harness = JarvisHarness()

        # Inbox items
        inbox_items = []
        if os.path.exists(harness.inbox_dir):
            for f in sorted(os.listdir(harness.inbox_dir)):
                fpath = os.path.join(harness.inbox_dir, f)
                if os.path.isfile(fpath) and not f.startswith("."):
                    task_obj = harness.parse_task_file(fpath)
                    if task_obj:
                        inbox_items.append(task_obj.to_dict())
                    else:
                        inbox_items.append({"file": f, "path": fpath})

        # Outbox items (recent 20)
        outbox_items = []
        if os.path.exists(harness.outbox_dir):
            for f in sorted(os.listdir(harness.outbox_dir), reverse=True)[:20]:
                fpath = os.path.join(harness.outbox_dir, f)
                if os.path.isfile(fpath) and f.endswith(".json"):
                    try:
                        with open(fpath, "r", encoding="utf-8") as fh:
                            outbox_items.append(json.load(fh))
                    except Exception:
                        outbox_items.append({"file": f})

        # Telemetry tail (recent 20)
        telemetry_tail = []
        if os.path.exists(harness.telemetry_file):
            try:
                with open(harness.telemetry_file, "r", encoding="utf-8") as fh:
                    lines = [l.strip() for l in fh.readlines() if l.strip()]
                    for line in lines[-20:]:
                        try:
                            telemetry_tail.append(json.loads(line))
                        except Exception:
                            pass
            except Exception:
                pass

        # Sentinel log tail
        sentinel_tail = read_sentinel_log(tail_n=15)

        return {
            "status": "ok",
            "jarvis_state": stat,
            "inbox_items": inbox_items,
            "outbox_items": outbox_items,
            "telemetry_tail": telemetry_tail,
            "sentinel_log_tail": sentinel_tail,
            "sentinel_vitals": stat.get("sentinel_health", {}),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }


def lh10_status():
    """Live state of the LH 10-agent parallel loop. 🦋"""
    base = os.path.join(ROOT, "loop", "lh10")
    out = {
        "status": "ok",
        "running": False,
        "wave": 0,
        "agents": {},
        "log_tail": [],
        "timestamp": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }
    try:
        with open(os.path.join(base, "lh10_state.json"), encoding="utf-8") as fh:
            st = json.load(fh)
        out["wave"] = st.get("wave", 0)
        out["agents"] = st.get("done", {})
        out["started"] = st.get("started", 0)
        out["running"] = (time.time() - st.get("started", 0)) < 3600 and st.get("wave", 0) > 0
    except Exception as exc:
        out["state_error"] = str(exc)
    try:
        with open(os.path.join(base, "lh10.log"), encoding="utf-8", errors="replace") as fh:
            out["log_tail"] = fh.readlines()[-15:]
    except Exception:
        pass
    try:
        ob = os.path.join(base, "outbox")
        files = sorted(os.listdir(ob)) if os.path.isdir(ob) else []
        out["outbox_count"] = len(files)
        previews = {}
        for f in files[-10:]:
            try:
                with open(os.path.join(ob, f), encoding="utf-8", errors="replace") as fh:
                    previews[f] = fh.read(600)
            except Exception:
                pass
        out["outbox_previews"] = previews
    except Exception:
        pass
    return out


def skills_status():
    try:
        skills_list = skills_tool.GLOBAL_REGISTRY.list_skills()
        val_res = skills_tool.GLOBAL_REGISTRY.validate_skills()
        return {
            "status": "ok",
            "total": len(skills_list),
            "skills": [s.to_dict() for s in skills_list],
            "validation": val_res,
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Client polled and hung up mid-response (dashboard refresh) — not a server fault. 🦋
            pass

    def do_OPTIONS(self):
        if not self._local_request():
            return
        self.send_response(200)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _local_request(self):
        host = self.headers.get("Host", "")
        parsed = urllib.parse.urlparse("http://" + host)
        if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            self._json(403, {"error": "Local Host required"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin != "http://" + host:
            self._json(403, {"error": "Cross-origin requests rejected"})
            return False
        return True

    def do_GET(self):
        if not self._local_request():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/api/health":
            self._json(200, {"status": "up", "service": "xola", "mark": WATERMARK})
        elif path == "/api/scout":
            quick = qs.get("quick", ["true"])[0].lower() not in ("false", "0", "no")
            self._json(200, _cached_json(f"scout:{quick}", 15.0, lambda: scout_status(quick=quick)))
        elif path == "/api/guard":
            self._json(200, _cached_json("guard", 30.0, guard_status))
        elif path == "/api/memory":
            self._json(200, _cached_json("memory", 20.0, memory_status))
        elif path == "/api/loop":
            self._json(200, loop_status())
        elif path == "/api/brains":
            self._json(200, brain_status())
        elif path == "/api/lh":
            self._json(200, lh_status())
        elif path == "/api/tasks":
            self._json(200, load_tasks())
        elif path == "/api/jarvis":
            self._json(200, _cached_json("jarvis", 5.0, jarvis_status))
        elif path == "/api/skills":
            self._json(200, skills_status())
        elif path == "/api/lh10":
            self._json(200, _cached_json("lh10", 10.0, lh10_status))
        elif path in ("/", "/index.html"):
            self.path = "/index.html"
            super().do_GET()
        elif path == "/lh10.html":
            super().do_GET()
        else:
            self._json(404, {"error": "not found"})

    def do_HEAD(self):
        if not self._local_request():
            return
        if urllib.parse.urlparse(self.path).path not in ("/", "/index.html", "/lh10.html"):
            return self._json(404, {"error": "not found"})
        return super().do_HEAD()

    def do_POST(self):
        if not self._local_request():
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 65536:
                return self._json(413, {"error": "Request body must be 1 to 65536 bytes"})
        except ValueError:
            return self._json(400, {"error": "Invalid Content-Length"})
        if self.headers.get_content_type() != "application/json":
            return self._json(415, {"error": "application/json required"})
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/tasks":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(req, dict):
                    raise ValueError("JSON object required")
            except Exception as exc:
                return self._json(400, {"error": f"bad request: {exc}", "mark": WATERMARK})
            text = str(req.get("task", "")).strip()
            if not text:
                return self._json(400, {"error": "empty task", "mark": WATERMARK})
            tasks = load_tasks()
            task = {
                "id": len(tasks) + 1,
                "task": text[:4000],
                "status": "queued",
                "created_at": datetime.datetime.now().isoformat(),
            }
            tasks.append(task)
            save_tasks(tasks)
            self._json(200, task)
        elif path == "/api/jarvis/send":
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(req, dict):
                    raise ValueError("JSON object required")
            except Exception as exc:
                return self._json(400, {"error": f"bad request: {exc}", "mark": WATERMARK})

            prompt = str(req.get("prompt", req.get("task", req.get("skill", "")))).strip()
            if not prompt:
                return self._json(400, {"error": "empty task prompt or skill", "mark": WATERMARK})

            action_type = str(req.get("action", "skill")).strip()
            args = req.get("args", {})
            if not isinstance(args, dict):
                args = {}

            harness = JarvisHarness()
            task_file = harness.submit_task(prompt_or_skill=prompt, args=args, action=action_type)
            task_id = os.path.splitext(os.path.basename(task_file))[0]

            self._json(200, {
                "status": "SUCCESS",
                "submitted": True,
                "task_id": task_id,
                "task_file": task_file,
                "prompt": prompt,
                "action": action_type,
                "args": args,
                "created_at": datetime.datetime.now().isoformat(),
                "mark": WATERMARK,
            })
        elif path == "/api/jarvis/chat":
            # Conversational shell: immediate JARVIS-style reply, not a queued task.
            # Mutations are proposed, never executed — same policy as the CLI shell. 🦋
            try:
                length = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(req, dict):
                    raise ValueError("JSON object required")
            except Exception as exc:
                return self._json(400, {"error": f"bad request: {exc}", "mark": WATERMARK})
            try:
                from jarvis.conversation import handle_chat_request
            except Exception as exc:
                return self._json(500, {"error": f"chat engine unavailable: {exc}",
                                        "mark": WATERMARK})
            code, payload = handle_chat_request(req)
            self._json(code, payload)
        else:
            self._json(404, {"error": "not found", "mark": WATERMARK})


def main():
    parser = argparse.ArgumentParser(
        description="xola-server — Lean Mission Control Workbench Server 🦋",
        epilog="Usage: python server.py [--port PORT]",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=PORT,
        help=f"Port to listen on (default: {PORT})",
    )
    args = parser.parse_args()

    os.chdir(ROOT)
    if not os.path.exists(TASKS):
        save_tasks([])
    socketserver.TCPServer.allow_reuse_address = True  # survive fast restarts 🦋
    socketserver.TCPServer.daemon_threads = True
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as httpd:
        print(f"X.O.L.A. Mission Control listening on http://127.0.0.1:{args.port}/ 🦋")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down X.O.L.A. Mission Control Server 🦋")


if __name__ == "__main__":
    main()
