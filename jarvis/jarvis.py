#!/usr/bin/env python3
"""Compatibility shim — the real orchestrator now lives at the project root
as xola.py (single unified orchestration point). This module re-exports the
same names so existing imports (cli.py, server.py, jarvis/__init__.py,
tests/test_jarvis.py) keep working unchanged. 🦋

Imports are done lazily via module __getattr__ to avoid a circular import:
xola.py imports from jarvis.sentinel -> jarvis/__init__.py imports this
shim -> this shim must NOT import xola.py at module load time, since xola.py
isn't finished initializing yet at that point.
"""
import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

_EXPORTED = (
    "JarvisTask", "JarvisResponse", "JarvisHarness", "process_inbox_task",
    "run_jarvis_loop", "get_jarvis_status", "run_smoke_test",
    "render_jarvis_status", "build_parser", "main", "WATERMARK", "VERSION",
)


def __getattr__(name):
    """PEP 562 lazy module attribute access — defers the xola.py import
    until something actually asks for one of these names, by which point
    xola.py has finished initializing."""
    if name == "run_smoke":
        name = "run_smoke_test"
    if name in _EXPORTED or name == "run_smoke_test":
        import xola as _xola
        return getattr(_xola, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


if __name__ == "__main__":
    import xola as _xola
    _xola.main()
