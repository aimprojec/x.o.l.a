#!/usr/bin/env python3
"""Usage: python security_guard.py [--smoke] [--json] # X.O.L.A. Security, Sandboxing & Verification 🦋

Security & Verification (todo items 196-200):
196. AST Static Code Analyzer (blocks eval, exec, unauthorized imports)
197. Secret and Key Leak Scanner (scans for tokens, api keys, credentials)
198. Universal Watermark Enforcer (asserts and injects 🦋 footprint)
199. End-to-End Smoke Test Suite (runs complete cycle across all layers)
200. Self-Healing Loop Watchdog (detects corrupted states, restores snapshot)
Pure stdlib. Zero external dependencies. 🦋
"""

import argparse
import ast
import datetime
import json
import os
import re
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Set, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

WATERMARK = "🦋"
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "loop", "lh10", "security")
SNAPSHOT_DIR = os.path.join(BASE, "snapshots")

# =====================================================================
# 196: AST Static Code Analyzer 🦋
# =====================================================================

BANNED_BUILTINS = {"eval", "exec", "__import__"}
BANNED_MODULES = {"openai", "anthropic", "langchain", "boto3", "paramiko"}

class CodeSecurityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.violations: List[str] = []

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            if node.func.id in BANNED_BUILTINS:
                self.violations.append(f"Forbidden builtin call: '{node.func.id}' at line {node.lineno}")
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name in BANNED_MODULES:
                self.violations.append(f"Unauthorized paid or external SDK import: '{alias.name}' at line {node.lineno}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module and node.module.split(".")[0] in BANNED_MODULES:
            self.violations.append(f"Unauthorized paid or external SDK import from: '{node.module}' at line {node.lineno}")
        self.generic_visit(node)

def analyze_code_ast(code: str) -> Dict[str, Any]:
    """196: Parse code with Python's ast module to block unsafe builtins and imports."""
    try:
        tree = ast.parse(code)
        visitor = CodeSecurityVisitor()
        visitor.visit(tree)
        passed = (len(visitor.violations) == 0)
        return {"status": "PASS" if passed else "KILL", "violations": visitor.violations, "mark": WATERMARK}
    except SyntaxError as syn:
        return {"status": "KILL", "violations": [f"Syntax error: {syn}"], "mark": WATERMARK}

# =====================================================================
# 197: Secret and Key Leak Scanner 🦋
# =====================================================================

SECRET_PATTERNS = [
    (re.compile(r"\b(?:sk-[a-zA-Z0-9]{20,})\b"), "OpenAI API Key"),
    (re.compile(r"\b(?:ghp_[a-zA-Z0-9]{36,})\b"), "GitHub Personal Access Token"),
    (re.compile(r"\b(?:Bearer\s+[a-zA-Z0-9_\-\.]{30,})\b"), "Bearer Token"),
    (re.compile(r"\b(?:AKIA[0-9A-Z]{16})\b"), "AWS Access Key"),
    (re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"), "Private Key Header"),
]

def scan_for_secrets(text: str) -> List[str]:
    """197: Run regex scans over network payloads and logs to block leaked credentials."""
    findings = []
    for pat, desc in SECRET_PATTERNS:
        if pat.search(text):
            findings.append(f"Potential secret leak detected: {desc}")
    return findings

# =====================================================================
# 198: Universal Watermark Enforcer 🦋
# =====================================================================

def verify_watermark(content: str) -> bool:
    """198: Ensure generated artifacts embed the required verification signature."""
    return WATERMARK in content

def inject_watermark(content: str, mode: str = "python") -> str:
    """198: Auto-inject missing 🦋 watermark into docstring or markdown header."""
    if verify_watermark(content):
        return content
    if mode == "python":
        lines = content.splitlines(keepends=True)
        if lines and lines[0].startswith("#!"):
            lines.insert(1, f"# Auto-injected watermark {WATERMARK}\n")
            return "".join(lines)
        return f"# {WATERMARK}\n" + content
    elif mode == "markdown":
        return f"# Document {WATERMARK}\n\n" + content
    return content + f" {WATERMARK}"

# =====================================================================
# 200: Self-Healing Loop Watchdog 🦋
# =====================================================================

class SelfHealingWatchdog:
    """200: Detect corrupted states, restore last safe snapshot, and resume core operations."""
    def __init__(self, state_file: str, backup_dir: str = SNAPSHOT_DIR):
        self.state_file = state_file
        self.backup_dir = backup_dir

    def create_safe_snapshot(self, state_data: Dict[str, Any]):
        os.makedirs(self.backup_dir, exist_ok=True)
        snap_path = os.path.join(self.backup_dir, f"snapshot_{int(time.time())}.json")
        with open(snap_path, "w", encoding="utf-8") as fh:
            json.dump(state_data, fh, indent=2)
        # Also maintain latest
        latest = os.path.join(self.backup_dir, "snapshot_latest.json")
        shutil.copy2(snap_path, latest)

    def recover_if_corrupted(self) -> Tuple[bool, Dict[str, Any]]:
        is_corrupt = False
        data = {}
        if not os.path.exists(self.state_file):
            is_corrupt = True
        else:
            try:
                with open(self.state_file, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                is_corrupt = True

        if is_corrupt:
            latest = os.path.join(self.backup_dir, "snapshot_latest.json")
            if os.path.exists(latest):
                try:
                    with open(latest, "r", encoding="utf-8") as fh:
                        recovered = json.load(fh)
                    with open(self.state_file, "w", encoding="utf-8") as fh:
                        json.dump(recovered, fh, indent=2)
                    return True, recovered
                except Exception:
                    pass
        return False, data

# =====================================================================
# 199: End-to-End Smoke Test Suite across all 7 layers 🦋
# =====================================================================

def run_e2e_integration_smoke() -> Dict[str, Any]:
    """199: Integration harness running complete cycle across all layers."""
    results: Dict[str, Any] = {}

    # Layer 1: Gateway
    import tools.gateway as gateway
    gw_res = gateway.smoke()
    results["L1_gateway"] = (gw_res["smoke"] == "PASS")

    # Layer 2: Vault
    import tools.vault as vault
    vault_res = vault.smoke()
    results["L2_vault"] = (vault_res["smoke"] == "PASS")

    # Layer 3: Orchestrator
    import tools.orchestrator as orchestrator
    orch_res = orchestrator.smoke()
    results["L3_orchestrator"] = (orch_res["smoke"] == "PASS")

    # Layer 4: Armory
    import tools.armory as armory
    arm_res = armory.smoke()
    results["L4_armory"] = (arm_res["smoke"] == "PASS")

    # Layer 5: Sentinel Daemon
    import tools.sentinel_daemon as sentinel_daemon
    sent_res = sentinel_daemon.smoke()
    results["L5_sentinel_daemon"] = (sent_res["smoke"] == "PASS")

    # Layer 6: Persona Engine
    import tools.persona_engine as persona_engine
    pers_res = persona_engine.smoke()
    results["L6_persona_engine"] = (pers_res["smoke"] == "PASS")

    # Layer 7: Workbench HUD
    import tools.workbench_hud as workbench_hud
    wb_res = workbench_hud.smoke()
    results["L7_workbench_hud"] = (wb_res["smoke"] == "PASS")

    # Security Layer
    sec_res = smoke_internal()
    results["Security_Guard"] = (sec_res["smoke"] == "PASS")

    all_passed = all(results.values())
    results["ALL_LAYERS_PASS"] = all_passed
    results["mark"] = WATERMARK
    return results

def smoke_internal() -> Dict[str, Any]:
    checks: Dict[str, Any] = {}

    # 1. AST Static Analyzer (196)
    clean_code = "import json\ndef run():\n    return 'clean 🦋'\n"
    dirty_code = "import openai\ndef bad():\n    eval('2+2')\n"
    checks["ast_clean"] = (analyze_code_ast(clean_code)["status"] == "PASS")
    checks["ast_dirty"] = (analyze_code_ast(dirty_code)["status"] == "KILL")

    # 2. Secret Scanner (197)
    sec_leaks = scan_for_secrets("Authorization: Bearer " + "A" * 35)
    checks["secret_scanner"] = (len(sec_leaks) > 0)

    # 3. Universal Watermark (198)
    checks["watermark_verify"] = (verify_watermark("hello 🦋") is True and verify_watermark("hello") is False)
    injected = inject_watermark("print('hello')", mode="python")
    checks["watermark_inject"] = verify_watermark(injected)

    # 4. Self-healing watchdog (200)
    test_state = os.path.join(BASE, "test_state.json")
    os.makedirs(BASE, exist_ok=True)
    sh = SelfHealingWatchdog(test_state)
    sh.create_safe_snapshot({"good": True})
    # Corrupt
    with open(test_state, "w", encoding="utf-8") as fh:
        fh.write("{corrupt_json")
    recovered, rec_data = sh.recover_if_corrupted()
    checks["self_healing"] = (recovered is True and rec_data.get("good") is True)

    passed = all(checks.values())
    checks["smoke"] = "PASS" if passed else "FAIL"
    checks["mark"] = WATERMARK
    return checks

def smoke() -> Dict[str, Any]:
    return smoke_internal()

def main() -> int:
    ap = argparse.ArgumentParser(description="X.O.L.A. Security & Verification (Items 196-200) 🦋")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--e2e", action="store_true", help="Run full 7-layer integration smoke test")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    
    if args.e2e:
        res = run_e2e_integration_smoke()
        status = "PASS" if res.get("ALL_LAYERS_PASS") else "FAIL"
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"🦋 Full 7-Layer E2E Smoke: {status} ({len(res)-2} layers verified) 🦋")
        return 0 if status == "PASS" else 1

    res = smoke()
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"🦋 Security Guard smoke: {res['smoke']} 🦋")
    return 0 if res["smoke"] == "PASS" else 1

if __name__ == "__main__":
    raise SystemExit(main())
