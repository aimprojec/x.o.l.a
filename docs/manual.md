# Xola — repaired desktop-assistant prototype

Xola combines a local task queue, model-assisted planning, Windows speech,
OS tools, persistent memory, and a local dashboard. This build repairs the
execution and approval gaps found in the uploaded prototype. It is still a
prototype; live Windows integrations and the configured model need local testing.
See `REPAIR_NOTES.md` for the exact changes and validation limits.

## Start on Windows

1. Extract the entire archive to a writable folder. Open a terminal in `xola_bundle`.
2. Use Python 3.10 or newer. Core Python execution and the test suite use the standard library.
3. Run diagnostics:

   ```powershell
   python xola.py --doctor
   ```

4. Configure your existing AGY CLI if it is not on PATH. Set a model identifier
   that the CLI actually supports. The inherited default model string is not
   a claim that the model is currently available.

   ```powershell
   $env:XOLA_AGY_BIN = 'C:\path\to\agy_real.exe'
   $env:XOLA_MODEL = 'your-supported-model-id'
   python xola.py --think "check disk space" --json
   ```

   Authenticate using the CLI's own normal login flow. No credentials are bundled.
   Provider availability, quotas and charges depend on your account. The legacy
   reports/dashboard labels mentioning free models do not establish current pricing.

5. Start the service and dashboard with `launch_windows.cmd`. To include the
   microphone listener, run `launch_windows.cmd voice` from a terminal. It uses
   Windows PowerShell and the installed System.Speech recognition language.
   Alternatively start components in separate terminals:

   ```powershell
   python xola.py --daemon
   python server.py
   python xola.py --listen
   ```

6. Open http://127.0.0.1:8101/. Submit execution requests using the Jarvis send
   control or the CLI. The older dashboard task list is a planning list, distinct
   from the execution inbox. Say “hey xola”, then a complete request; a request
   immediately following the wake phrase is also supported. Queued speech is
   processed on the following daemon cycles. Close the component windows or
   press Ctrl+C to stop them.

## Review and answer approvals

Agent-dispatched writes and window changes request approval by default. Existing
file overwrites, process control and RED skills always request approval. A
persisted approval authorizes one matching action with matching arguments and
scope; it expires after 24 hours. It does not authorize later changed arguments.

```powershell
python xola.py --pending
python xola.py --answer QUESTION_ID yes
python xola.py --answer QUESTION_ID no
```

Queued tasks stay in the inbox while waiting; the daemon resumes them after an
answer. Retry an identical one-off `--think` command explicitly after answering.
A chain retains its successful steps while waiting so earlier writes are not
repeated. A denied operation terminates the queued task.

```powershell
python xola.py --set-auto-allow on
python xola.py --set-auto-allow off
```

Auto-allow permits routine dispatched operations; it does not override high-stakes
tool gates. Direct Python helper functions and explicitly approved registry calls
are trusted programming APIs, not a security sandbox. The legacy external CLI
manager modes retain the external CLI's own permissions; bypass flags were removed.

## Memory

```powershell
python xola.py --remember "project milestone" "Finish voice command testing"
python xola.py --recall "project milestone"
```

Recall returns the stored values and supplies relevant facts to the planner.
Retrieval uses Unicode lexical matching, not an embedding model. Encrypted facts
are excluded from automatic recall. Use these commands for ordinary project facts,
not passwords; the inherited custom encryption scheme has not been redesigned or
certified. Existing vault data remains at `loop/lh10/vault/` inside this installation.

## Screen context

```powershell
python xola.py --think "Explain the visible error" --screen --json
```

Screen capture is requested only with `--screen`. OCR uses a local Tesseract
installation on PATH, or `XOLA_TESSERACT_BIN`. Missing capture/OCR support is
reported explicitly. OCR text is marked as untrusted input to the planner; this
is not a complete visual desktop-navigation agent. Image and desktop contents
included in a model request are sent through your configured model CLI.

## Multi-step work

The planner can return a bounded chain of actions. Chain steps can consume
`previous_result` by including `_pipe_prev: true`. A practical pattern is:
`hands.read` → `auto` with a summarization request → `hands.write` using the
previous text. File writes are atomic and the resulting content is read back and
hashed. The regression suite exercises this complete path with a deterministic
model fixture; live model quality is not implied by that test.

`CoreOrchestrator.dispatch_dag()` additionally runs real tools in isolated Python
workers. It rejects missing dependencies and cycles, blocks dependent actions
on failure, and enforces a worker timeout. It does not automatically retry
mutations. External programs intentionally launched by a tool can outlive a
worker; process control remains approval-gated.

## Self-proposed changes

```powershell
python xola.py --list-proposals
python xola.py --show-proposal PROPOSAL_ID
python xola.py --approve-evolution PROPOSAL_ID
python xola.py --reject-evolution PROPOSAL_ID
```

Evolution is explicit-review-only. Applying a proposal checks its target and
current contents, re-runs the guard, creates a vault snapshot and an original-code
backup, then writes atomically. The proposal records `code_backup` for manual
restoration. Guards are diagnostics, not proof of code correctness.

## Tests

```powershell
python -m unittest discover -s tests -q
python -m unittest tests.test_runtime_repairs -v
```

The Linux validation run passed 546 test executions, including 35 new regression
tests. The legacy suite imports some test classes twice, so that total is not a
count of distinct scenarios. Windows microphone, recognition accuracy, actual
speaker playback, desktop permissions and live AGY calls were unavailable here.

Historical `reports/`, `memory/`, and existing Git metadata are retained from the
upload. Their completion claims describe earlier work and are not new validation.
