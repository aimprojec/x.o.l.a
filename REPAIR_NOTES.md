# Repair notes — 2026-09-05

## Implemented changes

- Shared persistent approval store: stable request identity, exact action/argument
  matching, explicit denial, one-use consumption, expiry, atomic saves and
  serialization across threads and cooperating processes.
- Agent routes no longer silently auto-approve RED skills. A blocked registered
  skill does not fall through to another execution route.
- OS dispatcher gates mutations and fixes `kill`, `spawn`, `focus` and `write`
  aliases. Overwrites remain gated even when routine auto-allow is enabled.
- Pending queued tasks remain queued. Duplicate queue consumers use a per-task
  lock. Responses are written atomically and task IDs cannot escape output paths.
- Chains validate their length, bound nesting, persist completed steps, and
  pass prior results to later operations. Pending model plans are cached so
  approval resumes the same planned operation.
- DAG execution now invokes actual tools in isolated workers. Removed synthetic
  `executed_<action>` results. Added dependency validation, duplicate-ID rejection,
  blocked-child behavior, timeout handling and independent per-run state.
- File writes use temporary files and atomic replacement, then verify saved text
  and return a SHA-256 digest. Appends serialize concurrent cooperating writers.
- Windows speech listener captures a complete request after the wake phrase, or
  a combined wake-and-command phrase. Uses bounded dictation waiting and disposes
  the recognition engine. No microphone input is simulated as successful capture.
- Ears queue hands commands into durable executable inbox tasks before archiving.
  Handler failures retain requests. Voice-origin tasks request spoken responses.
- Non-Windows speech returns UNSUPPORTED rather than fake playback success.
- Memory recall returns actual fact values, supports Unicode tokens, filters
  common stopwords and sealed secrets, and feeds relevant facts into planning.
- On-demand screenshot/Tesseract OCR context is connected to the brain. Missing
  dependencies and OCR failures are explicit. Context is bounded and marked as
  untrusted data.
- Unknown requests return UNSUPPORTED. Nested tool failure results propagate
  through the brain instead of being wrapped as successful work.
- Core tool paths follow the installation directory. AGY binary/model, optional
  long-horizon source and OCR binary can be configured through environment variables.
- MEA pending steps are retained across approval cycles. Legacy external execution
  modes no longer pass permission-bypass flags to AGY.
- Evolution checks project boundaries, guards content again immediately before
  apply, preserves old code as well as a vault snapshot, and writes atomically.
- Local dashboard restricts Host/Origin, bounds JSON requests, rejects invalid
  body shapes and no longer serves arbitrary source files or databases.
- Added installation diagnostics, memory CLI commands and a Windows launcher.
- Added 35 behavioral regression tests. Updated existing expectations for explicit
  pending approvals, unsupported playback, output metadata and restricted CORS.

## Validation evidence

- `python -m unittest discover -s tests -q`: 546 test runs passed on Linux,
  Python 3.12.13. The legacy suite duplicates some test classes through imports.
- 35 dedicated repair regression tests cover approvals/concurrency, actual file
  operations, resumable chains, stable plans, real DAG workers, dependency failure,
  voice delivery, memory context, OCR boundary behavior and local HTTP access.
- Read → summarize → save test used real files and a deterministic planner fixture.
  The fixture replaces only model generation; actual routing, approval, persistence,
  writing and result verification run normally.
- A real local Tesseract invocation read the synthetic image text
  `XOLA runtime verification 12345` correctly. This checks OCR, not Windows capture.
- `python xola.py --doctor` completed. AGY and Windows PowerShell were unavailable
  in the validation environment. No paid model request was made for validation.

## Remaining limits

This is a repaired prototype, not a claim that every possible bug is eliminated.
Windows microphone/grammar behavior, TTS, screenshots and window actions still
need local testing. The listener is turn-based; full-duplex interruption is not
implemented. Model planning depends on your configured provider, account and model.
The default model identifier comes from the original upload and was not live-verified.

Memory remains lexical retrieval. OCR is text extraction, not comprehensive
scene understanding or reliable arbitrary GUI navigation. Legacy exploratory
modules still contain demonstrations and simplified helpers; numbered feature
comments in those modules are not proof of implemented capabilities.

Postcondition checks are strongest for file writes. General error diagnosis,
semantic task verification, autonomous repair, and transaction-wide rollback are
not universally implemented. A crash between an external side effect and recording
its result can still require manual inspection; no exactly-once guarantee is made
for arbitrary outside systems. A worker timeout cannot undo an external side effect.

The local tool library and external CLIs are trusted code, not an OS sandbox.
The permission gates cover the repaired agent-dispatch paths. A Python caller
invoking low-level helpers directly controls its own permissions. Existing vault
secret encryption remains inherited custom cryptography and is not certified.

## Speech API references

Implementation follows Microsoft's documented local speech grammar APIs:

- [GrammarBuilder.AppendDictation](https://learn.microsoft.com/en-us/dotnet/api/system.speech.recognition.grammarbuilder.appenddictation)
- [SpeechRecognitionEngine](https://learn.microsoft.com/en-us/dotnet/api/system.speech.recognition.speechrecognitionengine)

`Recognize(TimeSpan)` controls the initial-silence wait; it is not a hard wall-clock
limit on the full spoken utterance. Overall listener timeout is checked between
recognition calls.
