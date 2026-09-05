# X.O.L.A. 🦋

**X.O.L.A. — a local, stdlib-only desktop-assistant harness with a JARVIS-shaped ambition.**

A persistent task queue, model-assisted planning, Windows voice, OS hands,
memory, and a local Mission Control dashboard — pure Python standard library,
no paid dependencies. This repo was promoted from a shipped bundle
(`xola_fixed.zip`, kept as a snapshot) into a real working tree, then upgraded
toward the thing it was always reaching for: a conversational JARVIS.

> **How close to JARVIS?** Roughly **4/10** — honest scorecard in
> [`JARVIS_GAP.md`](JARVIS_GAP.md). Closest in OS hands + dashboard;
> farthest in always-on duplex voice and an embedded brain.

## Layout

| Path | What it is |
|---|---|
| `jarvis/conversation.py` | **NEW** — JARVIS-style conversational shell (REPL, one-shot, HTTP). Multi-turn dialogue, status briefs, fact memory, read-only execution; mutations are proposed, never run |
| `jarvis/brain.py` | Autonomous thinking engine: AGY model bridge + offline heuristic planner |
| `jarvis/hands.py` | OS hands & eyes: processes, windows, files, screenshots, disk, sysinfo |
| `jarvis/voice.py` | Windows SAPI speech synthesis + ears utterance queue |
| `jarvis/sentinel.py` | System health probes, scheduled nudges, change radar |
| `xola.py` | Unified orchestrator: daemon, think, voice, nudges, approvals, evolution |
| `server.py` | Mission Control dashboard + REST API (`:8101`), incl. new `POST /api/jarvis/chat` |
| `cli.py` | Unified CLI: `status\|scout\|build\|guard\|memory\|skills\|test\|server\|jarvis` |
| `tools/` | Scout, builder/forge, guard auditor, memory, skills registry, orchestrator, runtime gates |
| `agents/` | Agent specs (builder, guard, scout, memory, ember, furnace, lens, spark) |
| `tests/` | Full suite incl. `test_conversation.py` (27 tests for the new shell) |
| `docs/manual.md` | The original bundle operator manual |
| `JARVIS_GAP.md` | JARVIS-likeness scorecard + roadmap |
| `REPAIR_NOTES.md` / `UPGRADE_NOTES.md` | Prior repair + 100× performance pass notes |
| `reports/` / `validation/` | Historical build reports and validation evidence |
| `xola_v1.6.md` / `xola_v1.7.md` | Persona spec history |
| `xola_fixed.zip` | Original bundle snapshot (kept, not used at runtime) |

## Quickstart (Windows)

```powershell
python xola.py --doctor
python -m jarvis.conversation            # talk to Jarvis (this upgrade)
python server.py                         # Mission Control on http://127.0.0.1:8101/
python xola.py --daemon
```

## Quickstart (Linux — dev / CI)

Core, brain (heuristic), conversation shell, guard, memory, and tests all run
cross-platform. Voice capture/speech and some hands ops are Windows-only and
degrade gracefully (`UNSUPPORTED`, never faked).

```bash
python -m jarvis.conversation --prompt "give me a status report" --no-llm
python -m unittest discover -s tests -q
```

## Talk to it

```bash
# REPL
python -m jarvis.conversation
# One-shot
python -m jarvis.conversation --prompt "how much disk space is free?" --json
# Over HTTP (dashboard running)
curl -s -X POST localhost:8101/api/jarvis/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"remember that the deploy key is blue"}'
```

The shell **executes readings** (disk, processes, status, memory) and
**proposes mutations** (kill, write, launch…): you'll get the exact supervised
command instead of a silent side effect. Say `proceed` and it walks you through
the approval gate. Details in `JARVIS_GAP.md`.

## Tests

```bash
python -m unittest discover -s tests -q
python -m unittest tests.test_conversation -v
```

## Model lanes

Reasoning uses your own AGY CLI when present (`XOLA_AGY_BIN`, `XOLA_MODEL`);
otherwise the deterministic heuristic planner answers offline. Authenticate with
the CLI's own login — no credentials are bundled, and no paid request is ever
made by the test suite.
