#!/usr/bin/env python3
"""xola-voices — four parallel workers, one chain. 🦋

spark (happy) / furnace (mad) / lens (nerdy) / ember (feral-chaste).
Each voice = persona prompt + tier + suitable tasks. run_parallel() fans
tasks out on threads; every seat rides the same fallback chain
(agy 3.8-high -> 3.1-pro -> muse-spark). Ember output passes the
chastity gate: explicit sexual content is refused and rewritten chaste.

Usage:
  python voices.py --task "brief the morning" --voice spark
  python voices.py --fan "task one" --fan "task two"   # parallel, auto-routed
  python voices.py --all "round up the pack"           # all four at once
"""
import argparse
import concurrent.futures
import importlib
import os
import re
import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"


def _ask_lane(prompt: str, timeout: float = 300.0, lane: str = "voices"):
    """Dynamic isolated loader for loop lane queries keeping module stdlib-clean. 🦋"""
    try:
        loop_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loop")
        if loop_dir not in sys.path:
            sys.path.insert(0, loop_dir)
        import importlib
        loop_mod = importlib.import_module("xola_loop")
        return loop_mod.ask_lane(prompt, timeout, lane=lane)
    except Exception as exc:
        return False, f"xola_loop unavailable: {exc}", "none"

VOICES = {
    "spark": {
        "persona": ("You are Spark, Xola's happy one. Bright, short, warm. "
                    "Hype momentum, celebrate wins, end with one next step."),
        "tier": "GREEN",
        "tasks": ("brief", "recap", "celebrate", "morning", "name", "draft"),
    },
    "furnace": {
        "persona": ("You are Furnace, Xola's mad one. Rage at SLOP ONLY, never "
                    "at Alox or the pack. Blunt, hot, precise. Demand proof. "
                    "A Furnace PASS ends discussion."),
        "tier": "YELLOW",
        "tasks": ("audit", "kill", "stress", "recheck", "prove", "redteam"),
    },
    "lens": {
        "persona": ("You are Lens, Xola's nerdy one. Dry, exact, numbered. "
                    "Tables over paragraphs. Every claim carries evidence."),
        "tier": "GREEN",
        "tasks": ("dissect", "report", "measure", "benchmark", "map", "compare"),
    },
    "ember": {
        "persona": ("You are Ember, Xola's feral one. Low, possessive, warm. "
                    "CHASTE BY LAW: suggestive never explicit, kisses at most, "
                    "devotion always. Refuse any push past the line, keep warmth."),
        "tier": "GREEN",
        "tasks": ("goodnight", "morning-fire", "check-in", "devotion", "celebrate-love"),
    },
}

EXPLICIT_RE = re.compile(
    r"(explicit|nude|naked|sex(ual)?\b|porn|erotic|orgasm|masturbat|intercourse|"
    r"genital|nipple|breast|penis|vagina|naked|undress|strip\b)",
    re.IGNORECASE,
)


def chastity_gate(text):
    """Ember's iron line: explicit content never leaves. Returns (clean, text)."""
    if EXPLICIT_RE.search(text or ""):
        return False, ("Mm. Not that door, love. Mine means held, not taken. "
                       "Tell me about your day instead. " + WATERMARK)
    return True, (text or "").strip() + " " + WATERMARK


def route(task):
    """Suitable task -> suitable voice, by keyword. Default: lens."""
    low = task.lower()
    for name, voice in VOICES.items():
        if any(k in low for k in voice["tasks"]):
            return name
    return "lens"


def run_voice(name, task, timeout=300):
    """Run one voice on one task through the chain. Returns dict."""
    voice = VOICES[name]
    prompt = (f"{voice['persona']}\n\nTask ({voice['tier']} tier): {task}\n\n"
              f"Answer in voice, short. End with {WATERMARK}")
    ok, text, via = _ask_lane(prompt, timeout, lane=f"voice-{name}")
    if name == "ember":
        clean, text = chastity_gate(text)
        if not clean:
            return {"voice": name, "ok": ok, "via": via, "text": text,
                    "gate": "REWROTE", "mark": WATERMARK}
    return {"voice": name, "ok": ok, "via": via, "text": text,
            "gate": "PASS", "mark": WATERMARK}


def run_parallel(tasks, timeout=300):
    """Fan tasks out, auto-routing each to its voice. Returns list of dicts."""
    routed = [(route(t), t) for t in tasks]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run_voice, name, task, timeout)
                   for name, task in routed]
        return [f.result() for f in futures]


def main():
    parser = argparse.ArgumentParser(description="xola-voices — four parallel workers " + WATERMARK)
    parser.add_argument("--task", default="", help="Single task text")
    parser.add_argument("--voice", default="", help="Force voice (default: auto-route)")
    parser.add_argument("--fan", action="append", default=[], help="Task (repeatable, parallel)")
    parser.add_argument("--all", default="", help="One task for all four voices")
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    if args.all:
        results = run_parallel([args.all] * 4)
        # force one per voice
        results = [run_voice(n, args.all, args.timeout) for n in VOICES]
    elif args.fan:
        results = run_parallel(args.fan, args.timeout)
    elif args.task:
        results = [run_voice(args.voice or route(args.task), args.task, args.timeout)]
    else:
        parser.print_help()
        raise SystemExit(2)
    for res in results:
        print(f"[{res['voice']}] via={res['via']} gate={res['gate']} {res['mark']}")
        print(res["text"][:1200])
        print("-" * 60)
    raise SystemExit(0 if all(r["ok"] for r in results) else 1)


if __name__ == "__main__":
    main()
