# Target 4 Analysis Report: DeepSeek Harness & Skills Registry Architecture 🦋

**Target Paths:**  
- Harness Core: `C:\Users\user\AppData\Local\agy\bin\harness\`  
- Skills Registry: `C:\Users\user\AppData\Local\agy\bin\skills\`  
- LongHorizon DSH Adapter: `D:\alox\LongHorizon-Harness\src\lh_harness\adapters\deepseek_harness.py`  
- LongHorizon DSH Runner: `D:\alox\LongHorizon-Harness\src\lh_harness\adapters\deepseek_runner.py`  
**Generated Date:** 2026-09-03  
**Auditor / Executor:** Xola Long-Horizon Loop (Executor Hands) 🦋  

---

## 1. WHAT IT IS

The **DeepSeek Harness & Skills Registry** subsystem (`C:\Users\user\AppData\Local\agy\bin\harness\` and `C:\Users\user\AppData\Local\agy\bin\skills\`) is a modular, multi-tier Python orchestration and execution environment designed to pair DeepSeek reasoning engines (DeepSeek-R1 / DeepSeek-V3 / `deepseek-reasoner` / `deepseek-v4-flash`) with a structured, security-gated local OS tool execution framework.

The system combines four core architectural pillars:
1. **Unified Orchestration & Reasoning Trace Extraction (`agent_harness.py` & `deepseek_client.py`):**  
   Manages the agent lifecycle, handles model inference, parses DeepSeek-R1 `<think>...</think>` Chain-of-Thought (CoT) reasoning blocks, estimates token consumption, and parses tool invocations formatted as structured JSON payloads (`{"action": "call_tool", "tool": "...", "args": {...}}`).
2. **3-Tier Security Guardrails (`guardrails.py`):**  
   Implements a strict permission gating model (**GREEN** / **YELLOW** / **RED**) separating safe read-only actions, logged disk/app mutations, and destructive or system-critical operations requiring interactive operator approval. Writes persistent audit trails to `harness_audit.log`.
3. **Telemetry & Observability Tracker (`eval_tracker.py`):**  
   Records end-to-end execution latency, reasoning token volume, response token volume, tool invocation statistics by security tier, error states, and thought summaries. Exports full benchmark run histories to structured JSON (`harness_eval_results.json`).
4. **Dynamic Extensible Skills Registry (`skills\__init__.py` + skill modules):**  
   Provides a clean decorator-based plugin architecture (`@register_skill`) with prefix-matching priority, category tagging, keyword triggers, and native Windows automation handlers across Antigravity AI delegation, system diagnostics, process management, and local scratchpad storage.

```
+-------------------------------------------------------------------------+
|                      XOLA AUTONOMOUS RUNTIME / REPL                     |
|           (Interactive CLI, Autonomous Loop, Benchmark Suite)           |
+-------------------------------------------------------------------------+
                                     |
                          User Prompt Ingestion
                                     v
+-------------------------------------------------------------------------+
|                XOLA DEEPSEEK HARNESS (agent_harness.py)                  |
|  - Ingests User Prompt & Starts Evaluation Run                          |
|  - Calls DeepSeek Engine (API / Ollama / Offline Heuristic Simulator)   |
|  - Extracts <think> CoT Block & Estimates Reasoning/Completion Tokens   |
|  - Decodes Action JSON: {"action": "call_tool", "tool": ..., "args": ..}|
+-------------------------------------------------------------------------+
                                     |
                     Tool Authorization & Execution Gate
                                     v
+-------------------------------------------------------------------------+
|                 SECURITY GUARDRAIL (guardrails.py)                      |
|  [GREEN]  -> Auto-Execute Silently (Read-only / Safe diagnostics)       |
|  [YELLOW] -> Auto-Execute + Write Audit Log (App launch / Note write)   |
|  [RED]    -> Intercept + Require Operator (y/N) (kill proc, lock PC)    |
|  * Persistent Log: harness_audit.log                                    |
+-------------------------------------------------------------------------+
                                     |
                         Dispatches Authorized Tool
                                     v
+-------------------------------------------------------------------------+
|                 SKILLS REGISTRY (skills\__init__.py)                    |
|  - antigravity_core.py : Antigravity AI Query, Planning Mode, Models    |
|  - system_info.py      : OS Diagnostics, CPU, C: Disk Usage             |
|  - system_control.py   : Tasklist, Browser Launch, Taskkill, LockPC     |
|  - samples.py          : Note Scratchpad (Save, Read, Clear Notes)      |
+-------------------------------------------------------------------------+
                                     |
                          Collects Results & Telemetry
                                     v
+-------------------------------------------------------------------------+
|                 HARNESS TELEMETRY (eval_tracker.py)                     |
|  - Computes Latency (s), Token Breakdown, Tier Counts                   |
|  - Renders Terminal Summary Card & Exports harness_eval_results.json    |
+-------------------------------------------------------------------------+
```

---

### Core Inventory & File Paths

| File / Component | Absolute File Path | Size / Lines | Key Responsibilities & Capabilities |
| :--- | :--- | :--- | :--- |
| **`harness\__init__.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\__init__.py` | 634 bytes / 22 lines | Public API package exports for guardrails, telemetry, client, DSH process, and master harness. |
| **`harness\agent_harness.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\agent_harness.py` | 8,209 bytes / 193 lines | Master orchestrator `XolaDeepSeekHarness`. Binds `SKILL_REGISTRY` into guardrails, executes turns, parses action JSON, runs benchmark suite, and provides interactive REPL. |
| **`harness\guardrails.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\guardrails.py` | 4,512 bytes / 97 lines | `SecurityGuardrail` and `ToolPermissionTier` (GREEN/YELLOW/RED). Intercepts tool calls, enforces human-in-the-loop approval on RED, logs to `harness_audit.log`. |
| **`harness\eval_tracker.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\eval_tracker.py` | 3,280 bytes / 79 lines | `HarnessTelemetry` and `EvaluationMetrics`. Records latency, token counts, tier breakdown, renders summary cards, exports `harness_eval_results.json`. |
| **`harness\dsh_controller.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\dsh_controller.py` | 2,959 bytes / 79 lines | `DeepSeekHarnessProcess`. Supervises official `@deepseek-ai/dsh` runtime via `npx @deepseek-ai/dsh web --port 3080` with background spawning and lifecycle control. |
| **`harness\deepseek_client.py`** | `C:\Users\user\AppData\Local\agy\bin\harness\deepseek_client.py` | 5,826 bytes / 151 lines | `DeepSeekEngine` and `AgentThoughtTrace`. Extracts `<think>` regex blocks, computes token estimates, queries DeepSeek REST API, and provides offline simulation fallback. |
| **`skills\__init__.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\__init__.py` | 2,612 bytes / 88 lines | Decorator `@register_skill`, `Skill` class, `Tier` enum, global `SKILL_REGISTRY`, and `find_matching_skill()` matching logic. |
| **`skills\antigravity_core.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\antigravity_core.py` | 6,099 bytes / 191 lines | Subprocess bridge to `agy` CLI (`--print`, `--mode plan`, `--continue`, `models`, `mcp list`). All exposed as Tier GREEN skills. |
| **`skills\system_info.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\system_info.py` | 1,869 bytes / 54 lines | Tier GREEN diagnostics: OS version, CPU logical cores, RAM/disk C: metrics (`shutil.disk_usage`), timestamp, Python version. |
| **`skills\system_control.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\system_control.py` | 5,198 bytes / 138 lines | OS automation: `tasklist` (GREEN), browser URL launch & app startup (YELLOW), `taskkill` & workstation lock via `user32.dll` (RED). |
| **`skills\samples.py`** | `C:\Users\user\AppData\Local\agy\bin\skills\samples.py` | 2,459 bytes / 78 lines | Local persistent note-taking in `xola_notes.txt`: `read_notes` (GREEN), `save_quick_note` (YELLOW), `clear_notes` (RED). |
| **`lh_harness\deepseek_harness.py`** | `D:\alox\LongHorizon-Harness\src\lh_harness\adapters\deepseek_harness.py` | 3,718 bytes / 102 lines | Headless adapter for LongHorizon benchmark runs. Maps agent roles to permission modes (`read-only` vs `workspace-write`), isolates `DSH_HOME`. |
| **`lh_harness\deepseek_runner.py`** | `D:\alox\LongHorizon-Harness\src\lh_harness\adapters\deepseek_runner.py` | 2,767 bytes / 98 lines | Bridge generating dynamic model patch YAML (`.dsh-model-patch.yml`) and executing `dsh --profile headless --patch <patch> <prompt>` with JSON output. |

---

## 2. HOW IT RUNS FREE

The DeepSeek Harness & Skills Registry achieves complete zero-cost, zero-billing execution across four operational modes:

### A. Offline Simulated Heuristic Engine (100% Zero-Network / Zero-Key)
When `DEEPSEEK_API_KEY` is not provided (or when operating in offline testing/eval environments), `deepseek_client.py` gracefully falls back to `_simulate_deepseek_reasoning(prompt)`.  
- It synthesizes genuine DeepSeek-R1 style `<think>` Chain-of-Thought blocks.
- It dynamically maps intent to valid structured action JSON (`get_system_info`, `save_quick_note`, `lock_workstation`).
- It enables complete end-to-end testing of guardrail tiers, telemetry tracking, and tool execution without incurring network latency or token costs.

### B. Standard Library Native Python Architecture
Unlike heavyweight agent frameworks requiring extensive pip dependency graphs and cloud databases, the harness and skills registry run almost exclusively on standard Python 3:
- **Networking:** Standard `urllib.request` in `deepseek_client.py` (no external `requests` or `httpx` required).
- **Subprocesses:** Standard `subprocess.Popen` / `subprocess.run` in `antigravity_core.py`, `system_control.py`, and `dsh_controller.py`.
- **System Calls:** `ctypes.windll.user32` for Windows native API operations (e.g. `LockWorkStation`).
- **Telemetry & Data Structures:** Standard library `@dataclass`, `asdict`, `json`, `logging`, `time`.

### C. Free Multi-Provider Backend Routing
When connected to live LLM backends, the harness routes to zero-marginal-cost endpoints:
1. **Local Ollama / Llama.cpp Endpoints:** Configurable `base_url` pointing to `http://localhost:11434/v1` running quantized DeepSeek-R1 or DeepSeek-Coder models.
2. **OpenCode Free Tier Bridge:** Integration with `opencode/deepseek-v4-flash-free` (`DEFAULT_OPENCODE_MODEL`) or Cloudflare Workers AI free models (`@cf/deepseek-ai/deepseek-r1-distill-qwen-32b`).
3. **Antigravity AI Bridge:** Calling `skills\antigravity_core.py` delegates directly to `agy_real.exe` using Google session authentication for free Gemini 3.7 Flash High / Claude Sonnet thinking runs.

### D. Headless Batch Execution via LongHorizon Adapter
The LongHorizon Harness adapter (`deepseek_harness.py` & `deepseek_runner.py`) provides headless non-interactive execution:
- Writes dynamic `.dsh-model-patch.yml` configuration patches on the fly.
- Executes `dsh --profile headless --patch <patch_file> <prompt>` without human prompts.
- Emits newline-delimited JSON (`{"type": "dsh.result", "text": "...", "is_error": false, "exit_code": 0}`) to stdout.

---

## 3. STRENGTHS

1. **3-Tier Explicit Security Architecture (GREEN / YELLOW / RED):**  
   The separation between silent read-only execution (GREEN), logged state mutations (YELLOW), and human-gated destructive operations (RED) provides an exceptionally clean, robust security boundary. The guardrail intercepts execution before any system API is invoked.
2. **First-Class Chain-of-Thought (<think>) Telemetry:**  
   `deepseek_client.py` and `eval_tracker.py` treat reasoning traces as primary observability metrics. By separating `<think>` tokens from completion tokens, the system measures reasoning effort independently of output length.
3. **Decorator-Based Dynamic Skill Registration:**  
   The `@register_skill` decorator in `skills\__init__.py` makes extending agent capabilities trivial. Adding a new tool requires only decorating a Python function with metadata (`name`, `tier`, `keywords`, `description`, `category`, `prefix_match`).
4. **Resilient Fallback & Fault Tolerance:**  
   If an API call fails or the key is omitted, the engine does not crash; it wraps the failure inside a synthetic `<think>` block and falls back to deterministic simulation, keeping test suites and loop runs alive.
5. **Comprehensive Audit Logging:**  
   Every YELLOW and RED tool invocation is recorded with UTC timestamp, parameters, and return value in `harness_audit.log`, ensuring full traceability for autonomous long-horizon runs.
6. **Structured Evaluation Reporting:**  
   `eval_tracker.py` formats run metrics into both clean terminal visual summaries and machine-readable JSON dumps (`harness_eval_results.json`), enabling programmatic benchmark comparisons over time.

---

## 4. WEAKNESSES

1. **Blocking Interactive RED Intercept in Automated Loops:**  
   In `guardrails.py`, RED tier actions invoke Python's blocking `input()` prompt:
   ```python
   choice = input(f"Approve execution of '{tool_name}'? (y/N): ").strip().lower()
   ```
   In a headless or autonomous loop (such as the 10-hour Xola loop), this causes the process to hang indefinitely waiting for stdin unless an automated policy or bypass adapter is supplied.
2. **Simplified Rule-Based Simulator:**  
   The offline `_simulate_deepseek_reasoning` method uses basic substring checks (`"specs"`, `"note"`, `"lock"`). It does not maintain multi-turn conversational context or handle arbitrary complex multi-step reasoning offline.
3. **Rigid Regex for `<think>` Extraction:**  
   The regex `r"<think>(.*?)</think>"` requires a well-formed closing `</think>` tag. If a streaming response is cut off mid-thought or the model emits unclosed tags, the parser fails to isolate the thought block and dumps the entire output into `action_content`.
4. **Synchronous Single-Turn Execution:**  
   `XolaDeepSeekHarness.execute_turn()` is synchronous and executes only a single tool call per turn. It lacks a multi-step agentic loop (ReAct step cycle) to re-prompt the LLM with tool outputs within the same turn.
5. **Potential Shell Injection in `system_control.py`:**  
   `launch_app` calls `subprocess.Popen(f"start {app}", shell=True)` after checking a basic blocklist. A malicious or malformed app argument could bypass the keyword filter if not properly tokenized via `shlex.split`.

---

## 5. WHAT XOLA STEALS FROM IT

Xola extracts the core structural mechanics of the DeepSeek Harness and Skills Registry to empower the autonomous multi-agent mesh (`xola-scout`, `xola-builder`, `xola-guard`, `xola-memory`):

```
+-----------------------------------------------------------------------------------------+
|                              WHAT XOLA STEALS FROM TARGET 4                             |
+=========================================================================================+
| 1. 3-TIER GUARDRAIL SYSTEM  -> Injected into xola-guard (Policy Gating & Audit Logging) |
| 2. TELEMETRY & REASONING    -> Injected into xola-loop & xola-memory (Run Metrics)      |
| 3. DYNAMIC SKILL REGISTRY   -> Injected into xola-builder & tools/ (Tool Scaffolding)   |
| 4. HEADLESS MODEL RUNNER    -> Injected into xola_lh_bridge.py (JSONL Bridge Execution) |
+-----------------------------------------------------------------------------------------+
```

### A. 3-Tier Security Guardrail System for `xola-guard`

Xola adopts the exact GREEN / YELLOW / RED security classification model from `guardrails.py`. In Xola's autonomous loop, `xola-guard` uses this tier matrix to validate actions before they are executed or committed to disk:

- **Source:** `C:\Users\user\AppData\Local\agy\bin\harness\guardrails.py` (L22-97)
- **Destination:** `D:\alox\xola\agents\xola-guard.md` and Xola execution loop.

#### Tier Definition & Permission Matrix:
```python
class ToolPermissionTier(Enum):
    GREEN = "GREEN"    # Auto-execute silently: Read-only probes, system diagnostics, inspect files
    YELLOW = "YELLOW"  # Auto-execute & write audit log: Scaffold tools, write notes, curl APIs
    RED = "RED"        # Intercept & require guard/operator signoff: Delete files, kill procs, reset state
```

#### Guardrail Execution Pattern:
```python
def authorize_and_execute(self, tool_name: str, tool_args: Dict[str, Any], executor: Callable) -> Dict[str, Any]:
    tier = self.get_tier(tool_name)
    if tier == ToolPermissionTier.GREEN:
        return {"status": "SUCCESS", "tier": "GREEN", "output": executor(**tool_args)}
    elif tier == ToolPermissionTier.YELLOW:
        res = executor(**tool_args)
        self.logger.info(f"YELLOW] Tool '{tool_name}' executed. Args: {tool_args}")
        return {"status": "SUCCESS", "tier": "YELLOW", "output": res}
    elif tier == ToolPermissionTier.RED:
        # In automated mode, route to xola-guard validation logic instead of raw blocking stdin
        if self.auto_policy_allows(tool_name, tool_args):
            res = executor(**tool_args)
            self.logger.warning(f"RED] Auto-Authorized '{tool_name}'. Args: {tool_args}")
            return {"status": "SUCCESS", "tier": "RED", "output": res}
        return {"status": "DENIED", "tier": "RED", "error": "Blocked by xola-guard policy."}
```

---

### B. Telemetry & Reasoning Token Observability for `xola-memory` & Loop

Xola integrates the structured telemetry model from `eval_tracker.py` and `deepseek_client.py` into every loop iteration, logging latency, reasoning depth, and tier distribution directly into daily memory files (`D:\alox\xola\memory\YYYY-MM-DD.md`).

- **Source:** `C:\Users\user\AppData\Local\agy\bin\harness\eval_tracker.py` (L12-79) & `deepseek_client.py` (L40-62)
- **Destination:** `D:\alox\xola\loop\xola_loop.py` and `D:\alox\xola\agents\xola-memory.md`.

#### Thought Extraction & Token Estimator Pattern:
```python
@dataclass
class EvaluationMetrics:
    prompt: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    latency_seconds: float = 0.0
    reasoning_token_count: int = 0
    completion_token_count: int = 0
    total_tokens_estimated: int = 0
    tool_calls_count: int = 0
    tier_breakdown: Dict[str, int] = field(default_factory=lambda: {"GREEN": 0, "YELLOW": 0, "RED": 0})
    success: bool = True
    error_message: Optional[str] = None
    thought_summary: str = ""

    def finalize(self):
        self.end_time = time.time()
        self.latency_seconds = round(self.end_time - self.start_time, 3)
        self.total_tokens_estimated = self.reasoning_token_count + self.completion_token_count
```

#### Thought Parsing Logic:
```python
def parse_thoughts(text: str) -> Tuple[str, str, int, int]:
    think_pattern = r"<think>(.*?)</think>"
    match = re.search(think_pattern, text, re.DOTALL)
    if match:
        thoughts = match.group(1).strip()
        content = re.sub(think_pattern, "", text, flags=re.DOTALL).strip()
    else:
        thoughts = ""
        content = text.strip()
    think_tokens = int(len(thoughts.split()) * 1.3) if thoughts else 0
    content_tokens = int(len(content.split()) * 1.3) if content else 0
    return thoughts, content, think_tokens, content_tokens
```

---

### C. Dynamic Skill Decorator Registry for `xola-builder` & `tools/`

Xola borrows the decorator-based skill registry from `skills\__init__.py` to allow `xola-builder` to dynamically construct and hot-register custom Python tools into `D:\alox\xola\tools\` with automatic tier binding.

- **Source:** `C:\Users\user\AppData\Local\agy\bin\skills\__init__.py` (L13-88)
- **Destination:** `D:\alox\xola\tools\` and `xola-builder` tool generator.

#### Skill Registration Decorator:
```python
SKILL_REGISTRY: List[Skill] = []

def register_skill(
    name: str,
    tier: Tier = Tier.GREEN,
    keywords: Optional[List[str]] = None,
    description: str = "",
    category: str = "General",
    prefix_match: bool = False
):
    """Decorator to register an extensible skill in the global registry."""
    if keywords is None:
        keywords = []

    def decorator(func: Callable[[str], str]):
        skill = Skill(
            name=name,
            tier=tier,
            keywords=keywords,
            description=description,
            handler=func,
            category=category,
            prefix_match=prefix_match
        )
        SKILL_REGISTRY.append(skill)
        return func
    return decorator
```

#### Dynamic Bridge from Skill Registry to Guardrail Engine:
```python
def bind_skills_to_guardrail(guardrail: SecurityGuardrail):
    tier_mapping = {
        Tier.GREEN: ToolPermissionTier.GREEN,
        Tier.YELLOW: ToolPermissionTier.YELLOW,
        Tier.RED: ToolPermissionTier.RED,
    }
    for skill in SKILL_REGISTRY:
        tool_id = skill.name.lower().replace(" ", "_")
        guard_tier = tier_mapping.get(skill.tier, ToolPermissionTier.YELLOW)
        guardrail.register_tool_tier(tool_id, guard_tier)
```

---

### D. Native Diagnostics & Process Control Capabilities

Xola directly leverages the battle-tested Windows diagnostic and process execution routines from `system_info.py` and `system_control.py`:
- `shutil.disk_usage("C:\\")` and `shutil.disk_usage("D:\\")` for filesystem health monitoring.
- `subprocess.run(["tasklist", ...])` for background task visibility.
- `taskkill` subprocess routines for killing rogue processes.
- Safe note appending with UTC timestamps for fast local scratchpad persistence.

---

## 6. SYNTHESIS & TARGET INTEGRATION SUMMARY

With Target 4 completed, all four architectural foundations of the Xola ecosystem are thoroughly analyzed and mapped:

| Target | System Name | Core Paths | Key Technology Stolen |
| :---: | :--- | :--- | :--- |
| **01** | **Hermes** | `C:\Users\user\.hermes\` | Persona `SOUL.md` (5 facets), `§` delimited memory format, Cloudflare Workers AI provider config. |
| **02** | **Antigravity (AGY)** | `C:\Users\user\AppData\Local\agy\bin\`, `D:\alox\agy-proxy\` | Unmetered Google login lane (Gemini 3.7 Flash High / Claude Sonnet), `agy-proxy` prompt bridging, `--print` / `--output-format json` execution. |
| **03** | **OpenCode** | `C:\Users\user\.opencode\`, `lh_harness\adapters\opencode.py` | `opencode/deepseek-v4-flash-free` lane, Playwright/Firecrawl MCP servers, `opencode run --yolo` headless execution. |
| **04** | **DeepSeek Harness & Skills** | `C:\Users\user\AppData\Local\agy\bin\harness\`, `skills\` | **3-Tier Guardrail Gating (GREEN/YELLOW/RED)**, **`<think>` CoT token telemetry & JSON eval export**, **Dynamic `@register_skill` registry pattern**. |

All four target reports (`01_hermes_report.md`, `02_AGY.md`, `03_opencode.md`, `04_deepseek_harness.md`) stand complete in `D:\alox\xola\reports\`. The phase-1 analysis requirement is fulfilled, and the exact architectural components are mapped for Phase 2 agent creation (`xola-scout`, `xola-builder`, `xola-guard`, `xola-memory`). 🦋
