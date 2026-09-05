#!/usr/bin/env python3
"""Usage: python builder.py [--scaffold NAME] [--inspect [NAME]] [--validate [NAME]] [--list] [--run-test] [--json] # xola-builder: forge and validator for X.O.L.A. tools 🦋"""

import argparse
import ast
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import textwrap
import time

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
DEFAULT_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

# Stdlib module names detection
STDLIB_MODULES = set(getattr(sys, "stdlib_module_names", sys.builtin_module_names))


# =====================================================================
# Scaffolding Templates (Using __NAME__ and __DESC__ placeholders)
# =====================================================================

TOOL_TEMPLATES = {
    "tool": textwrap.dedent('''\
        #!/usr/bin/env python3
        """Usage: python __NAME__.py [--target PATH] [--json] # xola-__NAME__: __DESC__ 🦋"""

        import argparse
        import datetime
        import json
        import os
        import sys
        import time

        # Ensure UTF-8 output on Windows
        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass

        WATERMARK = "🦋"


        def run_action(target: str = "default", verbose: bool = False) -> dict:
            """Execute primary action for __NAME__."""
            t0 = time.perf_counter()
            # Implement core logic here
            success = True
            latency = time.perf_counter() - t0

            return {
                "action": "__NAME__",
                "target": target,
                "status": "SUCCESS" if success else "FAILURE",
                "latency_s": round(latency, 4),
                "timestamp": datetime.datetime.now().isoformat(),
                "details": f"Processed {target} successfully",
                "mark": WATERMARK,
            }


        def render_report(result: dict) -> str:
            """Render human-readable formatted report with butterfly banner."""
            lines = [
                f"🦋 X.O.L.A. __NAME_UPPER__ — Action Report [{result['timestamp']}] 🦋",
                "=" * 64,
                f"Status  : {result['status']}",
                f"Target  : {result['target']}",
                f"Latency : {result['latency_s']}s",
                f"Details : {result['details']}",
                "=" * 64,
            ]
            return "\\n".join(lines)


        def main():
            parser = argparse.ArgumentParser(
                description="xola-__NAME__ — __DESC__ 🦋",
                epilog="Usage: python __NAME__.py [--target PATH] [--json]",
            )
            parser.add_argument("--target", default="default", help="Target parameter to process")
            parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
            parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
            args = parser.parse_args()

            try:
                res = run_action(target=args.target, verbose=args.verbose)
                if args.json:
                    print(json.dumps(res, indent=2))
                else:
                    print(render_report(res))

                if res.get("status") != "SUCCESS":
                    sys.exit(1)
                sys.exit(0)
            except Exception as exc:
                print(f"ERROR in xola-__NAME__: {exc} 🦋", file=sys.stderr)
                sys.exit(1)


        if __name__ == "__main__":
            main()
    '''),

    "prober": textwrap.dedent('''\
        #!/usr/bin/env python3
        """Usage: python __NAME__.py [--quick] [--json] [--timeout SECONDS] # xola-__NAME__: __DESC__ 🦋"""

        import argparse
        import datetime
        import json
        import os
        import subprocess
        import sys
        import time

        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass

        WATERMARK = "🦋"
        NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


        def probe(quick: bool = False, timeout: float = 15.0) -> dict:
            """Run probe checks."""
            t0 = time.perf_counter()
            # Add probe commands / checks
            latency = time.perf_counter() - t0
            status = "UP"

            return {
                "prober": "__NAME__",
                "status": status,
                "latency_s": round(latency, 4),
                "timestamp": datetime.datetime.now().isoformat(),
                "details": "Probe completed cleanly",
                "mark": WATERMARK,
            }


        def render_report(data: dict) -> str:
            lines = [
                f"🦋 X.O.L.A. Prober [__NAME__] Report [{data['timestamp']}] 🦋",
                "=" * 64,
                f"Status  : {data['status']}",
                f"Latency : {data['latency_s']}s",
                f"Details : {data['details']}",
                "=" * 64,
            ]
            return "\\n".join(lines)


        def main():
            parser = argparse.ArgumentParser(
                description="xola-__NAME__ — Prober for __DESC__ 🦋",
                epilog="Usage: python __NAME__.py [--quick] [--json] [--timeout SECONDS]",
            )
            parser.add_argument("--quick", action="store_true", help="Quick triage probe")
            parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
            parser.add_argument("--timeout", type=float, default=15.0, help="Probe timeout in seconds")
            args = parser.parse_args()

            try:
                result = probe(quick=args.quick, timeout=args.timeout)
                if args.json:
                    print(json.dumps(result, indent=2))
                else:
                    print(render_report(result))

                if result.get("status") == "DOWN":
                    sys.exit(1)
                sys.exit(0)
            except Exception as exc:
                print(f"ERROR in xola-__NAME__: {exc} 🦋", file=sys.stderr)
                sys.exit(1)


        if __name__ == "__main__":
            main()
    '''),

    "auditor": textwrap.dedent('''\
        #!/usr/bin/env python3
        """Usage: python __NAME__.py [--target PATH] [--strict] [--json] # xola-__NAME__: __DESC__ 🦋"""

        import argparse
        import datetime
        import json
        import os
        import sys
        import time

        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass

        WATERMARK = "🦋"


        def audit(target: str, strict: bool = False) -> dict:
            """Execute audit checks on target."""
            t0 = time.perf_counter()
            findings = []

            if not os.path.exists(target):
                findings.append(f"Target path not found: {target}")

            verdict = "PASS" if not findings else ("KILL" if strict else "WARN")
            latency = time.perf_counter() - t0

            return {
                "auditor": "__NAME__",
                "target": target,
                "verdict": verdict,
                "findings": findings,
                "latency_s": round(latency, 4),
                "timestamp": datetime.datetime.now().isoformat(),
                "mark": WATERMARK,
            }


        def render_report(res: dict) -> str:
            lines = [
                f"🦋 X.O.L.A. Auditor [__NAME__] — Verdict: {res['verdict']} 🦋",
                "=" * 64,
                f"Target   : {res['target']}",
                f"Verdict  : {res['verdict']}",
                f"Findings : {len(res['findings'])} issue(s)",
            ]
            for f in res['findings']:
                lines.append(f"  • {f}")
            lines.append("=" * 64)
            return "\\n".join(lines)


        def main():
            parser = argparse.ArgumentParser(
                description="xola-__NAME__ — Auditor for __DESC__ 🦋",
                epilog="Usage: python __NAME__.py [--target PATH] [--strict] [--json]",
            )
            parser.add_argument("--target", default=".", help="Target file or directory to audit")
            parser.add_argument("--strict", action="store_true", help="Strict kill on any finding")
            parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
            args = parser.parse_args()

            try:
                res = audit(target=args.target, strict=args.strict)
                if args.json:
                    print(json.dumps(res, indent=2))
                else:
                    print(render_report(res))

                if res.get("verdict") == "KILL":
                    sys.exit(1)
                sys.exit(0)
            except Exception as exc:
                print(f"ERROR in xola-__NAME__: {exc} 🦋", file=sys.stderr)
                sys.exit(1)


        if __name__ == "__main__":
            main()
    '''),

    "distiller": textwrap.dedent('''\
        #!/usr/bin/env python3
        """Usage: python __NAME__.py [--input PATH] [--output PATH] [--json] # xola-__NAME__: __DESC__ 🦋"""

        import argparse
        import datetime
        import json
        import os
        import sys
        import time

        if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
                sys.stderr.reconfigure(encoding="utf-8")
            except Exception:
                pass

        WATERMARK = "🦋"


        def distill(input_path: str, output_path: str = None) -> dict:
            """Distill inputs into structured summaries."""
            t0 = time.perf_counter()
            if not os.path.exists(input_path):
                return {
                    "status": "FAILURE",
                    "error": f"Input not found: {input_path}",
                    "latency_s": round(time.perf_counter() - t0, 4),
                    "mark": WATERMARK,
                }

            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()

            summary = f"Distilled {len(content)} characters from {os.path.basename(input_path)}"
            if output_path:
                with open(output_path, "a", encoding="utf-8") as f:
                    f.write(f"\\n## Distillation {datetime.datetime.now():%Y-%m-%d %H:%M} 🦋\\n{summary}\\n")

            latency = time.perf_counter() - t0
            return {
                "distiller": "__NAME__",
                "input": input_path,
                "output": output_path,
                "status": "SUCCESS",
                "summary": summary,
                "latency_s": round(latency, 4),
                "timestamp": datetime.datetime.now().isoformat(),
                "mark": WATERMARK,
            }


        def render_report(res: dict) -> str:
            lines = [
                f"🦋 X.O.L.A. Distiller [__NAME__] Report 🦋",
                "=" * 64,
                f"Status  : {res.get('status')}",
                f"Input   : {res.get('input')}",
                f"Summary : {res.get('summary', res.get('error', ''))}",
                "=" * 64,
            ]
            return "\\n".join(lines)


        def main():
            parser = argparse.ArgumentParser(
                description="xola-__NAME__ — Distiller for __DESC__ 🦋",
                epilog="Usage: python __NAME__.py [--input PATH] [--output PATH] [--json]",
            )
            parser.add_argument("--input", required=True, help="Input file to distill")
            parser.add_argument("--output", default=None, help="Output memory file path")
            parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
            args = parser.parse_args()

            try:
                res = distill(input_path=args.input, output_path=args.output)
                if args.json:
                    print(json.dumps(res, indent=2))
                else:
                    print(render_report(res))

                if res.get("status") != "SUCCESS":
                    sys.exit(1)
                sys.exit(0)
            except Exception as exc:
                print(f"ERROR in xola-__NAME__: {exc} 🦋", file=sys.stderr)
                sys.exit(1)


        if __name__ == "__main__":
            main()
    ''')
}


# =====================================================================
# AST Code Inspector & AST Rules
# =====================================================================

def analyze_tool_code(file_path: str) -> dict:
    """Analyze a tool file using AST and regex to extract structural properties."""
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}", "valid_ast": False}

    # utf-8-sig transparently strips a leading BOM (U+FEFF) so AST parsing never chokes 🦋
    with open(file_path, "r", encoding="utf-8-sig", errors="replace") as f:
        content = f.read()

    lines = content.splitlines()
    loc = len(lines)
    size_bytes = len(content.encode("utf-8"))

    # Watermark check
    has_watermark = WATERMARK in content

    # AST Parse
    ast_error = None
    tree = None
    try:
        tree = ast.parse(content, filename=file_path)
        valid_ast = True
    except SyntaxError as e:
        valid_ast = False
        ast_error = f"SyntaxError line {e.lineno}: {e.msg}"

    # Extract module docstring
    docstring = ""
    if tree:
        docstring = ast.get_docstring(tree) or ""

    # Check for Usage header in docstring
    has_usage_header = bool(re.search(r"Usage:\s+python\s+", docstring, re.IGNORECASE))
    if not has_usage_header:
        # Check first 5 lines for usage comment or docstring
        first_lines = "\n".join(lines[:6])
        has_usage_header = bool(re.search(r"Usage:\s+python\s+", first_lines, re.IGNORECASE))

    # Inspect imports, functions, classes, sys.exit calls
    imports = []
    external_imports = []
    functions = []
    classes = []
    has_argparse = False
    has_exit_calls = False

    # Sibling modules of the same forge directory are intra-package, not external 🦋
    try:
        local_modules = {
            fn[:-3] for fn in os.listdir(os.path.dirname(os.path.abspath(file_path)))
            if fn.endswith(".py")
        }
    except Exception:
        local_modules = set()

    def _is_internal(pkg: str) -> bool:
        return pkg in STDLIB_MODULES or pkg == "tools" or pkg in local_modules

    if tree:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    pkg = alias.name.split(".")[0]
                    imports.append(pkg)
                    if not _is_internal(pkg):
                        external_imports.append(pkg)
                    if pkg == "argparse":
                        has_argparse = True

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    pkg = node.module.split(".")[0]
                    imports.append(pkg)
                    if not _is_internal(pkg):
                        external_imports.append(pkg)
                    if pkg == "argparse":
                        has_argparse = True

            elif isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "lineno": node.lineno,
                    "args": [arg.arg for arg in node.args.args],
                })

            elif isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "lineno": node.lineno,
                })

            elif isinstance(node, ast.Call):
                # Check for sys.exit or exit()
                if isinstance(node.func, ast.Attribute) and node.func.attr == "exit":
                    has_exit_calls = True
                elif isinstance(node.func, ast.Name) and node.func.id in ("exit", "quit"):
                    has_exit_calls = True

            elif isinstance(node, ast.Raise):
                # Check for raise SystemExit(...)
                if isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name) and node.exc.func.id == "SystemExit":
                    has_exit_calls = True
                elif isinstance(node.exc, ast.Name) and node.exc.id == "SystemExit":
                    has_exit_calls = True

    # Deduplicate imports
    imports = sorted(list(set(imports)))
    external_imports = sorted(list(set(external_imports)))

    return {
        "file": file_path,
        "name": os.path.basename(file_path),
        "size_bytes": size_bytes,
        "loc": loc,
        "valid_ast": valid_ast,
        "ast_error": ast_error,
        "has_watermark": has_watermark,
        "has_usage_header": has_usage_header,
        "docstring": docstring,
        "has_argparse": has_argparse,
        "has_exit_calls": has_exit_calls,
        "imports": imports,
        "external_imports": external_imports,
        "functions": functions,
        "classes": classes,
    }


# =====================================================================
# Validation Suite
# =====================================================================

def validate_tool(file_path: str, run_test: bool = False, timeout: float = 10.0) -> dict:
    """Validate a tool file against X.O.L.A. standard requirements."""
    analysis = analyze_tool_code(file_path)
    tool_name = os.path.basename(file_path)

    checks = []
    all_passed = True

    # Check 1: File Existence & AST Syntax
    if not os.path.exists(file_path):
        return {
            "tool": tool_name,
            "status": "FAIL",
            "passed": False,
            "checks": [{"name": "FILE_EXISTS", "status": "FAIL", "msg": "File does not exist"}],
            "mark": WATERMARK,
        }

    if analysis["valid_ast"]:
        checks.append({"name": "SYNTAX_AST", "status": "PASS", "msg": f"Valid Python AST ({analysis['loc']} LOC)"})
    else:
        checks.append({"name": "SYNTAX_AST", "status": "FAIL", "msg": analysis.get("ast_error", "Syntax parse error")})
        all_passed = False

    # Check 2: 🦋 Watermark
    if analysis["has_watermark"]:
        checks.append({"name": "WATERMARK_MARK", "status": "PASS", "msg": "Watermark 🦋 present in source"})
    else:
        checks.append({"name": "WATERMARK_MARK", "status": "FAIL", "msg": "Missing required 🦋 watermark"})
        all_passed = False

    # Check 3: Usage Docstring Header
    if analysis["has_usage_header"]:
        checks.append({"name": "USAGE_HEADER", "status": "PASS", "msg": "Usage header docstring present"})
    else:
        checks.append({"name": "USAGE_HEADER", "status": "FAIL", "msg": "Missing 'Usage: python <tool>.py ...' header"})
        all_passed = False

    # Check 4: Argparse Integration
    if analysis["has_argparse"]:
        checks.append({"name": "ARGPARSE_CLI", "status": "PASS", "msg": "Uses argparse standard CLI"})
    else:
        checks.append({"name": "ARGPARSE_CLI", "status": "FAIL", "msg": "Missing argparse import / CLI parsing"})
        all_passed = False

    # Check 5: Non-zero Exit On Failure Handling
    if analysis["has_exit_calls"]:
        checks.append({"name": "EXIT_ENFORCEMENT", "status": "PASS", "msg": "Explicit exit code handling found"})
    else:
        checks.append({"name": "EXIT_ENFORCEMENT", "status": "WARN", "msg": "No explicit sys.exit calls detected"})

    # Check 6: Pure stdlib (Zero external/paid dependencies)
    if not analysis["external_imports"]:
        checks.append({"name": "PURE_STDLIB", "status": "PASS", "msg": f"Pure stdlib imports ({len(analysis['imports'])} packages)"})
    else:
        checks.append({"name": "PURE_STDLIB", "status": "FAIL", "msg": f"External non-stdlib imports detected: {analysis['external_imports']}"})
        all_passed = False

    # Check 7: Smoke execution check (if requested)
    smoke_result = None
    if run_test and analysis["valid_ast"]:
        t0 = time.perf_counter()
        try:
            cmd = [sys.executable, file_path, "--help"]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=NO_WINDOW,
            )
            lat = time.perf_counter() - t0
            if proc.returncode == 0:
                checks.append({"name": "EXEC_HELP_TEST", "status": "PASS", "msg": f"Executed --help with returncode 0 ({lat:.3f}s)"})
            else:
                checks.append({"name": "EXEC_HELP_TEST", "status": "FAIL", "msg": f"Failed with returncode {proc.returncode}: {proc.stderr[:100]}"})
                all_passed = False
            smoke_result = {"returncode": proc.returncode, "stdout_len": len(proc.stdout), "latency_s": round(lat, 3)}
        except subprocess.TimeoutExpired:
            checks.append({"name": "EXEC_HELP_TEST", "status": "FAIL", "msg": f"Timeout after {timeout}s"})
            all_passed = False
        except Exception as e:
            checks.append({"name": "EXEC_HELP_TEST", "status": "FAIL", "msg": f"Exec error: {e}"})
            all_passed = False

    status = "PASS" if all_passed else "FAIL"
    return {
        "tool": tool_name,
        "path": file_path,
        "status": status,
        "passed": all_passed,
        "analysis": analysis,
        "checks": checks,
        "smoke": smoke_result,
        "mark": WATERMARK,
    }


# =====================================================================
# Scaffolding Logic
# =====================================================================

def scaffold_tool(
    name: str,
    desc: str = "",
    template_type: str = "tool",
    tools_dir: str = DEFAULT_TOOLS_DIR,
    force: bool = False,
) -> dict:
    """Scaffold a new tool file adhering strictly to X.O.L.A. standards."""
    clean_name = name.strip()
    if clean_name.endswith(".py"):
        clean_name = clean_name[:-3]
    clean_name = re.sub(r"[^a-zA-Z0-9_]", "_", clean_name).lower()
    if not clean_name:
        raise ValueError("Invalid tool name")

    if not desc:
        desc = f"utility for {clean_name}"

    os.makedirs(tools_dir, exist_ok=True)
    target_path = os.path.join(tools_dir, f"{clean_name}.py")

    if os.path.exists(target_path) and not force:
        return {
            "status": "ERROR",
            "message": f"Target file '{target_path}' already exists. Use --force to overwrite.",
            "path": target_path,
            "mark": WATERMARK,
        }

    template_body = TOOL_TEMPLATES.get(template_type, TOOL_TEMPLATES["tool"])
    content = (
        template_body
        .replace("__NAME__", clean_name)
        .replace("__NAME_UPPER__", clean_name.upper())
        .replace("__DESC__", desc)
    )

    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Immediately validate newly scaffolded tool
    validation = validate_tool(target_path, run_test=True)

    return {
        "status": "SUCCESS" if validation["passed"] else "VALIDATION_FAILED",
        "name": f"{clean_name}.py",
        "path": target_path,
        "template": template_type,
        "description": desc,
        "validation": validation,
        "mark": WATERMARK,
    }


# =====================================================================
# Inspection & Listing Logic
# =====================================================================

def list_tools(tools_dir: str = DEFAULT_TOOLS_DIR) -> list:
    """List all python tools in the tools directory."""
    if not os.path.exists(tools_dir):
        return []

    files = sorted([
        os.path.join(tools_dir, f)
        for f in os.listdir(tools_dir)
        if f.endswith(".py") and os.path.isfile(os.path.join(tools_dir, f))
    ])
    return files


def inspect_tools(target: str = None, tools_dir: str = DEFAULT_TOOLS_DIR) -> dict:
    """Inspect a single tool or all tools in tools directory."""
    if target:
        if not target.endswith(".py") and not os.path.exists(target):
            candidate = os.path.join(tools_dir, f"{target}.py")
            if os.path.exists(candidate):
                target_path = candidate
            else:
                target_path = os.path.join(tools_dir, target)
        else:
            target_path = target if os.path.isabs(target) else os.path.join(tools_dir, target)

        analysis = analyze_tool_code(target_path)
        return {
            "tools_dir": tools_dir,
            "target": target_path,
            "single": True,
            "analysis": analysis,
            "mark": WATERMARK,
        }

    tool_files = list_tools(tools_dir)
    analyses = [analyze_tool_code(tf) for tf in tool_files]

    return {
        "tools_dir": tools_dir,
        "count": len(analyses),
        "single": False,
        "tools": analyses,
        "mark": WATERMARK,
    }


def validate_all_tools(target: str = None, tools_dir: str = DEFAULT_TOOLS_DIR, run_test: bool = True) -> dict:
    """Run validation across target tool or all tools in directory."""
    if target:
        if not target.endswith(".py") and not os.path.exists(target):
            candidate = os.path.join(tools_dir, f"{target}.py")
            target_path = candidate if os.path.exists(candidate) else os.path.join(tools_dir, target)
        else:
            target_path = target if os.path.isabs(target) else os.path.join(tools_dir, target)

        val = validate_tool(target_path, run_test=run_test)
        return {
            "tools_dir": tools_dir,
            "total": 1,
            "passed_count": 1 if val["passed"] else 0,
            "failed_count": 0 if val["passed"] else 1,
            "all_passed": val["passed"],
            "results": [val],
            "mark": WATERMARK,
        }

    tool_files = list_tools(tools_dir)
    results = [validate_tool(tf, run_test=run_test) for tf in tool_files]
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count
    all_passed = (failed_count == 0) and (len(results) > 0)

    return {
        "tools_dir": tools_dir,
        "total": len(results),
        "passed_count": passed_count,
        "failed_count": failed_count,
        "all_passed": all_passed,
        "results": results,
        "mark": WATERMARK,
    }


# =====================================================================
# Rendering & Console UI
# =====================================================================

def render_scaffold_report(data: dict) -> str:
    lines = [
        f"🦋 X.O.L.A. Builder — Scaffolding Result [{data.get('status')}] 🦋",
        "=" * 68,
        f"Tool Name   : {data.get('name')}",
        f"Target Path : {data.get('path')}",
        f"Template    : {data.get('template')}",
        f"Description : {data.get('description')}",
        "-" * 68,
    ]
    if "validation" in data:
        val = data["validation"]
        lines.append(f"Auto-Validation Status: [{val.get('status')}]")
        for chk in val.get("checks", []):
            st = f"[{chk['status']:^6}]"
            lines.append(f"  {st} {chk['name']:<18} : {chk['msg']}")
    lines.append("=" * 68)
    return "\n".join(lines)


def render_inspect_report(data: dict) -> str:
    lines = [
        "🦋 X.O.L.A. Builder — Tool Inspection Report 🦋",
        "=" * 68,
    ]
    if data.get("single"):
        a = data.get("analysis", {})
        lines.extend([
            f"File       : {a.get('file')}",
            f"Size / LOC : {a.get('size_bytes')} bytes | {a.get('loc')} lines",
            f"Watermark  : {'YES (🦋)' if a.get('has_watermark') else 'NO'}",
            f"Usage Hdr  : {'YES' if a.get('has_usage_header') else 'NO'}",
            f"Argparse   : {'YES' if a.get('has_argparse') else 'NO'}",
            f"Exit Code  : {'YES' if a.get('has_exit_calls') else 'NO'}",
            f"Stdlib Only: {'YES' if not a.get('external_imports') else 'NO (ext: ' + str(a.get('external_imports')) + ')'}",
            f"Imports    : {', '.join(a.get('imports', [])) or 'None'}",
            "-" * 68,
            "Functions Defined:",
        ])
        for fn in a.get("functions", []):
            lines.append(f"  • line {fn['lineno']:<4}: {fn['name']}({', '.join(fn['args'])})")
        if not a.get("functions"):
            lines.append("  (none)")
        lines.extend([
            "-" * 68,
            "Usage / Docstring:",
            f"  {a.get('docstring', '(no docstring)').strip()}",
        ])
    else:
        lines.append(f"Tools Directory: {data.get('tools_dir')} (Total: {data.get('count')})")
        lines.append("-" * 68)
        header = f"{'Tool':<18} | {'LOC':<5} | {'Mark':<5} | {'Usage':<5} | {'Argp':<5} | {'Stdlib':<6} | {'Status'}"
        lines.append(header)
        lines.append("-" * 68)
        for a in data.get("tools", []):
            mark = "🦋" if a.get("has_watermark") else "NO"
            usage = "OK" if a.get("has_usage_header") else "MISS"
            argp = "OK" if a.get("has_argparse") else "MISS"
            stdlib = "OK" if not a.get("external_imports") else "EXT"
            status = "VALID" if a.get("valid_ast") else "ERR"
            lines.append(f"{a.get('name'):<18} | {a.get('loc'):<5} | {mark:<5} | {usage:<5} | {argp:<5} | {stdlib:<6} | {status}")
    lines.append("=" * 68)
    return "\n".join(lines)


def render_validate_report(data: dict) -> str:
    lines = [
        "🦋 X.O.L.A. Builder — Standards Validation Report 🦋",
        "=" * 68,
        f"Directory : {data.get('tools_dir')}",
        f"Summary   : Total {data.get('total')} | Passed: {data.get('passed_count')} | Failed: {data.get('failed_count')}",
        "-" * 68,
    ]
    for val in data.get("results", []):
        st = f"[{val['status']:^6}]"
        lines.append(f"{st} Tool: {val['tool']}")
        for chk in val.get("checks", []):
            c_st = f"[{chk['status']:^6}]"
            lines.append(f"       {c_st} {chk['name']:<18} : {chk['msg']}")
        lines.append("-" * 68)

    overall = "ALL STANDARDS PASSED 🦋" if data.get("all_passed") else "VALIDATION FAILURES DETECTED"
    lines.append(f"Final Verdict: {overall}")
    lines.append("=" * 68)
    return "\n".join(lines)


# =====================================================================
# Main CLI Entrypoint
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="xola-builder — Forge, inspect, and validate tools in D:\\alox\\xola\\tools 🦋",
        epilog="Usage: python builder.py [--scaffold NAME] [--inspect [NAME]] [--validate [NAME]] [--list] [--run-test] [--json]",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Subcommand: scaffold
    p_scaffold = subparsers.add_parser("scaffold", help="Scaffold a new tool")
    p_scaffold.add_argument("name", help="Name of tool to scaffold")
    p_scaffold.add_argument("--desc", default="", help="Description for the tool")
    p_scaffold.add_argument("--template", default="tool", choices=["tool", "prober", "auditor", "distiller"], help="Template type")
    p_scaffold.add_argument("--force", action="store_true", help="Overwrite existing file")
    p_scaffold.add_argument("--json", action="store_true", help="Output JSON format")

    # Subcommand: inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspect tool code and metadata")
    p_inspect.add_argument("target", nargs="?", default=None, help="Specific tool to inspect")
    p_inspect.add_argument("--json", action="store_true", help="Output JSON format")

    # Subcommand: validate
    p_validate = subparsers.add_parser("validate", help="Validate tools against X.O.L.A. standards")
    p_validate.add_argument("target", nargs="?", default=None, help="Specific tool to validate")
    p_validate.add_argument("--no-run-test", action="store_true", help="Skip execution smoke test")
    p_validate.add_argument("--json", action="store_true", help="Output JSON format")

    # Subcommand: list
    p_list = subparsers.add_parser("list", help="List all available tools")
    p_list.add_argument("--json", action="store_true", help="Output JSON format")

    # Direct Flags (alternative to subcommands for ease of invocation)
    parser.add_argument("--scaffold", dest="flag_scaffold", metavar="NAME", help="Scaffold a tool with given name")
    parser.add_argument("--desc", default="", help="Description for scaffolded tool")
    parser.add_argument("--template", default="tool", choices=["tool", "prober", "auditor", "distiller"], help="Template type for scaffolding")
    parser.add_argument("--inspect", dest="flag_inspect", nargs="?", const="__ALL__", help="Inspect tool(s)")
    parser.add_argument("--validate", dest="flag_validate", nargs="?", const="__ALL__", help="Validate tool(s)")
    parser.add_argument("--list", action="store_true", help="List tools in directory")
    parser.add_argument("--tools-dir", default=DEFAULT_TOOLS_DIR, help="Tools directory path")
    parser.add_argument("--force", action="store_true", help="Force overwrite when scaffolding")
    parser.add_argument("--run-test", action="store_true", default=True, help="Run live smoke test during validation")
    parser.add_argument("--no-run-test", action="store_true", help="Disable live smoke test during validation")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()
    tools_dir = args.tools_dir or DEFAULT_TOOLS_DIR
    json_mode = args.json or getattr(args, "json", False)

    # Determine requested operation
    try:
        # Case 1: Scaffold
        if args.command == "scaffold" or args.flag_scaffold:
            target_name = args.name if args.command == "scaffold" else args.flag_scaffold
            target_desc = args.desc or ""
            target_tmpl = args.template or "tool"
            force = args.force

            res = scaffold_tool(
                name=target_name,
                desc=target_desc,
                template_type=target_tmpl,
                tools_dir=tools_dir,
                force=force,
            )
            if json_mode:
                print(json.dumps(res, indent=2))
            else:
                print(render_scaffold_report(res))

            if res.get("status") not in ("SUCCESS",):
                sys.exit(1)
            sys.exit(0)

        # Case 2: Inspect
        elif args.command == "inspect" or args.flag_inspect is not None:
            target = args.target if args.command == "inspect" else (None if args.flag_inspect == "__ALL__" else args.flag_inspect)
            res = inspect_tools(target=target, tools_dir=tools_dir)
            if json_mode:
                print(json.dumps(res, indent=2))
            else:
                print(render_inspect_report(res))
            sys.exit(0)

        # Case 3: Validate
        elif args.command == "validate" or args.flag_validate is not None:
            target = args.target if args.command == "validate" else (None if args.flag_validate == "__ALL__" else args.flag_validate)
            run_smoke = not args.no_run_test
            res = validate_all_tools(target=target, tools_dir=tools_dir, run_test=run_smoke)
            if json_mode:
                print(json.dumps(res, indent=2))
            else:
                print(render_validate_report(res))

            if not res.get("all_passed"):
                sys.exit(1)
            sys.exit(0)

        # Case 4: List
        elif args.command == "list" or args.list:
            res = inspect_tools(target=None, tools_dir=tools_dir)
            if json_mode:
                print(json.dumps(res, indent=2))
            else:
                print(render_inspect_report(res))
            sys.exit(0)

        # Default fallback: validate all tools and print overview
        else:
            run_smoke = not args.no_run_test
            res = validate_all_tools(target=None, tools_dir=tools_dir, run_test=run_smoke)
            if json_mode:
                print(json.dumps(res, indent=2))
            else:
                print(render_validate_report(res))

            if not res.get("all_passed"):
                sys.exit(1)
            sys.exit(0)

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
            print(f"🦋 ERROR in builder: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
