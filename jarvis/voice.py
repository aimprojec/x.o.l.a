#!/usr/bin/env python3
"""Usage: python voice.py [--speak TEXT] [--listen] [--enqueue TEXT] [--process] [--tail N] [--test-ears] [--json] # Jarvis Voice Synthesis & Ears Subsystem 🦋"""

# =====================================================================
# X.O.L.A. Phase 4 — Jarvis Voice Synthesis & Ears Queue Interface
# ---------------------------------------------------------------------
# Zero-dependency, pure Python standard library voice synthesizer (Windows
# System.Speech.Synthesis / SAPI TTS) and ears audio/text queue subsystem.
# =====================================================================

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
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
PROJECT_ROOT = os.path.dirname(JARVIS_DIR)
EARS_DIR = os.path.join(JARVIS_DIR, "ears")
EARS_ARCHIVE_DIR = os.path.join(EARS_DIR, "archive")
VOICE_LOG_FILE = os.path.join(JARVIS_DIR, "voice.log")


# =====================================================================
# 1) Dataclasses: Utterance & VoiceLogEntry
# =====================================================================

@dataclass
class Utterance:
    """Incoming voice/audio/text utterance recorded into the ears queue."""
    id: str
    text: str
    source: str = "voice"  # "voice", "user", "audio", "mic", "text"
    speaker: str = "user"
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    processed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    mark: str = WATERMARK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class VoiceLogEntry:
    """Structured voice synthesis event logged to voice.log."""
    timestamp: str
    text: str
    rate: int = 0
    volume: int = 100
    voice: Optional[str] = None
    latency_s: float = 0.0
    status: str = "SUCCESS"  # "SUCCESS", "ERROR", "MUTED"
    error: Optional[str] = None
    mark: str = WATERMARK

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_log_line(self) -> str:
        err_part = f" | ERROR: {self.error}" if self.error else ""
        return (
            f"[{self.timestamp}] [{self.status}] Speak: \"{self.text}\" | "
            f"Rate: {self.rate} | Vol: {self.volume} | Latency: {self.latency_s:.4f}s{err_part} {self.mark}"
        )


# =====================================================================
# 2) Voice Synthesis Engine (TTS via PowerShell / SAPI)
# =====================================================================

class VoiceEngine:
    """Zero-dependency Windows speech synthesizer and prompt logger."""

    def __init__(self, log_path: str = VOICE_LOG_FILE, enabled: bool = True):
        self.log_path = log_path
        self.enabled = enabled
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(os.path.abspath(self.log_path)), exist_ok=True)

    def _build_powershell_tts_script(
        self,
        text: str,
        rate: int = 0,
        volume: int = 100,
        voice: Optional[str] = None,
    ) -> str:
        """Construct safe PowerShell System.Speech script."""
        safe_text = text.replace("'", "''").replace("`", "``")
        clamped_rate = max(-10, min(10, rate))
        clamped_vol = max(0, min(100, volume))

        script_lines = [
            "Add-Type -AssemblyName System.Speech;",
            "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;",
            f"$synth.Rate = {clamped_rate};",
            f"$synth.Volume = {clamped_vol};",
        ]
        if voice:
            safe_voice = voice.replace("'", "''")
            script_lines.append(f"$synth.SelectVoice('{safe_voice}');")

        script_lines.append(f"$synth.Speak('{safe_text}');")
        return " ".join(script_lines)

    def _build_sapi_fallback_script(self, text: str, rate: int = 0, volume: int = 100) -> str:
        """Construct SAPI.SpVoice COM fallback script."""
        safe_text = text.replace("'", "''").replace("`", "``")
        clamped_rate = max(-10, min(10, rate))
        clamped_vol = max(0, min(100, volume))
        return (
            f"$sapi = New-Object -ComObject SAPI.SpVoice; "
            f"$sapi.Rate = {clamped_rate}; "
            f"$sapi.Volume = {clamped_vol}; "
            f"$sapi.Speak('{safe_text}');"
        )

    def log_entry(self, entry: VoiceLogEntry) -> None:
        """Append voice log entry to voice.log."""
        with self._lock:
            try:
                line = entry.to_log_line() + "\n"
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(line)
            except Exception as e:
                print(f"🦋 Voice logging error: {e}", file=sys.stderr)

    def speak(
        self,
        text: str,
        rate: int = 0,
        volume: int = 100,
        voice: Optional[str] = None,
        wait: bool = True,
        log: bool = True,
        async_mode: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Synthesize speech using zero-dependency Windows TTS."""
        if async_mode is not None:
            wait = not async_mode

        if not text or not text.strip():
            return {
                "status": "EMPTY",
                "text": "",
                "latency_s": 0.0,
                "mark": WATERMARK,
            }

        if not self.enabled:
            entry = VoiceLogEntry(
                timestamp=datetime.datetime.now().isoformat(),
                text=text.strip(),
                rate=rate,
                volume=volume,
                voice=voice,
                latency_s=0.0,
                status="MUTED",
                mark=WATERMARK,
            )
            if log:
                self.log_entry(entry)
            return entry.to_dict()

        if not wait:
            # Run in daemon background thread
            t = threading.Thread(
                target=self._execute_speech,
                args=(text, rate, volume, voice, log),
                daemon=True,
                name="JarvisVoiceThread",
            )
            t.start()
            return {
                "status": "ASYNC_QUEUED",
                "text": text.strip(),
                "rate": rate,
                "volume": volume,
                "voice": voice,
                "mark": WATERMARK,
            }

        return self._execute_speech(text, rate, volume, voice, log)

    def _execute_speech(
        self,
        text: str,
        rate: int = 0,
        volume: int = 100,
        voice: Optional[str] = None,
        log: bool = True,
    ) -> Dict[str, Any]:
        """Internal synchronous speech execution handler."""
        t0 = time.perf_counter()
        clean_text = text.strip()
        now_ts = datetime.datetime.now().isoformat()

        if sys.platform != "win32":
            if log:
                self.log_entry(VoiceLogEntry(timestamp=now_ts, text=clean_text, rate=rate,
                    volume=volume, voice=voice, latency_s=0.0, status="UNSUPPORTED", mark=WATERMARK))
            return {"status": "UNSUPPORTED", "text": clean_text,
                    "error": "Speech output requires Windows System.Speech on this build",
                    "latency_s": round(time.perf_counter() - t0, 4), "mark": WATERMARK}

        # Primary attempt: System.Speech.Synthesis
        ps_cmd = self._build_powershell_tts_script(clean_text, rate, volume, voice)
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=NO_WINDOW,
            )
            lat = round(time.perf_counter() - t0, 4)

            if res.returncode == 0:
                entry = VoiceLogEntry(
                    timestamp=now_ts,
                    text=clean_text,
                    rate=rate,
                    volume=volume,
                    voice=voice,
                    latency_s=lat,
                    status="SUCCESS",
                    mark=WATERMARK,
                )
                if log:
                    self.log_entry(entry)
                return entry.to_dict()

            # Secondary attempt: SAPI fallback
            sapi_cmd = self._build_sapi_fallback_script(clean_text, rate, volume)
            res_sapi = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", sapi_cmd],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=NO_WINDOW,
            )
            lat_sapi = round(time.perf_counter() - t0, 4)

            if res_sapi.returncode == 0:
                entry = VoiceLogEntry(
                    timestamp=now_ts,
                    text=clean_text,
                    rate=rate,
                    volume=volume,
                    voice=voice,
                    latency_s=lat_sapi,
                    status="SUCCESS",
                    mark=WATERMARK,
                )
                if log:
                    self.log_entry(entry)
                return entry.to_dict()

            # If both failed
            err_msg = res.stderr or res_sapi.stderr or "PowerShell TTS returned non-zero code"
            entry = VoiceLogEntry(
                timestamp=now_ts,
                text=clean_text,
                rate=rate,
                volume=volume,
                voice=voice,
                latency_s=lat,
                status="ERROR",
                error=err_msg.strip(),
                mark=WATERMARK,
            )
            if log:
                self.log_entry(entry)
            return entry.to_dict()

        except Exception as exc:
            lat = round(time.perf_counter() - t0, 4)
            entry = VoiceLogEntry(
                timestamp=now_ts,
                text=clean_text,
                rate=rate,
                volume=volume,
                voice=voice,
                latency_s=lat,
                status="ERROR",
                error=str(exc),
                mark=WATERMARK,
            )
            if log:
                self.log_entry(entry)
            return entry.to_dict()


# =====================================================================
# 3) Ears Audio / Text Queue Subsystem
# =====================================================================

class EarsQueue:
    """Manages the ears inbox queue in jarvis/ears/ for audio & text utterances."""

    def __init__(self, ears_dir: str = EARS_DIR):
        self.ears_dir = ears_dir
        self.archive_dir = os.path.join(ears_dir, "archive")
        self.mark = WATERMARK

        os.makedirs(self.ears_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)

    def enqueue(
        self,
        text: str,
        source: str = "voice",
        speaker: str = "user",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Utterance:
        """Record a new utterance into the ears queue directory."""
        clean_text = text.strip()
        uid = uuid.uuid4().hex[:8]
        ts_slug = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        utterance_id = f"ears_{ts_slug}_{uid}"

        utt = Utterance(
            id=utterance_id,
            text=clean_text,
            source=source,
            speaker=speaker,
            timestamp=datetime.datetime.now().isoformat(),
            processed=False,
            metadata=metadata or {},
            mark=self.mark,
        )

        file_path = os.path.join(self.ears_dir, f"{utterance_id}.json")
        try:
            from tools.runtime.runtime_io import write_json
            write_json(file_path, utt.to_dict())
        except Exception as e:
            print(f"🦋 Ears enqueue write error: {e}", file=sys.stderr)

        return utt

    def list_pending(self) -> List[str]:
        """List all pending utterance JSON file paths in ears queue."""
        if not os.path.exists(self.ears_dir):
            return []
        files = []
        for f in sorted(os.listdir(self.ears_dir)):
            full_p = os.path.join(self.ears_dir, f)
            if os.path.isfile(full_p) and f.endswith(".json") and not f.startswith("."):
                files.append(full_p)
        return files

    def peek(self) -> List[Utterance]:
        """Inspect all pending utterances without archiving them."""
        pending_files = self.list_pending()
        results: List[Utterance] = []
        for fpath in pending_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(
                    Utterance(
                        id=data.get("id", os.path.splitext(os.path.basename(fpath))[0]),
                        text=data.get("text", ""),
                        source=data.get("source", "voice"),
                        speaker=data.get("speaker", "user"),
                        timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
                        processed=data.get("processed", False),
                        metadata=data.get("metadata", {}),
                        mark=data.get("mark", self.mark),
                    )
                )
            except Exception:
                pass
        return results

    def dequeue_single(self, file_path: str) -> Optional[Utterance]:
        """Read and archive a single utterance file."""
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            utt = Utterance(
                id=data.get("id", os.path.splitext(os.path.basename(file_path))[0]),
                text=data.get("text", ""),
                source=data.get("source", "voice"),
                speaker=data.get("speaker", "user"),
                timestamp=data.get("timestamp", datetime.datetime.now().isoformat()),
                processed=True,
                metadata=data.get("metadata", {}),
                mark=data.get("mark", self.mark),
            )

            # Archive file
            filename = os.path.basename(file_path)
            dest_path = os.path.join(self.archive_dir, filename)
            if os.path.exists(dest_path):
                os.remove(dest_path)
            shutil.move(file_path, dest_path)

            return utt
        except Exception as exc:
            print(f"🦋 Ears dequeue error for {file_path}: {exc}", file=sys.stderr)
            return None

    def process_queue(
        self,
        handler: Optional[Callable[[Utterance], Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Process all pending utterances and archive them."""
        pending_files = self.list_pending()
        processed_records = []

        for fpath in pending_files:
            try:
                with open(fpath, encoding="utf-8") as stream:
                    data = json.load(stream)
                utt = Utterance(**{k: v for k, v in data.items() if k in Utterance.__dataclass_fields__})
                handler_res = handler(utt) if callable(handler) else None
                if isinstance(handler_res, dict) and (handler_res.get("error") or
                        handler_res.get("status") in ("ERROR", "PENDING_APPROVAL")):
                    processed_records.append({"utterance": utt.to_dict(), "handler_result": handler_res})
                    continue
                archived = self.dequeue_single(fpath)
                if archived:
                    processed_records.append({"utterance": archived.to_dict(), "handler_result": handler_res,
                        "processed_at": datetime.datetime.now().isoformat(), "mark": self.mark})
            except Exception as exc:
                processed_records.append({"file": fpath, "handler_result": {"error": str(exc)}})

        return processed_records


# =====================================================================
# 4) Global Functional Helpers
# =====================================================================

_GLOBAL_VOICE = VoiceEngine()
_GLOBAL_EARS = EarsQueue()


def speak(
    text: str,
    rate: int = 0,
    volume: int = 100,
    voice: Optional[str] = None,
    wait: bool = True,
    log: bool = True,
    async_mode: Optional[bool] = None,
) -> Dict[str, Any]:
    """Top-level functional speech synthesis entrypoint."""
    return _GLOBAL_VOICE.speak(
        text=text,
        rate=rate,
        volume=volume,
        voice=voice,
        wait=wait,
        log=log,
        async_mode=async_mode,
    )


def enqueue_utterance(
    text: str,
    source: str = "voice",
    speaker: str = "user",
    metadata: Optional[Dict[str, Any]] = None,
    ears_dir: str = EARS_DIR,
) -> str:
    """Top-level helper to drop an utterance into the ears queue."""
    ears = EarsQueue(ears_dir=ears_dir)
    utt = ears.enqueue(text=text, source=source, speaker=speaker, metadata=metadata)
    return utt.id


def read_voice_log(tail_n: int = 20, log_path: str = VOICE_LOG_FILE) -> List[str]:
    """Read the last N lines of voice.log."""
    if not os.path.exists(log_path):
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f.readlines() if l.strip()]
            return lines[-tail_n:] if tail_n > 0 else lines
    except Exception:
        return []


def process_ears_queue(ears_dir: str = EARS_DIR) -> List[Dict[str, Any]]:
    """Process all queued utterances in ears directory."""
    ears = EarsQueue(ears_dir=ears_dir)
    return ears.process_queue()


def verify_ears_listener(ears_dir: str = EARS_DIR, timeout: int = 15) -> Dict[str, Any]:
    """Test verification of native Windows wake-word listener ears_listener.ps1 🦋."""
    listener_script = os.path.join(JARVIS_DIR, "ears_listener.ps1")
    if not os.path.exists(listener_script):
        return {
            "status": "FAILED",
            "error": f"Listener script not found: {listener_script}",
            "mark": WATERMARK,
        }

    test_phrase = "Round 151 wake-word verification test 🦋"
    cmd = [
        "powershell",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        listener_script,
        "-TestEmit",
        "-TestPhrase",
        test_phrase,
        "-EarsDir",
        ears_dir,
    ]

    try:
        t0 = time.perf_counter()
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            creationflags=NO_WINDOW,
        )
        latency = round(time.perf_counter() - t0, 4)

        if res.returncode != 0:
            return {
                "status": "ERROR",
                "error": res.stderr.strip() or f"Process returned code {res.returncode}",
                "latency_s": latency,
                "mark": WATERMARK,
            }

        ears = EarsQueue(ears_dir=ears_dir)
        pending = ears.peek()
        matching = [u for u in pending if u.text == test_phrase]
        if not matching:
            return {
                "status": "FAILED",
                "error": "Utterance was not found in ears queue after listener emit",
                "latency_s": latency,
                "mark": WATERMARK,
            }

        target_utt = matching[0]
        # Clean up / dequeue the test verification utterance
        for f in ears.list_pending():
            try:
                with open(f, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                if data.get("text") == test_phrase:
                    ears.dequeue_single(f)
            except Exception:
                pass

        return {
            "status": "PASSED",
            "listener_script": listener_script,
            "test_phrase": test_phrase,
            "utterance_id": target_utt.id,
            "source": target_utt.source,
            "confidence": target_utt.metadata.get("confidence", 1.0),
            "latency_s": latency,
            "mark": WATERMARK,
        }
    except Exception as exc:
        return {
            "status": "ERROR",
            "error": str(exc),
            "mark": WATERMARK,
        }


# =====================================================================
# 5) Terminal Rendering & CLI Entrypoint
# =====================================================================

def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser for voice synthesis and ears queue."""
    parser = argparse.ArgumentParser(
        prog="voice",
        description="Jarvis Voice Synthesis & Ears Queue Subsystem 🦋",
        epilog="Usage: python voice.py [--speak TEXT] [--listen] [--enqueue TEXT] [--process] [--tail N] [--test-ears] [--json]",
    )
    parser.add_argument("--speak", "-s", metavar="TEXT", help="Synthesize and speak text via Windows TTS")
    parser.add_argument("--rate", "-r", type=int, default=0, help="Speech rate from -10 to 10 (default: 0)")
    parser.add_argument("--volume", "-v", type=int, default=100, help="Speech volume from 0 to 100 (default: 100)")
    parser.add_argument("--voice", help="Specific voice name to select")
    parser.add_argument("--async-speak", "--bg", action="store_true", help="Speak asynchronously in background")
    parser.add_argument("--enqueue", "-e", metavar="TEXT", help="Record audio/text utterance into ears queue")
    parser.add_argument("--speaker", default="user", help="Speaker identifier for enqueued utterance")
    parser.add_argument("--source", default="voice", help="Source type (voice, text, mic, user)")
    parser.add_argument("--process", "-p", action="store_true", help="Process and archive pending ears queue")
    parser.add_argument("--peek", action="store_true", help="Inspect pending items in ears queue")
    parser.add_argument("--tail", type=int, default=0, metavar="N", help="Display last N entries from voice.log")
    parser.add_argument("--test-ears", "--verify-ears", action="store_true", help="Run test verification of native ears listener")
    parser.add_argument("--json", action="store_true", help="Output result in machine-readable JSON")
    return parser


def main():
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if args.tail > 0:
        lines = read_voice_log(tail_n=args.tail)
        if args.json:
            print(json.dumps({"voice_log": lines, "total": len(lines), "mark": WATERMARK}, indent=2))
        else:
            print(f"🦋 Jarvis Voice Log (Last {len(lines)} entries) 🦋")
            print("=" * 72)
            for l in lines:
                print(l)
            print("=" * 72)
        sys.exit(0)

    if args.speak:
        res = speak(
            text=args.speak,
            rate=args.rate,
            volume=args.volume,
            voice=args.voice,
            wait=not args.async_speak,
        )
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            st = res.get("status", "SUCCESS")
            lat = res.get("latency_s", 0.0)
            print(f"🦋 Spoken [{st}] ({lat:.3f}s): \"{args.speak}\" {WATERMARK}")
        sys.exit(0 if res.get("status") in ("SUCCESS", "ASYNC_QUEUED") else 1)

    if args.enqueue:
        utt_id = enqueue_utterance(
            text=args.enqueue,
            source=args.source,
            speaker=args.speaker,
        )
        if args.json:
            print(json.dumps({"status": "ENQUEUED", "utterance_id": utt_id, "mark": WATERMARK}, indent=2))
        else:
            print(f"🦋 Enqueued utterance into ears queue [ID: {utt_id}]: \"{args.enqueue}\" 🦋")
        sys.exit(0)

    if args.peek:
        ears = EarsQueue()
        pending = ears.peek()
        if args.json:
            print(json.dumps([p.to_dict() for p in pending], indent=2, ensure_ascii=False))
        else:
            print(f"🦋 Jarvis Ears Queue ({len(pending)} pending utterances) 🦋")
            print("=" * 72)
            for p in pending:
                print(f"[{p.timestamp}] ({p.speaker}/{p.source}) {p.id}: {p.text}")
            print("=" * 72)
        sys.exit(0)

    if args.process:
        processed = process_ears_queue()
        if args.json:
            print(json.dumps(processed, indent=2, ensure_ascii=False))
        else:
            print(f"🦋 Processed {len(processed)} utterance(s) from ears queue 🦋")
            for r in processed:
                u = r.get("utterance", {})
                print(f"  • [{u.get('id')}] {u.get('text')}")
        sys.exit(0)

    if args.test_ears:
        res = verify_ears_listener()
        if args.json:
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            st = res.get("status", "UNKNOWN")
            print(f"🦋 Ears Listener Verification [{st}] 🦋")
            print("=" * 72)
            print(f"Status       : {st}")
            print(f"Script       : {res.get('listener_script')}")
            print(f"Test Phrase  : {res.get('test_phrase')}")
            print(f"Utterance ID : {res.get('utterance_id')}")
            print(f"Confidence   : {res.get('confidence')}")
            print(f"Latency      : {res.get('latency_s')}s")
            if res.get("error"):
                print(f"Error        : {res.get('error')}")
            print("=" * 72)
        sys.exit(0 if res.get("status") == "PASSED" else 1)

    # Default action if no flags: status
    ears = EarsQueue()
    pending = ears.peek()
    recent_logs = read_voice_log(tail_n=5)
    status_payload = {
        "status": "HEALTHY",
        "timestamp": datetime.datetime.now().isoformat(),
        "ears_pending_count": len(pending),
        "recent_voice_logs": len(recent_logs),
        "mark": WATERMARK,
    }
    if args.json:
        print(json.dumps(status_payload, indent=2))
    else:
        print(f"🦋 Jarvis Voice & Ears Status [HEALTHY] 🦋")
        print("=" * 72)
        print(f"Timestamp    : {status_payload['timestamp']}")
        print(f"Ears Pending : {status_payload['ears_pending_count']} utterance(s)")
        print(f"Voice Log    : {len(recent_logs)} recent entries logged")
        print("=" * 72)
    sys.exit(0)


if __name__ == "__main__":
    main()
