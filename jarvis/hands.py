#!/usr/bin/env python3
"""Usage: python hands.py [ps|kill|windows|focus|screenshot|tree|disk] ... # Jarvis Zero-Dep OS Hands & Eyes Module 🦋"""

import argparse
from pathlib import Path
import csv
import ctypes
import datetime
import fnmatch
import io
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Ensure UTF-8 output on Windows consoles
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
VERSION = "1.0.0"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

JARVIS_DIR = os.path.dirname(os.path.abspath(__file__))
EYES_DIR = os.path.join(JARVIS_DIR, "eyes")


# =====================================================================
# 1) Process Management Hands
# =====================================================================

@dataclass
class ProcessInfo:
    """Structured process metadata."""
    pid: int
    name: str
    memory_mb: float = 0.0
    session_name: str = ""
    session_num: int = 0
    mark: str = WATERMARK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def list_processes(filter_name: Optional[str] = None, limit: int = 200) -> List[ProcessInfo]:
    """List running OS processes with zero third-party dependencies. 🦋"""
    # Harden: clamp limit stdlib-only, sanitize filter
    try:
        limit = int(limit)
    except Exception:
        limit = 200
    limit = max(1, min(200, limit))
    procs: List[ProcessInfo] = []
    clean_filter = filter_name.lower().strip() if filter_name else None
    if clean_filter == "":
        clean_filter = None

    if sys.platform == "win32":
        try:
            # tasklist /FO CSV /NH provides fast, structured process listing
            cmd = ["tasklist", "/FO", "CSV", "/NH"]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=NO_WINDOW,
            )
            if res.returncode == 0:
                reader = csv.reader(io.StringIO(res.stdout))
                for row in reader:
                    if not row or len(row) < 5:
                        continue
                    p_name = row[0].strip()
                    try:
                        p_pid = int(row[1].strip())
                    except ValueError:
                        continue
                    p_sess_name = row[2].strip()
                    try:
                        p_sess_num = int(row[3].strip())
                    except ValueError:
                        p_sess_num = 0
                    mem_str = re.sub(r"[^\d]", "", row[4] or "")
                    try:
                        mem_kb = float(mem_str) if mem_str else 0.0
                        mem_mb = round(mem_kb / 1024.0, 2)
                    except ValueError:
                        mem_mb = 0.0

                    if clean_filter and clean_filter not in p_name.lower() and clean_filter != str(p_pid):
                        continue

                    procs.append(
                        ProcessInfo(
                            pid=p_pid,
                            name=p_name,
                            memory_mb=mem_mb,
                            session_name=p_sess_name,
                            session_num=p_sess_num,
                            mark=WATERMARK,
                        )
                    )
                    # NOTE: no early break here — collect all, sort by memory, slice at return 🦋
        except Exception:
            pass
    else:
        # Unix ps -eo pid,rss,comm
        try:
            res = subprocess.run(
                ["ps", "-eo", "pid,rss,comm"],
                capture_output=True,
                text=True,
                timeout=4,
            )
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()[1:]
                for line in lines:
                    parts = line.split(None, 2)
                    if len(parts) == 3:
                        pid = int(parts[0])
                        rss_kb = float(parts[1])
                        comm = parts[2].strip()
                        if clean_filter and clean_filter not in comm.lower() and clean_filter != str(pid):
                            continue
                        procs.append(
                            ProcessInfo(
                                pid=pid,
                                name=comm,
                                memory_mb=round(rss_kb / 1024.0, 2),
                                mark=WATERMARK,
                            )
                        )
                        # NOTE: no early break — sort then slice 🦋
        except Exception:
            pass

    if not procs and sys.platform.startswith("linux") and os.path.isdir("/proc"):
        for proc_dir in Path("/proc").iterdir():
            if not proc_dir.name.isdigit():
                continue
            try:
                name = (proc_dir / "comm").read_text().strip()
                if clean_filter and clean_filter not in name.lower() and clean_filter != proc_dir.name:
                    continue
                pages = int((proc_dir / "statm").read_text().split()[1])
                procs.append(ProcessInfo(pid=int(proc_dir.name), name=name,
                    memory_mb=round(pages * os.sysconf("SC_PAGE_SIZE") / 1048576, 2), mark=WATERMARK))
            except (OSError, ValueError, IndexError):
                continue
    return sorted(procs, key=lambda p: p.memory_mb, reverse=True)[:limit]


def find_process(query: Union[str, int]) -> List[ProcessInfo]:
    """Find processes matching PID or name substring 🦋."""
    return list_processes(filter_name=str(query))


def get_process_info(pid_or_name: Optional[Union[int, str]] = None) -> Dict[str, Any]:
    """Retrieve detailed process metadata by PID, image name, or current process 🦋."""
    t0 = time.perf_counter()
    try:
        target = os.getpid() if (pid_or_name is None or str(pid_or_name).strip() in ("", "0", "current", "self")) else pid_or_name
        target_str = str(target).strip()

        all_procs = list_processes(filter_name=target_str, limit=50)
        exact_match = None

        if target_str.isdigit():
            target_pid = int(target_str)
            for p in all_procs:
                if p.pid == target_pid:
                    exact_match = p
                    break
        else:
            clean_target = target_str.lower()
            for p in all_procs:
                p_name_lower = p.name.lower()
                if p_name_lower == clean_target or p_name_lower == f"{clean_target}.exe":
                    exact_match = p
                    break
            if not exact_match and all_procs:
                exact_match = all_procs[0]

        if exact_match:
            return {
                "status": "SUCCESS",
                "found": True,
                "target": target,
                "pid": exact_match.pid,
                "name": exact_match.name,
                "memory_mb": exact_match.memory_mb,
                "session_name": exact_match.session_name,
                "session_num": exact_match.session_num,
                "process": exact_match.to_dict(),
                "total_matches": len(all_procs),
                "latency_s": round(time.perf_counter() - t0, 4),
                "mark": WATERMARK,
            }
        else:
            return {
                "status": "NOT_FOUND",
                "found": False,
                "target": target,
                "error": f"No process matching '{target}' was found",
                "matches": [],
                "latency_s": round(time.perf_counter() - t0, 4),
                "mark": WATERMARK,
            }
    except Exception as exc:
        return {
            "status": "ERROR",
            "found": False,
            "target": pid_or_name,
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }


def kill_process(pid_or_name: Union[int, str], force: bool = False) -> Dict[str, Any]:
    """Terminate process by PID or image name."""
    t0 = time.perf_counter()
    target_str = str(pid_or_name).strip()

    if sys.platform == "win32":
        cmd = ["taskkill"]
        if force:
            cmd.append("/F")
        if target_str.isdigit():
            cmd.extend(["/PID", target_str])
        else:
            if not target_str.lower().endswith(".exe"):
                target_str = f"{target_str}.exe"
            cmd.extend(["/IM", target_str])

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=NO_WINDOW,
            )
            success = res.returncode == 0
            return {
                "target": pid_or_name,
                "action": "kill",
                "success": success,
                "output": (res.stdout or res.stderr).strip(),
                "returncode": res.returncode,
                "latency_s": round(time.perf_counter() - t0, 4),
                "mark": WATERMARK,
            }
        except Exception as e:
            return {
                "target": pid_or_name,
                "action": "kill",
                "success": False,
                "error": str(e),
                "latency_s": round(time.perf_counter() - t0, 4),
                "mark": WATERMARK,
            }
    else:
        try:
            if target_str.isdigit():
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(int(target_str), sig)
                return {
                    "target": pid_or_name,
                    "action": "kill",
                    "success": True,
                    "latency_s": round(time.perf_counter() - t0, 4),
                    "mark": WATERMARK,
                }
            else:
                cmd = ["pkill", "-9" if force else "-15", target_str]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=4)
                return {
                    "target": pid_or_name,
                    "action": "kill",
                    "success": res.returncode == 0,
                    "output": res.stdout.strip(),
                    "latency_s": round(time.perf_counter() - t0, 4),
                    "mark": WATERMARK,
                }
        except Exception as e:
            return {
                "target": pid_or_name,
                "action": "kill",
                "success": False,
                "error": str(e),
                "latency_s": round(time.perf_counter() - t0, 4),
                "mark": WATERMARK,
            }


def spawn_process(command: Union[str, List[str]], cwd: Optional[str] = None, background: bool = True) -> Dict[str, Any]:
    """Spawn an application or shell process."""
    t0 = time.perf_counter()
    try:
        flags = NO_WINDOW if (sys.platform == "win32" and background) else 0
        if isinstance(command, str):
            cmd_args = command if sys.platform == "win32" else command.split()
            shell_mode = isinstance(command, str)
        else:
            cmd_args = command
            shell_mode = False

        proc = subprocess.Popen(
            cmd_args,
            cwd=cwd,
            shell=shell_mode,
            creationflags=flags,
            stdout=subprocess.PIPE if not background else subprocess.DEVNULL,
            stderr=subprocess.PIPE if not background else subprocess.DEVNULL,
        )

        return {
            "action": "spawn",
            "command": str(command),
            "pid": proc.pid,
            "background": background,
            "status": "STARTED",
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
    except Exception as e:
        return {
            "action": "spawn",
            "command": str(command),
            "status": "ERROR",
            "error": str(e),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }


# =====================================================================
# 2) Window & Application Control Hands (Pure CTypes on Win32)
# =====================================================================

@dataclass
class WindowInfo:
    """Structured desktop window metadata."""
    hwnd: int
    title: str
    pid: int = 0
    is_visible: bool = True
    mark: str = WATERMARK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def list_windows(visible_only: bool = True) -> List[WindowInfo]:
    """List open desktop windows with pure ctypes (zero external dependencies)."""
    windows: List[WindowInfo] = []

    if sys.platform != "win32":
        return windows

    try:
        user32 = ctypes.windll.user32
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def enum_windows_callback(hwnd, lParam):
            if visible_only and not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                title = buff.value.strip()
                if title:
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    windows.append(
                        WindowInfo(
                            hwnd=hwnd,
                            title=title,
                            pid=pid.value,
                            is_visible=bool(user32.IsWindowVisible(hwnd)),
                            mark=WATERMARK,
                        )
                    )
            return True

        cb = WNDENUMPROC(enum_windows_callback)
        user32.EnumWindows(cb, 0)
    except Exception:
        pass

    return windows


def find_windows(title_query: str) -> List[WindowInfo]:
    """Find windows whose title matches the query substring."""
    clean_q = title_query.lower().strip()
    all_wins = list_windows(visible_only=True)
    return [w for w in all_wins if clean_q in w.title.lower()]


def focus_window(hwnd_or_title: Union[int, str]) -> Dict[str, Any]:
    """Bring target window to foreground."""
    t0 = time.perf_counter()
    if sys.platform != "win32":
        return {
            "action": "focus_window",
            "target": hwnd_or_title,
            "success": False,
            "error": "Window focus only supported on Windows platform",
            "mark": WATERMARK,
        }

    try:
        target_hwnd = None
        target_title = ""

        if isinstance(hwnd_or_title, int) or (isinstance(hwnd_or_title, str) and hwnd_or_title.isdigit()):
            target_hwnd = int(hwnd_or_title)
        else:
            matches = find_windows(str(hwnd_or_title))
            if matches:
                target_hwnd = matches[0].hwnd
                target_title = matches[0].title
            else:
                return {
                    "action": "focus_window",
                    "target": hwnd_or_title,
                    "success": False,
                    "error": f"No window found matching title '{hwnd_or_title}'",
                    "latency_s": round(time.perf_counter() - t0, 4),
                    "mark": WATERMARK,
                }

        user32 = ctypes.windll.user32
        # SW_RESTORE = 9
        user32.ShowWindow(target_hwnd, 9)
        ok = bool(user32.SetForegroundWindow(target_hwnd))

        return {
            "action": "focus_window",
            "hwnd": target_hwnd,
            "title": target_title,
            "success": ok,
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
    except Exception as e:
        return {
            "action": "focus_window",
            "target": hwnd_or_title,
            "success": False,
            "error": str(e),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }


def minimize_window(hwnd_or_title: Union[int, str]) -> Dict[str, Any]:
    """Minimize target window."""
    t0 = time.perf_counter()
    if sys.platform != "win32":
        return {"action": "minimize_window", "success": False, "error": "Windows only", "mark": WATERMARK}

    try:
        target_hwnd = None
        if isinstance(hwnd_or_title, int) or (isinstance(hwnd_or_title, str) and hwnd_or_title.isdigit()):
            target_hwnd = int(hwnd_or_title)
        else:
            matches = find_windows(str(hwnd_or_title))
            if matches:
                target_hwnd = matches[0].hwnd

        if not target_hwnd:
            return {"action": "minimize_window", "success": False, "error": "Window not found", "mark": WATERMARK}

        # SW_MINIMIZE = 6
        ok = bool(ctypes.windll.user32.ShowWindow(target_hwnd, 6))
        return {
            "action": "minimize_window",
            "hwnd": target_hwnd,
            "success": ok,
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
    except Exception as e:
        return {"action": "minimize_window", "success": False, "error": str(e), "mark": WATERMARK}


# =====================================================================
# 3) Eyes: Zero-Dep PowerShell Screenshot Capture
# =====================================================================

def capture_screenshot(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Capture full desktop screenshot using zero-dep PowerShell and .NET Drawing."""
    t0 = time.perf_counter()
    os.makedirs(EYES_DIR, exist_ok=True)

    if not output_path:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = os.path.join(EYES_DIR, f"screenshot_{ts}.png")

    target_abs = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(target_abs), exist_ok=True)

    if sys.platform == "win32":
        # Pure PowerShell screen grab via System.Windows.Forms & System.Drawing
        ps_script = (
            "Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            "$bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            "$bmp = New-Object System.Drawing.Bitmap $bounds.Width, $bounds.Height; "
            "$g = [System.Drawing.Graphics]::FromImage($bmp); "
            "$g.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size); "
            f"$bmp.Save('{target_abs.replace(chr(39), chr(39)*2)}', [System.Drawing.Imaging.ImageFormat]::Png); "
            "$g.Dispose(); $bmp.Dispose(); "
            "Write-Output \"$($bounds.Width)x$($bounds.Height)\""
        )
        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=NO_WINDOW,
            )
            dim_str = res.stdout.strip()
            if os.path.exists(target_abs) and os.path.getsize(target_abs) > 0:
                size_bytes = os.path.getsize(target_abs)
                return {
                    "action": "screenshot",
                    "status": "SUCCESS",
                    "path": target_abs,
                    "resolution": dim_str or "unknown",
                    "size_bytes": size_bytes,
                    "size_kb": round(size_bytes / 1024.0, 1),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "latency_s": round(time.perf_counter() - t0, 4),
                    "mark": WATERMARK,
                }
            else:
                return {
                    "action": "screenshot",
                    "status": "ERROR",
                    "error": res.stderr.strip() or "Screenshot file was not created",
                    "latency_s": round(time.perf_counter() - t0, 4),
                    "mark": WATERMARK,
                }
        except Exception as e:
            return {
                "action": "screenshot",
                "status": "ERROR",
                "error": str(e),
                "latency_s": round(time.perf_counter() - t0, 4),
                "mark": WATERMARK,
            }
    else:
        # Fallback for Linux / macOS via scrot or screencapture if available
        try:
            res = subprocess.run(["screencapture", target_abs], capture_output=True, timeout=5)
            if res.returncode == 0 and os.path.exists(target_abs):
                return {
                    "action": "screenshot",
                    "status": "SUCCESS",
                    "path": target_abs,
                    "size_bytes": os.path.getsize(target_abs),
                    "timestamp": datetime.datetime.now().isoformat(),
                    "latency_s": round(time.perf_counter() - t0, 4),
                    "mark": WATERMARK,
                }
        except Exception:
            pass
        return {
            "action": "screenshot",
            "status": "ERROR",
            "error": "Screenshot capture only supported on Windows in stdlib mode",
            "mark": WATERMARK,
        }


# =====================================================================
# 4) Filesystem Hands Helpers
# =====================================================================

def list_directory_tree(
    root_dir: str = ".",
    max_depth: int = 2,
    max_entries: int = 100,
    include_files: bool = True,
) -> Dict[str, Any]:
    """Generate structured hierarchy tree of a directory with depth and entry bounds 🦋."""
    t0 = time.perf_counter()
    if not root_dir or not isinstance(root_dir, str):
        return {"status": "ERROR", "error": "Invalid or empty root directory path provided", "mark": WATERMARK}

    try:
        root_abs = os.path.abspath(root_dir)
        if not os.path.exists(root_abs):
            return {
                "status": "ERROR",
                "error": f"Directory '{root_dir}' does not exist",
                "root": root_abs,
                "mark": WATERMARK,
            }
        if not os.path.isdir(root_abs):
            return {
                "status": "ERROR",
                "error": f"Path '{root_dir}' is a file, not a directory",
                "root": root_abs,
                "mark": WATERMARK,
            }

        entries = []
        total_found = 0

        for dirpath, dirnames, filenames in os.walk(root_abs):
            rel = os.path.relpath(dirpath, root_abs)
            depth = 0 if rel == "." else len(rel.split(os.sep))
            if depth > max_depth:
                dirnames.clear()
                continue

            if include_files:
                for f in filenames:
                    total_found += 1
                    if len(entries) < max_entries:
                        fpath = os.path.join(dirpath, f)
                        try:
                            sz = os.path.getsize(fpath)
                        except Exception:
                            sz = 0
                        entries.append({
                            "path": os.path.relpath(fpath, root_abs),
                            "size_bytes": sz,
                            "type": "file",
                        })

            for d in dirnames:
                total_found += 1
                if len(entries) < max_entries:
                    dpath = os.path.join(dirpath, d)
                    entries.append({
                        "path": os.path.relpath(dpath, root_abs),
                        "type": "directory",
                    })

        return {
            "status": "SUCCESS",
            "root": root_abs,
            "max_depth": max_depth,
            "total_scanned": total_found,
            "entries_count": len(entries),
            "entries": entries,
            "truncated": total_found > max_entries,
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "root": str(root_dir),
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }


# Maintain backward-compatible alias
file_tree = list_directory_tree


def read_file_safe(
    path: str,
    max_bytes: int = 1048576,
    encoding: str = "utf-8",
    tail_lines: Optional[int] = None,
) -> Dict[str, Any]:
    """Safely read content of a file with size cap, encoding safety, and optional tail support 🦋."""
    t0 = time.perf_counter()
    if not path or not isinstance(path, str):
        return {"status": "ERROR", "error": "Invalid or empty file path provided", "mark": WATERMARK}

    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {"status": "ERROR", "path": abs_path, "error": f"File '{path}' does not exist", "mark": WATERMARK}
        if not os.path.isfile(abs_path):
            return {"status": "ERROR", "path": abs_path, "error": f"Path '{path}' is a directory, not a regular file", "mark": WATERMARK}

        sz = os.path.getsize(abs_path)
        if tail_lines and tail_lines > 0:
            return tail_log_safe(abs_path, lines=tail_lines, max_bytes=max_bytes, encoding=encoding)

        with open(abs_path, "rb") as f:
            raw = f.read(max_bytes)
        text = raw.decode(encoding, errors="replace")
        return {
            "status": "SUCCESS",
            "path": abs_path,
            "size_bytes": sz,
            "read_bytes": len(raw),
            "truncated": sz > max_bytes,
            "content": text,
            "line_count": len(text.splitlines()),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "path": str(path),
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }


def write_file_safe(
    path: str,
    content: str,
    make_dirs: bool = True,
    append: bool = False,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """Safely write or append text content to a target file with directory creation 🦋."""
    t0 = time.perf_counter()
    if not path or not isinstance(path, str):
        return {"status": "ERROR", "error": "Invalid or empty file path provided", "mark": WATERMARK}

    try:
        abs_path = os.path.abspath(path)
        if make_dirs:
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)

        from tools.runtime.runtime_io import atomic_write, transaction
        content_str = str(content)
        with transaction(abs_path):
            previous = ""
            if append and os.path.exists(abs_path):
                with open(abs_path, encoding=encoding, newline="") as stream:
                    previous = stream.read()
            expected = previous + content_str
            atomic_write(abs_path, expected, encoding=encoding)
            with open(abs_path, encoding=encoding, newline="") as stream:
                if stream.read() != expected:
                    raise IOError("File verification failed after write")

        bytes_written = len(content_str.encode(encoding, errors="replace"))
        return {
            "status": "SUCCESS",
            "path": abs_path,
            "append": append,
            "bytes_written": bytes_written,
            "verified": True,
            "sha256": __import__("hashlib").sha256(Path(abs_path).read_bytes()).hexdigest(),
            "lines_written": len(content_str.splitlines()),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "path": str(path),
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }


def tail_log_safe(
    path: str,
    lines: int = 50,
    max_bytes: int = 1048576,
    encoding: str = "utf-8",
) -> Dict[str, Any]:
    """Safely read the trailing lines of a log or text file with strict memory bounds 🦋."""
    t0 = time.perf_counter()
    if not path or not isinstance(path, str):
        return {"status": "ERROR", "error": "Invalid or empty log file path provided", "mark": WATERMARK}

    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return {"status": "ERROR", "path": abs_path, "error": f"Log file '{path}' not found", "mark": WATERMARK}
        if not os.path.isfile(abs_path):
            return {"status": "ERROR", "path": abs_path, "error": f"Path '{path}' is not a regular file", "mark": WATERMARK}

        file_size = os.path.getsize(abs_path)
        read_size = min(file_size, max_bytes)

        with open(abs_path, "rb") as f:
            if file_size > read_size:
                f.seek(file_size - read_size)
            raw_bytes = f.read(read_size)

        decoded_text = raw_bytes.decode(encoding, errors="replace")
        all_lines = decoded_text.splitlines()

        # If we seeked into the middle of a file, the first line might be incomplete
        if file_size > read_size and len(all_lines) > 1:
            all_lines = all_lines[1:]

        target_lines_count = max(1, int(lines))
        tail_slice = all_lines[-target_lines_count:] if len(all_lines) >= target_lines_count else all_lines

        return {
            "status": "SUCCESS",
            "path": abs_path,
            "total_file_size": file_size,
            "read_bytes": len(raw_bytes),
            "lines_requested": target_lines_count,
            "lines_returned": len(tail_slice),
            "lines": tail_slice,
            "content": "\n".join(tail_slice),
            "truncated": file_size > read_size,
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "path": str(path),
            "error": str(exc),
            "latency_s": round(time.perf_counter() - t0, 4),
            "mark": WATERMARK,
        }


def find_files(root_dir: str, pattern: str = "*.*", recursive: bool = True, max_results: int = 100) -> List[Dict[str, Any]]:
    """Search for files matching glob pattern."""
    results = []
    root_abs = os.path.abspath(root_dir)
    if not os.path.exists(root_abs):
        return results

    if recursive:
        for dirpath, _, filenames in os.walk(root_abs):
            for f in filenames:
                if fnmatch.fnmatch(f, pattern):
                    fpath = os.path.join(dirpath, f)
                    try:
                        sz = os.path.getsize(fpath)
                    except Exception:
                        sz = 0
                    results.append({
                        "path": fpath,
                        "rel_path": os.path.relpath(fpath, root_abs),
                        "size_bytes": sz,
                        "mark": WATERMARK,
                    })
                    if len(results) >= max_results:
                        return results
    else:
        for f in os.listdir(root_abs):
            fpath = os.path.join(root_abs, f)
            if os.path.isfile(fpath) and fnmatch.fnmatch(f, pattern):
                results.append({
                    "path": fpath,
                    "rel_path": f,
                    "size_bytes": os.path.getsize(fpath),
                    "mark": WATERMARK,
                })
                if len(results) >= max_results:
                    return results

    return results


def disk_space(drive: str = "D:") -> Dict[str, Any]:
    """Inspect disk space for a given drive or mount path.

    Windows: drive letters like ``D:`` are normalized to ``D:\\``.
    POSIX: if the requested drive is not a valid mount path, fall back to
    the primary volume (``/``) so autonomous storage queries still succeed.
    """
    if sys.platform == "win32":
        target = drive if drive.endswith(("\\", "/")) else f"{drive}\\"
    else:
        target = drive if os.path.isdir(drive) else "/"
    try:
        usage = shutil.disk_usage(target)
        return {
            "drive": drive,
            "mount": target,
            "total_gb": round(usage.total / (1024 ** 3), 2),
            "used_gb": round(usage.used / (1024 ** 3), 2),
            "free_gb": round(usage.free / (1024 ** 3), 2),
            "used_percent": round((usage.used / usage.total) * 100.0, 1),
            "mark": WATERMARK,
        }
    except Exception as e:
        return {"drive": drive, "error": str(e), "mark": WATERMARK}


def get_sysinfo(drive: Optional[str] = None) -> Dict[str, Any]:
    """Inspect host OS, Python runtime, CPU cores, memory, and storage metrics 🦋."""
    t0 = time.perf_counter()
    drives_info = {}
    target_drives = [drive] if drive else (["C:\\", "D:\\"] if sys.platform == "win32" else ["/"])
    for d in target_drives:
        try:
            total, used, free = shutil.disk_usage(d)
            drives_info[d] = {
                "total_gb": round(total / (1024 ** 3), 2),
                "used_gb": round(used / (1024 ** 3), 2),
                "free_gb": round(free / (1024 ** 3), 2),
                "percent_used": round((used / total) * 100.0, 1) if total > 0 else 0.0,
            }
        except Exception as exc:
            drives_info[d] = {"error": str(exc)}

    mem_info: Dict[str, Any] = {}
    if sys.platform == "win32":
        try:
            res = subprocess.run(
                ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/Value"],
                capture_output=True,
                text=True,
                timeout=4,
                creationflags=NO_WINDOW,
            )
            if res.returncode == 0:
                vals = {}
                for line in res.stdout.splitlines():
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        if v.isdigit():
                            vals[k] = int(v)
                if "TotalVisibleMemorySize" in vals and "FreePhysicalMemory" in vals:
                    tot_kb = vals["TotalVisibleMemorySize"]
                    free_kb = vals["FreePhysicalMemory"]
                    used_kb = tot_kb - free_kb
                    mem_info = {
                        "total_gb": round(tot_kb / (1024 * 1024), 2),
                        "used_gb": round(used_kb / (1024 * 1024), 2),
                        "free_gb": round(free_kb / (1024 * 1024), 2),
                        "percent_used": round((used_kb / tot_kb) * 100.0, 1) if tot_kb > 0 else 0.0,
                    }
        except Exception:
            pass

    return {
        "status": "SUCCESS",
        "action": "sysinfo",
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "platform": platform.platform(),
        },
        "cpu_count": os.cpu_count() or 1,
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "memory": mem_info,
        "disk": drives_info,
        "timestamp": datetime.datetime.now().isoformat(),
        "latency_s": round(time.perf_counter() - t0, 4),
        "mark": WATERMARK,
    }


# =====================================================================
# 5) Unified OSHands Class
# =====================================================================

class OSHands:
    """Unified OS Hands & Eyes Controller."""

    def __init__(self):
        self.mark = WATERMARK

    def execute_action(self, action: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Dispatch hands action with security tier validation."""
        tool_args = args or {}
        act = action.lower().strip()
        aliases = {"kill": "ps.kill", "spawn": "ps.spawn", "focus": "win.focus",
                   "minimize": "win.minimize", "write": "fs.write", "write_file_safe": "fs.write"}
        act = aliases.get(act, act)
        if act == "fs.write" and tool_args.get("_pipe_prev"):
            value = tool_args.get("previous_result")
            for _ in range(5):
                if not isinstance(value, dict):
                    break
                value = next((value[k] for k in ("text", "content", "output", "final_output") if k in value), None)
            if not isinstance(value, str):
                return {"status": "ERROR", "error": "Previous result contains no text to write"}
            tool_args = dict(tool_args, content=value)
        if act in ("ps.kill", "process.kill", "ps.spawn", "process.spawn", "fs.write",
                   "win.focus", "windows.focus", "win.minimize", "windows.minimize"):
            from tools.runtime.approvals import authorize_tool
            high = act in ("ps.kill", "process.kill", "ps.spawn", "process.spawn")
            high = high or (act == "fs.write" and os.path.exists(tool_args.get("path", "")))
            blocked = authorize_tool("hands." + act, tool_args, high_stakes=high)
            if blocked:
                return blocked

        # Process actions
        if act in ("ps", "ps.list", "process.list"):
            limit = int(tool_args.get("limit", 100))
            filt = tool_args.get("filter")
            procs = list_processes(filter_name=filt, limit=limit)
            return {
                "action": "process.list",
                "total": len(procs),
                "processes": [p.to_dict() for p in procs],
                "mark": WATERMARK,
            }
        elif act in ("ps.info", "process.info", "info", "get_process_info"):
            target = tool_args.get("target") or tool_args.get("pid") or tool_args.get("name")
            return get_process_info(target)
        elif act in ("ps.find", "process.find"):
            q = tool_args.get("query", "")
            procs = find_process(q)
            return {
                "action": "process.find",
                "query": q,
                "matches": [p.to_dict() for p in procs],
                "mark": WATERMARK,
            }
        elif act in ("ps.kill", "process.kill"):
            target = tool_args.get("target") or tool_args.get("pid")
            force = bool(tool_args.get("force", False))
            return kill_process(target, force=force)
        elif act in ("ps.spawn", "process.spawn"):
            cmd = tool_args.get("command")
            cwd = tool_args.get("cwd")
            bg = bool(tool_args.get("background", True))
            return spawn_process(cmd, cwd=cwd, background=bg)

        # Window actions
        elif act in ("win.list", "windows.list", "windows"):
            wins = list_windows(visible_only=bool(tool_args.get("visible_only", True)))
            return {
                "action": "windows.list",
                "total": len(wins),
                "windows": [w.to_dict() for w in wins],
                "mark": WATERMARK,
            }
        elif act in ("win.focus", "windows.focus"):
            target = tool_args.get("target") or tool_args.get("hwnd") or tool_args.get("title")
            return focus_window(target)
        elif act in ("win.minimize", "windows.minimize"):
            target = tool_args.get("target") or tool_args.get("hwnd")
            return minimize_window(target)

        # Eyes actions
        elif act in ("eyes.screenshot", "screenshot", "screen"):
            out = tool_args.get("output")
            return capture_screenshot(output_path=out)

        # Filesystem actions
        elif act in ("fs.tree", "tree", "list_directory_tree"):
            root = tool_args.get("root", ".")
            depth = int(tool_args.get("depth", tool_args.get("max_depth", 2)))
            max_entries = int(tool_args.get("max_entries", 100))
            return list_directory_tree(root, max_depth=depth, max_entries=max_entries)
        elif act in ("fs.read", "read", "read_file_safe"):
            path = tool_args.get("path", "")
            max_b = int(tool_args.get("max_bytes", 1048576))
            tail_n = int(tool_args.get("tail_lines", 0)) if tool_args.get("tail_lines") else None
            return read_file_safe(path, max_bytes=max_b, tail_lines=tail_n)
        elif act in ("fs.write", "write", "write_file_safe"):
            path = tool_args.get("path", "")
            content = tool_args.get("content", "")
            append = bool(tool_args.get("append", False))
            return write_file_safe(path, content, append=append)
        elif act in ("fs.tail", "tail", "tail_log_safe"):
            path = tool_args.get("path", "")
            lines = int(tool_args.get("lines", tool_args.get("n", 50)))
            max_b = int(tool_args.get("max_bytes", 1048576))
            return tail_log_safe(path, lines=lines, max_bytes=max_b)
        elif act in ("fs.disk", "disk"):
            drv = tool_args.get("drive", "D:")
            return disk_space(drv)
        elif act in ("sysinfo", "sys_info", "system.info", "system_info", "hostinfo"):
            drv = tool_args.get("drive")
            return get_sysinfo(drv)
        elif act in ("health", "health_check", "hands.health"):
            drv = tool_args.get("drive", "D:")
            return check_hands_health(drive=drv, log_telemetry=True)

        else:
            return {
                "status": "ERROR",
                "error": f"Unknown OS Hands action '{action}'",
                "mark": WATERMARK,
            }


def check_hands_health(drive: Optional[str] = "D:", log_telemetry: bool = True) -> Dict[str, Any]:
    """Execute OS hands and eyes subsystem health check and telemetry logging 🦋."""
    t0 = time.perf_counter()
    procs = list_processes(limit=10)
    proc_ok = len(procs) > 0

    # Check screen / eyes capability
    eyes_res = capture_screenshot()
    eyes_ok = eyes_res.get("status") == "SUCCESS"

    # Check sysinfo & disk
    sys_res = get_sysinfo(drive=drive)
    disk_ok = bool(sys_res.get("disk"))
    ram_ok = bool(sys_res.get("memory"))

    overall_status = "HEALTHY" if (proc_ok and disk_ok and ram_ok) else "DEGRADED"
    lat = round(time.perf_counter() - t0, 4)

    res = {
        "status": overall_status,
        "subsystem": "hands_and_eyes",
        "hands": {
            "processes_detected": len(procs),
            "process_subsystem": "UP" if proc_ok else "DOWN",
            "filesystem_subsystem": "UP" if disk_ok else "DOWN",
        },
        "eyes": {
            "screenshot_subsystem": "UP" if eyes_ok else "DOWN",
            "last_capture": eyes_res.get("path"),
            "resolution": eyes_res.get("resolution"),
            "size_kb": eyes_res.get("size_kb"),
        },
        "system": {
            "platform": sys_res.get("os", {}).get("platform"),
            "cpu_cores": sys_res.get("cpu_count"),
            "memory": sys_res.get("memory"),
            "disk": sys_res.get("disk"),
        },
        "latency_s": lat,
        "timestamp": datetime.datetime.now().isoformat(),
        "mark": WATERMARK,
    }

    if log_telemetry:
        telemetry_file = os.path.join(JARVIS_DIR, "telemetry.jsonl")
        event = {
            "task_id": f"hands_health_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            "timestamp": res["timestamp"],
            "status": "SUCCESS" if overall_status == "HEALTHY" else "WARNING",
            "action": "hands.health",
            "skill_used": "hands_and_eyes",
            "latency_s": lat,
            "telemetry": {
                "cpu_cores": sys_res.get("cpu_count"),
                "ram_used_pct": sys_res.get("memory", {}).get("percent_used", 0.0),
                "processes_count": len(procs),
                "eyes_ok": eyes_ok,
            },
            "error": None if overall_status == "HEALTHY" else "Degraded subsystem component",
            "result_summary": f"Hands & Eyes Health [{overall_status}]: procs={len(procs)}, eyes={'OK' if eyes_ok else 'FAIL'}",
            "mark": WATERMARK,
        }
        try:
            with open(telemetry_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass

    return res


# =====================================================================
# 6) CLI Routing & Entrypoint
# =====================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for OS hands."""
    parser = argparse.ArgumentParser(
        prog="hands",
        description="Jarvis OS Hands — Zero-dep process, window, screenshot, and filesystem control 🦋",
        epilog="Usage: python hands.py [ps|info|kill|windows|focus|screenshot|tree|read|write|tail|disk] ... [--json]",
    )
    parser.add_argument("--screenshot", action="store_true", help="Capture full desktop screenshot shortcut")
    parser.add_argument("--health", action="store_true", help="Execute OS hands and eyes health check")
    subparsers = parser.add_subparsers(dest="subcommand", help="Hands subcommands")

    # Subcommand: ps
    p_ps = subparsers.add_parser("ps", help="List active OS processes")
    p_ps.add_argument("--filter", "-f", help="Filter process by name or PID")
    p_ps.add_argument("--limit", "-n", type=int, default=30, help="Max processes to return (default: 30)")
    p_ps.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: info
    p_info = subparsers.add_parser("info", help="Get detailed metadata for a PID or process name")
    p_info.add_argument("target", nargs="?", default=None, help="PID or image name (default: current process)")
    p_info.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: kill
    p_kill = subparsers.add_parser("kill", help="Kill process by PID or name")
    p_kill.add_argument("target", help="PID or executable name to kill")
    p_kill.add_argument("--force", "-f", action="store_true", help="Force terminate process")
    p_kill.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: windows
    p_win = subparsers.add_parser("windows", help="List visible desktop windows")
    p_win.add_argument("--all", action="store_true", help="Include invisible windows")
    p_win.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: focus
    p_foc = subparsers.add_parser("focus", help="Bring window to foreground")
    p_foc.add_argument("target", help="Window title substring or HWND integer")
    p_foc.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: screenshot
    p_shot = subparsers.add_parser("screenshot", help="Capture full desktop screenshot via PowerShell")
    p_shot.add_argument("--output", "-o", help="Target output image file path")
    p_shot.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: tree
    p_tree = subparsers.add_parser("tree", help="Display directory tree hierarchy")
    p_tree.add_argument("root", nargs="?", default=".", help="Root directory path")
    p_tree.add_argument("--depth", "-d", type=int, default=2, help="Max recursion depth")
    p_tree.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: read
    p_read = subparsers.add_parser("read", help="Safely read file content")
    p_read.add_argument("path", help="File path to read")
    p_read.add_argument("--max-bytes", "-b", type=int, default=1048576, help="Max bytes to read (default: 1MB)")
    p_read.add_argument("--tail", "-t", type=int, default=None, help="Tail last N lines")
    p_read.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: write
    p_write = subparsers.add_parser("write", help="Safely write content to file")
    p_write.add_argument("path", help="File path to write")
    p_write.add_argument("--content", "-c", required=True, help="Content to write")
    p_write.add_argument("--append", "-a", action="store_true", help="Append instead of overwrite")
    p_write.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: tail
    p_tail = subparsers.add_parser("tail", help="Safely tail log file")
    p_tail.add_argument("path", help="Log file path to tail")
    p_tail.add_argument("--lines", "-n", type=int, default=50, help="Number of trailing lines to return (default: 50)")
    p_tail.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: disk
    p_dsk = subparsers.add_parser("disk", help="Inspect drive storage space")
    p_dsk.add_argument("drive", nargs="?", default="D:", help="Drive letter or path (default: D:)")
    p_dsk.add_argument("--json", action="store_true", help="JSON output")

    # Subcommand: sysinfo
    p_sys = subparsers.add_parser("sysinfo", help="Inspect host OS, Python, CPU, memory, and storage metrics")
    p_sys.add_argument("--drive", "-d", help="Optional drive letter to inspect")
    p_sys.add_argument("--json", action="store_true", help="JSON output")

    return parser


def main():
    """Main CLI entrypoint router."""
    parser = build_parser()
    args = parser.parse_args()

    if getattr(args, "screenshot", False):
        res = capture_screenshot()
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            if res.get("status") == "SUCCESS":
                print(f"🦋 Screenshot Captured: {res.get('path')} ({res.get('resolution')}, {res.get('size_kb')} KB) 🦋")
            else:
                print(f"🦋 Screenshot Failed: {res.get('error')} 🦋")
        sys.exit(0 if res.get("status") == "SUCCESS" else 1)

    if getattr(args, "health", False):
        res = check_hands_health(log_telemetry=True)
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"🦋 OS Hands & Eyes Health Check [{res.get('status')}] 🦋")
            print("=" * 72)
            print(f"Subsystem Status : {res.get('status')}")
            print(f"Hands (Processes): {res.get('hands', {}).get('process_subsystem')} ({res.get('hands', {}).get('processes_detected')} procs)")
            print(f"Eyes (Screen)    : {res.get('eyes', {}).get('screenshot_subsystem')} ({res.get('eyes', {}).get('resolution') or 'N/A'}, {res.get('eyes', {}).get('size_kb') or 0} KB)")
            print(f"Platform         : {res.get('system', {}).get('platform')}")
            print(f"CPU Cores        : {res.get('system', {}).get('cpu_cores')}")
            mem = res.get('system', {}).get('memory') or {}
            if mem:
                print(f"RAM Usage        : {mem.get('used_gb')} GB / {mem.get('total_gb')} GB ({mem.get('percent_used')}%)")
            for drv, ddata in (res.get('system', {}).get('disk') or {}).items():
                if isinstance(ddata, dict) and 'used_gb' in ddata:
                    print(f"Disk {drv:<10}: {ddata.get('used_gb')} GB / {ddata.get('total_gb')} GB ({ddata.get('percent_used')}%)")
            print(f"Telemetry Logged : jarvis/telemetry.jsonl")
            print(f"Timestamp        : {res.get('timestamp')}")
            print("=" * 72)
        sys.exit(0 if res.get("status") in ("HEALTHY", "SUCCESS") else 1)

    if not args.subcommand:
        parser.print_help()
        sys.exit(0)

    if args.subcommand == "ps":
        procs = list_processes(filter_name=args.filter, limit=args.limit)
        if args.json:
            print(json.dumps([p.to_dict() for p in procs], indent=2))
        else:
            print(f"🦋 OS Process List ({len(procs)} processes) 🦋")
            print("=" * 72)
            print(f"{'PID':<8} | {'Memory (MB)':<12} | {'Process Name'}")
            print("-" * 72)
            for p in procs:
                print(f"{p.pid:<8} | {p.memory_mb:>10.2f} MB | {p.name}")
            print("=" * 72)

    elif args.subcommand == "info":
        res = get_process_info(args.target)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            st = "FOUND" if res.get("found") else "NOT_FOUND"
            print(f"🦋 Process Info for '{args.target or 'current'}' [{st}] 🦋")
            if res.get("found"):
                p = res.get("process", {})
                print(f"  • PID         : {p.get('pid')}")
                print(f"  • Name        : {p.get('name')}")
                print(f"  • Memory      : {p.get('memory_mb')} MB")
                print(f"  • Session     : {p.get('session_name')} (#{p.get('session_num')})")

    elif args.subcommand == "kill":
        res = kill_process(args.target, force=args.force)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            st = "SUCCESS" if res.get("success") else "FAILED"
            print(f"🦋 Kill Process '{args.target}' [{st}]: {res.get('output') or res.get('error', '')} 🦋")

    elif args.subcommand == "windows":
        wins = list_windows(visible_only=not args.all)
        if args.json:
            print(json.dumps([w.to_dict() for w in wins], indent=2))
        else:
            print(f"🦋 Open Desktop Windows ({len(wins)} windows) 🦋")
            print("=" * 72)
            print(f"{'HWND':<10} | {'PID':<8} | {'Window Title'}")
            print("-" * 72)
            for w in wins:
                print(f"{w.hwnd:<10} | {w.pid:<8} | {w.title}")
            print("=" * 72)

    elif args.subcommand == "focus":
        res = focus_window(args.target)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"🦋 Focus Window '{args.target}': {'SUCCESS' if res.get('success') else 'FAILED'} 🦋")

    elif args.subcommand == "screenshot":
        res = capture_screenshot(output_path=args.output)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("status") == "SUCCESS":
                print(f"🦋 Screenshot Captured: {res.get('path')} ({res.get('resolution')}, {res.get('size_kb')} KB) 🦋")
            else:
                print(f"🦋 Screenshot Failed: {res.get('error')} 🦋")

    elif args.subcommand == "tree":
        res = list_directory_tree(args.root, max_depth=args.depth)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"🦋 Directory Tree for: {res.get('root')} (depth={args.depth}) 🦋")
            for e in res.get("entries", []):
                t_icon = "📁" if e.get("type") == "directory" else "📄"
                print(f"  {t_icon} {e.get('path')}")

    elif args.subcommand == "read":
        res = read_file_safe(args.path, max_bytes=args.max_bytes, tail_lines=args.tail)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("status") == "SUCCESS":
                print(f"🦋 File Read: {res.get('path')} ({res.get('read_bytes')} bytes) 🦋")
                print(res.get("content", ""))
            else:
                print(f"🦋 File Read Failed: {res.get('error')} 🦋")

    elif args.subcommand == "write":
        res = write_file_safe(args.path, args.content, append=args.append)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            st = res.get("status", "UNKNOWN")
            print(f"🦋 File Write [{st}]: {res.get('path')} ({res.get('bytes_written')} bytes) 🦋")

    elif args.subcommand == "tail":
        res = tail_log_safe(args.path, lines=args.lines)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            if res.get("status") == "SUCCESS":
                print(f"🦋 Tail Log: {res.get('path')} ({res.get('lines_returned')} lines) 🦋")
                print(res.get("content", ""))
            else:
                print(f"🦋 Tail Log Failed: {res.get('error')} 🦋")

    elif args.subcommand == "disk":
        res = disk_space(args.drive)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"🦋 Disk Space: {args.drive} -> {res.get('used_gb')} GB used / {res.get('total_gb')} GB total ({res.get('used_percent')}%) | Free: {res.get('free_gb')} GB 🦋")

    elif args.subcommand == "sysinfo":
        res = get_sysinfo(args.drive)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"🦋 System Diagnostics & Metrics 🦋")
            print("=" * 72)
            print(f"OS Platform     : {res.get('os', {}).get('platform')}")
            print(f"CPU Cores       : {res.get('cpu_count')}")
            print(f"Python Version  : {res.get('python', {}).get('version')}")
            mem = res.get('memory', {})
            if mem:
                print(f"RAM Usage       : {mem.get('used_gb')} GB / {mem.get('total_gb')} GB ({mem.get('percent_used')}%)")
            for drv, ddata in res.get('disk', {}).items():
                if isinstance(ddata, dict) and 'used_gb' in ddata:
                    print(f"Disk {drv:<10}: {ddata.get('used_gb')} GB / {ddata.get('total_gb')} GB ({ddata.get('percent_used')}%)")
            print(f"Timestamp       : {res.get('timestamp')}")
            print("=" * 72)


if __name__ == "__main__":
    main()
