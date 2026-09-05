#!/usr/bin/env python3
"""Usage: python memory.py [--append] [--distill] [--query PATTERN] [--timeline] [--stats] [--json] # xola-memory: round distiller and memory engine 🦋"""

import argparse
import collections
import datetime
import json
import os
import pathlib
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"

# Standard known project directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_MEMORY_DIR = os.path.join(PROJECT_ROOT, "memory")
DEFAULT_LOOP_DIR = os.path.join(PROJECT_ROOT, "loop")
DEFAULT_LOG_PATH = os.path.join(DEFAULT_LOOP_DIR, "loop.log")
DEFAULT_STATE_PATH = os.path.join(DEFAULT_LOOP_DIR, "state.json")

# Tracked modules for coverage analysis
TRACKED_MODULES = [
    "scout",
    "builder",
    "guard",
    "memory",
    "hermes",
    "agy",
    "opencode",
    "deepseek",
    "harness",
    "server",
    "reports",
]


# =====================================================================
# Path Resolution Helpers
# =====================================================================

def resolve_memory_dir(custom_path: Optional[str] = None) -> str:
    """Resolve active memory directory path."""
    if custom_path:
        return os.path.abspath(custom_path)
    if os.path.exists(DEFAULT_MEMORY_DIR):
        return DEFAULT_MEMORY_DIR
    cwd_candidate = os.path.join(os.getcwd(), "memory")
    if os.path.exists(cwd_candidate):
        return cwd_candidate
    return DEFAULT_MEMORY_DIR


def resolve_loop_dir(custom_path: Optional[str] = None) -> str:
    """Resolve active loop directory path."""
    if custom_path:
        return os.path.abspath(custom_path)
    if os.path.exists(DEFAULT_LOOP_DIR):
        return DEFAULT_LOOP_DIR
    cwd_candidate = os.path.join(os.getcwd(), "loop")
    if os.path.exists(cwd_candidate):
        return cwd_candidate
    return DEFAULT_LOOP_DIR


# =====================================================================
# Memory Record Parsing Engine
# =====================================================================

def parse_memory_section(section_text: str, source_file: str, date_str: str) -> Optional[Dict[str, Any]]:
    """Parse a single markdown section (under ##) into a structured round record."""
    lines = section_text.strip().splitlines()
    if not lines:
        return None

    header = lines[0].strip()
    body_lines = lines[1:]
    body_text = "\n".join(body_lines).strip()

    # Extract time from header, e.g. "## 13:43 loop round" or "## 14:20 loop round (Round 9: PASS) 🦋"
    time_match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", header)
    time_part = time_match.group(1) if time_match else "00:00"

    # Extract round index and verdict from header or body
    round_idx = None
    verdict = "UNKNOWN"

    round_hdr_match = re.search(r"[Rr]ound\s+(\d+)(?:\s*:\s*([A-Za-z0-9_-]+))?", header)
    if round_hdr_match:
        round_idx = int(round_hdr_match.group(1))
        if round_hdr_match.group(2):
            verdict = round_hdr_match.group(2).upper()

    step_text = ""
    evidence_text = ""
    guard_verdict = verdict
    key_lessons = ""
    next_step = ""
    tags = []
    timestamp_str = f"{date_str} {time_part}"

    # Parse structured bullet lines or key-value patterns
    current_key = None
    current_val_lines = []

    def commit_field(key: Optional[str], val_lines: List[str]):
        nonlocal round_idx, verdict, step_text, evidence_text, guard_verdict, key_lessons, next_step, tags, timestamp_str
        if not key:
            return
        val = "\n".join(val_lines).strip()
        k_lower = key.lower()

        if k_lower in ("round", "round_idx", "round index"):
            m = re.search(r"(\d+)", val)
            if m:
                round_idx = int(m.group(1))
            v_match = re.search(r"(?:PASS|KILL|WARN|FAIL|SUCCESS|ERROR)", val, re.IGNORECASE)
            if v_match:
                verdict = v_match.group(0).upper()
        elif k_lower in ("verdict", "guard verdict", "guard audit verdict", "audit verdict"):
            verdict = val.upper()
            guard_verdict = val.upper()
        elif k_lower in ("step", "step executed", "prompt", "goal"):
            step_text = val
        elif k_lower in ("evidence", "result", "tool evidence", "tool evidence & actions taken", "actions"):
            evidence_text = val
        elif k_lower in ("lessons", "key lessons", "key lesson", "learnings"):
            key_lessons = val
        elif k_lower in ("next_step", "next step", "next"):
            next_step = val
        elif k_lower in ("tags", "tag"):
            tags = [t.strip() for t in val.split(",") if t.strip()]
        elif k_lower in ("timestamp", "time", "date"):
            timestamp_str = val

    for line in body_lines:
        line_clean = line.strip()

        # Check structured bullet e.g. "- **Round**: 9" or "round 1: PASS"
        bullet_kv = re.match(r"^[-*•]\s+\*\*([^:]+)\*\*:\s*(.*)$", line_clean)
        plain_kv = re.match(r"^([a-zA-Z\s_]{3,24}):\s*(.*)$", line_clean)
        round_line_match = re.match(r"^[Rr]ound\s+(\d+)\s*:\s*([A-Za-z0-9_-]+)(.*)$", line_clean)

        if bullet_kv:
            commit_field(current_key, current_val_lines)
            current_key = bullet_kv.group(1).strip()
            current_val_lines = [bullet_kv.group(2).strip()]
        elif round_line_match:
            commit_field(current_key, current_val_lines)
            round_idx = int(round_line_match.group(1))
            verdict = round_line_match.group(2).upper()
            guard_verdict = verdict
            current_key = None
            current_val_lines = []
        elif plain_kv and plain_kv.group(1).lower() in (
            "step", "result", "evidence", "verdict", "lessons", "key lessons", "next step", "next", "tags", "timestamp"
        ):
            commit_field(current_key, current_val_lines)
            current_key = plain_kv.group(1).strip()
            current_val_lines = [plain_kv.group(2).strip()]
        else:
            if current_key:
                current_val_lines.append(line)
            else:
                # If no key set yet, add to general body
                current_val_lines.append(line)

    commit_field(current_key, current_val_lines)

    # Fallback extraction if body was unstructured
    if not step_text and body_text:
        # Check first 2 lines as step
        first_lines = body_lines[:2]
        step_text = " ".join(l.strip() for l in first_lines if l.strip())
    if not evidence_text and len(body_lines) > 2:
        evidence_text = "\n".join(body_lines[2:]).strip()

    # Determine standard normalized verdict
    v_norm = verdict.upper()
    if "PASS" in v_norm or "SUCCESS" in v_norm:
        normalized_verdict = "PASS"
    elif "KILL" in v_norm or "FAIL" in v_norm or "ERROR" in v_norm:
        normalized_verdict = "KILL"
    elif "WARN" in v_norm:
        normalized_verdict = "WARN"
    else:
        normalized_verdict = "PASS" if verdict != "UNKNOWN" else "UNKNOWN"

    return {
        "round": round_idx,
        "verdict": normalized_verdict,
        "raw_verdict": verdict,
        "guard_verdict": guard_verdict,
        "step": step_text,
        "evidence": evidence_text,
        "lessons": key_lessons,
        "next_step": next_step,
        "tags": tags,
        "header": header,
        "date": date_str,
        "time": time_part,
        "timestamp": timestamp_str,
        "source_file": source_file,
        "raw_text": section_text.strip(),
        "char_count": len(section_text),
    }


def parse_memory_file(file_path: str) -> List[Dict[str, Any]]:
    """Parse an entire dated markdown memory file into records."""
    if not os.path.exists(file_path):
        return []

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception:
        return []

    # Infer date from filename YYYY-MM-DD.md
    base_name = os.path.basename(file_path)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", base_name)
    date_str = date_match.group(1) if date_match else datetime.date.today().isoformat()

    # Split by top-level loop round or distillation headers starting with ##
    # e.g. "## 13:43 loop round", "## Round 1", "## Distillation"
    raw_sections = re.split(
        r"(?m)^(?=##\s+(?:(?:\d{1,2}:\d{2}\b)|(?:[Rr]ound\s+\d+)|(?:Distillation\b)))",
        content,
    )
    records = []

    for sec in raw_sections:
        sec_clean = sec.strip()
        if not sec_clean or not sec_clean.startswith("##"):
            continue
        rec = parse_memory_section(sec_clean, file_path, date_str)
        if rec and (rec.get("round") is not None or rec.get("verdict") != "UNKNOWN" or "distill" in rec.get("header", "").lower()):
            records.append(rec)

    return records


def parse_all_memory(memory_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Scan and parse all markdown memory files in memory_dir."""
    mem_dir = resolve_memory_dir(memory_dir)
    if not os.path.exists(mem_dir):
        return []

    all_records = []
    files = sorted([
        os.path.join(mem_dir, f)
        for f in os.listdir(mem_dir)
        if f.endswith(".md") and os.path.isfile(os.path.join(mem_dir, f))
    ])

    for f_path in files:
        file_records = parse_memory_file(f_path)
        all_records.extend(file_records)

    # Sort primarily by round index, secondarily by date/time
    def sort_key(r: Dict[str, Any]):
        r_num = r.get("round") if r.get("round") is not None else 999999
        t_str = r.get("timestamp") or r.get("date") or ""
        return (r_num, t_str)

    return sorted(all_records, key=sort_key)


def parse_loop_log(log_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse raw loop.log into structured round execution events."""
    l_path = log_path or DEFAULT_LOG_PATH
    if not os.path.exists(l_path):
        return []

    try:
        with open(l_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return []

    rounds = []
    current_round: Optional[Dict[str, Any]] = None
    last_ts: Optional[datetime.datetime] = None

    ts_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})")

    for line in lines:
        line_str = line.strip()
        if not line_str:
            continue

        ts_match = ts_pattern.match(line_str)
        current_ts = None
        if ts_match:
            try:
                current_ts = datetime.datetime.strptime(ts_match.group(1), "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

        # Check round header: e.g. "=== ROUND 1 ==="
        round_start = re.search(r"=== ROUND (\d+) ===", line_str)
        if round_start:
            if current_round:
                if last_ts and current_round.get("start_ts"):
                    current_round["duration_s"] = round(
                        (last_ts - current_round["start_ts"]).total_seconds(), 2
                    )
                rounds.append(current_round)

            r_idx = int(round_start.group(1))
            current_round = {
                "round": r_idx,
                "start_time": ts_match.group(1) if ts_match else datetime.datetime.now().isoformat(),
                "start_ts": current_ts or datetime.datetime.now(),
                "scout": None,
                "manager": {},
                "executor": {},
                "audit": {},
                "warnings": [],
                "errors": [],
                "verdict": "UNKNOWN",
                "raw_lines": [line_str],
            }
            if current_ts:
                last_ts = current_ts
            continue

        if current_round:
            current_round["raw_lines"].append(line_str)
            if current_ts:
                last_ts = current_ts

            if "SCOUT:" in line_str:
                current_round["scout"] = line_str.split("SCOUT:", 1)[1].strip()
            elif "MANAGER" in line_str:
                via_m = re.search(r"via=([a-zA-Z0-9_-]*)", line_str)
                ok_m = re.search(r"ok=([A-Za-z]+)", line_str)
                chars_m = re.search(r"chars=(\d+)", line_str)
                current_round["manager"] = {
                    "via": via_m.group(1) if via_m else "default",
                    "ok": ok_m.group(1) == "True" if ok_m else True,
                    "chars": int(chars_m.group(1)) if chars_m else 0,
                    "raw": line_str,
                }
            elif "EXECUTOR" in line_str:
                ok_m = re.search(r"ok=([A-Za-z]+)", line_str)
                chars_m = re.search(r"chars=(\d+)", line_str)
                current_round["executor"] = {
                    "ok": ok_m.group(1) == "True" if ok_m else True,
                    "chars": int(chars_m.group(1)) if chars_m else 0,
                    "raw": line_str,
                }
            elif "AUDIT" in line_str or "SMOKE" in line_str:
                pass_m = re.search(r"pass=([A-Za-z]+)", line_str)
                if pass_m:
                    is_pass = pass_m.group(1) == "True"
                    current_round["verdict"] = "PASS" if is_pass else "KILL"
                elif "SMOKE PASS" in line_str:
                    current_round["verdict"] = "PASS"
                elif "SMOKE FAIL" in line_str:
                    current_round["verdict"] = "KILL"
                current_round["audit"] = {"raw": line_str, "verdict": current_round["verdict"]}
            elif "WARN" in line_str:
                current_round["warnings"].append(line_str)
            elif "Traceback" in line_str or "Error:" in line_str or "ROUND-ERROR:" in line_str:
                current_round["errors"].append(line_str)

    if current_round:
        if last_ts and current_round.get("start_ts"):
            current_round["duration_s"] = round(
                (last_ts - current_round["start_ts"]).total_seconds(), 2
            )
        rounds.append(current_round)

    return rounds


# =====================================================================
# Mode 1: `--append` Engine
# =====================================================================

def append_round(
    round_idx: Optional[int] = None,
    step: str = "",
    evidence: str = "",
    verdict: str = "PASS",
    lessons: str = "",
    next_step: str = "",
    tags: Optional[List[str]] = None,
    lane: Optional[str] = None,
    latency: Optional[float] = None,
    memory_dir: Optional[str] = None,
    target_date: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Append a structured round record to the dated memory file."""
    t0 = time.perf_counter()
    mem_dir = resolve_memory_dir(memory_dir)
    os.makedirs(mem_dir, exist_ok=True)

    today_str = target_date or datetime.date.today().isoformat()
    now_dt = datetime.datetime.now()
    now_time = now_dt.strftime("%H:%M")
    full_ts = now_dt.strftime("%Y-%m-%d %H:%M:%S")

    target_file = output_path or os.path.join(mem_dir, f"{today_str}.md")

    # Auto-infer round index if not provided
    if round_idx is None:
        existing = parse_all_memory(mem_dir)
        max_r = max([r["round"] for r in existing if r.get("round") is not None] + [0])
        round_idx = max_r + 1

    clean_verdict = verdict.strip().upper() if verdict else "PASS"
    clean_step = step.strip() or "General autonomous loop bounded step."
    clean_evidence = evidence.strip() or "Tool execution completed with verifiable outputs."
    clean_lessons = lessons.strip() or "Strict stdlib boundaries and guard-check passes ensure clean loop progress."
    clean_next_step = next_step.strip() or "Advance to next mission objective."
    tag_list = tags or []
    if lane:
        tag_list.append(f"lane:{lane}")

    # Build structured markdown block
    lines = [
        "",
        f"## {now_time} loop round (Round {round_idx}: {clean_verdict}) {WATERMARK}",
        f"- **Round**: {round_idx}",
        f"- **Verdict**: {clean_verdict}",
        f"- **Step**: {clean_step}",
        f"- **Evidence**: {clean_evidence}",
        f"- **Guard Audit Verdict**: {clean_verdict}",
        f"- **Key Lessons**: {clean_lessons}",
        f"- **Next Step**: {clean_next_step}",
    ]

    if tag_list:
        lines.append(f"- **Tags**: {', '.join(tag_list)}")
    if latency is not None:
        lines.append(f"- **Latency**: {latency:.4f}s")

    lines.append(f"- **Timestamp**: {full_ts}")
    lines.append(f"- **Mark**: {WATERMARK}")
    lines.append("")

    content_to_write = "\n".join(lines)

    try:
        with open(target_file, "a", encoding="utf-8") as f:
            f.write(content_to_write)
        status = "SUCCESS"
        error_msg = None
    except Exception as exc:
        status = "FAILURE"
        error_msg = str(exc)

    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "action": "append",
        "status": status,
        "round": round_idx,
        "verdict": clean_verdict,
        "file": target_file,
        "bytes_written": len(content_to_write.encode("utf-8")),
        "timestamp": full_ts,
        "latency_s": elapsed,
        "error": error_msg,
        "mark": WATERMARK,
    }


# =====================================================================
# Mode 2: `--distill` Engine
# =====================================================================

def distill_logs(
    input_path: Optional[str] = None,
    output_path: Optional[str] = None,
    round_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """Distill raw loop logs or execution traces into concise, high-signal entries."""
    t0 = time.perf_counter()
    in_path = input_path or (DEFAULT_LOG_PATH if os.path.exists(DEFAULT_LOG_PATH) else None)

    if not in_path or not os.path.exists(in_path):
        return {
            "distiller": "memory",
            "action": "distill",
            "status": "FAILURE",
            "error": f"Input log file not found: {in_path}",
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }

    # Check if input is standard loop.log format or arbitrary text file
    has_round_header = False
    try:
        with open(in_path, "r", encoding="utf-8", errors="replace") as f:
            has_round_header = "=== ROUND" in f.read(2048)
    except Exception:
        pass
    is_loop_log = os.path.basename(in_path) == "loop.log" or has_round_header

    distilled_rounds = []
    summary_lines = []

    if is_loop_log:
        parsed_rounds = parse_loop_log(in_path)
        if round_limit and round_limit > 0:
            parsed_rounds = parsed_rounds[-round_limit:]

        for pr in parsed_rounds:
            r_num = pr.get("round", "?")
            v_status = pr.get("verdict", "UNKNOWN")
            dur = f" ({pr['duration_s']}s)" if pr.get("duration_s") else ""
            scout_info = f" | scout: {pr['scout']}" if pr.get("scout") else ""
            mgr_chars = pr.get("manager", {}).get("chars", 0)
            exec_chars = pr.get("executor", {}).get("chars", 0)
            warns = f" | {len(pr['warnings'])} warnings" if pr.get("warnings") else ""
            errs = f" | {len(pr['errors'])} errors" if pr.get("errors") else ""

            dist_line = f"• Round {r_num:02d} [{v_status}]{dur}: Mgr {mgr_chars}c -> Exec {exec_chars}c{scout_info}{warns}{errs}"
            summary_lines.append(dist_line)
            distilled_rounds.append({
                "round": r_num,
                "verdict": v_status,
                "duration_s": pr.get("duration_s"),
                "manager_chars": mgr_chars,
                "executor_chars": exec_chars,
                "warnings_count": len(pr.get("warnings", [])),
                "errors_count": len(pr.get("errors", [])),
            })
    else:
        with open(in_path, "r", encoding="utf-8", errors="replace") as f:
            raw_text = f.read()

        lines = raw_text.splitlines()
        char_count = len(raw_text)
        line_count = len(lines)

        # Extract high-signal markers (Headers, PASS/KILL, Errors, Watermarks)
        key_lines = []
        for idx, line in enumerate(lines, start=1):
            l_str = line.strip()
            if not l_str:
                continue
            if l_str.startswith("#") or "PASS" in l_str or "KILL" in l_str or "ERROR" in l_str or WATERMARK in l_str:
                key_lines.append(f"L{idx:03d}: {l_str[:120]}")

        dist_summary = f"Distilled {char_count} chars ({line_count} lines) into {len(key_lines)} high-signal markers."
        summary_lines.append(dist_summary)
        summary_lines.extend(key_lines[:25])
        distilled_rounds.append({
            "raw_lines": line_count,
            "raw_chars": char_count,
            "signals_extracted": len(key_lines),
        })

    full_distillation_text = (
        f"## Distillation {datetime.datetime.now():%Y-%m-%d %H:%M} {WATERMARK}\n"
        + "\n".join(summary_lines)
        + "\n"
    )

    if output_path:
        try:
            with open(output_path, "a", encoding="utf-8") as f:
                f.write("\n" + full_distillation_text + "\n")
        except Exception as exc:
            return {
                "distiller": "memory",
                "action": "distill",
                "status": "FAILURE",
                "error": f"Failed writing to output {output_path}: {exc}",
                "latency_s": round(time.perf_counter() - t0, 4),
                "mark": WATERMARK,
            }

    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "distiller": "memory",
        "action": "distill",
        "status": "SUCCESS",
        "input": in_path,
        "output": output_path,
        "rounds_distilled": len(distilled_rounds),
        "distillation": summary_lines,
        "summary_text": "\n".join(summary_lines),
        "latency_s": elapsed,
        "timestamp": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }


# =====================================================================
# Mode 3: `--query` Engine
# =====================================================================

def query_memory(
    pattern: str,
    verdict_filter: Optional[str] = None,
    tag_filter: Optional[str] = None,
    date_filter: Optional[str] = None,
    memory_dir: Optional[str] = None,
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    """Search historical memory entries by keyword, tag, regex, or verdict."""
    t0 = time.perf_counter()
    mem_dir = resolve_memory_dir(memory_dir)
    records = parse_all_memory(mem_dir)

    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        # Fallback to escaped literal match if regex pattern is invalid
        regex = re.compile(re.escape(pattern), flags)

    matches = []
    pass_matches = 0
    kill_matches = 0

    for rec in records:
        # Check verdict filter if specified
        if verdict_filter:
            v_req = verdict_filter.strip().upper()
            if rec.get("verdict", "").upper() != v_req and v_req not in rec.get("raw_verdict", "").upper():
                continue

        # Check tag filter if specified
        if tag_filter:
            t_req = tag_filter.strip().lower()
            rec_tags = [t.lower() for t in rec.get("tags", [])]
            if t_req not in rec_tags and not any(t_req in t for t in rec_tags):
                continue

        # Check date filter if specified
        if date_filter:
            d_req = date_filter.strip()
            if d_req not in rec.get("date", "") and d_req not in rec.get("timestamp", ""):
                continue

        # Search pattern in record fields
        searchable_text = "\n".join([
            str(rec.get("round", "")),
            rec.get("verdict", ""),
            rec.get("step", ""),
            rec.get("evidence", ""),
            rec.get("lessons", ""),
            rec.get("next_step", ""),
            " ".join(rec.get("tags", [])),
            rec.get("raw_text", ""),
        ])

        found = regex.search(searchable_text)
        if found:
            # Extract snippet
            start_pos = max(0, found.start() - 60)
            end_pos = min(len(searchable_text), found.end() + 60)
            snippet = searchable_text[start_pos:end_pos].replace("\n", " ")

            matches.append({
                "round": rec.get("round"),
                "verdict": rec.get("verdict"),
                "date": rec.get("date"),
                "time": rec.get("time"),
                "timestamp": rec.get("timestamp"),
                "step": rec.get("step", "")[:180],
                "evidence": rec.get("evidence", "")[:240],
                "lessons": rec.get("lessons", "")[:140],
                "file": rec.get("source_file"),
                "snippet": f"...{snippet}...",
            })

            if rec.get("verdict") == "PASS":
                pass_matches += 1
            elif rec.get("verdict") == "KILL":
                kill_matches += 1

    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "action": "query",
        "pattern": pattern,
        "verdict_filter": verdict_filter,
        "tag_filter": tag_filter,
        "date_filter": date_filter,
        "memory_dir": mem_dir,
        "total_records_scanned": len(records),
        "total_matches": len(matches),
        "pass_matches": pass_matches,
        "kill_matches": kill_matches,
        "matches": matches,
        "latency_s": elapsed,
        "timestamp": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }


# =====================================================================
# Mode 4: `--timeline` Engine
# =====================================================================

def generate_timeline(
    memory_dir: Optional[str] = None,
    loop_dir: Optional[str] = None,
    date_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Generate a formatted chronological timeline of loop rounds."""
    t0 = time.perf_counter()
    mem_dir = resolve_memory_dir(memory_dir)
    lp_dir = resolve_loop_dir(loop_dir)

    mem_records = parse_all_memory(mem_dir)
    log_rounds = parse_loop_log(os.path.join(lp_dir, "loop.log"))

    # Index log rounds by round number for fast enrichment
    log_by_round = {lr.get("round"): lr for lr in log_rounds if lr.get("round") is not None}

    timeline_items = []
    for rec in mem_records:
        if date_filter and date_filter not in rec.get("date", ""):
            continue

        r_num = rec.get("round")
        log_entry = log_by_round.get(r_num, {})

        step_snip = rec.get("step", "").strip().replace("\n", " ")
        if len(step_snip) > 90:
            step_snip = step_snip[:87] + "..."

        lessons_snip = rec.get("lessons", "").strip().replace("\n", " ")
        if len(lessons_snip) > 80:
            lessons_snip = lessons_snip[:77] + "..."

        timeline_items.append({
            "round": r_num if r_num is not None else "?",
            "verdict": rec.get("verdict", "UNKNOWN"),
            "date": rec.get("date"),
            "time": rec.get("time"),
            "timestamp": rec.get("timestamp"),
            "step_summary": step_snip or "(No step recorded)",
            "lessons": lessons_snip,
            "duration_s": log_entry.get("duration_s"),
            "file": os.path.basename(rec.get("source_file", "")),
        })

    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "action": "timeline",
        "total_rounds": len(timeline_items),
        "date_filter": date_filter,
        "memory_dir": mem_dir,
        "timeline": timeline_items,
        "latency_s": elapsed,
        "timestamp": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }


# =====================================================================
# Mode 5: `--stats` Engine
# =====================================================================

def compute_stats(
    memory_dir: Optional[str] = None,
    loop_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute pass/fail rates, latency averages, and module coverage."""
    t0 = time.perf_counter()
    mem_dir = resolve_memory_dir(memory_dir)
    lp_dir = resolve_loop_dir(loop_dir)

    mem_records = parse_all_memory(mem_dir)
    log_rounds = parse_loop_log(os.path.join(lp_dir, "loop.log"))

    total_rounds = len(mem_records)
    pass_count = sum(1 for r in mem_records if r.get("verdict") == "PASS")
    kill_count = sum(1 for r in mem_records if r.get("verdict") == "KILL")
    warn_count = sum(1 for r in mem_records if r.get("verdict") == "WARN")
    other_count = total_rounds - (pass_count + kill_count + warn_count)

    evaluated_rounds = pass_count + kill_count
    pass_rate = round((pass_count / evaluated_rounds * 100.0), 2) if evaluated_rounds > 0 else 100.0

    # Timing analysis from log rounds
    durations = [r["duration_s"] for r in log_rounds if r.get("duration_s") is not None]
    avg_latency = round(sum(durations) / len(durations), 2) if durations else 0.0
    min_latency = min(durations) if durations else 0.0
    max_latency = max(durations) if durations else 0.0

    # Module coverage analysis across all round steps, evidence, and notes
    module_mentions: Dict[str, Dict[str, Any]] = {}
    for mod in TRACKED_MODULES:
        pattern = re.compile(rf"\b{re.escape(mod)}\b", re.IGNORECASE)
        matching_rounds = []
        for r in mem_records:
            full_text = f"{r.get('step', '')} {r.get('evidence', '')} {r.get('lessons', '')}"
            if pattern.search(full_text):
                matching_rounds.append(r.get("round"))

        module_mentions[mod] = {
            "mentions_count": len(matching_rounds),
            "rounds": matching_rounds,
            "covered": len(matching_rounds) > 0,
        }

    # Daily breakdown
    daily_stats: Dict[str, Dict[str, int]] = collections.defaultdict(lambda: {"total": 0, "pass": 0, "kill": 0})
    for r in mem_records:
        d = r.get("date", "unknown")
        daily_stats[d]["total"] += 1
        if r.get("verdict") == "PASS":
            daily_stats[d]["pass"] += 1
        elif r.get("verdict") == "KILL":
            daily_stats[d]["kill"] += 1

    elapsed = round(time.perf_counter() - t0, 4)

    return {
        "action": "stats",
        "memory_dir": mem_dir,
        "total_rounds": total_rounds,
        "verdicts": {
            "pass": pass_count,
            "kill": kill_count,
            "warn": warn_count,
            "other": other_count,
            "pass_rate_pct": pass_rate,
        },
        "latency_stats": {
            "avg_round_duration_s": avg_latency,
            "min_round_duration_s": min_latency,
            "max_round_duration_s": max_latency,
            "rounds_measured": len(durations),
        },
        "module_coverage": module_mentions,
        "daily_breakdown": dict(daily_stats),
        "latency_s": elapsed,
        "timestamp": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }


# =====================================================================
# Console Renderers
# =====================================================================

def render_append_report(res: Dict[str, Any]) -> str:
    lines = [
        f"🦋 X.O.L.A. Memory Engine — Round Appended 🦋",
        "=" * 68,
        f"Status       : {res.get('status')}",
        f"Round Index  : {res.get('round')}",
        f"Verdict      : {res.get('verdict')}",
        f"Target File  : {res.get('file')}",
        f"Bytes Written: {res.get('bytes_written')} bytes",
        f"Timestamp    : {res.get('timestamp')}",
        f"Latency      : {res.get('latency_s')}s",
        "=" * 68,
    ]
    return "\n".join(lines)


def render_distill_report(res: Dict[str, Any]) -> str:
    lines = [
        f"🦋 X.O.L.A. Memory Distiller — High-Signal Summary 🦋",
        "=" * 68,
        f"Status       : {res.get('status')}",
        f"Input Log    : {res.get('input')}",
        f"Output Target: {res.get('output') or '(stdout only)'}",
        f"Rounds Dist. : {res.get('rounds_distilled')}",
        f"Latency      : {res.get('latency_s')}s",
        "-" * 68,
        "Distilled Signals:",
    ]
    for d_line in res.get("distillation", []):
        lines.append(f"  {d_line}")
    lines.append("=" * 68)
    return "\n".join(lines)


def render_query_report(res: Dict[str, Any]) -> str:
    lines = [
        f"🦋 X.O.L.A. Memory Query — Search Results 🦋",
        "=" * 68,
        f"Query Pattern: '{res.get('pattern')}'",
        f"Scanned      : {res.get('total_records_scanned')} records across {res.get('memory_dir')}",
        f"Matches Found: {res.get('total_matches')} ({res.get('pass_matches')} PASS, {res.get('kill_matches')} KILL)",
        f"Latency      : {res.get('latency_s')}s",
        "-" * 68,
    ]
    matches = res.get("matches", [])
    if not matches:
        lines.append("  (No matching historical memory records found)")
    else:
        for idx, m in enumerate(matches, start=1):
            r_str = f"Round {m.get('round', '?')}" if m.get("round") is not None else "Entry"
            v_str = f"[{m.get('verdict', 'UNKNOWN')}]"
            lines.append(f"[{idx:02d}] {r_str} {v_str} ({m.get('timestamp')}) in {os.path.basename(m.get('file', ''))}:")
            lines.append(f"     Step    : {m.get('step')}")
            if m.get("lessons"):
                lines.append(f"     Lessons : {m.get('lessons')}")
            lines.append(f"     Snippet : {m.get('snippet')}")
            lines.append("")
    lines.append("=" * 68)
    return "\n".join(lines)


def render_timeline_report(res: Dict[str, Any]) -> str:
    lines = [
        f"🦋 X.O.L.A. Memory Engine — Chronological Timeline 🦋",
        "=" * 76,
        f"Total Rounds : {res.get('total_rounds')}",
        f"Memory Root  : {res.get('memory_dir')}",
        f"Latency      : {res.get('latency_s')}s",
        "-" * 76,
        f"{'RND':<5} | {'TIME':<16} | {'STATUS':<6} | {'STEP EXECUTED / MILESTONE':<42}",
        "-" * 76,
    ]
    timeline = res.get("timeline", [])
    for t in timeline:
        r_str = f"r{t.get('round', '?')}"
        ts_str = f"{t.get('date', '')} {t.get('time', '')}"[:16]
        v_str = t.get("verdict", "UNKNOWN")[:6]
        step_snip = t.get("step_summary", "")[:42]
        lines.append(f"{r_str:<5} | {ts_str:<16} | {v_str:<6} | {step_snip:<42}")
    lines.append("=" * 76)
    return "\n".join(lines)


def render_stats_report(res: Dict[str, Any]) -> str:
    v = res.get("verdicts", {})
    lat = res.get("latency_stats", {})
    cov = res.get("module_coverage", {})

    lines = [
        f"🦋 X.O.L.A. Memory Engine — Performance & Coverage Analytics 🦋",
        "=" * 72,
        f"Total Rounds Recorded : {res.get('total_rounds')}",
        f"Pass / Kill Rate      : {v.get('pass', 0)} PASS | {v.get('kill', 0)} KILL | {v.get('warn', 0)} WARN ({v.get('pass_rate_pct', 0.0)}% Pass Rate)",
        f"Round Latency Avg     : {lat.get('avg_round_duration_s', 0.0)}s (min: {lat.get('min_round_duration_s', 0.0)}s, max: {lat.get('max_round_duration_s', 0.0)}s)",
        f"Engine Scan Latency   : {res.get('latency_s', 0.0)}s",
        "-" * 72,
        "Subsystem & Module Coverage:",
    ]

    for mod, data in cov.items():
        st = "[COV]" if data.get("covered") else "[GAP]"
        r_list = data.get("rounds", [])
        r_str = f"(Rounds: {', '.join(str(r) for r in r_list)})" if r_list else "(None)"
        lines.append(f"  {st} {mod:<16} : {data.get('mentions_count', 0):>2} mention(s) {r_str}")

    daily = res.get("daily_breakdown", {})
    if daily:
        lines.append("-" * 72)
        lines.append("Daily Activity Breakdown:")
        for d, d_stat in daily.items():
            lines.append(f"  • {d} : {d_stat.get('total', 0)} rounds ({d_stat.get('pass', 0)} PASS, {d_stat.get('kill', 0)} KILL)")

    lines.append("=" * 72)
    return "\n".join(lines)


# =====================================================================
# CLI Entrypoint
# =====================================================================

def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="xola-memory — Round distiller, memory query engine, and analytics 🦋",
        epilog="Usage: python memory.py [--append] [--distill] [--query PATTERN] [--timeline] [--stats] [--json]",
    )

    # Core Action Flags
    action_group = parser.add_argument_group("Action Modes")
    action_group.add_argument("--append", action="store_true", help="Append structured round record to memory file")
    action_group.add_argument("--distill", action="store_true", help="Distill raw loop logs into concise summaries")
    action_group.add_argument("--query", "-q", nargs="?", const="", default=None, help="Query historical memory entries")
    action_group.add_argument("--timeline", action="store_true", help="Generate chronological timeline of all rounds")
    action_group.add_argument("--stats", action="store_true", help="Compute pass/fail rates, latency, and module coverage")

    # Parameters for --append and filters
    param_group = parser.add_argument_group("Record & Filter Options")
    param_group.add_argument("--round", "-r", type=int, default=None, help="Round index number")
    param_group.add_argument("--step", "-s", default="", help="Step executed or goal description")
    param_group.add_argument("--evidence", "-e", default="", help="Tool execution evidence and outputs")
    param_group.add_argument("--verdict", "-v", default="PASS", help="Guard audit verdict (PASS, KILL, WARN)")
    param_group.add_argument("--lessons", "-l", default="", help="Key lessons learned")
    param_group.add_argument("--next-step", "-n", default="", help="Next planned objective")
    param_group.add_argument("--tags", "-t", default="", help="Comma-separated tags")
    param_group.add_argument("--lane", default=None, help="Execution lane used (agy, opencode, python)")
    param_group.add_argument("--latency", type=float, default=None, help="Measured execution latency in seconds")

    # Path & Output Options
    io_group = parser.add_argument_group("I/O & Formatting")
    io_group.add_argument("--input", "-i", default=None, help="Input file to distill or process")
    io_group.add_argument("--output", "-o", default=None, help="Output destination file")
    io_group.add_argument("--memory-dir", default=None, help="Custom memory directory path")
    io_group.add_argument("--loop-dir", default=None, help="Custom loop directory path")
    io_group.add_argument("--date", "-d", default=None, help="Target date filter or append date (YYYY-MM-DD)")
    io_group.add_argument("--limit", type=int, default=None, help="Limit number of items processed")
    io_group.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    return parser


def main():
    parser = build_cli_parser()
    args = parser.parse_args()

    # If no action mode is explicitly selected, default to showing stats or timeline
    if not (args.append or args.distill or args.query is not None or args.timeline or args.stats):
        # Default behavior: run stats
        args.stats = True

    try:
        if args.append:
            tags_list = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
            res = append_round(
                round_idx=args.round,
                step=args.step,
                evidence=args.evidence,
                verdict=args.verdict,
                lessons=args.lessons,
                next_step=args.next_step,
                tags=tags_list,
                lane=args.lane,
                latency=args.latency,
                memory_dir=args.memory_dir,
                target_date=args.date,
                output_path=args.output,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(render_append_report(res))
            sys.exit(0 if res.get("status") == "SUCCESS" else 1)

        elif args.distill:
            res = distill_logs(
                input_path=args.input,
                output_path=args.output,
                round_limit=args.limit,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(render_distill_report(res))
            sys.exit(0 if res.get("status") == "SUCCESS" else 1)

        elif args.query is not None:
            pattern_to_search = args.query or args.step or ""
            res = query_memory(
                pattern=pattern_to_search,
                verdict_filter=args.verdict if args.verdict != "PASS" or ("--verdict" in sys.argv or "-v" in sys.argv) else None,
                tag_filter=args.tags if args.tags else None,
                date_filter=args.date,
                memory_dir=args.memory_dir,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(render_query_report(res))
            sys.exit(0)

        elif args.timeline:
            res = generate_timeline(
                memory_dir=args.memory_dir,
                loop_dir=args.loop_dir,
                date_filter=args.date,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(render_timeline_report(res))
            sys.exit(0)

        elif args.stats:
            res = compute_stats(
                memory_dir=args.memory_dir,
                loop_dir=args.loop_dir,
            )
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(render_stats_report(res))
            sys.exit(0)

    except Exception as exc:
        print(f"ERROR in xola-memory: {exc} {WATERMARK}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
