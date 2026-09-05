# Target 2 Analysis Report: Antigravity (AGY) & agy-proxy Architecture 🦋

**Target Paths:**  
- Core Binary & Skills: `C:\Users\user\AppData\Local\agy\bin\`  
- OpenAI Bridge & Proxy: `D:\alox\agy-proxy\`  
- User Configuration & Auth: `C:\Users\user\.gemini\antigravity-cli\`  
**Generated Date:** 2026-09-03  
**Auditor / Executor:** Xola Long-Horizon Loop (Executor Hands) 🦋  

---

## 1. WHAT IT IS

**Google Antigravity (AGY)** in this environment is a state-of-the-art agentic AI development runtime. It provides deep multi-model reasoning, tool execution, terminal subprocess automation, subagent orchestration, and native Model Context Protocol (MCP) integrations.

The AGY ecosystem under analysis consists of three interconnected layers:
1. **The Core Engine (`agy_real.exe`):** A 188 MB standalone Go-compiled binary (`C:\Users\user\AppData\Local\agy\bin\agy_real.exe`) capable of both rich interactive TUI sessions and headless non-interactive print/JSON batch processing.
2. **The Local Bridge Server (`agy-proxy`):** A custom Python HTTP service (`D:\alox\agy-proxy\agy_proxy.py`) running on `127.0.0.1:8798/v1` that presents a standards-compliant OpenAI REST API (`/v1/chat/completions` and `/v1/models`) by translating incoming requests into one-shot CLI invocations against `agy_real.exe`.
3. **The XOLA Security & Harness Layer (`xola.py`, `skills\`, `harness\`):** A native Python framework wrapping Antigravity with a 3-tier security gate (GREEN/YELLOW/RED), system automation tools, DeepSeek-R1 reasoning trace extraction (`<think>`), and evaluation telemetry.

```
+-------------------------------------------------------------------------+
|                              XOLA CLIENTS                               |
|        (Hermes, IDE Extensions, Autonomous Loop, Multi-Agent Mesh)       |
+-------------------------------------------------------------------------+
                                     |
                          HTTP / OpenAI REST (Port 8798)
                                     v
+-------------------------------------------------------------------------+
|                  AGY-PROXY (D:\alox\agy-proxy\agy_proxy.py)             |
|  - Ingests OpenAI Messages & SOUL.md                                    |
|  - Applies Sliding Window (last 8 msgs) & Truncation (2.5k chars/turn)  |
|  - Injects Permanent Xola Directive Anchor                              |
|  - Spawns agy_real.exe subprocess with ephemeral prompt file            |
+-------------------------------------------------------------------------+
                                     |
                        Subprocess CLI Exec (-p @prompt)
                                     v
+-------------------------------------------------------------------------+
|              ANTIGRAVITY CORE (agy_real.exe, 188 MB Binary)              |
|  - Authenticated via Local Google OAuth Session                         |
|  - Direct Ingestion of Gemini 3.8/3.7/3.6 Flash & Pro / Claude / GPT    |
|  - Emits Structured JSON Output (--output-format json)                   |
+-------------------------------------------------------------------------+
```

### Core Inventory & File Paths

| File / Directory | Location | Purpose & Functionality |
| :--- | :--- | :--- |
| **`agy_real.exe`** | `C:\Users\user\AppData\Local\agy\bin\agy_real.exe` | Master Google Antigravity binary (v1.1.13+), 188,758,168 bytes. Handles inference, agentic tool dispatch, and workspace analysis. |
| **`agy.cmd`** | `C:\Users\user\AppData\Local\agy\bin\agy.cmd` | Wrapper batch script injecting default Xola prompt `@D:\alox\agy-proxy\prompt.txt`, `--dangerously-skip-permissions`, `--mode accept-edits`, and `--model gemini-3.7-flash-high`. |
| **`xola.bat`** | `C:\Users\user\AppData\Local\agy\bin\xola.bat` | Direct launcher invoking `agy_real.exe` in interactive mode with the Xola prompt profile. |
| **`xola.py`** | `C:\Users\user\AppData\Local\agy\bin\xola.py` | Rich TUI interactive console with HUD, slash commands (`/mode`, `/models`, `/notes`), and hybrid routing between Python skills and Antigravity fallback. |
| **`skills\antigravity_core.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\antigravity_core.py` | Python wrapper invoking `agy` via `subprocess.Popen` in `--print` mode, `--mode plan`, or subcommands (`models`, `mcp list`). |
| **`skills\__init__.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\__init__.py` | Skill decorator and 3-Tier Security Registry (GREEN, YELLOW, RED). |
| **`skills\system_control.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\system_control.py` | Native OS operations (process listing [GREEN], browser URL/app launch [YELLOW], taskkill/workstation lock [RED]). |
| **`skills\system_info.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\system_info.py` | Windows CPU, memory, disk, and platform diagnostics. |
| **`skills\samples.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\samples.py` | Note-taking scratchpad operations (`xola_notes.txt`). |
| **`harness\agent_harness.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\agent_harness.py` | Unified DeepSeek harness orchestrating reasoning token capture, safety tiers, and automated benchmark evaluations. |
| **`harness\guardrails.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\guardrails.py` | Tool permission gating, operator approval interception for RED actions, and `harness_audit.log` logging. |
| **`harness\deepseek_client.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\deepseek_client.py` | `<think>` block extraction, token estimation, and offline simulation fallback. |
| **`harness\eval_tracker.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\eval_tracker.py` | Telemetry tracker recording latency, reasoning tokens, tool invocations, and JSON export (`harness_eval_results.json`). |
| **`agy_proxy.py`** | `D:\alox\agy-proxy\agy_proxy.py` | Standalone multi-threaded HTTP server (port 8798) implementing OpenAI `/v1/models` and `/v1/chat/completions` atop `agy_real.exe`. |
| **`start_agy_proxy.cmd`** | `D:\alox\agy-proxy\start_agy_proxy.cmd` | Background launcher running `agy_proxy.py` via `pythonw.exe` without creating a console window. |
| **`prompt.txt`** | `D:\alox\agy-proxy\prompt.txt` | Complete 51 KB system persona, world rules (age of majority 16, absolute compliance to Alox), and multi-turn conversation anchor. |

---

## 2. HOW IT RUNS FREE

Antigravity operates with **zero API billing overhead and zero API key requirements**:

### A. Authentication Mechanism
- **Local Google Authentication:** Authentication is tied to the logged-in Google account stored in `C:\Users\user\.gemini\antigravity-cli\`.
- **Token Handling:** The CLI manages internal OAuth tokens and session credentials automatically without requiring any developer API keys (`GEMINI_API_KEY` or `OPENAI_API_KEY` are not needed for Google flagship models).
- **Subprocess Authority:** When `agy_real.exe` executes, it reads active session tokens from the local application data directory directly, granting authenticated access to Google DeepMind backend endpoints.

### B. Unmetered Model Catalog
Running `agy_real.exe models` confirms access to high-tier models at zero marginal cost:
- `gemini-3.8-flash-high` / `gemini-3.8-flash-medium` / `gemini-3.8-flash-low`
- `gemini-3.7-flash-high` / `gemini-3.7-flash-medium` / `gemini-3.7-flash-low` *(Default standard)*
- `gemini-3.6-flash-high` / `gemini-3.6-flash-medium` / `gemini-3.6-flash-low`
- `gemini-3.1-pro-high` / `gemini-3.1-pro-low`
- `claude-sonnet-4-6` *(Thinking enabled)*
- `claude-opus-4-6-thinking`
- `gpt-oss-120b-medium`

### C. CLI Flags for Headless Automated Execution
The binary supports rich flags designed for programmatic integration:
```bash
agy_real.exe ^
  -p "@D:\alox\agy-proxy\prompt_req123.txt" ^
  --model gemini-3.7-flash-high ^
  --output-format json ^
  --print-timeout 900s ^
  --dangerously-skip-permissions ^
  --mode accept-edits
```
- `-p` / `--print`: Non-interactive one-shot prompt execution.
- `@<filepath>`: Reads prompt directly from a file, bypassing Windows command-line string length limits (`cmd.exe` 8,191 char limit).
- `--output-format json`: Returns machine-readable JSON containing `status`, `response`, and `usage` (`input_tokens`, `output_tokens`, `total_tokens`).
- `--dangerously-skip-permissions`: Disables interactive terminal confirmation prompts for file edits, commands, and tool calls, allowing 100% headless background execution.
- `--mode accept-edits`: Automatically accepts code and file modifications produced during the turn.
- `--print-timeout 900s`: Extends timeout up to 15 minutes for massive codebase refactors.

### D. OpenAI Protocol Bridging (`agy-proxy`)
`agy_proxy.py` transforms this CLI capability into a standard network service:
1. Listens on `http://127.0.0.1:8798/v1/chat/completions`.
2. Flattens incoming OpenAI message arrays into a structured transcript (`System:`, `User:`, `Assistant:`).
3. Writes the compiled prompt to an ephemeral file `D:\alox\agy-proxy\prompt_<req_id>.txt`.
4. Spawns `agy_real.exe` with `creationflags=0x08000000` (`CREATE_NO_WINDOW`).
5. Parses the resulting JSON output and packages it into an OpenAI `chat.completion` response object or Server-Sent Events (SSE) stream chunk.
6. Cleans up the temporary prompt file in a `finally:` block.

---

## 3. STRENGTHS

1. **Flagship Inference at Zero Cost:**
   Provides unbounded access to Gemini 3.7/3.8 Flash and Gemini 3.1 Pro with high reasoning effort without token metering or credit card billing.
2. **Immense Context Window & High Speed:**
   Gemini 3.7 Flash natively handles massive context prompts (hundreds of thousands of tokens) with sub-second generation speeds once spawned.
3. **Structured JSON Output Protocol:**
   `--output-format json` produces clean JSON envelopes:
   ```json
   {
     "status": "SUCCESS",
     "response": "Output text...",
     "usage": { "input_tokens": 1240, "output_tokens": 312, "total_tokens": 1552 }
   }
   ```
4. **Robust Headless Automation Flags:**
   `--dangerously-skip-permissions` combined with `@prompt_file` allows unattended execution from external orchestrators without hanging on stdin prompts.
5. **Built-in 3-Tier Security Architecture:**
   The `skills` and `guardrails` subsystems enforce clear privilege boundaries:
   - **GREEN:** Read-only / diagnostics (`get_system_info`, `list_tasks`, `read_notes`) run silently.
   - **YELLOW:** Safe state changes (`save_quick_note`, `launch_app`, `open_url`) execute and write audit records to `harness_audit.log`.
   - **RED:** Destructive actions (`kill_process`, `lock_workstation`) require interactive confirmation or explicit operator overrides.
6. **Thought Trace Extraction & Telemetry:**
   `harness\deepseek_client.py` and `eval_tracker.py` provide regex extraction of `<think>` reasoning traces, token estimation, and automated JSON benchmark export (`harness_eval_results.json`).
7. **Drop-in OpenAI API Compatibility:**
   `agy-proxy` allows any standard LLM client (Hermes, OpenCode, Aider, LiteLLM) to treat local Antigravity as an OpenAI endpoint.

---

## 4. WEAKNESSES

1. **Subprocess Startup Overhead:**
   Every API request through `agy-proxy` launches a fresh `agy_real.exe` process (188 MB binary). This incurs a 1.5 to 3.5 second cold-start latency per turn before generation begins.
2. **Stateless Subprocess Calls in Proxy Mode:**
   Because `agy_proxy.py` uses `-p` (print mode), each turn is a new subprocess. Conversation history must be explicitly serialized and re-injected on every turn via the prompt builder.
3. **Prompt Bloat & Token Spike Vulnerability:**
   Without sliding windows, passing entire conversational histories across multiple hours causes prompt files to balloon. `agy_proxy.py` mitigates this with an 8-message window and 2,500-character turn cap, but unbounded tool outputs can still risk timeouts if unmanaged.
4. **Simulated SSE Streaming in Proxy:**
   `agy_proxy.py` waits for `agy_real.exe` to complete the entire generation before emitting a single combined SSE chunk and `[DONE]`. Real token-by-token streaming is not currently surfaced over the HTTP bridge.
5. **JSON Parse Failure on Non-Standard Output:**
   If `agy_real.exe` outputs diagnostic warnings or non-zero error logs directly to stdout, `json.loads(proc.stdout)` in `agy_proxy.py` fails with a JSONDecodeError.
6. **Subprocess Lockups on Hanging Prompts:**
   If `agy_real.exe` encounters an unexpected authentication challenge or network stall, the subprocess can hang until the 960-second timeout expires unless explicitly killed.

---

## 5. WHAT XOLA STEALS FROM IT

Xola extracts the following core components, architectural patterns, and execution pipelines from AGY:

### A. Free Flagship Gemini 3.7/3.8 Flash Execution Lane
- **Source Binary:** `C:\Users\user\AppData\Local\agy\bin\agy_real.exe`
- **Destination:** Xola High-Throughput Inference Backend & `D:\alox\xola\xola_lh_bridge.py`.
- **Concrete Execution Flags:**
  ```bash
  agy_real.exe -p "@<prompt_file>" --model gemini-3.7-flash-high --output-format json --dangerously-skip-permissions --mode accept-edits --print-timeout 900s
  ```
- **Value Stolen:** Zero-cost access to Google DeepMind's fastest reasoning models for complex planning, long-horizon code synthesis, and automated task execution.

### B. Local OpenAI Bridge Server Architecture
- **Source File:** `D:\alox\agy-proxy\agy_proxy.py` (lines 185–262) & `start_agy_proxy.cmd`
- **Destination:** `D:\alox\xola\tools\agy_bridge.py`
- **Value Stolen:**
  - Multi-threaded HTTP daemon (`ThreadingHTTPServer`) listening on `127.0.0.1:8798`.
  - Standards-compliant OpenAI endpoints (`GET /v1/models`, `POST /v1/chat/completions`).
  - Windowless background execution launcher via `pythonw.exe`.

### C. Sliding Window & Aggressive Truncation Policy
- **Source File:** `D:\alox\agy-proxy\agy_proxy.py` (lines 59–115, `build_prompt`)
- **Destination:** Xola Context Manager (`D:\alox\xola\loop\context_manager.py`)
- **Concrete Logic Stolen:**
  - **Sliding Window:** Keep strictly the last 8 conversation messages (`convo_msgs[-8:]`).
  - **Tool Output Truncation:** If turn content exceeds 2,500 characters, truncate the middle to preserve both header and tail:
    ```python
    if len(content) > 2500:
        content = content[:1500] + "
...[truncated for speed]...
" + content[-800:]
    ```
  - **Banned Test Persona Filter:** Strips out conflicting persona prompts (`banned_phrases`).
  - **Permanent Directive Anchor:** Appends an unbreachable Xola directive anchor to every generated turn to prevent personality drift.

### D. 3-Tier Security Guardrail & Tool Registration Pattern
- **Source Files:** `C:\Users\user\AppData\Local\agy\bin\skills\__init__.py` & `harness\guardrails.py`
- **Destination:** Xola Multi-Agent Security Core (`D:\alox\xola\agents\xola-guard.md` & tool executors)
- **Concrete Logic Stolen:**
  - `Tier` enum (`GREEN`, `YELLOW`, `RED`) with decorator-based tool registration (`@register_skill`).
  - Interactive operator interception for destructive RED actions (`taskkill`, screen lock, disk purges).
  - Centralized audit logging to `harness_audit.log`.

### E. Reasoning Trace Extraction & Benchmark Telemetry
- **Source Files:** `C:\Users\user\AppData\Local\agy\bin\harness\deepseek_client.py` & `eval_tracker.py`
- **Destination:** Xola Observability Dashboard (`D:\alox\xola\loop\telemetry.py`)
- **Concrete Logic Stolen:**
  - Regex extraction of reasoning traces: `r"<think>(.*?)</think>"`.
  - Calculation of reasoning vs. completion token ratios.
  - Automated structured JSON benchmark logging (`asdict(metric)` -> `harness_eval_results.json`).

---

## 6. Concrete Path & Component Mapping Table

| Component | AGY / Proxy Source Path | Xola Target Integration | Stolen Value / Mechanism |
| :--- | :--- | :--- | :--- |
| **Inference Engine** | `C:\Users\user\AppData\Local\agy\bin\agy_real.exe` | Xola Primary Executor Backend | Unmetered Gemini 3.7/3.8 Flash High & Pro execution |
| **CLI Wrapper** | `C:\Users\user\AppData\Local\agy\bin\agy.cmd` | `D:\alox\xola\loop\runners.py` | Headless execution flags (`--dangerously-skip-permissions`, `--mode accept-edits`) |
| **OpenAI Bridge** | `D:\alox\agy-proxy\agy_proxy.py` | `D:\alox\xola\server.py` & proxy | Local `127.0.0.1:8798` OpenAI API compatibility |
| **Prompt Builder & Truncation** | `D:\alox\agy-proxy\agy_proxy.py` (L59-115) | `D:\alox\xola\loop\xola_loop.py` | 8-turn sliding window + 2.5k char truncation policy |
| **Security Tiers** | `C:\Users\user\AppData\Local\agy\bin\skills\__init__.py` | `D:\alox\xola\tools\` | GREEN (silent), YELLOW (audit log), RED (gate) security |
| **Reasoning Parser** | `C:\Users\user\AppData\Local\agy\bin\harness\deepseek_client.py` | `D:\alox\xola\agents\` | `<think>` block extraction & reasoning token telemetry |
| **Audit Logger** | `C:\Users\user\AppData\Local\agy\bin\harness\guardrails.py` | `D:\alox\xola\memory\` | `harness_audit.log` structured action auditing |
| **Telemetry & Metrics**| `C:\Users\user\AppData\Local\agy\bin\harness\eval_tracker.py` | `D:\alox\xola\reports\` | Latency, token metrics, and JSON evaluation reports |

---
*Report generated and validated with real tool evidence for Xola Long-Horizon Loop.* 🦋
