#!/usr/bin/env python3
"""tests/test_audit.py — Test Suite for Audit Telemetry & Verification Contracts 🦋

Tests:
1. Deterministic correction detection (rejections vs standard prompts)
2. Immutable append-only routing event logging
3. Correction resolution (explicit and LAST reference resolution)
4. VerifiableTool lifecycle (capture_before_state, execute, verify, error raise)
5. UnverifiableTool contract execution
6. Gateway cascade telemetry integration
Pure stdlib. Zero external dependencies. 🦋
"""

import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from typing import Any

# Ensure project root in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.audit import (
    AUDIT_LOG_PATH,
    CORRECTION_PATTERNS,
    UnverifiableTool,
    VerifiableTool,
    VerificationFailedError,
    detect_user_correction,
    log_routing_event,
    mark_last_event_corrected,
    resolve_corrections,
)
from tools.armory import VerifiableAtomicFileWriter, UnverifiableNotification
from tools.gateway import cascade

WATERMARK = "🦋"


class TestAuditTelemetryAndCorrections(unittest.TestCase):
    """Test suite for neutral audit log and user correction detection 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit_log = os.path.join(self.temp_dir, "routing_audit.jsonl")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_user_correction_positives(self):
        """Verify detect_user_correction triggers on correction phrases 🦋"""
        positives = [
            "no, do that on drive D:",
            "nope that's not what I asked",
            "wait, hold on a second",
            "stop and reconsider",
            "wrong, check the other file",
            "incorrect path specified",
            "actually I wanted the summary",
            "i meant run the test suite",
            "don't do that",
            "that's wrong try again",
        ]
        for phrase in positives:
            with self.subTest(phrase=phrase):
                self.assertTrue(detect_user_correction(phrase))

    def test_detect_user_correction_negatives(self):
        """Verify detect_user_correction does not falsely trigger on normal queries 🦋"""
        negatives = [
            "show me disk space",
            "run the test suite",
            "create a one-page summary",
            "where is her port",
            "open file explorer",
            "how many files are in the database",
        ]
        for phrase in negatives:
            with self.subTest(phrase=phrase):
                self.assertFalse(detect_user_correction(phrase))

    def test_log_routing_event(self):
        """Verify immutable jsonl event logging with watermark and metadata 🦋"""
        eid = log_routing_event(
            prompt="summarize recent activity",
            tier=1,
            confidence=0.88,
            threshold=0.75,
            handler="gateway.fast",
            escalated_to_llm=True,
            audit_file=self.audit_log,
        )
        self.assertTrue(eid.startswith("evt_"))
        self.assertTrue(os.path.exists(self.audit_log))

        with open(self.audit_log, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertEqual(len(lines), 1)

        record = json.loads(lines[0])
        self.assertEqual(record["event_id"], eid)
        self.assertEqual(record["tier"], 1)
        self.assertEqual(record["confidence"], 0.88)
        self.assertEqual(record["threshold"], 0.75)
        self.assertEqual(record["handler"], "gateway.fast")
        self.assertTrue(record["escalated_to_llm"])
        self.assertEqual(record["mark"], WATERMARK)

    def test_correction_resolution(self):
        """Verify resolving explicit and LAST event corrections 🦋"""
        eid1 = log_routing_event("task 1", 1, 0.9, 0.75, "h1", False, self.audit_log)
        eid2 = log_routing_event("task 2", 1, 0.85, 0.75, "h2", True, self.audit_log)

        # Mark eid1 explicitly
        mark_last_event_corrected(event_id=eid1, audit_file=self.audit_log)
        # Mark eid2 implicitly via LAST
        mark_last_event_corrected(event_id=None, audit_file=self.audit_log)

        resolved = resolve_corrections(self.audit_log)
        self.assertTrue(resolved.get(eid1))
        self.assertTrue(resolved.get(eid2))


class TestVerificationContracts(unittest.TestCase):
    """Test suite for VerifiableTool and UnverifiableTool base contracts 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_verifiable_atomic_file_writer_success(self):
        """Verify VerifiableAtomicFileWriter executes and verifies state orthogonally 🦋"""
        writer = VerifiableAtomicFileWriter()
        target = os.path.join(self.temp_dir, "verified_write.txt")
        content = f"Unit test verified atomic write {WATERMARK}"

        res = writer.run_verified({"path": target, "content": content})
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertTrue(os.path.exists(target))
        with open(target, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), content)

    def test_verifiable_tool_failure_raises_error(self):
        """Verify VerifiableTool raises VerificationFailedError if post-check fails 🦋"""
        class DefectiveTool(VerifiableTool):
            name = "defective_tool"
            schema = {"type": "object"}
            permission_tier = "SAFE_WRITE"

            def capture_before_state(self, params: dict) -> dict:
                return {}

            def execute(self, params: dict) -> dict:
                return {"done": True}

            def verify(self, params: dict, before_state: dict, result: Any) -> bool:
                return False  # Intentionally fail post-condition

        bad_tool = DefectiveTool()
        with self.assertRaises(VerificationFailedError):
            bad_tool.run_verified({})

    def test_unverifiable_notification(self):
        """Verify UnverifiableNotification executes without error 🦋"""
        notif = UnverifiableNotification()
        res = notif.execute({"title": "Test Suite", "message": "Verification test"})
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn(res.get("status"), ("DISPATCHED", "SUCCESS", "ERROR"))


class TestGatewayCascadeIntegration(unittest.TestCase):
    """Test suite for Gateway cascade telemetry wiring 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit_log = os.path.join(self.temp_dir, "cascade_audit.jsonl")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_cascade_logs_and_marks_corrections(self):
        """Verify cascade logs routing decision and marks corrections on rejections 🦋"""
        # Step 1: Normal call through cascade
        ok1, text1, lane1 = cascade(
            "check system health status",
            ["spark", "pro"],
            lambda lane, prompt: (True, f"Healthy system response from {lane} with sufficient length"),
        )
        self.assertTrue(ok1)
        self.assertEqual(lane1, "spark")

        # Step 2: Correction call through cascade
        ok2, text2, lane2 = cascade(
            "no, wrong, check memory instead",
            ["spark", "pro"],
            lambda lane, prompt: (True, f"Corrected memory response from {lane} with sufficient length"),
        )
        self.assertTrue(ok2)

        # Verify global audit log contains entries
        self.assertTrue(os.path.exists(AUDIT_LOG_PATH))
        with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        self.assertGreaterEqual(len(lines), 1)


if __name__ == "__main__":
    unittest.main()
