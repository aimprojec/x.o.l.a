# Target 3 Analysis Report: OpenCode Agent Architecture 🦋

**Target Paths:**  
- OpenCode User Config & MCP: `C:\Users\user\.opencode\`  
- Standalone Binary: `C:\Users\user\.opencode\bin\opencode.exe` (v1.17.18)  
- NPM Global Binary: `C:\Users\user\AppData\Roaming\npm\opencode.CMD` (v1.18.27)  
- Desktop App State: `C:\Users\user\AppData\Roaming\ai.opencode.desktop\`  
- LongHorizon Harness Adapter: `D:\alox\LongHorizon-Harness\src\lh_harness\adapters\opencode.py`  
- Event Stream Parser: `D:\alox\LongHorizon-Harness\src\lh_harness\agent_logs.py`  
**Generated Date:** 2026-09-03  
**Auditor / Executor:** Xola Long-Horizon Loop (Executor Hands) 🦋  

---

## 1. WHAT IT IS

**OpenCode** is an open-source, extensible AI agent runtime, CLI, and multi-model development environment built specifically for terminal and autonomous software engineering. It combines an interactive terminal user interface (TUI), a headless streaming batch execution engine (`opencode run`), a rich plugin ecosystem (`@opencode-ai/plugin`), native Model Context Protocol (MCP) server orchestration, and multi-provider model routing.

In this environment, OpenCode operates across four distinct operational layers:
1. **User Configuration & MCP Hub (`C:\Users\user\.opencode\`):**  
   The primary configuration hub containing `opencode.json`, which registers local MCP tool servers (`playwright` for headless browser automation and `firecrawl` for deep web scraping) and configures custom OpenAI-compatible provider overlays (`freebuff` proxy on `http://localhost:8080/v1`).
2. **Dual-Distribution Binaries:**  
   - **NPM Global CLI:** `C:\Users\user\AppData\Roaming\npm\opencode.CMD` (v1.18.27, Node.js wrapper).
   - **Standalone Binary:** `C:\Users\user\.opencode\bin\opencode.exe` (v1.17.18, 184,048,520 bytes standalone Go/compiled binary).
3. **Desktop Session Store (`C:\Users\user\AppData\Roaming\ai.opencode.desktop\`):**  
   Contains persistent SQLite databases (`drafts.sqlite`), workspace metadata files (`opencode.workspace.*.dat`), and layout preferences.
4. **LongHorizon Harness Adapter (`lh_harness\adapters\opencode.py`):**  
   A specialized adapter that executes OpenCode in headless non-interactive mode via `opencode run --format json --yolo`, pipes prompts through stdin, injects dynamic endpoint configurations via `OPENCODE_CONFIG`, and normalizes JSON event streams into standardized benchmark trajectories.

```
+-------------------------------------------------------------------------+
|                  XOLA AUTONOMOUS MULTI-AGENT MESH                       |
|           (Manager, Scout, Builder, Auditor, Memory Distiller)           |
+-------------------------------------------------------------------------+
                                     |
                          Subprocess / Stdin Exec
                                     v
+-------------------------------------------------------------------------+
|                 OPENCODE RUNTIME (opencode run --yolo)                  |
|  - Flags: --format json --yolo --model <model> --variant <effort>       |
|  - Config Resolution: ~/.opencode/opencode.json + OPENCODE_CONFIG env  |
|  - Stdin Prompt Ingestion: < {prompt_path}                              |
+-------------------------------------------------------------------------+
                    |                                 |
         MCP Tool Dispatch (stdio)          Multi-Provider Model Routing
                    v                                 v
+---------------------------------------+ +-------------------------------+
|          ACTIVE MCP SERVERS           | |       FREE MODEL POOL         |
| 1. Playwright (@playwright/mcp@latest)| | - opencode/*-free (DeepSeek)  |
|    - Headless Chrome/Edge Automation  | | - Cloudflare Workers AI       |
|    - Screenshots, Clicks, Form Input  | | - Freebuff Proxy (Port 8080)  |
| 2. Firecrawl (firecrawl-mcp)          | | - Nvidia NIM / SiliconFlow    |
|    - Deep Web Crawl & Scraping        | | - Groq Free Tier              |
+---------------------------------------+ +-------------------------------+
```

### Core Inventory & File Paths

| Component | File Path | Size / Lines | Purpose & Description |
| :--- | :--- | :--- | :--- |
| **Global User Config** | `C:\Users\user\.opencode\opencode.json` | 1,828 bytes / 76 lines | Master configuration registering MCP servers (`playwright`, `firecrawl`) and `freebuff` custom provider proxy. |
| **Config Backup** | `C:\Users\user\.opencode\openconfig.b4freebuff.json` | 1,429 bytes / 54 lines | Base provider configuration prior to Freebuff proxy binding. |
| **Standalone Binary** | `C:\Users\user\.opencode\bin\opencode.exe` | 184,048,520 bytes | Compiled standalone binary executable (v1.17.18). |
| **NPM Global CLI** | `C:\Users\user\AppData\Roaming\npm\opencode.CMD` | CMD wrapper | Active Node.js CLI entrypoint (v1.18.27). |
| **Plugin Package** | `C:\Users\user\.opencode\package.json` | 65 bytes | Manages dependencies: `@opencode-ai/plugin` v1.18.23. |
| **Desktop App Data** | `C:\Users\user\AppData\Roaming\ai.opencode.desktop\` | ~2.5 MB (29 files) | SQLite workspace storage (`drafts.sqlite`), workspace states, and window configurations. |
| **Harness Adapter** | `D:\alox\LongHorizon-Harness\src\lh_harness\adapters\opencode.py` | 6,107 bytes / 152 lines | Command-line adapter executing OpenCode headlessly with `--format json --yolo --variant`. |
| **Event Parser** | `D:\alox\LongHorizon-Harness\src\lh_harness\agent_logs.py` | 34,902 bytes (L589-720) | Extracts `tool_use`, `text`, `step_finish`, token counts, and cost from OpenCode JSON logs. |
| **Binary Resolver** | `D:\alox\LongHorizon-Harness\src\lh_harness\utils\agent_cli.py` | 9,306 bytes (L77-80) | `resolve_opencode_binary()` with `LH_HARNESS_OPENCODE_BINARY` override support. |

---

## 2. HOW IT RUNS FREE

OpenCode achieves zero API billing overhead through a multi-tiered free routing ecosystem combining built-in free model lanes, serverless API providers, custom local OpenAI-compatible proxies, and non-interactive headless CLI execution.

### A. Free Model Catalog Breakdown

Running `opencode models` in the environment reveals a vast pool of zero-cost and free-tier models:

#### 1. Native Built-in OpenCode Free Models (`opencode/*-free`)
- `opencode/deepseek-v4-flash-free` *(Default OpenCode Model in LongHorizon Harness: `DEFAULT_OPENCODE_MODEL`)*
- `opencode/ling-3.0-flash-fin-free`
- `opencode/mimo-v2.5-free`
- `opencode/muse-spark-1.2-contributor-free`
- `opencode/muse-spark-1.3-contributor-free`
- `opencode/nemotron-3-ultra-free`
- `opencode/nemotron-3.5-lightning-free`

#### 2. Cloudflare Workers AI Free Tier (`cloudflare-workers-ai/*`)
Accessible via Cloudflare account tokens without token pricing:
- `@cf/meta/llama-4-scout-17b-16e-instruct` (High-speed triage)
- `@cf/meta/llama-3.3-70b-instruct-fp8-fast` (General coding & reasoning)
- `@cf/moonshotai/kimi-k2.7-code` & `kimi-k2.6` (Deep code reasoning)
- `@cf/deepseek-ai/deepseek-r1-distill-qwen-32b` & `deepseek-v4-flash-0731`
- `@cf/qwen/qwq-32b` & `qwen2.5-coder-32b-instruct`
- `@cf/google/gemma-4-26b-a4b-it`
- `@cf/openai/gpt-oss-120b` & `gpt-oss-20b`

#### 3. Custom Local Proxy Overlay (`freebuff` in `opencode.json`)
Configured in `C:\Users\user\.opencode\opencode.json` using `@ai-sdk/openai-compatible` with `baseURL: "http://localhost:8080/v1"`:
- `freebuff/google/gemini-3.1-pro-preview`
- `freebuff/google/gemini-3.1-flash-lite-preview`
- `freebuff/google/gemini-2.5-flash-lite`
- `freebuff/anthropic/claude-fable-5`
- `freebuff/crof/kimi-k3-eco`
- `freebuff/meta/muse-spark-1.2-contributor`
- `freebuff/mimo/mimo-v2.5`
- `freebuff/openai/gpt-5.6-luna`

#### 4. Additional Connected Hubs
- **Groq Free/Low-Tier:** `groq/llama-3.3-70b-versatile`, `groq/llama-3.1-8b-instant`, `groq/openai/gpt-oss-120b`, `groq/qwen/qwen3.8-27b`.
- **Nvidia NIM & SiliconFlow:** DeepSeek V4 Flash, Qwen 3 Coder 480B, MiniMax M2.5, GLM 5.2.

---

### B. Headless Execution Protocol & CLI Flags

To run autonomously without human intervention or terminal prompts, OpenCode is executed with a specific combination of flags mapped in `lh_harness\adapters\opencode.py`:

```bash
[OPENCODE_API_KEY="..."] [OPENCODE_CONFIG="..."] opencode.CMD run \
  --format json \
  --yolo \
  --model opencode/deepseek-v4-flash-free \
  --variant high \
  < prompt_input.txt
```

#### Detailed Flag Breakdown:
- **`run`**: Non-interactive command runner sub-command.
- **`--format json`**: Emits raw, single-line JSON events on stdout (`step_start`, `tool_use`, `text`, `step_finish`, `error`).
- **`--yolo`** (or `--auto`): Automatically approves all file operations, terminal commands, and tool executions. Critical for unattended 10-hour loops.
- **`--model <provider/model>`**: Explicitly routes the request to a specific provider and model identifier.
- **`--variant <effort>`**: Maps provider-specific reasoning effort levels (`minimal`, `low`, `medium`, `high`, `max`). In DeepSeek and Qwen models, this controls reasoning token budgets.
- **`--thinking`**: Instructs the engine to surface `<think>` blocks in event traces.
- **Stdin Ingestion (`< {prompt_path}`)**: Reads the task prompt directly from standard input, completely avoiding Windows command-line argument limits (`cmd.exe` 8,191 character cap).

---

### C. Dynamic Endpoint Configuration via `OPENCODE_CONFIG`

OpenCode uses a hierarchical configuration loading model:
1. **Global User Config:** `C:\Users\user\.opencode\opencode.json` (defines base providers and MCP servers).
2. **Environment Override:** `OPENCODE_CONFIG` environment variable.
3. **Project Config:** `.opencode/config.json` inside the working directory.

The harness leverages this design in `_write_endpoint_config()` (`opencode.py`, lines 127–152):
- Writes an ephemeral JSON file (e.g. `opencode-endpoint-<provider>.json`) containing only the endpoint URL:
  ```json
  {
    "provider": {
      "opencode": {
        "options": { "baseURL": "http://127.0.0.1:8798/v1" }
      }
    }
  }
  ```
- Sets `OPENCODE_CONFIG=<path_to_ephemeral_config>`.
- **Result:** Overrides the target provider base URL without modifying or deleting the user's global MCP tools (`playwright`, `firecrawl`) or other custom providers.

---

### D. MCP Tool Server Bindings (`opencode.json`)

The Model Context Protocol (MCP) configuration in `C:\Users\user\.opencode\opencode.json` equips OpenCode with native system and web interaction tools:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "playwright": {
      "type": "local",
      "command": [
        "npx",
        "@playwright/mcp@latest"
      ],
      "enabled": true
    },
    "firecrawl": {
      "type": "local",
      "command": [
        "npx",
        "-y",
        "firecrawl-mcp"
      ],
      "environment": {
        "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}"
      },
      "enabled": true
    }
  }
}
```

1. **Playwright MCP (`@playwright/mcp@latest`):**
   - Launched locally via `npx` over stdio.
   - Provides tools for browser navigation, clicking DOM elements, form input, page evaluation, taking screenshots, and inspecting network requests.
2. **Firecrawl MCP (`firecrawl-mcp`):**
   - Launched locally via `npx -y` over stdio.
   - Ingests `FIRECRAWL_API_KEY` from environment variables.
   - Provides deep web crawling, clean markdown extraction, sitemap traversal, and search.

---

## 3. STRENGTHS

1. **Standardized Single-Line JSON Event Stream (`--format json`):**  
   The streaming event model emits discrete, easily deserializable JSON objects per turn on stdout:
   - `step_start`: Initial session setup.
   - `tool_use`: Captures tool name, unique ID, inputs, execution status (`completed`, `failed`, `error`), and return outputs.
   - `text`: Incremental assistant responses.
   - `step_finish`: Includes detailed token metrics (`tokens.input`, `tokens.output`, `tokens.reasoning`, `tokens.cache.read`) and total cost (`part.cost`).
   - `error`: Structured failure payloads with clean error messages.
2. **Native Model Context Protocol (MCP) Orchestration:**  
   Out-of-the-box support for stdio and SSE MCP servers. The pre-configured `playwright` and `firecrawl` servers give the agent full web automation and web scraping without writing custom scraping scripts.
3. **Flexible Provider & Proxy Architecture (`@ai-sdk/openai-compatible`):**  
   Adding local proxies (like `agy-proxy` on port 8798 or `freebuff` on port 8080) is declarative and requires only a small JSON entry with standard base URLs.
4. **Clean Non-Destructive Config Overrides (`OPENCODE_CONFIG`):**  
   Allows external harnesses and multi-agent orchestrators to dynamically swap endpoints and models on a per-task basis while retaining all registered MCP servers.
5. **Universal Headless Auto-Approval (`--yolo`):**  
   Provides a clean, documented bypass for interactive prompts, preventing child processes from blocking on terminal stdin.
6. **Reasoning Effort Control (`--variant`):**  
   Exposes granular control over model reasoning intensity directly on the CLI.

---

## 4. WEAKNESSES

1. **Server-Side Free Tier Flakiness & Rate Limits:**  
   As observed in `xola_loop.py` and `loop.log`:
   `2026-09-03 13:46:02 WARN manager opencode lane failed (opencode rc!=0: ), falling back to agy-low`  
   Public free endpoints (`opencode/deepseek-v4-flash-free`) suffer from upstream community saturation, 503/429 spikes, or temporary downtime. Relying solely on `opencode/*-free` without local fallback (like AGY Google auth) leads to stalled loops.
2. **Version Divergence Between NPM CLI and Standalone Binary:**  
   - NPM wrapper (`C:\Users\user\AppData\Roaming\npm\opencode.CMD`) runs **v1.18.27**.
   - Standalone binary (`C:\Users\user\.opencode\bin\opencode.exe`) is **v1.17.18**.  
   Calling the standalone binary directly can miss newer flag features or bug fixes present in v1.18+.
3. **Node.js Subprocess Startup Overhead:**  
   Because `opencode.CMD` invokes Node.js, loads NPM plugins, and initializes MCP child processes over stdio, each one-shot execution incurs a 1.2 to 2.8 second cold-start penalty.
4. **Orphaned MCP Stdio Process Risk:**  
   Local MCP servers spawned via `npx` (`@playwright/mcp`, `firecrawl-mcp`) spawn background Node.js and Chromium child processes. If OpenCode is terminated via timeout or SIGKILL, these child processes can remain running in the background as orphans.
5. **Lack of Internal Prompt Sliding Window:**  
   Unlike `agy-proxy` which actively prunes turns to an 8-message window and middle-truncates tool outputs at 2,500 chars, OpenCode does not truncate input history when fed raw stdin, requiring the external orchestrator to manage context length.

---

## 5. WHAT XOLA STEALS FROM IT

Xola extracts the following key architectural capabilities, patterns, and tool bindings from OpenCode:

### A. Headless JSON Event Stream Parsing & Telemetry
- **Source Code:** `D:\alox\LongHorizon-Harness\src\lh_harness\agent_logs.py` (lines 589–720)
- **Target Integration:** `D:\alox\xola\loop\telemetry.py` & `D:\alox\xola\xola_lh_bridge.py`
- **Pattern Stolen:**
  - Consume single-line JSON events (`step_start`, `tool_use`, `text`, `step_finish`).
  - Extract `tokens.reasoning` and `tokens.cache.read` for observability.
  - Intercept `tool_use` state outputs for instant crash/error detection.

### B. Playwright & Firecrawl MCP Tool Definitions
- **Source Config:** `C:\Users\user\.opencode\opencode.json` (lines 3–24)
- **Target Integration:** `D:\alox\xola\tools\` & `D:\alox\xola\agents\xola-scout.md`
- **Bindings Stolen:**
  - **Playwright MCP:** `npx @playwright/mcp@latest` for headless browser inspection and UI testing.
  - **Firecrawl MCP:** `npx -y firecrawl-mcp` with `FIRECRAWL_API_KEY` for structured web research and markdown conversion.

### C. Dynamic Configuration Ingestion Pattern (`OPENCODE_CONFIG`)
- **Source Code:** `D:\alox\LongHorizon-Harness\src\lh_harness\adapters\opencode.py` (lines 127–152)
- **Target Integration:** `D:\alox\xola\tools\opencode_bridge.py`
- **Pattern Stolen:**
  - Generate ephemeral JSON override files per episode in `prompt_dir`.
  - Point OpenCode to local proxies (e.g. `agy-proxy` on port 8798 or `freebuff` on port 8080) via `OPENCODE_CONFIG` without modifying the global `~/.opencode/opencode.json`.

### D. Multi-Tier Reasoning Effort Mapping (`--variant`)
- **Source Code:** `lh_harness\adapters\opencode.py` (lines 57–60, 85–86) & `test_reasoning_effort_chain.py`
- **Target Integration:** `D:\alox\xola\agents\*.md` (Scout, Builder, Guard)
- **Pattern Stolen:**
  - Map task criticality to `--variant`:
    - `xola-scout` -> `--variant minimal` (fast, low-latency search).
    - `xola-builder` -> `--variant medium` (balanced coding & tool execution).
    - `xola-guard` -> `--variant high` or `--variant max` (deep red-team verification).

### E. Robust Headless Subprocess Template
- **Source Code:** `lh_harness\adapters\opencode.py` (lines 76–90)
- **Target Integration:** `D:\alox\xola\loop\runners.py`
- **Recipe Stolen:**
  ```bash
  opencode.CMD run --format json --yolo --model <model> [--variant <effort>] < {prompt_file}
  ```
  - Standardized stdin pipe `< {prompt_file}` to handle unbounded prompt lengths without Windows command-line truncation.

---

## 6. Concrete Path & Component Mapping Table

| OpenCode Component | Source Path / Artifact | Xola Target Usage | Stolen Value / Mechanism |
| :--- | :--- | :--- | :--- |
| **Playwright MCP** | `C:\Users\user\.opencode\opencode.json` (L4-11) | `D:\alox\xola\tools\browser.py` | Browser automation & UI screenshots (`@playwright/mcp@latest`) 🦋 |
| **Firecrawl MCP** | `C:\Users\user\.opencode\opencode.json` (L12-23) | `D:\alox\xola\tools\scraper.py` | Web research & markdown extraction (`firecrawl-mcp`) |
| **Freebuff Proxy Config** | `C:\Users\user\.opencode\opencode.json` (L25-75) | `D:\alox\xola\server.py` | `@ai-sdk/openai-compatible` local port 8080 routing schema |
| **Harness CLI Adapter** | `lh_harness\adapters\opencode.py` (L25-125) | `D:\alox\xola\xola_lh_bridge.py` | Headless execution runner (`--format json --yolo < prompt`) |
| **Dynamic Config Pattern** | `lh_harness\adapters\opencode.py` (L127-152) | `D:\alox\xola\loop\runners.py` | `OPENCODE_CONFIG` ephemeral provider `baseURL` overriding |
| **JSON Event Parser** | `lh_harness\agent_logs.py` (L589-720) | `D:\alox\xola\loop\telemetry.py` | Real-time extraction of `tool_use`, reasoning tokens & costs |
| **Effort Variant Chain** | `lh_harness\agent_registry.py` & adapter | `D:\alox\xola\agents\*.md` | `--variant` effort mapping (`minimal`, `medium`, `high`, `max`) |
| **Binary Resolution** | `lh_harness\utils\agent_cli.py` (L77-80) | `D:\alox\xola\loop\xola_loop.py` | Authoritative CLI resolution favoring `opencode.CMD` v1.18.27 |

---
*Report generated and validated with real tool evidence for Xola Long-Horizon Loop.* 🦋
