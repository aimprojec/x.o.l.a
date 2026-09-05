#!/usr/bin/env python3
"""Usage: python guard.py [--target PATH] [--all] [--strict] [--fix] [--smoke] [--json] # xola-guard: red-team reviewer that kills slop before checkpoint 🦋"""

import argparse
import ast
import datetime
import json
import os
import re
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
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Stdlib module names detection
STDLIB_MODULES = set(getattr(sys, "stdlib_module_names", sys.builtin_module_names))

# Directories to ignore during recursive tree audits
IGNORE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    ".gemini",
    ".system_generated",
    "dist",
    "build",
    ".egg-info",
    # Runtime artifact directories: machine-generated data, not source 🦋
    "archive",
    "outbox",
    "done",
    "snapshots",
    "lh10",
}

# File extensions to audit
AUDIT_EXTENSIONS = {
    ".py",
    ".json",
    ".md",
    ".txt",
    ".html",
    ".js",
    ".ts",
    ".sh",
    ".cmd",
    ".bat",
    ".toml",
    ".yaml",
    ".yml",
}

# Known unauthorized paid / heavy external SDKs (Xola enforces stdlib first & free CLI lanes)
UNAUTHORIZED_PAID_SDKS = {
    "openai": "OpenAI Paid API client (use free agy/opencode CLI instead)",
    "anthropic": "Anthropic Paid API client (use free agy/opencode CLI instead)",
    "cohere": "Cohere Paid API client (use free agy/opencode CLI instead)",
    "replicate": "Replicate Paid API client (use free agy/opencode CLI instead)",
    "boto3": "AWS Paid SDK (boto3)",
    "botocore": "AWS Paid SDK (botocore)",
    "google.generativeai": "Google Generative AI direct paid SDK (use agy CLI instead)",
    "langchain": "LangChain heavy framework (enforce stdlib first)",
    "langsmith": "LangSmith tracing framework",
    "llama_index": "LlamaIndex framework (enforce stdlib first)",
    "groq": "Groq API client",
    "together": "Together AI API client",
    "mistralai": "Mistral AI API client",
}

# Known internal / project package roots
PROJECT_INTERNAL_PACKAGES = {
    "tools",
    "tests",
    "agents",
    "loop",
    "memory",
    "reports",
    "lh_harness",
    "xola_lh_bridge",
    "server",
    "cli",
    "jarvis",
}

# Secret / credential detection patterns (regex, rule_name, description)
SECRET_RULES = [
    (
        r"\b(?:sk-[a-zA-Z0-9_-]{20,}|sk-proj-[a-zA-Z0-9_-]{20,})\b",
        "SECRET_OPENAI_KEY",
        "OpenAI API Key (sk-...)",
    ),
    (
        r"\b(?:sk-ant-[a-zA-Z0-9_-]{20,})\b",
        "SECRET_ANTHROPIC_KEY",
        "Anthropic API Key (sk-ant-...)",
    ),
    (
        r"\b(?:AIza[0-9A-Za-z-_]{35})\b",
        "SECRET_GOOGLE_KEY",
        "Google AI / Gemini API Key (AIza...)",
    ),
    (
        r"\b(?:AKIA[0-9A-Z]{16})\b",
        "SECRET_AWS_KEY_ID",
        "AWS Access Key ID (AKIA...)",
    ),
    (
        r"""(?i)\b(?:aws_secret_access_key|aws_secret_key)\s*=\s*['"]([a-zA-Z0-9/+=]{40})['"]""",
        "SECRET_AWS_SECRET_KEY",
        "AWS Secret Access Key",
    ),
    (
        r"\b(?:(?:ghp|gho|ghu|ghs|ghr)_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{22,})\b",
        "SECRET_GITHUB_TOKEN",
        "GitHub Personal Access Token",
    ),
    (
        r"\b(?:xox[baprs]-[0-9a-zA-Z]{10,48})\b",
        "SECRET_SLACK_TOKEN",
        "Slack Token (xox...)",
    ),
    (
        r"-----BEGIN (?:[A-Z0-9_-]+ )?PRIVATE KEY-----",
        "SECRET_PRIVATE_KEY",
        "Private Key Header",
    ),
    (
        r"""(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|client[_-]?secret)\s*=\s*['"]([a-zA-Z0-9_\-\.]{16,})['"]""",
        "SECRET_GENERIC_KEY",
        "Hardcoded Generic API Key / Secret Token",
    ),
    (
        r"""(?i)\b(?:password|passwd|pwd)\s*=\s*['"]([^'"]{6,})['"]""",
        "SECRET_HARDCODED_PASSWORD",
        "Hardcoded Password Assignment",
    ),
    (
        r"""(?i)\bbearer\s+([a-zA-Z0-9_\-\.]{20,})""",
        "SECRET_BEARER_TOKEN",
        "Hardcoded Bearer Auth Token",
    ),
]

# Common benign placeholder values to ignore
BENIGN_PLACEHOLDER_SUBSTRINGS = {
    "your_api_key",
    "your_key",
    "your-key",
    "your-api-key",
    "your_token",
    "your-token",
    "your_password",
    "example",
    "placeholder",
    "dummy",
    "fake",
    "test",
    "replace_me",
    "none",
    "default",
    "sk-proj-test",
    "aizafake",
    "sk-xxx",
    "aiza-xxx",
    "xxx",
    "...",
    "<api_key>",
    "<token>",
    "${",
    "process.env",
    "os.environ",
}


def redact_secret(val: str) -> str:
    """Safely redact secret tokens for reporting."""
    clean = str(val).strip()
    if len(clean) <= 8:
        return "****"
    prefix = clean[:4]
    suffix = clean[-4:]
    return f"{prefix}****{suffix} [len {len(clean)}]"


def is_benign_placeholder(val: str) -> bool:
    """Check if matched string is a documentation placeholder or benign dummy value."""
    lower = val.lower().strip()
    if any(sub in lower for sub in BENIGN_PLACEHOLDER_SUBSTRINGS):
        return True
    # All repeating characters or dummy sequences
    if len(set(lower)) <= 3:
        return True
    return False


# =====================================================================
# 1) Syntax and AST Compilation Verification
# =====================================================================

def check_syntax_and_ast(file_path: str, content: str) -> list[dict]:
    """Verify syntax and AST compilation for code files."""
    findings = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".py":
        try:
            tree = ast.parse(content, filename=file_path)
            # Verify code object compilation
            compile(content, file_path, "exec")
        except SyntaxError as e:
            line_str = f" (line {e.lineno}, col {e.offset})" if e.lineno else ""
            snippet = f": {e.text.strip()}" if e.text else ""
            findings.append({
                "rule": "AST_SYNTAX_ERROR",
                "severity": "KILL",
                "file": file_path,
                "line": e.lineno or 1,
                "col": e.offset or 1,
                "message": f"SyntaxError{line_str}: {e.msg}{snippet}",
            })
        except Exception as e:
            findings.append({
                "rule": "AST_PARSE_ERROR",
                "severity": "KILL",
                "file": file_path,
                "line": 1,
                "col": 1,
                "message": f"AST compilation error: {e}",
            })

    elif ext == ".json":
        try:
            json.loads(content)
        except json.JSONDecodeError as e:
            findings.append({
                "rule": "JSON_SYNTAX_ERROR",
                "severity": "KILL",
                "file": file_path,
                "line": e.lineno,
                "col": e.colno,
                "message": f"JSON syntax error at line {e.lineno}, col {e.colno}: {e.msg}",
            })

    return findings


# =====================================================================
# 2) Secret / Credential Leak Detection
# =====================================================================

def check_secret_leaks(file_path: str, content: str) -> list[dict]:
    """Detect potential credentials, API keys, and secrets."""
    findings = []
    # Avoid scanning guard.py or test_guard.py itself for regex rule definition matches
    is_guard_tool = os.path.basename(file_path) in ("guard.py", "test_guard.py")

    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        # Skip comment lines explaining rules or regex in guard/testing tools
        if is_guard_tool and ("SECRET_RULES" in line or "SECRET_" in line or "r\"" in line or "r'" in line):
            continue

        for pattern, rule_name, desc in SECRET_RULES:
            matches = re.finditer(pattern, line)
            for m in matches:
                # Extract matched token or capture group
                matched_token = m.group(1) if m.groups() else m.group(0)
                if not matched_token:
                    continue

                if is_benign_placeholder(matched_token):
                    continue

                # In code files, exclude regex patterns like r"sk-..."
                if "\\b" in line or "[a-zA-Z" in line or "re.compile" in line:
                    continue

                redacted = redact_secret(matched_token)
                findings.append({
                    "rule": rule_name,
                    "severity": "KILL",
                    "file": file_path,
                    "line": line_idx,
                    "col": m.start() + 1,
                    "message": f"CRITICAL: Potential secret leak detected ({desc}): {redacted}",
                })

    return findings


# =====================================================================
# 3) 🦋 Watermark Presence Verification
# =====================================================================

def check_watermark_presence(file_path: str, content: str) -> list[dict]:
    """Verify presence of the required 🦋 watermark."""
    findings = []
    has_mark = (WATERMARK in content) or (r"\ud83e\udd8b" in content)
    if not has_mark:
        findings.append({
            "rule": "WATERMARK_MISSING",
            "severity": "WARN",
            "file": file_path,
            "line": 1,
            "col": 1,
            "message": f"Missing required {WATERMARK} watermark in file content",
        })
    return findings


# =====================================================================
# 4) Dependency Analysis (Enforce stdlib first, flag paid libraries)
# =====================================================================

def check_dependencies(file_path: str, content: str) -> list[dict]:
    """Analyze imports in Python files, enforce pure stdlib, and flag unauthorized paid SDKs."""
    findings = []
    ext = os.path.splitext(file_path)[1].lower()
    if ext != ".py":
        return findings

    try:
        tree = ast.parse(content, filename=file_path)
    except Exception:
        return findings  # Syntax check handles syntax failures

    for node in ast.walk(tree):
        imported_pkgs = []
        lineno = getattr(node, "lineno", 1)

        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_pkgs.append((alias.name, alias.name.split(".")[0]))
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                imported_pkgs.append((node.module, node.module.split(".")[0]))

        for full_name, top_pkg in imported_pkgs:
            # Check unauthorized paid libraries first
            if full_name in UNAUTHORIZED_PAID_SDKS or top_pkg in UNAUTHORIZED_PAID_SDKS:
                reason = UNAUTHORIZED_PAID_SDKS.get(full_name) or UNAUTHORIZED_PAID_SDKS.get(top_pkg)
                findings.append({
                    "rule": "UNAUTHORIZED_PAID_DEPENDENCY",
                    "severity": "KILL",
                    "file": file_path,
                    "line": lineno,
                    "col": 1,
                    "message": f"Unauthorized paid/restricted dependency '{full_name}': {reason}",
                })
            # Check if non-stdlib and non-internal
            elif top_pkg not in STDLIB_MODULES and top_pkg not in PROJECT_INTERNAL_PACKAGES:
                # Check if it's a local file next to target
                target_dir = os.path.dirname(os.path.abspath(file_path))
                local_candidate = os.path.join(target_dir, f"{top_pkg}.py")
                local_dir = os.path.join(target_dir, top_pkg)
                if not os.path.exists(local_candidate) and not os.path.exists(local_dir):
                    findings.append({
                        "rule": "EXTERNAL_NON_STDLIB_DEPENDENCY",
                        "severity": "WARN",
                        "file": file_path,
                        "line": lineno,
                        "col": 1,
                        "message": f"External non-stdlib dependency imported: '{top_pkg}'",
                    })

    return findings


# =====================================================================
# 5) Optional Execution Smoke Tests
# =====================================================================

def run_smoke_test(file_path: str, timeout: float = 8.0) -> dict:
    """Run lightweight CLI smoke test on Python file to verify clean invocation."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext != ".py":
        return {"status": "SKIPPED", "msg": "Non-python file"}

    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            [sys.executable, file_path, "--help"],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
        latency = time.perf_counter() - t0
        if proc.returncode == 0:
            return {
                "status": "PASS",
                "latency_s": round(latency, 4),
                "msg": f"Clean --help execution (returncode 0, {latency:.3f}s)",
            }
        else:
            err_snip = (proc.stderr or proc.stdout or "").strip()[:160].replace("\n", " ")
            return {
                "status": "FAIL",
                "latency_s": round(latency, 4),
                "returncode": proc.returncode,
                "msg": f"Smoke test returned non-zero code {proc.returncode}: {err_snip}",
            }
    except subprocess.TimeoutExpired:
        return {
            "status": "FAIL",
            "latency_s": round(time.perf_counter() - t0, 4),
            "msg": f"Smoke test timed out after {timeout}s",
        }
    except Exception as exc:
        return {
            "status": "FAIL",
            "latency_s": round(time.perf_counter() - t0, 4),
            "msg": f"Smoke test execution error: {exc}",
        }


# =====================================================================
# Auto-Fix Engine (--fix)
# =====================================================================

def apply_fixes(file_path: str, content: str, findings: list[dict]) -> tuple[str, list[dict]]:
    """Automatically fix remediable issues (such as missing 🦋 watermark)."""
    fixes_applied = []
    new_content = content
    ext = os.path.splitext(file_path)[1].lower()

    watermark_findings = [f for f in findings if f["rule"] == "WATERMARK_MISSING"]
    if watermark_findings and WATERMARK not in new_content:
        if ext == ".py":
            # If docstring at start, append watermark to docstring
            docstring_match = re.search(r'^(#!\s*/[^\n]+\n)?\s*([rubRUB]*"""[\s\S]*?"""|[rubRUB]*\'\'\'[\s\S]*?\'\'\')', new_content)
            if docstring_match:
                orig_doc = docstring_match.group(2)
                closing = orig_doc[-3:]
                inner = orig_doc[:-3].rstrip()
                fixed_doc = f"{inner} {WATERMARK}{closing}"
                new_content = new_content[:docstring_match.start(2)] + fixed_doc + new_content[docstring_match.end(2):]
                fixes_applied.append({"file": file_path, "fix": f"Injected {WATERMARK} watermark into module docstring"})
            else:
                # Prepend watermark header
                lines = new_content.splitlines(keepends=True)
                if lines and lines[0].startswith("#!"):
                    new_content = lines[0] + f'"""X.O.L.A. component {WATERMARK}"""\n\n' + "".join(lines[1:])
                else:
                    new_content = f'"""X.O.L.A. component {WATERMARK}"""\n\n' + new_content
                fixes_applied.append({"file": file_path, "fix": f"Added {WATERMARK} watermark docstring at file start"})

        elif ext == ".md":
            lines = new_content.splitlines(keepends=True)
            if lines and lines[0].startswith("#"):
                lines[0] = lines[0].rstrip() + f" {WATERMARK}\n"
                new_content = "".join(lines)
            else:
                new_content = f"<!-- {WATERMARK} X.O.L.A. -->\n\n" + new_content
            fixes_applied.append({"file": file_path, "fix": f"Appended {WATERMARK} watermark to Markdown header"})

        elif ext == ".json":
            try:
                data = json.loads(new_content)
                if isinstance(data, dict) and "mark" not in data:
                    data["mark"] = WATERMARK
                    new_content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
                    fixes_applied.append({"file": file_path, "fix": f"Added 'mark': '{WATERMARK}' to JSON object"})
            except Exception:
                pass

    if fixes_applied and new_content != content:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    return new_content, fixes_applied


# =====================================================================
# Incremental Audit Cache (warm-run accelerator) 🦋
# =====================================================================

AUDIT_CACHE_FILENAME = ".guard_cache.json"


def _audit_cache_path(target: str) -> str:
    """Cache lives beside the audit target root as a hidden dotfile."""
    t = target if os.path.isdir(target) else (os.path.dirname(os.path.abspath(target)) or ".")
    return os.path.join(t, AUDIT_CACHE_FILENAME)


def _load_audit_cache(target: str, enabled: bool):
    """Load prior per-file results; return None when cache is disabled."""
    if not enabled:
        return None
    try:
        p = _audit_cache_path(target)
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_audit_cache(target: str, cache: dict) -> None:
    """Atomically persist the cache; failures degrade silently to no-cache."""
    try:
        p = _audit_cache_path(target)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(cache, fh, ensure_ascii=False)
        os.replace(tmp, p)
    except Exception:
        pass


def _cache_key(file_path: str, strict: bool) -> str:
    """Cache identity: strict flag + nanosecond mtime + size + path."""
    st = os.stat(file_path)
    return f"{int(strict)}|{st.st_mtime_ns}:{st.st_size}:{os.path.abspath(file_path)}"


# =====================================================================
# Main Audit Engine
# =====================================================================

def collect_files(target_path: str) -> list[str]:
    """Collect all target files for auditing."""
    if not os.path.exists(target_path):
        return []

    if os.path.isfile(target_path):
        return [os.path.abspath(target_path)]

    collected = []
    for root, dirs, files in os.walk(target_path):
        # Filter ignore dirs in-place
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        for file_name in files:
            # Skip hidden/dot files (e.g. .guard_cache.json) — never audit them 🦋
            if file_name.startswith("."):
                continue
            ext = os.path.splitext(file_name)[1].lower()
            if ext in AUDIT_EXTENSIONS:
                collected.append(os.path.abspath(os.path.join(root, file_name)))

    return sorted(collected)


def audit_file(
    file_path: str,
    strict: bool = False,
    fix: bool = False,
    smoke: bool = False,
) -> dict:
    """Audit an individual file across all 5 checks.

    Existence is verified by the open() guard below: collect_files already
    returns existing paths, and an extra os.path.exists() stat per file
    doubles I/O latency on large audits. 🦋
    """
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as exc:
        return {
            "file": file_path,
            "status": "KILL",
            "findings": [{
                "rule": "FILE_READ_ERROR",
                "severity": "KILL",
                "file": file_path,
                "line": 1,
                "col": 1,
                "message": f"Failed to read file: {exc}",
            }],
            "fixes": [],
            "smoke": None,
        }

    # Run check 1: Syntax & AST
    syntax_findings = check_syntax_and_ast(file_path, content)

    # Run check 2: Secrets
    secret_findings = check_secret_leaks(file_path, content)

    # Run check 3: Watermark
    watermark_findings = check_watermark_presence(file_path, content)

    # Run check 4: Dependencies
    dep_findings = check_dependencies(file_path, content)

    initial_findings = syntax_findings + secret_findings + watermark_findings + dep_findings
    fixes_applied = []

    # Run Auto-Fix if requested
    if fix and initial_findings:
        content, fixes_applied = apply_fixes(file_path, content, initial_findings)
        if fixes_applied:
            # Re-evaluate after fixes
            syntax_findings = check_syntax_and_ast(file_path, content)
            secret_findings = check_secret_leaks(file_path, content)
            watermark_findings = check_watermark_presence(file_path, content)
            dep_findings = check_dependencies(file_path, content)

    all_findings = syntax_findings + secret_findings + watermark_findings + dep_findings

    # Run check 5: Optional Smoke Test
    smoke_res = None
    if smoke and not syntax_findings:
        smoke_res = run_smoke_test(file_path)
        if smoke_res.get("status") == "FAIL":
            all_findings.append({
                "rule": "SMOKE_TEST_FAILED",
                "severity": "KILL" if strict else "WARN",
                "file": file_path,
                "line": 1,
                "col": 1,
                "message": smoke_res.get("msg", "Smoke test failure"),
            })

    # File verdict computation
    has_critical = any(f["severity"] == "KILL" for f in all_findings)
    has_warn = any(f["severity"] == "WARN" for f in all_findings)

    if has_critical:
        file_status = "KILL"
    elif has_warn:
        file_status = "KILL" if strict else "WARN"
    else:
        file_status = "PASS"

    return {
        "file": file_path,
        "status": file_status,
        "findings": all_findings,
        "fixes": fixes_applied,
        "smoke": smoke_res,
    }


def audit(
    target: str = ".",
    strict: bool = False,
    fix: bool = False,
    smoke: bool = False,
    verbose: bool = False,
    use_cache: bool = True,
) -> dict:
    """Execute complete red-team audit suite on target file or directory.

    use_cache: reuse per-file results for unchanged files (mtime_ns+size key).
    fix/smoke runs always bypass the cache because they mutate or execute files.
    """
    t0 = time.perf_counter()

    if not os.path.exists(target):
        return {
            "auditor": "guard",
            "target": target,
            "verdict": "KILL",
            "timestamp": datetime.datetime.now().isoformat(),
            "latency_s": round(time.perf_counter() - t0, 4),
            "strict": strict,
            "mark": WATERMARK,
            "summary": {
                "files_scanned": 0,
                "files_passed": 0,
                "files_warned": 0,
                "files_killed": 1,
                "total_findings": 1,
                "critical_count": 1,
                "warning_count": 0,
                "fixes_applied": 0,
            },
            "findings": [{
                "rule": "TARGET_NOT_FOUND",
                "severity": "KILL",
                "file": target,
                "line": 1,
                "col": 1,
                "message": f"Target path does not exist: {target}",
            }],
            "fixes": [],
            "file_results": {},
        }

    target_files = collect_files(target)
    # Mutating or execution-based runs must always recompute 🦋
    cache = _load_audit_cache(target, enabled=(use_cache and not fix and not smoke))
    cache_dirty = False
    cache_hits = 0
    file_results = {}
    all_findings = []
    all_fixes = []

    files_passed = 0
    files_warned = 0
    files_killed = 0

    syntax_passed = 0
    syntax_failed = 0
    secret_passed = 0
    secret_failed = 0
    watermark_passed = 0
    watermark_failed = 0
    dep_passed = 0
    dep_failed = 0
    smoke_passed = 0
    smoke_failed = 0
    smoke_skipped = 0

    for file_path in target_files:
        ck = None
        res = None
        if cache is not None:
            try:
                ck = _cache_key(file_path, strict)
                res = cache.get(ck)
                if res is not None:
                    cache_hits += 1
            except Exception:
                res = None
        if res is None:
            res = audit_file(file_path, strict=strict, fix=fix, smoke=smoke)
            if cache is not None and ck is not None:
                cache[ck] = res
                cache_dirty = True
        file_results[file_path] = res
        all_findings.extend(res["findings"])
        all_fixes.extend(res["fixes"])

        if res["status"] == "PASS":
            files_passed += 1
        elif res["status"] == "WARN":
            files_warned += 1
        else:
            files_killed += 1

        # Check breakdown metrics
        f_rules = {f["rule"] for f in res["findings"]}
        if any("AST" in r or "SYNTAX" in r for r in f_rules):
            syntax_failed += 1
        else:
            syntax_passed += 1

        if any("SECRET" in r for r in f_rules):
            secret_failed += 1
        else:
            secret_passed += 1

        if "WATERMARK_MISSING" in f_rules:
            watermark_failed += 1
        else:
            watermark_passed += 1

        if any("DEPENDENCY" in r for r in f_rules):
            dep_failed += 1
        else:
            dep_passed += 1

        if res.get("smoke"):
            if res["smoke"].get("status") == "PASS":
                smoke_passed += 1
            elif res["smoke"].get("status") == "FAIL":
                smoke_failed += 1
            else:
                smoke_skipped += 1
        else:
            smoke_skipped += 1

    if cache is not None and cache_dirty:
        _save_audit_cache(target, cache)

    total_scanned = len(target_files)
    critical_count = sum(1 for f in all_findings if f["severity"] == "KILL")
    warning_count = sum(1 for f in all_findings if f["severity"] == "WARN")

    if files_killed > 0 or critical_count > 0:
        overall_verdict = "KILL"
    elif files_warned > 0 or warning_count > 0:
        overall_verdict = "KILL" if strict else "WARN"
    else:
        overall_verdict = "PASS"

    latency = time.perf_counter() - t0

    return {
        "auditor": "guard",
        "target": target,
        "verdict": overall_verdict,
        "timestamp": datetime.datetime.now().isoformat(),
        "latency_s": round(latency, 4),
        "strict": strict,
        "mark": WATERMARK,
        "summary": {
            "files_scanned": total_scanned,
            "files_passed": files_passed,
            "files_warned": files_warned,
            "files_killed": files_killed,
            "total_findings": len(all_findings),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "fixes_applied": len(all_fixes),
            "cache_hits": cache_hits,
        },
        "checks": {
            "syntax_ast": {"passed": syntax_passed, "failed": syntax_failed},
            "secret_detection": {"passed": secret_passed, "failed": secret_failed},
            "watermark": {"passed": watermark_passed, "failed": watermark_failed},
            "dependencies": {"passed": dep_passed, "failed": dep_failed},
            "smoke_tests": {
                "passed": smoke_passed,
                "failed": smoke_failed,
                "skipped": smoke_skipped,
            },
        },
        "findings": all_findings,
        "fixes": all_fixes,
        "file_results": file_results,
    }


# =====================================================================
# Rendering & Console UI
# =====================================================================

def render_report(res: dict, verbose: bool = False) -> str:
    """Format human-readable audit report with clear butterfly headers."""
    s = res.get("summary", {})
    c = res.get("checks", {})
    verdict = res.get("verdict", "UNKNOWN")
    strict_str = "ON (Kill on any warning)" if res.get("strict") else "OFF"

    lines = [
        f"🦋 X.O.L.A. Red-Team Auditor [guard] — Verdict: {verdict} 🦋",
        "=" * 72,
        f"Target        : {res.get('target')}",
        f"Verdict       : {verdict}",
        f"Strict Mode   : {strict_str}",
        f"Files Audited : {s.get('files_scanned', 0)} ({s.get('files_passed', 0)} clean, {s.get('files_warned', 0)} warn, {s.get('files_killed', 0)} kill)",
        f"Findings      : {s.get('total_findings', 0)} issue(s) [{s.get('critical_count', 0)} critical, {s.get('warning_count', 0)} warning]",
        f"Fixes Applied : {s.get('fixes_applied', 0)}",
        f"Latency       : {res.get('latency_s', 0.0):.4f}s",
        "-" * 72,
        "Check Metrics:",
        f"  • AST / Syntax Compilation : {c.get('syntax_ast', {}).get('passed', 0)} passed, {c.get('syntax_ast', {}).get('failed', 0)} failed",
        f"  • Secret Leak Scanners     : {c.get('secret_detection', {}).get('passed', 0)} clean, {c.get('secret_detection', {}).get('failed', 0)} leaked",
        f"  • {WATERMARK} Watermark Presence     : {c.get('watermark', {}).get('passed', 0)} present, {c.get('watermark', {}).get('failed', 0)} missing",
        f"  • Pure Stdlib Dependencies : {c.get('dependencies', {}).get('passed', 0)} clean, {c.get('dependencies', {}).get('failed', 0)} flagged",
    ]

    if c.get("smoke_tests", {}).get("passed", 0) or c.get("smoke_tests", {}).get("failed", 0):
        lines.append(
            f"  • Smoke Execution Tests    : {c.get('smoke_tests', {}).get('passed', 0)} passed, {c.get('smoke_tests', {}).get('failed', 0)} failed"
        )

    findings = res.get("findings", [])
    if findings:
        lines.append("-" * 72)
        lines.append("Audit Findings & Evidence:")
        for idx, f in enumerate(findings, start=1):
            sev_tag = f"[{f.get('severity', 'INFO'):^6}]"
            rel_file = os.path.relpath(f.get('file', ''), res.get('target', '')) if os.path.isabs(f.get('file', '')) else f.get('file', '')
            lines.append(f"  {idx}. {sev_tag} {rel_file}:L{f.get('line', 1)}:C{f.get('col', 1)} [{f.get('rule')}]")
            lines.append(f"     ↳ {f.get('message')}")

    fixes = res.get("fixes", [])
    if fixes:
        lines.append("-" * 72)
        lines.append(f"Automated Remediations Applied ({len(fixes)}):")
        for fx in fixes:
            rel_f = os.path.basename(fx.get("file", ""))
            lines.append(f"  • {rel_f}: {fx.get('fix')}")

    lines.append("=" * 72)
    return "\n".join(lines)


# =====================================================================
# CLI Entry Point
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="xola-guard — Red-team reviewer that kills slop before checkpoint 🦋",
        epilog="Usage: python guard.py [--target PATH] [--strict] [--fix] [--smoke] [--json]",
    )
    parser.add_argument(
        "--target",
        default=".",
        help="Target file or directory path to audit (default: .)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Audit all files across entire project directory (default: .)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Strict mode: elevate any warning/finding to KILL (exit code 1)",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix remediable issues (e.g. inject missing 🦋 watermark)",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run lightweight CLI execution smoke tests (--help) on code files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output details",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Force full re-audit (bypass the incremental .guard_cache.json)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output machine-readable JSON",
    )
    args = parser.parse_args()

    try:
        result = audit(
            target=args.target,
            strict=args.strict,
            fix=args.fix,
            smoke=args.smoke,
            verbose=args.verbose,
            use_cache=not args.no_cache,
        )

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(render_report(result, verbose=args.verbose))

        if result.get("verdict") == "KILL":
            sys.exit(1)
        sys.exit(0)

    except KeyboardInterrupt:
        print(f"\nAudit interrupted by user {WATERMARK}", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"ERROR in xola-guard: {exc} {WATERMARK}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

