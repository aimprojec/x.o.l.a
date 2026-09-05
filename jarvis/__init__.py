#!/usr/bin/env python3
"""Usage: from jarvis import JarvisHarness, Sentinel, OSHands, AutonomousBrain, VoiceEngine # Jarvis Autonomous OS Harness & Cognitive Service Loop 🦋"""

# =====================================================================
# X.O.L.A. Phase 4 — Jarvis Autonomous Harness & Cognitive Subsystems
# ---------------------------------------------------------------------
# Zero-dependency, pure Python standard library harness powering
# persistent service loop, OS hands, background sentinel, AGY reasoning
# bridge, voice synthesis TTS, ears queue, and inbox/outbox.
# =====================================================================

import sys

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
VERSION = "1.0.0"

from jarvis.sentinel import (
    Sentinel,
    SentinelCheck,
    NudgeSchedule,
    get_system_health,
    run_sentinel_once,
    execute_scheduled_nudges,
    nudge_health_monitor,
    nudge_guard_audit,
    nudge_scout_probe,
    run_nudge_by_name,
    read_sentinel_log,
    SENTINEL_LOG_FILE,
)

from jarvis.hands import (
    OSHands,
    ProcessInfo,
    WindowInfo,
    list_processes,
    find_process,
    get_process_info,
    kill_process,
    spawn_process,
    list_windows,
    focus_window,
    capture_screenshot,
    file_tree,
    list_directory_tree,
    read_file_safe,
    write_file_safe,
    tail_log_safe,
    find_files,
    disk_space,
    get_sysinfo,
)

from jarvis.brain import (
    AutonomousBrain,
    AGYReasoningBridge,
    HeuristicPlanner,
    BrainPlan,
    BrainExecutionResult,
    think,
    think_and_execute,
    get_brain_engine,
)

from jarvis.voice import (
    VoiceEngine,
    EarsQueue,
    Utterance,
    VoiceLogEntry,
    speak,
    enqueue_utterance,
    read_voice_log,
    process_ears_queue,
    EARS_DIR,
    VOICE_LOG_FILE,
)

try:
    from jarvis.jarvis import (
        JarvisHarness,
        JarvisTask,
        JarvisResponse,
        process_inbox_task,
        run_jarvis_loop,
        get_jarvis_status,
        run_smoke_test,
        run_smoke,
    )
except ImportError:
    # jarvis.jarvis is a compatibility shim pointing at xola.py at the
    # project root. If xola.py is still mid-initialization (it imports
    # jarvis.sentinel above, which triggers this __init__.py, before
    # xola.py itself has defined JarvisHarness etc.), that circular import
    # resolves once xola.py finishes loading. Defer these names via
    # __getattr__ instead of failing the whole package import.
    def __getattr__(name):
        import jarvis.jarvis as _shim
        return getattr(_shim, name)

__all__ = [
    "WATERMARK",
    "VERSION",
    # Sentinel exports
    "Sentinel",
    "SentinelCheck",
    "NudgeSchedule",
    "get_system_health",
    "run_sentinel_once",
    "execute_scheduled_nudges",
    "nudge_health_monitor",
    "nudge_guard_audit",
    "nudge_scout_probe",
    "run_nudge_by_name",
    "read_sentinel_log",
    "SENTINEL_LOG_FILE",
    # Hands exports
    "OSHands",
    "ProcessInfo",
    "WindowInfo",
    "list_processes",
    "find_process",
    "get_process_info",
    "kill_process",
    "spawn_process",
    "list_windows",
    "focus_window",
    "capture_screenshot",
    "file_tree",
    "list_directory_tree",
    "read_file_safe",
    "write_file_safe",
    "tail_log_safe",
    "find_files",
    "disk_space",
    "get_sysinfo",
    # Brain exports
    "AutonomousBrain",
    "AGYReasoningBridge",
    "HeuristicPlanner",
    "BrainPlan",
    "BrainExecutionResult",
    "think",
    "think_and_execute",
    "get_brain_engine",
    # Voice & Ears exports
    "VoiceEngine",
    "EarsQueue",
    "Utterance",
    "VoiceLogEntry",
    "speak",
    "enqueue_utterance",
    "read_voice_log",
    "process_ears_queue",
    "EARS_DIR",
    "VOICE_LOG_FILE",
    # Jarvis Core exports
    "JarvisHarness",
    "JarvisTask",
    "JarvisResponse",
    "process_inbox_task",
    "run_jarvis_loop",
    "get_jarvis_status",
    "run_smoke_test",
    "run_smoke",
]
