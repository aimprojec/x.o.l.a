#!/usr/bin/env python3
"""xola-router — deterministic intent first, LLM only on miss. 🦋

Manual pages 3-5: routing is deterministic pattern match; the task state
machine is PENDING -> DOING -> VERIFY -> DONE/KILL; verification is a
one-shot falsifiable command; idempotency keys stop double-runs.

Usage:
  python router.py --route "audit the tools dir"     # prints PLAN JSON
  python router.py --run "audit the tools dir"       # executes bounded step
  python router.py --verify <id>                      # one-shot verify
"""
import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loop", "queue")
os.makedirs(STATE_DIR, exist_ok=True)


def _ask_lane(prompt: str, timeout: float = 300.0, lane: str = "router"):
    """Dynamic isolated loader for loop lane queries keeping module stdlib-clean. 🦋"""
    try:
        loop_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loop")
        if loop_dir not in sys.path:
            sys.path.insert(0, loop_dir)
        loop_mod = importlib.import_module("xola_loop")
        return loop_mod.ask_lane(prompt, timeout, lane=lane)
    except Exception as exc:
        return False, f'{{"error": "{exc}"}}', "none"

# Deterministic routes: pattern -> (skill/tool, tier, bounded action). LLM never
# sees traffic these patterns already cover.
ROUTES = [
    (("scout", "probe", "lane", "health", "status"), "tools.scout", "GREEN"),
    (("audit", "guard", "review", "kill slop"), "tools.guard", "YELLOW"),
    (("remember", "memory", "recall", "distill"), "tools.memory", "GREEN"),
    (("build", "scaffold", "forge", "implement"), "tools.builder", "YELLOW"),
    (("brief", "recap", "celebrate", "morning"), "voices.spark", "GREEN"),
    (("stress", "prove", "redteam", "recheck"), "voices.furnace", "YELLOW"),
    (("dissect", "measure", "benchmark", "compare", "report"), "voices.lens", "GREEN"),
    (("goodnight", "devotion", "check-in"), "voices.ember", "GREEN"),
    (("jarvis", "service", "sentinel", "hands", "voice"), "jarvis", "YELLOW"),
    (("task", "queue", "mission", "workbench"), "server", "GREEN"),
]


def route(text):
    """Deterministic first. Returns (target, tier) or (None, None) on miss."""
    low = text.lower()
    for keywords, target, tier in ROUTES:
        if any(k in low for k in keywords):
            return target, tier
    return None, None


def idem_key(text):
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def task_path(key):
    return os.path.join(STATE_DIR, f"{key}.json")


def enqueue(text):
    """PENDING. Idempotent: same text = same key, never doubled."""
    key = idem_key(text)
    path = task_path(key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    target, tier = route(text)
    task = {"id": key, "text": text, "target": target, "tier": tier,
            "state": "PENDING", "created": time.time(), "attempts": 0,
            "verify": "", "mark": WATERMARK}
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(task, fh, indent=2)
    return task


def advance(key, timeout=300):
    """DOING -> VERIFY -> DONE/KILL in one bounded move."""
    path = task_path(key)
    with open(path, encoding="utf-8") as fh:
        task = json.load(fh)
    if task["state"] == "DONE":
        return task  # closed stays closed
    task["state"] = "DOING"
    task["attempts"] += 1
    target = task["target"]
    if target is None:
        # LLM only on miss, and only to pick the target + falsifiable verify.
        ok, reply, via = _ask_lane(
            f"Route this task to exactly one of: tools.scout, tools.guard, "
            f"tools.memory, tools.builder, voices.spark, voices.furnace, "
            f"voices.lens, voices.ember, jarvis, server. Reply JSON only: "
            f'{{\"target\": \"...\", \"verify\": \"<one falsifiable shell check>\"}}. '
            f"Task: {task['text'][:2000]}",
            timeout, lane="router")
        try:
            data = json.loads(reply[reply.index("{"):reply.rindex("}") + 1])
            task["target"] = data.get("target")
            task["verify"] = str(data.get("verify", ""))[:500]
        except Exception:
            task["target"] = "voices.lens"
    else:
        task["verify"] = task["verify"] or f"test -f {task['id']}"
    task["state"] = "VERIFY"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(task, fh, indent=2)
    return task


def verify(key):
    """One-shot falsifiable verify. Pass -> DONE, fail -> KILL. No retries."""
    path = task_path(key)
    with open(path, encoding="utf-8") as fh:
        task = json.load(fh)
    check = task.get("verify", "")
    passed = False
    if check:
        try:
            proc = subprocess.run(check, shell=True, capture_output=True,
                                  timeout=120, cwd=r"D:\alox",
                                  creationflags=0x08000000)
            passed = proc.returncode == 0
        except Exception:
            passed = False
    task["state"] = "DONE" if passed else "KILL"
    task["verified_at"] = time.time()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(task, fh, indent=2)
    return task


def main():
    parser = argparse.ArgumentParser(description="xola-router — deterministic intent first " + WATERMARK)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--route", default="", help="Print routing PLAN JSON, no execution")
    group.add_argument("--run", default="", help="Enqueue + advance one bounded step")
    group.add_argument("--verify", default="", help="One-shot verify of task id")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()
    if args.route:
        target, tier = route(args.route)
        print(json.dumps({"target": target, "tier": tier, "deterministic": target is not None,
                          "id": idem_key(args.route), "mark": WATERMARK}, indent=2))
        sys.exit(0)
    elif args.run:
        task = enqueue(args.run)
        task = advance(task["id"], args.timeout)
        print(json.dumps(task, indent=2)[:2000])
        sys.exit(0 if task.get("state") in ("VERIFY", "DONE") else 1)
    elif args.verify:
        v = verify(args.verify)
        print(json.dumps(v, indent=2)[:2000])
        sys.exit(0 if v.get("state") == "DONE" else 1)
    sys.exit(0)


if __name__ == "__main__":
    main()
