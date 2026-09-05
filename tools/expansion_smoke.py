#!/usr/bin/env python3
"""Usage: python expansion_smoke.py [--json] # Master E2E Smoke Suite for Directives 201–500 🦋

Runs complete integration and unit smoke test passes across all 8 architectural modules:
- Section I: Perception, Screen & Multimodal Ingestion (201–245)
- Section II: MCP, External Plugins & JSON-RPC Sidecars (246–285)
- Section III: Proactive Behavior, Environment Rules & Sentinel (286–325)
- Section IV: Subprocess Isolation, Bulkheading & Sandboxing (326–365)
- Section V: Advanced Verification, Chaos & Fault Injection (366–405)
- Section VI: Memory Vault, Context Graphs & Compaction (406–440)
- Section VII: Low-Latency Audio, Speech & VAD Pipeline (441–470)
- Section VIII: Service Daemonization, Multi-Node & OS Integration (471–500)
Pure stdlib. Zero external dependencies. 🦋
"""

import argparse
import json
import os
import sys
import time
from typing import Any, Dict

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

def run_all_expansion_checks() -> Dict[str, Any]:
    results = {}

    # 1. Perception (201–245)
    import tools.perception as perception
    p_res = perception.smoke()
    results["Section_I_Perception_201_245"] = (p_res["smoke"] == "PASS")

    # 2. Sidecar (246–285)
    import tools.sidecar as sidecar
    s_res = sidecar.smoke()
    results["Section_II_Sidecar_246_285"] = (s_res["smoke"] == "PASS")

    # 3. Sentinel Proactive (286–325)
    import tools.sentinel_proactive as sentinel_proactive
    sp_res = sentinel_proactive.smoke()
    results["Section_III_Sentinel_Proactive_286_325"] = (sp_res["smoke"] == "PASS")

    # 4. Sandbox (326–365)
    import tools.sandbox as sandbox
    sb_res = sandbox.smoke()
    results["Section_IV_Sandbox_326_365"] = (sb_res["smoke"] == "PASS")

    # 5. Chaos (366–405)
    import tools.chaos as chaos
    c_res = chaos.smoke()
    results["Section_V_Chaos_366_405"] = (c_res["smoke"] == "PASS")

    # 6. Vault Graph (406–440)
    import tools.vault_graph as vault_graph
    vg_res = vault_graph.smoke()
    results["Section_VI_Vault_Graph_406_440"] = (vg_res["smoke"] == "PASS")

    # 7. Audio Pipeline (441–470)
    import tools.audio_pipeline as audio_pipeline
    ap_res = audio_pipeline.smoke()
    results["Section_VII_Audio_Pipeline_441_470"] = (ap_res["smoke"] == "PASS")

    # 8. Daemon Bridge (471–500)
    import tools.daemon_bridge as daemon_bridge
    db_res = daemon_bridge.smoke()
    results["Section_VIII_Daemon_Bridge_471_500"] = (db_res["smoke"] == "PASS")

    all_passed = all(results.values())
    return {
        "title": "X.O.L.A. Architecture Expansion Directives 201–500 Smoke Test",
        "total_sections": len(results),
        "passed_sections": sum(1 for v in results.values() if v),
        "all_passed": all_passed,
        "sections": results,
        "timestamp": time.time(),
        "mark": WATERMARK
    }

def main() -> int:
    ap = argparse.ArgumentParser(description="X.O.L.A. Master Expansion Smoke (201–500) 🦋")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    res = run_all_expansion_checks()
    if args.json:
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        status_text = "ALL PASS" if res["all_passed"] else "SOME FAILED"
        print(f"\n=======================================================")
        print(f"🦋 X.O.L.A. EXPANSION (DIRECTIVES 201–500): {status_text} 🦋")
        print(f"=======================================================")
        for sec, passed in res["sections"].items():
            sym = "✓" if passed else "✗"
            print(f"  [{sym}] {sec}: {'PASS' if passed else 'FAIL'}")
        print(f"=======================================================\n")
    return 0 if res["all_passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
