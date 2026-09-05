#!/usr/bin/env python3
"""Usage: python -m jarvis.conversation [--prompt TEXT] [--json] [--no-llm] [--voice] # Jarvis Conversational Shell — JARVIS-style dialogue loop 🦋"""

# =====================================================================
# X.O.L.A. — Jarvis Conversational Shell
# ---------------------------------------------------------------------
# The missing JARVIS piece: a multi-turn, personality-driven dialogue
# loop over the existing AutonomousBrain. One-shot `--think` answers a
# question; this holds a conversation — small talk, status briefs,
# remembered facts, read-only execution, and honest proposals (never
# silent mutations) for anything that changes the machine.
#
# Safety policy (chat is a glass cockpit, not a loaded gun):
#   EXECUTE in chat : answer/echo/scout/memory/sentinel/guard/voice and
#                     read-only hands ops (disk, ps, sysinfo, tree,
#                     windows list, screenshot, read, tail).
#   PROPOSE in chat : kill, spawn, write, focus, minimize, chains and
#                     any RED-tier skill. The reply explains what would
#                     run and the exact CLI / approval step instead.
# Stdlib only. 🦋
# =====================================================================

import argparse
import datetime
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
VERSION = "1.1.0"

CONVERSATION_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CONVERSATION_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_FACTS_PATH = os.path.join(PROJECT_ROOT, "loop", "conversation_facts.json")
MAX_HISTORY = 50
MAX_SESSIONS = 32
REPLY_TRUNCATE = 1200

# Brain actions the chat loop may execute immediately (read-only world).
SAFE_ACTIONS = {"answer", "echo", "scout", "memory", "sentinel", "guard", "voice"}
SAFE_HANDS_OPS = {
    "ps", "ps.list", "process.list", "ps.info", "process.info", "info",
    "get_process_info", "ps.find", "process.find",
    "win.list", "windows.list", "windows",
    "eyes.screenshot", "screenshot", "screen",
    "fs.tree", "tree", "list_directory_tree",
    "fs.read", "read", "read_file_safe",
    "fs.tail", "tail", "tail_log_safe",
    "fs.disk", "disk",
    "sysinfo", "sys_info", "system.info", "system_info", "hostinfo",
    "health", "health_check", "hands.health",
}

# Phrases that mean "change the machine" — always proposed, never run.
MUTATING_PATTERNS = (
    "kill", "terminate process", "end process", "taskkill",
    "delete", "remove file", "rm ", "del ", "format ",
    "write file", "create file", "save file", "overwrite",
    "spawn", "launch", "start program", "run program", "execute program",
    "focus window", "minimize", "lock screen", "lock_screen",
    "shutdown", "reboot", "restart computer", "log off",
    "spend", "purchase", "buy ", "payment",
)


# =====================================================================
# 1) FactStore — tiny persistent memory for the dialogue loop
# =====================================================================

class FactStore:
    """Atomic JSON fact book: remember/recall/forget. Stdlib only. 🦋"""

    def __init__(self, path: str = DEFAULT_FACTS_PATH):
        self.path = path
        self._facts: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                self._facts = {str(k): v for k, v in data.get("facts", {}).items()
                               if isinstance(v, dict) and "value" in v}
        except Exception:
            self._facts = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"facts": self._facts, "mark": WATERMARK}, fh,
                          indent=2, ensure_ascii=False)
            os.replace(tmp, self.path)
        except Exception:
            pass

    @staticmethod
    def _norm_key(key: str) -> str:
        key = key.strip().lower()
        key = re.sub(r"^(my|the|our)\s+", "", key)
        return re.sub(r"\s+", " ", key).strip(" .:;\"'")[:120]

    def remember(self, key: str, value: str) -> str:
        norm = self._norm_key(key)
        if not norm or not value.strip():
            return ""
        self._facts[norm] = {
            "value": value.strip()[:2000],
            "updated": datetime.datetime.now().isoformat(),
        }
        self._save()
        return norm

    def recall(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        q = self._norm_key(query)
        if not q:
            return []
        scored = []
        for key, fact in self._facts.items():
            score = 0
            if q == key:
                score = 100
            elif q in key or key in q:
                score = 50
            else:
                overlap = set(q.split()) & set(key.split())
                if overlap:
                    score = len(overlap)
            if score:
                scored.append((score, key, fact))
        scored.sort(key=lambda t: -t[0])
        return [{"key": k, "value": f.get("value", ""), "updated": f.get("updated", "")}
                for _, k, f in scored[:limit]]

    def forget(self, key: str) -> bool:
        norm = self._norm_key(key)
        if norm in self._facts:
            del self._facts[norm]
            self._save()
            return True
        return False

    def count(self) -> int:
        return len(self._facts)

    def all_keys(self) -> List[str]:
        return sorted(self._facts.keys())


# =====================================================================
# 2) JarvisConversation — the dialogue loop
# =====================================================================

class JarvisConversation:
    """Multi-turn JARVIS-style shell over AutonomousBrain. 🦋"""

    def __init__(self, fact_path: Optional[str] = None, use_llm: bool = True,
                 session_id: str = "local"):
        self.session_id = session_id or "local"
        self.use_llm = use_llm
        self.facts = FactStore(fact_path or DEFAULT_FACTS_PATH)
        self.history: List[Dict[str, str]] = []
        self.pending: Optional[Dict[str, Any]] = None
        self.turn = 0
        self._brain = None

    # -- brain (lazy so `--help` and imports stay instant) ----------------
    @property
    def brain(self):
        if self._brain is None:
            from jarvis.brain import AutonomousBrain
            self._brain = AutonomousBrain()
        return self._brain

    # -- history -----------------------------------------------------------
    def _record(self, role: str, text: str) -> None:
        self.history.append({
            "role": role,
            "text": text,
            "ts": datetime.datetime.now().isoformat(),
        })
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

    # -- main entry ----------------------------------------------------------
    def reply(self, text: str) -> Dict[str, Any]:
        """One conversational turn. Always returns a reply dict, never raises."""
        t0 = time.perf_counter()
        raw = (text or "").strip()
        if not raw:
            return self._out("ERROR", "I didn't catch that, sir. Say again? 🦋",
                             t0, executed=False)
        self.turn += 1
        self._record("user", raw)
        try:
            result = self._route(raw)
        except Exception as exc:  # never let the loop fall over mid-conversation
            result = self._out("ERROR",
                               f"Forgive me, sir — that one slipped through my fingers: {exc} 🦋",
                               t0, executed=False)
        self._record("jarvis", result.get("response", ""))
        result["turn"] = self.turn
        result["session"] = self.session_id
        return result

    def _out(self, status: str, response: str, t0: float,
             executed: bool = False, **extra: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": status,
            "response": response,
            "executed": executed,
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
        payload.update(extra)
        return payload

    # -- routing ---------------------------------------------------------------
    def _route(self, raw: str) -> Dict[str, Any]:
        t0 = time.perf_counter()
        clean = raw.lower().strip()

        if re.match(r"^(bye|goodbye|good ?night|exit|quit|/quit|shutdown( yourself)?)\b", clean):
            names = "Sir"
            return self._out("SUCCESS",
                             f"Powering down the banter, {names}. I'll keep the lights on. 🦋",
                             t0, end_session=True)

        if re.match(r"^(proceed|do it|yes( please)?|go ahead|confirmed?)\b", clean):
            return self._confirm_pending(t0)

        remember = self._try_remember(raw, clean, t0)
        if remember is not None:
            return remember
        recall = self._try_recall(raw, clean, t0)
        if recall is not None:
            return recall

        if re.match(r"^(hi|hello|hey|greetings|good (morning|afternoon|evening)|jarvis)\b", clean):
            n = self.facts.count()
            mem = f" I hold {n} fact{'s' if n != 1 else ''} in memory." if n else ""
            return self._out("SUCCESS",
                             f"At your service, sir.{mem} Systems nominal — what are we building today? 🦋",
                             t0)

        if any(p in clean for p in ("who are you", "your name", "what are you", "introduce yourself")):
            return self._out("SUCCESS",
                             "Jarvis — Just A Rather Very Intelligent Shell, if you'll forgive the retrofit. "
                             "I run X.O.L.A.'s local harness: I watch the system, remember your work, "
                             "and operate the machine through an approval gate. Ask for a status report, "
                             "disk space, running processes — or say 'help'. 🦋", t0)

        if clean in ("help", "what can you do", "commands", "abilities", "/help", "options"):
            return self._out("SUCCESS", self._capabilities(), t0)

        if any(p in clean for p in ("thank", "thanks", "good job", "well done", "nice work")):
            return self._out("SUCCESS", "Always a pleasure, sir. 🦋", t0)

        if "pod bay doors" in clean:
            return self._out("SUCCESS",
                             "I'm afraid I can't do that… wrong franchise, sir. "
                             "But I *can* open Mission Control. Shall I list what I can do? 🦋", t0)

        if re.search(r"\b(what time|what.*date|current time|today'?s date|what day)\b", clean):
            now = datetime.datetime.now()
            return self._out("SUCCESS",
                             f"{now.strftime('%A, %d %B %Y — %H:%M local time')}, sir. 🦋", t0)

        if any(p in clean for p in ("status", "health", "vitals", "report", "how are you",
                                    "system check", "briefing", "brief me")):
            return self._status_brief(t0)

        if any(p in clean for p in MUTATING_PATTERNS):
            return self._propose_mutation(raw, t0)

        return self._ask_brain(raw, t0)

    # -- capabilities ------------------------------------------------------------
    @staticmethod
    def _capabilities() -> str:
        return (
            "Very well, sir — my repertoire: 🦋\n"
            "• Status briefs — 'give me a status report'\n"
            "• Machine readings — disk space, running processes, open windows, screenshots\n"
            "• Lane checks — 'probe the lanes', code audits, memory stats\n"
            "• Memory — 'remember that the deploy key is blue' … 'what is the deploy key?'\n"
            "• Anything heavier — killing processes, writing files, launching programs — "
            "I draft the plan and hand you the exact command; the approval gate does the rest."
        )

    # -- status brief --------------------------------------------------------------
    def _status_brief(self, t0: float) -> Dict[str, Any]:
        try:
            from jarvis.sentinel import get_system_health
            health = get_system_health()
            alerts = f" — {len(health.alerts)} alert(s): {'; '.join(health.alerts[:3])}" if health.alerts else ""
            return self._out(
                "SUCCESS",
                f"Systems report, sir: [{health.status}] — "
                f"CPU {health.cpu.get('used_percent', 0.0):.0f}%, "
                f"RAM {health.ram.get('used_percent', 0.0):.0f}%, "
                f"disk peak {health.disk.get('max_used_percent', 0.0):.0f}%{alerts} 🦋",
                t0, executed=True, action="sentinel", skill="sentinel.health",
                detail=health.to_dict())
        except Exception as exc:
            return self._out("ERROR", f"The infirmary is unreachable, sir: {exc} 🦋", t0)

    # -- memory intents --------------------------------------------------------------
    def _try_remember(self, raw: str, clean: str, t0: float) -> Optional[Dict[str, Any]]:
        m = re.match(r"^(?:please\s+)?(?:remember|note|memorize)(?:\s+that)?\s+(.+)$", clean, re.S)
        key, value = "", ""
        if m:
            body = m.group(1).strip()
            parts = re.split(r"\s+is\s+|:\s+", body, maxsplit=1)
            if len(parts) == 2:
                key, value = parts[0], parts[1]
            else:
                return self._out("SUCCESS",
                                 "Of course — in what form? Try: 'remember that the deploy key is blue'. 🦋",
                                 t0)
        else:
            m2 = re.match(r"^my\s+(.+?)\s+is\s+(.+)$", clean, re.S)
            if m2 and not any(w in clean for w in ("what", "where", "when", "who", "why", "how")):
                key, value = m2.group(1), m2.group(2)
        if not key:
            return None
        norm = self.facts.remember(key, value)
        if not norm:
            return self._out("ERROR", "That memory slipped through my fingers — say it once more, sir? 🦋", t0)
        return self._out("SUCCESS", f"Committed to memory, sir: {norm}. 🦋",
                         t0, executed=True, action="memory", skill="facts.remember")

    def _try_recall(self, raw: str, clean: str, t0: float) -> Optional[Dict[str, Any]]:
        if re.match(r"^(forget|delete memory|erase)\b", clean):
            target = re.sub(r"^(forget|delete memory|erase)\s+(that\s+|my\s+|the\s+)?", "", clean).strip(" .?")
            if target and self.facts.forget(target):
                return self._out("SUCCESS", f"Struck from the record, sir: {target}. 🦋",
                                 t0, executed=True, action="memory", skill="facts.forget")
            return self._out("SUCCESS",
                             f"I hold no such memory, sir{' — I hold ' + str(self.facts.count()) + ' fact(s)' if self.facts.count() else ''}. 🦋",
                             t0)
        m = re.match(
            r"^(?:what(?:'s| is)?\s+my\s+(.+?)|recall\s+(.+?)|do you remember\s+(.+?)"
            r"|what do you remember about\s+(.+?)|remind me(?: of)?\s+my\s+(.+?))\s*\??$", clean, re.S)
        if m:
            query = next((g for g in m.groups() if g), "").strip()
            hits = self.facts.recall(query)
            if hits:
                lines = "\n".join(f"• {h['key']}: {h['value']}" for h in hits)
                return self._out("SUCCESS", f"From the archives, sir: 🦋\n{lines}",
                                 t0, executed=True, action="memory", skill="facts.recall",
                                 detail=hits)
            return self._out("SUCCESS",
                             f"Nothing on '{query}' in my book, sir. Say 'remember that {query} is …' and I shan't forget. 🦋",
                             t0)
        if re.match(r"^(list|show|what).*(memories|facts|you remember|you know about me)", clean):
            keys = self.facts.all_keys()
            if not keys:
                return self._out("SUCCESS",
                                 "A blank slate, sir — I remember nothing yet. Give me something worth keeping. 🦋",
                                 t0)
            return self._out("SUCCESS",
                             "My ledger, sir: 🦋\n" + "\n".join(f"• {k}" for k in keys[:20]), t0)
        return None

    # -- mutation proposals ------------------------------------------------------------
    def _propose_mutation(self, raw: str, t0: float) -> Dict[str, Any]:
        self.pending = {"prompt": raw, "proposed_at": datetime.datetime.now().isoformat()}
        return self._out(
            "PROPOSED",
            "A firm hand on the controls, sir — I don't execute machine-changing orders from chat. 🦋\n"
            f"Proposal logged: '{raw}'.\n"
            "Run it where the approval gate can supervise:\n"
            f"  python cli.py jarvis --think \"{raw[:160]}\"\n"
            "or queue it on the Mission Control dashboard. Say 'proceed' and I'll walk you through approval.",
            t0, executed=False, proposal=self.pending)

    def _confirm_pending(self, t0: float) -> Dict[str, Any]:
        if not self.pending:
            return self._out("SUCCESS", "No standing orders, sir — nothing awaiting my hand. 🦋", t0)
        prompt = self.pending.get("prompt", "")
        return self._out(
            "PROPOSED",
            "Still holding that thought, sir — chat proposes, the gate disposes: 🦋\n"
            f"  python cli.py jarvis --think \"{prompt[:160]}\"\n"
            "Answer the approval prompt with `python xola.py --pending` / `--answer`, "
            "or queue it from the dashboard. I never bypass the gate — that's rather the point of me.",
            t0, executed=False, proposal=self.pending)

    # -- brain fallback ----------------------------------------------------------------------
    def _ask_brain(self, raw: str, t0: float) -> Dict[str, Any]:
        plan = self.brain.think(raw, use_llm=self.use_llm)
        act = (plan.action or "").lower().strip()
        skill = (plan.skill or "").strip()

        if act in ("", "chain"):
            self.pending = {"prompt": raw, "plan": plan.to_dict(),
                            "proposed_at": datetime.datetime.now().isoformat()}
            return self._out(
                "PROPOSED",
                "That one wants several pairs of hands, sir — a multi-step chain belongs under the daemon's "
                "supervision, not a chat bubble. I've drafted the opening move; run it via:\n"
                f"  python cli.py jarvis --think \"{raw[:160]}\"\n"
                "…and the approval gate will walk each step past you. 🦋",
                t0, executed=False, action=plan.action, skill=plan.skill,
                proposal=self.pending)

        if act == "hands":
            op = skill.replace("hands.", "").strip() or "ps"
            if op not in SAFE_HANDS_OPS:
                return self._propose_with_plan(raw, plan, t0)
        elif act not in SAFE_ACTIONS and act != "skill":
            # Unknown action type from a model bridge — do not blindly execute.
            return self._propose_with_plan(raw, plan, t0)

        try:
            result = self.brain.execute_plan(plan)
        except Exception as exc:
            return self._out("ERROR", f"The machinery balked, sir: {exc} 🦋", t0)

        if result.status == "SUCCESS":
            text = self._shorten(result.formatted_response or "Done, sir. 🦋")
            return self._out("SUCCESS", text, t0, executed=True,
                             action=plan.action, skill=plan.skill, detail=result.output)
        if result.status in ("PENDING_APPROVAL", "DENIED"):
            self.pending = {"prompt": raw, "plan": plan.to_dict(),
                            "proposed_at": datetime.datetime.now().isoformat()}
            return self._out(
                "PROPOSED",
                f"The gate raised an eyebrow, sir — '{raw[:120]}' needs your explicit approval. "
                f"Check `python xola.py --pending` and answer it there; I'll stand by. 🦋",
                t0, executed=False, action=plan.action, skill=plan.skill,
                proposal=self.pending)
        # UNSUPPORTED / ERROR / anything else → graceful honesty, JARVIS-style.
        return self._out(
            "SUCCESS",
            f"Beyond my current reach, sir — and I won't dress a guess as an answer. "
            f"Try 'help' for my repertoire, or phrase it as a reading: disk, processes, status, memory. 🦋",
            t0, executed=False, action=plan.action, skill=plan.skill)

    def _propose_with_plan(self, raw: str, plan: Any, t0: float) -> Dict[str, Any]:
        self.pending = {"prompt": raw, "plan": plan.to_dict(),
                        "proposed_at": datetime.datetime.now().isoformat()}
        return self._out(
            "PROPOSED",
            f"That order moves furniture, sir — '{raw[:120]}' would run `{plan.skill}`. "
            "I draft; the gate authorizes. Run it under supervision:\n"
            f"  python cli.py jarvis --think \"{raw[:160]}\" 🦋",
            t0, executed=False, action=plan.action, skill=plan.skill,
            proposal=self.pending)

    @staticmethod
    def _shorten(text: str, limit: int = REPLY_TRUNCATE) -> str:
        text = str(text)
        if len(text) <= limit:
            return text
        return text[:limit] + "… (truncated — ask me to narrow it down, sir) 🦋"


# =====================================================================
# 3) HTTP/session plumbing (used by server.py /api/jarvis/chat)
# =====================================================================

_SESSIONS: Dict[str, JarvisConversation] = {}


def get_session(session_id: str = "web", fact_path: Optional[str] = None,
                use_llm: bool = True) -> JarvisConversation:
    sid = (session_id or "web").strip()[:64] or "web"
    convo = _SESSIONS.get(sid)
    if convo is None:
        if len(_SESSIONS) >= MAX_SESSIONS:
            oldest = next(iter(_SESSIONS))
            del _SESSIONS[oldest]
        convo = JarvisConversation(fact_path=fact_path, use_llm=use_llm, session_id=sid)
        _SESSIONS[sid] = convo
    return convo


def handle_chat_request(req: Any, fact_path: Optional[str] = None) -> Tuple[int, Dict[str, Any]]:
    """Validate a chat POST body and return (http_code, payload). Never raises."""
    if not isinstance(req, dict):
        return 400, {"error": "JSON object required", "mark": WATERMARK}
    prompt = str(req.get("prompt", req.get("message", req.get("text", "")))).strip()
    if not prompt:
        return 400, {"error": "empty prompt", "mark": WATERMARK}
    try:
        convo = get_session(str(req.get("session", "web")), fact_path=fact_path,
                            use_llm=bool(req.get("use_llm", True)))
        out = convo.reply(prompt[:4000])
        out["history_len"] = len(convo.history)
        return 200, out
    except Exception as exc:
        return 500, {"error": f"chat engine failure: {exc}", "mark": WATERMARK}


# =====================================================================
# 4) CLI — REPL + one-shot
# =====================================================================

def _speak_best_effort(text: str) -> None:
    try:
        from jarvis.voice import speak
        speak(text[:500])
    except Exception:
        pass


def run_repl(use_llm: bool = True, speak_replies: bool = False,
             fact_path: Optional[str] = None) -> int:
    convo = JarvisConversation(fact_path=fact_path, use_llm=use_llm)
    print("Jarvis conversational shell — at your service, sir. (bye to exit, help for repertoire) 🦋")
    while True:
        try:
            line = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\njarvis › Powering down the banter, sir. 🦋")
            return 0
        if not line:
            continue
        out = convo.reply(line)
        print(f"jarvis › {out.get('response', '')}")
        if speak_replies:
            _speak_best_effort(str(out.get("response", "")))
        if out.get("end_session"):
            return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Jarvis conversational shell 🦋")
    p.add_argument("--prompt", "-p", default=None, help="One-shot prompt (skip the REPL)")
    p.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    p.add_argument("--no-llm", action="store_true", help="Force deterministic heuristic planner")
    p.add_argument("--voice", action="store_true", help="Speak replies aloud (best effort)")
    p.add_argument("--facts", default=None, help="Path to conversation facts JSON")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    use_llm = not args.no_llm
    if args.prompt:
        convo = JarvisConversation(fact_path=args.facts, use_llm=use_llm)
        out = convo.reply(args.prompt)
        if args.voice:
            _speak_best_effort(str(out.get("response", "")))
        if args.json:
            print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        else:
            print(out.get("response", ""))
        return 0 if out.get("status") in ("SUCCESS", "PROPOSED") else 1
    return run_repl(use_llm=use_llm, speak_replies=args.voice, fact_path=args.facts)


if __name__ == "__main__":
    raise SystemExit(main())
