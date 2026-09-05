#!/usr/bin/env python3
"""Usage: python cli.py [status|scout|build|guard|memory|skills|test|server|jarvis] ... # X.O.L.A. Unified Tool Suite CLI 🦋

Unified command-line interface for the entire X.O.L.A. autonomous engineering system:
  • status : Holistic system health, lane availability, tool standards, and loop overview
  • scout  : Fast triage prober for free LLM and execution lanes (agy, opencode, python)
  • build  : Tool forge, AST inspector, template scaffolder, and standards validator
  • guard  : Red-team code reviewer, secret scanner, dependency auditor, and slop killer
  • memory : Long-horizon round distiller, query engine, timeline generator, and analytics
  • skills : Dynamic Skills Registry, keyword/prefix matching, and execution engine
  • test   : Master automated test suite runner with per-subsystem metric reporting
  • server : Mission Control Workbench HTTP server & REST API service
  • jarvis : Jarvis Autonomous Harness, inbox/outbox queue engine, and Sentinel vitals

Pure Python standard library only. 🦋
"""

import argparse
import datetime
import io
import json
import os
import shutil
import socketserver
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
VERSION = "1.0.0"

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Import internal XOLA modules
import tools.scout as scout_tool
import tools.builder as builder_tool
import tools.guard as guard_tool
import tools.memory as memory_tool
import tools.skills as skills_tool
import server as server_mod
import jarvis
from jarvis.jarvis import (
    JarvisHarness,
    get_jarvis_status,
    render_jarvis_status,
    run_smoke_test as run_jarvis_smoke_test,
    run_jarvis_loop,
)
from jarvis.sentinel import (
    Sentinel,
    get_system_health,
    run_sentinel_once,
    read_sentinel_log,
    render_sentinel_report,
    execute_scheduled_nudges,
    run_nudge_by_name,
)
from jarvis.brain import think_and_execute as jarvis_think_and_execute
from jarvis.voice import speak as jarvis_speak
from jarvis.hands import OSHands


# =====================================================================
# 1) Subcommand: 'status' (Holistic System Overview)
# =====================================================================

def get_system_status(quick: bool = True, target_dir: Optional[str] = None) -> Dict[str, Any]:
    """Gather holistic system status across scout, builder, guard, memory, and server."""
    t0 = time.perf_counter()
    target_root = target_dir or ROOT_DIR

    # 1. Scout status
    py_info = scout_tool.probe_python()
    agy_info = scout_tool.probe_agy(quick=quick)
    op_info = scout_tool.probe_opencode(quick=quick)
    lanes = {
        "python": py_info,
        "agy": agy_info,
        "opencode": op_info,
    }
    recs = scout_tool.recommend_execution_plan(lanes)

    # 2. Builder status
    tools_path = os.path.join(target_root, "tools")
    build_val = builder_tool.validate_all_tools(tools_dir=tools_path, run_test=False)

    # 3. Guard audit status
    guard_res = guard_tool.audit(target=target_root, strict=False, fix=False, smoke=False)

    # 4. Memory stats
    mem_path = os.path.join(target_root, "memory")
    loop_path = os.path.join(target_root, "loop")
    mem_stats = memory_tool.compute_stats(memory_dir=mem_path, loop_dir=loop_path)

    # 5. Skills status
    skills_val = skills_tool.GLOBAL_REGISTRY.validate_skills()
    skills_count = len(skills_tool.GLOBAL_REGISTRY)

    # 6. Server & Loop state
    loop_info = server_mod.loop_status()
    tasks_list = server_mod.load_tasks()

    # 7. Jarvis & Sentinel status
    jarvis_stat = get_jarvis_status()

    # Determine overall system health
    scout_ok = any(l.get("status") in ("UP", "DEGRADED") for l in lanes.values())
    builder_ok = build_val.get("all_passed", False)
    guard_ok = guard_res.get("verdict") in ("PASS", "WARN")
    jarvis_ok = jarvis_stat.get("status") != "CRITICAL"

    if scout_ok and builder_ok and guard_ok and jarvis_ok:
        overall_status = "HEALTHY"
    elif not scout_ok or guard_res.get("verdict") == "KILL" or not jarvis_ok:
        overall_status = "CRITICAL"
    else:
        overall_status = "DEGRADED"

    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "command": "status",
        "status": overall_status,
        "timestamp": datetime.datetime.now().isoformat(),
        "latency_s": elapsed,
        "scout": {
            "lanes": lanes,
            "recommendations": recs,
        },
        "builder": {
            "tools_count": build_val.get("total", 0),
            "passed_count": build_val.get("passed_count", 0),
            "failed_count": build_val.get("failed_count", 0),
            "all_passed": build_val.get("all_passed", False),
        },
        "guard": {
            "verdict": guard_res.get("verdict", "UNKNOWN"),
            "files_scanned": guard_res.get("summary", {}).get("files_scanned", 0),
            "findings_count": guard_res.get("summary", {}).get("total_findings", 0),
            "critical_count": guard_res.get("summary", {}).get("critical_count", 0),
            "warning_count": guard_res.get("summary", {}).get("warning_count", 0),
        },
        "memory": {
            "total_rounds": mem_stats.get("total_rounds", 0),
            "pass_rate_pct": mem_stats.get("verdicts", {}).get("pass_rate_pct", 0.0),
            "avg_latency_s": mem_stats.get("latency_stats", {}).get("avg_round_duration_s", 0.0),
        },
        "skills": {
            "total_skills": skills_count,
            "all_passed": skills_val.get("all_passed", False),
            "passed_count": skills_val.get("passed_count", 0),
            "failed_count": skills_val.get("failed_count", 0),
        },
        "loop": {
            "round": loop_info.get("round", 0),
            "started": loop_info.get("started"),
            "notes_count": len(loop_info.get("notes", [])),
        },
        "tasks": {
            "total_tasks": len(tasks_list),
            "queued_tasks": sum(1 for t in tasks_list if t.get("status") == "queued"),
        },
        "jarvis": {
            "status": jarvis_stat.get("status", "UNKNOWN"),
            "inbox_queue_count": jarvis_stat.get("inbox_queue_count", 0),
            "outbox_total_count": jarvis_stat.get("outbox_total_count", 0),
            "tasks_processed_total": jarvis_stat.get("tasks_processed_total", 0),
            "tasks_succeeded": jarvis_stat.get("tasks_succeeded", 0),
            "tasks_failed": jarvis_stat.get("tasks_failed", 0),
            "last_task_id": jarvis_stat.get("last_task_id"),
            "last_task_time": jarvis_stat.get("last_task_time"),
            "sentinel": {
                "status": jarvis_stat.get("sentinel_health", {}).get("status", "UNKNOWN"),
                "cpu_pct": jarvis_stat.get("sentinel_health", {}).get("cpu", {}).get("used_percent", 0.0),
                "ram_pct": jarvis_stat.get("sentinel_health", {}).get("ram", {}).get("used_percent", 0.0),
                "disk_pct": jarvis_stat.get("sentinel_health", {}).get("disk", {}).get("max_used_percent", 0.0),
            },
        },
        "mark": WATERMARK,
    }


def render_status_report(res: Dict[str, Any], verbose: bool = False) -> str:
    """Render formatted status report banner with butterfly markers."""
    s = res.get("status", "UNKNOWN")
    ts = res.get("timestamp", "")
    scout_data = res.get("scout", {})
    lanes = scout_data.get("lanes", {})
    recs = scout_data.get("recommendations", {})
    b = res.get("builder", {})
    g = res.get("guard", {})
    m = res.get("memory", {})
    sk = res.get("skills", {})
    lp = res.get("loop", {})
    tk = res.get("tasks", {})
    j = res.get("jarvis", {})
    j_sent = j.get("sentinel", {})

    status_tag = f"[{s}]"
    lines = [
        f"🦋 X.O.L.A. System Status Overview [{ts}] {status_tag} 🦋",
        "=" * 74,
        "1. Free Execution Lanes (Scout):",
    ]

    for name, l_info in lanes.items():
        st = f"[{l_info.get('status', 'DOWN'):^8}]"
        lat = l_info.get("latency_s", 0.0)
        ver = l_info.get("version", "unknown")
        lines.append(f"   {st} {name:<10} | ver: {ver:<14} | lat: {lat:6.3f}s")

    lines.append(f"   Topology   : Executor: {recs.get('executor', 'NONE')}")
    lines.append(f"                Manager : {recs.get('manager', 'NONE')}")
    lines.append(f"                Auditor : {recs.get('auditor', 'NONE')}")
    lines.append("-" * 74)

    lines.append("2. Tooling & Standards (Builder):")
    b_stat = "ALL PASSED" if b.get("all_passed") else "FAILURES DETECTED"
    lines.append(f"   • Registered Tools : {b.get('tools_count', 0)} ({b.get('passed_count', 0)} passed, {b.get('failed_count', 0)} failed) — [{b_stat}]")
    lines.append("-" * 74)

    lines.append("3. Red-Team Integrity (Guard):")
    g_verdict = g.get("verdict", "UNKNOWN")
    lines.append(f"   • Audit Verdict    : [{g_verdict:^6}] ({g.get('findings_count', 0)} findings: {g.get('critical_count', 0)} critical, {g.get('warning_count', 0)} warn)")
    lines.append(f"   • Files Audited    : {g.get('files_scanned', 0)} files scanned across project root")
    lines.append("-" * 74)

    lines.append("4. Memory & Long Horizon (Memory):")
    lines.append(f"   • Rounds Recorded  : {m.get('total_rounds', 0)} rounds ({m.get('pass_rate_pct', 0.0):.1f}% pass rate)")
    lines.append(f"   • Avg Latency      : {m.get('avg_latency_s', 0.0):.2f}s per loop execution")
    lines.append("-" * 74)

    lines.append("5. Dynamic Skills Engine (Skills):")
    lines.append(f"   • Registered Skills: {sk.get('total_skills', 0)} ({sk.get('passed_count', 0)} validated clean)")
    lines.append("-" * 74)

    lines.append("6. Mission Control & Loop State (Server):")
    lines.append(f"   • Loop Progress    : Round {lp.get('round', 0)} active ({lp.get('notes_count', 0)} notes)")
    lines.append(f"   • Workbench Tasks  : {tk.get('total_tasks', 0)} total ({tk.get('queued_tasks', 0)} queued)")
    lines.append("-" * 74)

    lines.append("7. Jarvis Autonomous Harness & Sentinel:")
    lines.append(
        f"   • Jarvis State     : [{j.get('status', 'UNKNOWN')}] (Inbox: {j.get('inbox_queue_count', 0)} pending, "
        f"Outbox: {j.get('outbox_total_count', 0)} responses, Processed: {j.get('tasks_processed_total', 0)})"
    )
    lines.append(
        f"   • Sentinel Vitals  : State: [{j_sent.get('status', 'UNKNOWN')}] | "
        f"CPU: {j_sent.get('cpu_pct', 0.0):.1f}% | "
        f"RAM: {j_sent.get('ram_pct', 0.0):.1f}% | "
        f"Disk: {j_sent.get('disk_pct', 0.0):.1f}%"
    )
    lines.append("=" * 74)

    return "\n".join(lines)


# =====================================================================
# 2) Subcommand: 'scout' (Triage Prober)
# =====================================================================

def execute_scout_cmd(
    quick: bool = False,
    model: str = "gemini-3.7-flash-low",
    timeout: float = 30.0,
    live_timeout: float = 120.0,
    json_mode: bool = False,
) -> int:
    """Execute scout subcommand and return status code."""
    py_info = scout_tool.probe_python()
    op_info = scout_tool.probe_opencode(
        quick=quick,
        timeout=min(15.0, timeout),
        live_timeout=live_timeout,
    )
    agy_info = scout_tool.probe_agy(quick=quick, model=model, timeout=timeout)

    lanes = {
        "python": py_info,
        "agy": agy_info,
        "opencode": op_info,
    }
    recs = scout_tool.recommend_execution_plan(lanes)

    if json_mode:
        payload = {
            "command": "scout",
            "timestamp": datetime.datetime.now().isoformat(),
            "lanes": lanes,
            "recommendations": recs,
            "quick": quick,
            "mark": WATERMARK,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(scout_tool.render_report(lanes, recs, quick=quick))

    all_down = all(data.get("status") == "DOWN" for data in lanes.values())
    return 1 if all_down else 0


# =====================================================================
# 3) Subcommand: 'build' (Tool Forge & Validator)
# =====================================================================

def execute_build_cmd(
    action: str = "validate",
    target: Optional[str] = None,
    scaffold_name: Optional[str] = None,
    desc: str = "",
    template: str = "tool",
    force: bool = False,
    no_run_test: bool = False,
    tools_dir: Optional[str] = None,
    json_mode: bool = False,
) -> int:
    """Execute builder subcommand operations."""
    tdir = tools_dir or os.path.join(ROOT_DIR, "tools")

    if action == "scaffold" or scaffold_name:
        name_to_use = scaffold_name or target or "new_tool"
        res = builder_tool.scaffold_tool(
            name=name_to_use,
            desc=desc,
            template_type=template,
            tools_dir=tdir,
            force=force,
        )
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(builder_tool.render_scaffold_report(res))
        return 0 if res.get("status") == "SUCCESS" else 1

    elif action == "inspect":
        res = builder_tool.inspect_tools(target=target, tools_dir=tdir)
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(builder_tool.render_inspect_report(res))
        return 0

    elif action == "list":
        res = builder_tool.inspect_tools(target=None, tools_dir=tdir)
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(builder_tool.render_inspect_report(res))
        return 0

    else:  # validate
        run_smoke = not no_run_test
        res = builder_tool.validate_all_tools(target=target, tools_dir=tdir, run_test=run_smoke)
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(builder_tool.render_validate_report(res))
        return 0 if res.get("all_passed") else 1


# =====================================================================
# 4) Subcommand: 'guard' (Red-Team Auditor)
# =====================================================================

def execute_guard_cmd(
    target: str = ".",
    strict: bool = False,
    fix: bool = False,
    smoke: bool = False,
    verbose: bool = False,
    json_mode: bool = False,
) -> int:
    """Execute red-team guard audit."""
    target_path = target if os.path.isabs(target) else os.path.abspath(target)
    res = guard_tool.audit(
        target=target_path,
        strict=strict,
        fix=fix,
        smoke=smoke,
        verbose=verbose,
    )

    if json_mode:
        print(json.dumps(res, indent=2))
    else:
        print(guard_tool.render_report(res, verbose=verbose))

    return 1 if res.get("verdict") == "KILL" else 0


# =====================================================================
# 5) Subcommand: 'memory' (Memory & Distillation Engine)
# =====================================================================

def execute_memory_cmd(
    append: bool = False,
    distill: bool = False,
    query: Optional[str] = None,
    timeline: bool = False,
    stats: bool = False,
    round_idx: Optional[int] = None,
    step: str = "",
    evidence: str = "",
    verdict: str = "PASS",
    lessons: str = "",
    next_step: str = "",
    tags: str = "",
    lane: Optional[str] = None,
    latency: Optional[float] = None,
    input_path: Optional[str] = None,
    output_path: Optional[str] = None,
    memory_dir: Optional[str] = None,
    loop_dir: Optional[str] = None,
    target_date: Optional[str] = None,
    limit: Optional[int] = None,
    json_mode: bool = False,
) -> int:
    """Execute memory engine actions."""
    mem_dir = memory_dir or os.path.join(ROOT_DIR, "memory")
    lp_dir = loop_dir or os.path.join(ROOT_DIR, "loop")

    if append:
        tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        res = memory_tool.append_round(
            round_idx=round_idx,
            step=step,
            evidence=evidence,
            verdict=verdict,
            lessons=lessons,
            next_step=next_step,
            tags=tags_list,
            lane=lane,
            latency=latency,
            memory_dir=mem_dir,
            target_date=target_date,
            output_path=output_path,
        )
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(memory_tool.render_append_report(res))
        return 0 if res.get("status") == "SUCCESS" else 1

    elif distill:
        res = memory_tool.distill_logs(
            input_path=input_path,
            output_path=output_path,
            round_limit=limit,
        )
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(memory_tool.render_distill_report(res))
        return 0 if res.get("status") == "SUCCESS" else 1

    elif query is not None:
        pattern_to_search = query or step or ""
        res = memory_tool.query_memory(
            pattern=pattern_to_search,
            verdict_filter=verdict if verdict != "PASS" or "--verdict" in sys.argv or "-v" in sys.argv else None,
            tag_filter=tags if tags else None,
            date_filter=target_date,
            memory_dir=mem_dir,
        )
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(memory_tool.render_query_report(res))
        return 0

    elif timeline:
        res = memory_tool.generate_timeline(
            memory_dir=mem_dir,
            loop_dir=lp_dir,
            date_filter=target_date,
        )
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(memory_tool.render_timeline_report(res))
        return 0

    else:  # stats (default)
        res = memory_tool.compute_stats(
            memory_dir=mem_dir,
            loop_dir=lp_dir,
        )
        if json_mode:
            print(json.dumps(res, indent=2))
        else:
            print(memory_tool.render_stats_report(res))
        return 0


# =====================================================================
# 6) Subcommand: 'skills' (Dynamic Skills Registry & Engine)
# =====================================================================

def execute_skills_cmd(
    action: str = "list",
    name: Optional[str] = None,
    args_json: str = "{}",
    query: Optional[str] = None,
    validate: bool = False,
    category: Optional[str] = None,
    tier: Optional[str] = None,
    auto_approve: bool = False,
    json_mode: bool = False,
) -> int:
    """Execute dynamic skills registry operations."""
    if validate or action == "validate":
        val_res = skills_tool.GLOBAL_REGISTRY.validate_skills()
        if json_mode:
            print(json.dumps(val_res, indent=2))
        else:
            print(skills_tool.render_validation_report(val_res))
        return 0 if val_res.get("all_passed") else 1

    elif name and action == "info":
        skill = skills_tool.GLOBAL_REGISTRY.get(name) or skills_tool.GLOBAL_REGISTRY.find_matching_skill(name)
        if not skill:
            err_payload = {
                "status": "ERROR",
                "error": f"Skill '{name}' not found in registry",
                "mark": WATERMARK,
            }
            if json_mode:
                print(json.dumps(err_payload, indent=2))
            else:
                print(f"🦋 ERROR: Skill '{name}' not found in registry", file=sys.stderr)
            return 1

        if json_mode:
            print(json.dumps(skill.to_dict(), indent=2))
        else:
            print(skills_tool.render_skill_info(skill))
        return 0

    elif query:
        skill = skills_tool.GLOBAL_REGISTRY.find_matching_skill(query)
        if not skill:
            err_payload = {
                "status": "NO_MATCH",
                "query": query,
                "error": f"No skill found matching query '{query}'",
                "mark": WATERMARK,
            }
            if json_mode:
                print(json.dumps(err_payload, indent=2))
            else:
                print(f"🦋 No skill found matching query '{query}'", file=sys.stderr)
            return 1

        if json_mode:
            print(json.dumps(skill.to_dict(), indent=2))
        else:
            print(skills_tool.render_skill_info(skill))
        return 0

    elif name and action == "run":
        payload_args = skills_tool.parse_args_payload(args_json)
        exec_res = skills_tool.GLOBAL_REGISTRY.execute(
            name_or_query=name,
            args=payload_args,
            auto_approve_red=auto_approve,
        )
        if json_mode:
            print(json.dumps(exec_res, indent=2, ensure_ascii=False))
        else:
            print(skills_tool.render_execution_result(exec_res))
        return 0 if exec_res.get("status") == "SUCCESS" else 1

    else:  # list
        skills_list = skills_tool.GLOBAL_REGISTRY.list_skills(category=category, tier=tier)
        if json_mode:
            payload = {
                "command": "skills",
                "action": "list",
                "total": len(skills_list),
                "skills": [s.to_dict() for s in skills_list],
                "timestamp": datetime.datetime.now().isoformat(),
                "mark": WATERMARK,
            }
            print(json.dumps(payload, indent=2))
        else:
            print(skills_tool.render_skills_list(skills_list))
        return 0


# =====================================================================
# 7) Subcommand: 'test' (Automated Test Suite Runner)
# =====================================================================

def get_available_test_modules() -> List[Tuple[str, Any]]:
    """Dynamically import and return all available test suite modules."""
    tests_dir = os.path.join(ROOT_DIR, "tests")
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)

    modules = []

    # Import modules with error tolerance
    import tests.test_scout as ts_scout
    modules.append(("xola-scout", ts_scout))

    import tests.test_builder as ts_builder
    modules.append(("xola-builder", ts_builder))

    import tests.test_guard as ts_guard
    modules.append(("xola-guard", ts_guard))

    import tests.test_memory as ts_memory
    modules.append(("xola-memory", ts_memory))

    import tests.test_skills as ts_skills
    modules.append(("xola-skills", ts_skills))

    import tests.test_server as ts_server
    modules.append(("xola-server", ts_server))

    try:
        import tests.test_cli as ts_cli
        modules.append(("xola-cli", ts_cli))
    except ImportError:
        pass

    try:
        import tests.test_jarvis as ts_jarvis
        modules.append(("xola-jarvis", ts_jarvis))
    except ImportError:
        pass

    return modules


def execute_test_cmd(
    suite_name: str = "all",
    verbose: bool = True,
    quiet: bool = False,
    failfast: bool = False,
    json_mode: bool = False,
) -> int:
    """Execute unit tests and output formatted reports or JSON."""
    start_time = time.perf_counter()
    all_modules = get_available_test_modules()

    # Filter target suites
    suite_clean = suite_name.lower().strip()
    if suite_clean in ("all", "master", "*", ""):
        selected_modules = all_modules
    else:
        selected_modules = [
            (name, mod) for name, mod in all_modules
            if suite_clean in name.lower() or suite_clean in mod.__name__.lower()
        ]

    if not selected_modules:
        err_msg = f"No test suite found matching '{suite_name}'. Available: {', '.join(name for name, _ in all_modules)}"
        if json_mode:
            print(json.dumps({
                "command": "test",
                "status": "ERROR",
                "error": err_msg,
                "timestamp": datetime.datetime.now().isoformat(),
                "mark": WATERMARK,
            }, indent=2))
        else:
            print(f"🦋 ERROR in xola-test: {err_msg}", file=sys.stderr)
        return 1

    verbosity = 0 if (quiet or json_mode) else (2 if verbose else 1)
    loader = unittest.TestLoader()

    suite_results = []
    total_tests_run = 0
    total_failures = 0
    total_errors = 0
    total_skipped = 0

    if not json_mode and not quiet:
        ts_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🦋 X.O.L.A. Automated Test Suite [{ts_now}] 🦋")
        print("=" * 76)
        print(f"Target Suite     : {suite_name} ({len(selected_modules)} module(s))")
        print(f"Python Runtime   : {sys.version.split()[0]} ({sys.executable})")
        print(f"Dependencies     : Pure Stdlib (unittest)")
        print("-" * 76)

    for mod_name, mod in selected_modules:
        t0 = time.perf_counter()
        mod_suite = loader.loadTestsFromModule(mod)

        # In quiet / JSON mode, suppress runner stream
        stream = io.StringIO() if (quiet or json_mode) else sys.stdout
        runner = unittest.TextTestRunner(
            verbosity=verbosity,
            failfast=failfast,
            stream=stream,
        )

        if verbosity > 1:
            print(f"\n[SUITE] Executing {mod_name} ({mod.__name__}) {WATERMARK} ...")

        res = runner.run(mod_suite)
        lat = time.perf_counter() - t0

        passed = res.testsRun - len(res.failures) - len(res.errors) - len(res.skipped)
        status_tag = "PASS" if res.wasSuccessful() else "FAIL"

        suite_results.append({
            "name": mod_name,
            "module": mod.__name__,
            "status": status_tag,
            "tests_run": res.testsRun,
            "passed": passed,
            "failures": len(res.failures),
            "errors": len(res.errors),
            "skipped": len(res.skipped),
            "latency_s": round(lat, 4),
        })

        total_tests_run += res.testsRun
        total_failures += len(res.failures)
        total_errors += len(res.errors)
        total_skipped += len(res.skipped)

        if failfast and not res.wasSuccessful():
            break

    total_duration = round(time.perf_counter() - start_time, 4)
    total_passed = total_tests_run - total_failures - total_errors - total_skipped
    all_passed = (total_failures == 0) and (total_errors == 0) and (total_tests_run > 0)
    pass_rate = round((total_passed / total_tests_run * 100.0), 2) if total_tests_run > 0 else 0.0

    if json_mode:
        payload = {
            "command": "test",
            "status": "PASS" if all_passed else "FAIL",
            "suite_filter": suite_name,
            "timestamp": datetime.datetime.now().isoformat(),
            "duration_s": total_duration,
            "summary": {
                "total_tests": total_tests_run,
                "passed": total_passed,
                "failures": total_failures,
                "errors": total_errors,
                "skipped": total_skipped,
                "pass_rate_pct": pass_rate,
            },
            "suites": suite_results,
            "mark": WATERMARK,
        }
        print(json.dumps(payload, indent=2))
    else:
        print("\n" + "=" * 76)
        print("🦋 X.O.L.A. Automated Test Suite — Summary Breakdown 🦋")
        print("=" * 76)
        print(f"{'Module / Subsystem':<20} | {'Status':<6} | {'Tests':<5} | {'Passed':<6} | {'Fail':<4} | {'Err':<4} | {'Latency'}")
        print("-" * 76)

        for sr in suite_results:
            st_tag = f"[{sr['status']}]"
            print(
                f"{sr['name']:<20} | {st_tag:<6} | {sr['tests_run']:>5} | "
                f"{sr['passed']:>6} | {sr['failures']:>4} | {sr['errors']:>4} | {sr['latency_s']:>6.3f}s"
            )

        print("-" * 76)
        verdict_banner = "ALL TEST SUITES PASSED CLEANLY 🦋" if all_passed else "FAILURES DETECTED IN TEST SUITE"
        print(f"Overall Result : {verdict_banner}")
        print(f"Total Tests    : {total_tests_run} total | {total_passed} passed | {total_failures} failed | {total_errors} errors | {total_skipped} skipped")
        print(f"Pass Rate      : {pass_rate:.2f}%")
        print(f"Total Duration : {total_duration:.3f}s")
        print("=" * 76 + "\n")

    return 0 if all_passed else 1


# =====================================================================
# 7) Subcommand: 'server' (Mission Control Workbench)
# =====================================================================

def execute_server_cmd(
    port: int = 8101,
    check: bool = False,
    timeout: float = 3.0,
    json_mode: bool = False,
) -> int:
    """Run or check Mission Control workbench server."""
    if check:
        t0 = time.perf_counter()
        url = f"http://127.0.0.1:{port}/api/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status_code = resp.status
                body = json.loads(resp.read().decode("utf-8"))
                lat = time.perf_counter() - t0

                if status_code == 200 and body.get("status") == "up":
                    if json_mode:
                        print(json.dumps({
                            "command": "server",
                            "action": "check",
                            "status": "UP",
                            "port": port,
                            "url": url,
                            "latency_s": round(lat, 4),
                            "health": body,
                            "mark": WATERMARK,
                        }, indent=2))
                    else:
                        print(f"🦋 X.O.L.A. Mission Control is UP on http://127.0.0.1:{port}/ (latency: {lat:.3f}s) 🦋")
                    return 0
        except Exception as exc:
            lat = time.perf_counter() - t0
            if json_mode:
                print(json.dumps({
                    "command": "server",
                    "action": "check",
                    "status": "DOWN",
                    "port": port,
                    "url": url,
                    "error": str(exc),
                    "latency_s": round(lat, 4),
                    "mark": WATERMARK,
                }, indent=2))
            else:
                print(f"🦋 X.O.L.A. Mission Control is DOWN on port {port}: {exc}", file=sys.stderr)
            return 1

    # Foreground server launch
    os.chdir(ROOT_DIR)
    tasks_file = os.path.join(ROOT_DIR, "tasks.json")
    if not os.path.exists(tasks_file):
        server_mod.save_tasks([])

    try:
        with socketserver.TCPServer(("127.0.0.1", port), server_mod.Handler) as httpd:
            print(f"🦋 X.O.L.A. Mission Control listening on http://127.0.0.1:{port}/ 🦋")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print(f"\nShutting down X.O.L.A. Mission Control Server {WATERMARK}")
        return 0
    except Exception as exc:
        print(f"🦋 ERROR starting X.O.L.A. Server on port {port}: {exc}", file=sys.stderr)
        return 1


# =====================================================================
# 8) Subcommand: 'jarvis' (Autonomous Harness & Sentinel)
# =====================================================================

def execute_jarvis_cmd(
    action: str = "status",
    task: Optional[str] = None,
    think_prompt: Optional[str] = None,
    voice_text: Optional[str] = None,
    nudge_name: Optional[str] = None,
    hands_cmd: Optional[str] = None,
    args_json: str = "{}",
    tail: int = 0,
    interval: float = 2.0,
    smoke: bool = False,
    tick: bool = False,
    json_mode: bool = False,
) -> int:
    """Execute Jarvis autonomous harness actions: status, tick, send, sentinel, smoke, daemon, think, voice, nudge, hands."""
    harness = JarvisHarness()

    if smoke or action == "smoke":
        smoke_res = run_jarvis_smoke_test()
        if json_mode:
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
        return 0 if smoke_res.get("smoke_test") == "PASSED" else 1

    elif action == "hands":
        cmd_val = hands_cmd or task or "disk"
        try:
            task_args = json.loads(args_json) if isinstance(args_json, str) else (args_json or {})
        except Exception:
            task_args = {}
        hands_instance = OSHands()
        h_res = hands_instance.execute_action(cmd_val, task_args)
        if json_mode:
            print(json.dumps(h_res, indent=2, ensure_ascii=False))
        else:
            print(f"🦋 Jarvis OS Hands [{cmd_val}] 🦋")
            print("=" * 72)
            for k, v in h_res.items():
                if isinstance(v, (dict, list)):
                    print(f"{k.ljust(16)}: {json.dumps(v, ensure_ascii=False)}")
                else:
                    print(f"{k.ljust(16)}: {v}")
            print("=" * 72)
        return 0 if h_res.get("status") != "ERROR" else 1

    elif action == "think" or think_prompt:
        prompt_val = think_prompt or task or ""
        brain_res = jarvis_think_and_execute(prompt_val)
        if json_mode:
            print(json.dumps(brain_res.to_dict(), indent=2, ensure_ascii=False))
        else:
            p = brain_res.plan
            print(f"🦋 Jarvis Brain Thinking & Execution [{brain_res.status}] 🦋")
            print("=" * 72)
            print(f"Prompt   : {p.prompt}")
            print(f"Thought  : {p.thought}")
            print(f"Action   : {p.action} -> {p.skill}")
            print(f"Response : {brain_res.formatted_response}")
            print(f"Latency  : {brain_res.latency_s:.4f}s")
            print("=" * 72)
        return 0 if brain_res.status == "SUCCESS" else 1

    elif action == "voice" or voice_text:
        text_val = voice_text or task or ""
        v_res = jarvis_speak(text_val)
        if json_mode:
            print(json.dumps(v_res, indent=2, ensure_ascii=False))
        else:
            print(f"🦋 Voice synthesis: \"{text_val}\" [{v_res.get('status')}] ({v_res.get('latency_s', 0.0)}s) 🦋")
        return 0 if v_res.get("status") in ("SUCCESS", "ASYNC_QUEUED", "MUTED") else 1

    elif action == "nudge" or nudge_name:
        n_name = nudge_name or task or "all"
        if n_name.lower() == "all":
            results = execute_scheduled_nudges(force=True)
            if json_mode:
                print(json.dumps(results, indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Executed {len(results)} Scheduled Nudges 🦋")
                for r in results:
                    print(f"  • [{r.get('status')}] {r.get('nudge')} -> {r.get('log_line')}")
            return 0
        else:
            r = run_nudge_by_name(n_name)
            if json_mode:
                print(json.dumps(r, indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Nudge '{n_name}' [{r.get('status')}]: {r.get('log_line')}")
            return 0 if r.get("status") not in ("ERROR", "KILL") else 1

    elif tick or action in ("tick", "once"):
        resps = harness.process_pending_inbox()
        if json_mode:
            payload = {
                "command": "jarvis",
                "action": "tick",
                "processed_count": len(resps),
                "responses": [r.to_dict() for r in resps],
                "mark": WATERMARK,
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"🦋 Processed {len(resps)} pending task(s) from Jarvis inbox 🦋")
            for r in resps:
                print(f"  • [{r.status}] {r.task_id} -> {r.skill_used} ({r.latency_s}s) {WATERMARK}")
        return 0

    elif action == "task":
        prompt_text = task or ""
        if not prompt_text:
            prompt_text = "sys_info"

        try:
            task_args = json.loads(args_json) if isinstance(args_json, str) else (args_json or {})
        except Exception:
            task_args = {}

        task_path = harness.submit_task(prompt_or_skill=prompt_text, args=task_args)
        resp = harness.process_single_task_file(task_path)

        if json_mode:
            print(json.dumps(resp.to_dict() if resp else {"status": "ERROR"}, indent=2, ensure_ascii=False))
        else:
            if resp:
                print(f"🦋 Jarvis Task Execution [{resp.status}] 🦋")
                print("=" * 72)
                print(f"Task ID     : {resp.task_id}")
                print(f"Action      : {resp.action}")
                print(f"Skill Used  : {resp.skill_used}")
                print(f"Status      : {resp.status}")
                print(f"Latency     : {resp.latency_s}s")
                res_str = str(resp.result)
                if len(res_str) > 200:
                    res_str = res_str[:200] + "..."
                print(f"Result      : {res_str}")
                print(f"Outbox File : {os.path.join(harness.outbox_dir, f'response_{resp.task_id}_*.json')}")
                print("=" * 72)
            else:
                print(f"🦋 Jarvis Task Execution [ERROR]: Failed to process task")
        return 0 if (resp and resp.status == "SUCCESS") else 1

    elif action == "send":
        prompt_text = task or ""
        if not prompt_text:
            prompt_text = "sys_info"

        try:
            task_args = json.loads(args_json) if isinstance(args_json, str) else (args_json or {})
        except Exception:
            task_args = {}

        task_path = harness.submit_task(prompt_or_skill=prompt_text, args=task_args)
        filename = os.path.basename(task_path)
        base_id, _ = os.path.splitext(filename)

        if json_mode:
            print(json.dumps({
                "command": "jarvis",
                "action": "send",
                "status": "SUCCESS",
                "submitted": True,
                "task_id": base_id,
                "task_file": task_path,
                "prompt": prompt_text,
                "args": task_args,
                "mark": WATERMARK,
            }, indent=2, ensure_ascii=False))
        else:
            print(f"🦋 Dispatched task to Jarvis inbox: {task_path} [ID: {base_id}] 🦋")
        return 0

    elif action == "sentinel":
        if tail > 0:
            lines = read_sentinel_log(tail_n=tail)
            if json_mode:
                print(json.dumps({
                    "command": "jarvis",
                    "action": "sentinel",
                    "log_lines": lines,
                    "total": len(lines),
                    "mark": WATERMARK,
                }, indent=2, ensure_ascii=False))
            else:
                print(f"🦋 Jarvis Sentinel Log (Last {len(lines)} entries) 🦋")
                print("=" * 72)
                for l in lines:
                    print(l)
                print("=" * 72)
            return 0
        else:
            chk = run_sentinel_once()
            if json_mode:
                payload = {
                    "command": "jarvis",
                    "action": "sentinel",
                    "health": chk.to_dict(),
                    "mark": WATERMARK,
                }
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(render_sentinel_report(chk))
            return 0 if chk.status != "CRITICAL" else 1

    elif action == "daemon":
        run_jarvis_loop(interval=interval)
        return 0

    else:  # status (default)
        stat = get_jarvis_status()
        if json_mode:
            payload = {
                "command": "jarvis",
                "action": "status",
                "status": stat.get("status", "HEALTHY"),
                "data": stat,
                "mark": WATERMARK,
            }
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(render_jarvis_status(stat))
        return 0 if stat.get("status") != "CRITICAL" else 1


# =====================================================================
# CLI Parser Definition & Main Router
# =====================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build root CLI parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="xola",
        description="X.O.L.A. — Unified Tool Suite Command Line Interface 🦋",
        epilog="Usage: python cli.py [status|scout|build|guard|memory|test|server] ...",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"xola CLI v{VERSION} {WATERMARK}",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Global flag for machine-readable JSON output",
    )

    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to execute")

    # 1. status
    p_status = subparsers.add_parser("status", help="Holistic system health & triage overview 🦋")
    p_status.add_argument("--json", action="store_true", help="Output JSON format")
    p_status.add_argument("--quick", action="store_true", default=True, help="Fast triage check without active LLM probes")
    p_status.add_argument("-v", "--verbose", action="store_true", help="Include detailed component telemetry")

    # 2. scout
    p_scout = subparsers.add_parser("scout", help="Fast triage prober for free lanes 🦋")
    p_scout.add_argument("--quick", action="store_true", help="Probe CLI versions only, skipping live LLM test")
    p_scout.add_argument("--model", default="gemini-3.7-flash-low", help="Model for AGY health probe")
    p_scout.add_argument("--timeout", type=float, default=30.0, help="Timeout in seconds for LLM probe")
    p_scout.add_argument("--live-timeout", type=float, default=120.0, help="Timeout for OpenCode live server test")
    p_scout.add_argument("--json", action="store_true", help="Output JSON format")

    # 3. build
    p_build = subparsers.add_parser("build", aliases=["builder"], help="Forge, inspect, and validate X.O.L.A. tools 🦋")
    p_build.add_argument("action", nargs="?", default="validate", choices=["validate", "inspect", "scaffold", "list"], help="Build action")
    p_build.add_argument("--action", "-a", dest="flag_action", default=None, choices=["validate", "inspect", "scaffold", "list"], help="Build action flag")
    p_build.add_argument("--target", "-t", default=None, help="Target tool name or file path")
    p_build.add_argument("--scaffold", dest="flag_scaffold", metavar="NAME", help="Scaffold a new tool with NAME")
    p_build.add_argument("--name", default=None, help="Name of tool to scaffold")
    p_build.add_argument("--desc", default="", help="Description for scaffolded tool")
    p_build.add_argument("--template", default="tool", choices=["tool", "prober", "auditor", "distiller"], help="Template type")
    p_build.add_argument("--force", action="store_true", help="Overwrite existing file during scaffolding")
    p_build.add_argument("--inspect", dest="flag_inspect", nargs="?", const="__ALL__", help="Inspect tool(s)")
    p_build.add_argument("--validate", dest="flag_validate", nargs="?", const="__ALL__", help="Validate tool(s)")
    p_build.add_argument("--list", action="store_true", help="List all available tools")
    p_build.add_argument("--no-run-test", action="store_true", help="Skip live execution smoke test during validation")
    p_build.add_argument("--tools-dir", default=None, help="Custom tools directory path")
    p_build.add_argument("--json", action="store_true", help="Output JSON format")

    # 4. guard
    p_guard = subparsers.add_parser("guard", help="Red-team reviewer that kills slop before checkpoint 🦋")
    p_guard.add_argument("--target", default=".", help="Target file or directory path to audit")
    p_guard.add_argument("--strict", action="store_true", help="Strict mode: elevate any warning to KILL")
    p_guard.add_argument("--fix", action="store_true", help="Auto-fix remediable issues (e.g. inject missing watermark)")
    p_guard.add_argument("--smoke", action="store_true", help="Run lightweight CLI execution smoke tests")
    p_guard.add_argument("-v", "--verbose", action="store_true", help="Verbose finding details")
    p_guard.add_argument("--json", action="store_true", help="Output JSON format")

    # 5. memory
    p_memory = subparsers.add_parser("memory", help="Round distiller, memory query engine, and analytics 🦋")
    p_memory.add_argument("--append", action="store_true", help="Append structured round record to memory file")
    p_memory.add_argument("--distill", action="store_true", help="Distill raw loop logs into concise summaries")
    p_memory.add_argument("--query", "-q", nargs="?", const="", default=None, help="Query historical memory entries")
    p_memory.add_argument("--timeline", action="store_true", help="Generate chronological timeline of all rounds")
    p_memory.add_argument("--stats", action="store_true", help="Compute pass/fail rates, latency, and module coverage")
    p_memory.add_argument("--round", "-r", type=int, default=None, help="Round index number")
    p_memory.add_argument("--step", "-s", default="", help="Step executed or goal description")
    p_memory.add_argument("--evidence", "-e", default="", help="Tool execution evidence and outputs")
    p_memory.add_argument("--verdict", "-v", default="PASS", choices=["PASS", "KILL", "WARN"], help="Round verdict")
    p_memory.add_argument("--lessons", "-l", default="", help="Lessons learned during round")
    p_memory.add_argument("--next-step", "-n", default="", help="Recommended next engineering step")
    p_memory.add_argument("--tags", default="general", help="Comma-separated tags for round record")
    p_memory.add_argument("--lane", default="python", help="Execution lane used (python, agy, opencode)")
    p_memory.add_argument("--latency", type=float, default=0.0, help="Round execution latency in seconds")
    p_memory.add_argument("--input", "-i", default=None, help="Input loop file to distill")
    p_memory.add_argument("--output", "-o", default=None, help="Output destination for distilled summary")
    p_memory.add_argument("--memory-dir", default=None, help="Custom memory directory path")
    p_memory.add_argument("--loop-dir", default=None, help="Custom loop directory path")
    p_memory.add_argument("--date", "-d", default=None, help="Target date for timeline/queries (YYYY-MM-DD)")
    p_memory.add_argument("--limit", type=int, default=10, help="Max query results to return")
    p_memory.add_argument("--json", action="store_true", help="Output JSON format")

    # 6. skills
    p_skills = subparsers.add_parser("skills", aliases=["skill"], help="Skills registry, matching, and execution 🦋")
    p_skills.add_argument("--list", "-l", action="store_true", help="List all registered skills")
    p_skills.add_argument("--run", "-r", metavar="SKILL", help="Execute specified skill")
    p_skills.add_argument("--info", "-i", metavar="SKILL", help="Display documentation and schema for skill")
    p_skills.add_argument("--args", "-a", default="{}", help="JSON string or file path containing arguments for skill execution")
    p_skills.add_argument("--query", "-q", metavar="QUERY", default=None, help="Find skill matching search query")
    p_skills.add_argument("--validate", action="store_true", help="Validate integrity and schemas of all registered skills")
    p_skills.add_argument("--category", "-c", default=None, help="Filter skills list by category")
    p_skills.add_argument("--tier", "-t", default=None, help="Filter skills list by security tier (GREEN, YELLOW, RED)")
    p_skills.add_argument("--auto-approve", action="store_true", help="Auto-approve RED tier skills for autonomous non-interactive runs")
    p_skills.add_argument("--json", action="store_true", help="Output machine-readable JSON format")

    # 7. test
    p_test = subparsers.add_parser("test", help="Automated test suite runner and reporting 🦋")
    p_test.add_argument("--suite", "-s", default="all", help="Target test suite (all, scout, builder, guard, memory, skills, server, cli)")
    p_test.add_argument("-v", "--verbose", action="store_true", default=True, help="Enable verbose test reporting")
    p_test.add_argument("-q", "--quiet", action="store_true", help="Quiet mode, minimal output")
    p_test.add_argument("--failfast", action="store_true", help="Stop on first failure")
    p_test.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # 8. server
    p_server = subparsers.add_parser("server", help="Mission Control Workbench HTTP server 🦋")
    p_server.add_argument("--port", "-p", type=int, default=8101, help="Port to listen on (default: 8101)")
    p_server.add_argument("--check", action="store_true", help="Check if server is currently running and healthy")
    p_server.add_argument("--timeout", type=float, default=3.0, help="Timeout in seconds for health check")
    p_server.add_argument("--json", action="store_true", help="Output JSON format")

    # 9. jarvis
    p_jarvis = subparsers.add_parser("jarvis", help="Jarvis Autonomous Harness, Cognitive Brain, Voice, Hands & Sentinel 🦋")
    p_jarvis.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "tick", "send", "task", "sentinel", "smoke", "daemon", "think", "voice", "nudge", "hands"],
        help="Jarvis action: status, tick (process inbox), send (queue task), task (execute task), sentinel (diagnostics), smoke, daemon, think, voice, nudge, hands",
    )
    p_jarvis.add_argument(
        "--action",
        "-a",
        dest="flag_action",
        default=None,
        choices=["status", "tick", "send", "task", "sentinel", "smoke", "daemon", "think", "voice", "nudge", "hands"],
        help="Jarvis action flag (alternative to positional argument)",
    )
    p_jarvis.add_argument("--command", "-c", dest="hands_cmd", default=None, help="Hands action command (e.g. disk, ps, tree, read, write, screenshot, windows)")
    p_jarvis.add_argument("--task", "-t", "--prompt", "-m", dest="task", default=None, help="Task prompt or skill to send to inbox")
    p_jarvis.add_argument("--think", "-p", dest="think_prompt", default=None, help="Process natural language prompt with Autonomous Brain")
    p_jarvis.add_argument("--voice", "-v", dest="voice_text", default=None, help="Synthesize and speak text via voice engine")
    p_jarvis.add_argument("--nudge", dest="nudge_name", default=None, help="Trigger scheduled nudge ('all', 'health', 'guard', 'scout')")
    p_jarvis.add_argument("--args", default="{}", help="JSON string of arguments for submitted task")
    p_jarvis.add_argument("--tail", type=int, default=0, help="Display last N entries from sentinel.log")
    p_jarvis.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds for daemon")
    p_jarvis.add_argument("--smoke", action="store_true", help="Execute complete end-to-end smoke test")
    p_jarvis.add_argument("--tick", "--once", dest="tick", action="store_true", help="Process pending inbox tasks once")
    p_jarvis.add_argument("--sentinel", dest="flag_sentinel", action="store_true", help="Run sentinel health diagnostic")
    p_jarvis.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    return parser


def main() -> None:
    """Main CLI entrypoint router."""
    parser = build_parser()
    args = parser.parse_args()

    # If no subcommand provided, default to status
    if not args.subcommand:
        status_res = get_system_status(quick=True)
        if args.json:
            print(json.dumps(status_res, indent=2))
        else:
            print(render_status_report(status_res))
        sys.exit(0 if status_res.get("status") != "CRITICAL" else 1)

    json_mode = args.json or getattr(args, "json", False)

    try:
        # 1. status
        if args.subcommand == "status":
            status_res = get_system_status(quick=args.quick)
            if json_mode:
                print(json.dumps(status_res, indent=2))
            else:
                print(render_status_report(status_res, verbose=args.verbose))
            sys.exit(0 if status_res.get("status") != "CRITICAL" else 1)

        # 2. scout
        elif args.subcommand == "scout":
            code = execute_scout_cmd(
                quick=args.quick,
                model=args.model,
                timeout=args.timeout,
                live_timeout=args.live_timeout,
                json_mode=json_mode,
            )
            sys.exit(code)

        # 3. build / builder
        elif args.subcommand in ("build", "builder"):
            action = getattr(args, "flag_action", None) or args.action
            if args.flag_scaffold:
                action = "scaffold"
            elif args.flag_inspect is not None:
                action = "inspect"
            elif args.flag_validate is not None:
                action = "validate"
            elif args.list:
                action = "list"

            target = args.target
            if action == "inspect" and args.flag_inspect and args.flag_inspect != "__ALL__":
                target = args.flag_inspect
            elif action == "validate" and args.flag_validate and args.flag_validate != "__ALL__":
                target = args.flag_validate

            code = execute_build_cmd(
                action=action,
                target=target,
                scaffold_name=args.flag_scaffold or args.name,
                desc=args.desc,
                template=args.template,
                force=args.force,
                no_run_test=args.no_run_test,
                tools_dir=args.tools_dir,
                json_mode=json_mode,
            )
            sys.exit(code)

        # 4. guard
        elif args.subcommand == "guard":
            code = execute_guard_cmd(
                target=args.target,
                strict=args.strict,
                fix=args.fix,
                smoke=args.smoke,
                verbose=args.verbose,
                json_mode=json_mode,
            )
            sys.exit(code)

        # 5. memory
        elif args.subcommand == "memory":
            code = execute_memory_cmd(
                append=args.append,
                distill=args.distill,
                query=args.query,
                timeline=args.timeline,
                stats=args.stats,
                round_idx=args.round,
                step=args.step,
                evidence=args.evidence,
                verdict=args.verdict,
                lessons=args.lessons,
                next_step=args.next_step,
                tags=args.tags,
                lane=args.lane,
                latency=args.latency,
                input_path=args.input,
                output_path=args.output,
                memory_dir=args.memory_dir,
                loop_dir=args.loop_dir,
                target_date=args.date,
                limit=args.limit,
                json_mode=json_mode,
            )
            sys.exit(code)

        # 6. skills
        elif args.subcommand in ("skills", "skill"):
            action = "list"
            name = None
            if args.run:
                action = "run"
                name = args.run
            elif args.info:
                action = "info"
                name = args.info
            elif args.validate:
                action = "validate"

            code = execute_skills_cmd(
                action=action,
                name=name,
                args_json=args.args,
                query=args.query,
                validate=args.validate,
                category=args.category,
                tier=args.tier,
                auto_approve=args.auto_approve,
                json_mode=json_mode,
            )
            sys.exit(code)

        # 7. test
        elif args.subcommand == "test":
            code = execute_test_cmd(
                suite_name=args.suite,
                verbose=args.verbose,
                quiet=args.quiet,
                failfast=args.failfast,
                json_mode=json_mode,
            )
            sys.exit(code)

        # 8. server
        elif args.subcommand == "server":
            code = execute_server_cmd(
                port=args.port,
                check=args.check,
                timeout=args.timeout,
                json_mode=json_mode,
            )
            sys.exit(code)

        # 9. jarvis
        elif args.subcommand == "jarvis":
            action = getattr(args, "flag_action", None) or args.action
            if args.smoke:
                action = "smoke"
            elif args.tick:
                action = "tick"
            elif args.flag_sentinel:
                action = "sentinel"
            elif args.think_prompt:
                action = "think"
            elif args.voice_text:
                action = "voice"
            elif args.nudge_name:
                action = "nudge"
            elif getattr(args, "hands_cmd", None) and action in ("status", "hands"):
                action = "hands"
            elif args.task and action == "status":
                action = "task"

            code = execute_jarvis_cmd(
                action=action,
                task=args.task,
                think_prompt=args.think_prompt,
                voice_text=args.voice_text,
                nudge_name=args.nudge_name,
                hands_cmd=getattr(args, "hands_cmd", None),
                args_json=args.args,
                tail=args.tail,
                interval=args.interval,
                smoke=args.smoke,
                tick=args.tick,
                json_mode=json_mode,
            )
            sys.exit(code)

        else:
            print(f"Unknown subcommand '{args.subcommand}' {WATERMARK}", file=sys.stderr)
            sys.exit(1)

    except KeyboardInterrupt:
        print(f"\nExecution interrupted by user {WATERMARK}", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        err_payload = {
            "status": "ERROR",
            "error": str(exc),
            "timestamp": datetime.datetime.now().isoformat(),
            "mark": WATERMARK,
        }
        if json_mode:
            print(json.dumps(err_payload, indent=2))
        else:
            print(f"🦋 ERROR in xola CLI ({args.subcommand}): {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
