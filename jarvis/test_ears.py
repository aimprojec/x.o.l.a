#!/usr/bin/env python3
"""Usage: python test_ears.py [--json] # Standalone Test Suite for Jarvis Native Ears & Wake-Word Subsystem 🦋"""

import argparse
import json
import os
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

JARVIS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(JARVIS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from jarvis.voice import EarsQueue, verify_ears_listener, Utterance


def test_listener_script_exists() -> Tuple[bool, str]:
    """Verify ears_listener.ps1 script exists."""
    path = os.path.join(JARVIS_DIR, "ears_listener.ps1")
    if os.path.isfile(path) and os.path.getsize(path) > 100:
        return True, f"Found ears_listener.ps1 ({os.path.getsize(path)} bytes)"
    return False, f"Missing or empty ears_listener.ps1 at {path}"


def test_powershell_syntax() -> Tuple[bool, str]:
    """Verify PowerShell script parses without syntax errors using System.Management.Automation.Language.Parser."""
    ps_path = os.path.join(JARVIS_DIR, "ears_listener.ps1")
    ps_cmd = (
        f"$content = [System.IO.File]::ReadAllText('{ps_path}'); "
        f"$tokens = $null; $errors = $null; "
        f"[System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$tokens, [ref]$errors) | Out-Null; "
        f"if ($errors.Count -gt 0) {{ Write-Error ($errors | Out-String) }} else {{ Write-Host 'SYNTAX_OK' }}"
    )
    cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
        if "SYNTAX_OK" in res.stdout:
            return True, "PowerShell AST parser confirmed zero syntax errors"
        return False, f"PowerShell parse error: {res.stderr or res.stdout}"
    except Exception as exc:
        return False, f"Syntax validation execution failed: {exc}"


def test_listener_atomic_emit() -> Tuple[bool, str]:
    """Verify atomic utterance JSON emission and schema correctness."""
    ears_dir = os.path.join(JARVIS_DIR, "ears")
    ps_path = os.path.join(JARVIS_DIR, "ears_listener.ps1")
    test_phrase = "hey jarvis wake test 🦋"

    cmd = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        ps_path,
        "-TestEmit",
        "-TestPhrase",
        test_phrase,
        "-EarsDir",
        ears_dir,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10, creationflags=NO_WINDOW)
        if res.returncode != 0:
            return False, f"Script execution returned non-zero ({res.returncode}): {res.stderr}"

        ears = EarsQueue(ears_dir=ears_dir)
        pending = ears.peek()
        matching = [u for u in pending if u.text == test_phrase]
        if not matching:
            return False, "Emitted test utterance was not detected in pending queue"

        utt = matching[0]
        # Validate schema fields
        if not utt.id.startswith("ears_"):
            return False, f"Invalid utterance ID prefix: {utt.id}"
        if utt.source != "mic_wake_word":
            return False, f"Expected source 'mic_wake_word', got '{utt.source}'"
        if utt.mark != WATERMARK:
            return False, f"Expected watermark '{WATERMARK}', got '{utt.mark}'"

        # Cleanup
        for f in ears.list_pending():
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    d = json.load(jf)
                if d.get("text") == test_phrase:
                    ears.dequeue_single(f)
            except Exception:
                pass

        return True, f"Atomic utterance verified: ID={utt.id}, text='{utt.text}', confidence={utt.metadata.get('confidence')}"
    except Exception as exc:
        return False, f"Test emit execution failed: {exc}"


def test_voice_verify_module() -> Tuple[bool, str]:
    """Verify the voice.py built-in verify_ears_listener() entrypoint."""
    res = verify_ears_listener()
    if res.get("status") == "PASSED":
        return True, f"verify_ears_listener() passed in {res.get('latency_s')}s"
    return False, f"verify_ears_listener() failed: {res.get('error')}"


def run_all_tests() -> Dict[str, Any]:
    """Execute all tests and report results."""
    t0 = time.perf_counter()
    test_suite = [
        ("SCRIPT_EXISTS", test_listener_script_exists),
        ("POWERSHELL_SYNTAX", test_powershell_syntax),
        ("ATOMIC_EMIT_SCHEMA", test_listener_atomic_emit),
        ("VOICE_VERIFY_HELPER", test_voice_verify_module),
    ]

    results = []
    all_passed = True

    for name, test_func in test_suite:
        t_start = time.perf_counter()
        passed, detail = test_func()
        t_lat = round(time.perf_counter() - t_start, 4)
        if not passed:
            all_passed = False
        results.append({
            "test": name,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
            "latency_s": t_lat,
        })

    total_lat = round(time.perf_counter() - t0, 4)
    return {
        "suite": "JarvisEarsWakeWordTests",
        "verdict": "PASS" if all_passed else "FAIL",
        "total_tests": len(results),
        "passed": sum(1 for r in results if r["status"] == "PASS"),
        "failed": sum(1 for r in results if r["status"] == "FAIL"),
        "results": results,
        "total_latency_s": total_lat,
        "mark": WATERMARK,
    }


def main():
    parser = argparse.ArgumentParser(
        prog="test_ears",
        description="Jarvis Ears & Wake-Word Test Suite 🦋",
    )
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    report = run_all_tests()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"🦋 Jarvis Ears Wake-Word Test Suite [{report['verdict']}] 🦋")
        print("=" * 72)
        print(f"Summary: Total {report['total_tests']} | Passed: {report['passed']} | Failed: {report['failed']} ({report['total_latency_s']}s)")
        print("-" * 72)
        for r in report["results"]:
            st = r["status"]
            icon = "[ PASS ]" if st == "PASS" else "[ FAIL ]"
            print(f"{icon} {r['test']:<22} : {r['detail']} ({r['latency_s']}s)")
        print("=" * 72)

    sys.exit(0 if report["verdict"] == "PASS" else 1)


if __name__ == "__main__":
    main()
