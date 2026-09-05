# How close is X.O.L.A. to JARVIS? 🦋

**Verdict: ~4/10 — a real, working prototype with the right organs, not the
movie magic.** It genuinely operates the machine (processes, files, windows,
screenshots), watches system health, remembers work across sessions, queues
autonomous tasks, and now holds a conversation. What it lacks is JARVIS's
effortlessness: always-on duplex voice, true language understanding, eyes that
*comprehend* the screen, and initiative.

Scores are against the fiction (10 = indistinguishable from the films), judged
on the code in this repo as of this upgrade.

## Scorecard

| # | Dimension | Score | What's real | What's missing |
|---|---|---|---|---|
| 1 | 🗣️ Voice loop (talk + listen) | **3/10** | Windows SAPI speech output; turn-based wake-phrase listener (`ears_listener.ps1`); utterance queue; new text-chat shell | No duplex/interruption, mic path Windows-only and untested here, no speaker ID, no continuous listening on Linux |
| 2 | 🧠 Brain (understanding) | **4/10** | Offline heuristic intent planner (instant, deterministic); AGY/Gemini bridge when your CLI is present; skill registry + chain planner | No embedded model; heuristics are keyword rules, not NLU; multi-step plans need the daemon, not chat |
| 3 | 🖐️ Hands (act on the machine) | **6/10** | Real process/window/file/screenshot/disk control, stdlib-only, approval-gated, atomic writes | No in-app control (browser DOM, GUI clicking beyond focus), no mobile/IoT/suit 😄 |
| 4 | 👀 Eyes (see the screen) | **3/10** | On-demand screenshot + local Tesseract OCR, explicitly flagged untrusted input | Text extraction only — no UI grounding ("click the red button"), no video/scene understanding |
| 5 | 👂 Ears (always-on hearing) | **2/10** | Wake-phrase queue plumbing, durable inbox tasks | Turn-based, not always-on; no diarization; biggest single gap alongside duplex voice |
| 6 | 🧬 Memory | **6/10** | SQLite vault + markdown distillation + timeline/stats + **new** chat fact book (`remember that X is Y`) | Lexical retrieval only, no embeddings; no forgetting curve beyond manual `forget` |
| 7 | ⚡ Proactivity | **4/10** | Sentinel health + scheduled nudges; long-horizon loop with Manage→Execute→Audit | Nudges, not initiative — no self-set goals, no "I noticed X so I did Y" beyond narrow monitors |
| 8 | 🖥️ Presence (dashboard) | **7/10** | Mission Control workbench, 10+ REST endpoints with TTL cache, **new** `POST /api/jarvis/chat` for live dialogue | Desktop web UI only; no companion app, no overlay/HUD |
| 9 | 🛡️ Reliability & safety | **6/10** | Approval gates, atomic writes, 500+ passing tests, PENDING/DENIED propagation | No exactly-once guarantee across external side effects (see `REPAIR_NOTES.md`); Windows paths need local proving |
| 10 | 🎭 Personality | **5/10** | **New** conversational shell: dry butler wit, status briefs, graceful "beyond my reach" honesty, one HAL joke | Persona engine + agent voices exist but aren't deeply wired into dialogue yet |

**Closest:** hands + dashboard — it really does things. **Farthest:** ears + duplex voice.

## What this upgrade added (v1.8-track)

1. **Conversational shell** (`jarvis/conversation.py`) — the JARVIS interaction
   model the repo was missing: everything was one-shot (`--think`) or queued
   (inbox). Now: REPL + `--prompt` one-shot + shared sessions over HTTP.
2. **Glass-cockpit safety policy** — chat executes *readings* and *proposes*
   mutations with the exact supervised command. "Proceed" walks you to the
   approval gate instead of bypassing it. 27 regression tests pin this.
3. **Chat fact memory** — `remember/recall/forget` in dialogue, persisted to
   `loop/conversation_facts.json` (git-ignored runtime state).
4. **Dashboard chat endpoint** — `POST /api/jarvis/chat` (`{prompt, session?}`)
   → `{status, response, executed, …}`. Same engine as the CLI shell.
5. **Repo promotion** — 86 source files extracted from `xola_fixed.zip` into a
   real tree; runtime junk (logs, telemetry, screenshot PNGs, 396K of
   machine-local memory, embedded `.git`) left out; `.gitignore` hardened.

## Roadmap to 7/10 (ordered by leverage)

1. **Duplex voice** — streaming STT + barge-in + TTS on the chat engine; the
   dialogue state machine already exists, it just needs a real-time transport.
2. **Embedded local-model lane** — a small on-device model as the default
   planner so the brain works fully offline and stops being keyword-bound.
3. **Screen grounding** — from OCR text to "the Save button at (x, y)": UI
   element detection + safe click/type actions behind the existing gate.
4. **Goal loop** — let the sentinel file standing objectives ("keep disk under
   85%") that the daemon pursues and reports on, instead of only nudging.
5. **Cross-platform hands** — first-class Linux/macOS parity for the ops that
   are Windows-only today; CI already runs the suite on Linux.

## Try the gap yourself

```bash
python -m jarvis.conversation --prompt "give me a status report" --no-llm
python -m jarvis.conversation --prompt "kill process 1234" --no-llm   # PROPOSED, not run
python -m jarvis.conversation --prompt "remember that the deploy key is blue" --no-llm
```
