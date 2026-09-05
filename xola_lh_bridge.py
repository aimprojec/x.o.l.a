#!/usr/bin/env python3
"""Usage: python xola_lh_bridge.py [--go] "<task>" # X.O.L.A. x LongHorizon bridge 🦋

Roles (all free, no API keys):
  manager  : opencode / deepseek-v4-flash-free  (plans, cheap, fast)
  executor : agy / gemini-3.8-flash-high        (does, Google login lane)
  auditor  : opencode / deepseek-v4-flash-free  (checks, blocks slop)

Usage:
  python xola_lh_bridge.py "build ..."        # dry-run: print the command
  python xola_lh_bridge.py --go "build ..."   # execute the long run 🦋
"""
import os
import subprocess
import sys

LH_SRC = r"D:\alox\LongHorizon-Harness\src"
WORKSPACE = r"D:\alox"

MANAGER = "opencode:opencode/deepseek-v4-flash-free"
EXECUTOR = "agy:gemini-3.8-flash-high"
AUDITOR = "opencode:opencode/deepseek-v4-flash-free"


def build_command(task):
    def split(spec):
        agent, _, model = spec.partition(":")
        return agent, model

    m_agent, m_model = split(MANAGER)
    e_agent, e_model = split(EXECUTOR)
    a_agent, a_model = split(AUDITOR)
    return [
        sys.executable, "-m", "lh_harness", "run",
        "--manager-agent", m_agent, "--manager-model", m_model,
        "--executor-agent", e_agent, "--executor-model", e_model,
        "--auditor-agent", a_agent, "--auditor-model", a_model,
        "--max-rounds", "25",
        task,
    ]


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Usage: python xola_lh_bridge.py [--go] \"<task>\" # 🦋")
        sys.exit(0)
    args = [a for a in sys.argv[1:] if a != "--go"]
    go = "--go" in sys.argv[1:]
    if not args:
        print("usage: xola_lh_bridge.py [--go] \"<task>\" 🦋")
        raise SystemExit(2)
    task = " ".join(args)
    env = dict(os.environ)
    env["PYTHONPATH"] = LH_SRC + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONUTF8"] = "1"
    cmd = build_command(task)
    print("manager :", MANAGER)
    print("executor:", EXECUTOR)
    print("auditor :", AUDITOR)
    print("cmd     :", " ".join(cmd), "🦋")
    if not go:
        print("(dry-run — pass --go to execute)")
        return
    proc = subprocess.run(cmd, cwd=WORKSPACE, env=env)
    raise SystemExit(proc.returncode)


if __name__ == "__main__":
    main()

