#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_server.py # Automated tests for xola-server 🦋"""

import io
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import server

WATERMARK = "🦋"


class TestServerHelperFunctions(unittest.TestCase):
    """Test server backend status generators and task storage 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_tasks = server.TASKS
        server.TASKS = os.path.join(self.temp_dir, "tasks.json")

    def tearDown(self):
        server.TASKS = self.orig_tasks
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_and_save_tasks(self):
        """Verify loading and saving task list to tasks.json 🦋"""
        self.assertEqual(server.load_tasks(), [])
        sample = [{"id": 1, "task": "Initial task 🦋", "status": "queued"}]
        server.save_tasks(sample)
        loaded = server.load_tasks()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["id"], 1)
        self.assertIn("🦋", loaded[0]["task"])

    def test_brain_status_structure(self):
        """Verify brain_status returns agy and muse_spark lane metadata 🦋"""
        res = server.brain_status()
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn("agy", res)
        self.assertIn("muse_spark", res)
        self.assertTrue(res["agy"]["free"])
        self.assertTrue(res["muse_spark"]["free"])

    def test_lh_status_structure(self):
        """Verify lh_status returns LongHorizon-Harness configuration 🦋"""
        res = server.lh_status()
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn("present", res)
        self.assertIn("agy_lane", res)

    @patch("tools.scout.probe_python", return_value={"status": "UP", "latency_s": 0.01})
    @patch("tools.scout.probe_agy", return_value={"status": "UP", "live": True})
    @patch("tools.scout.probe_opencode", return_value={"status": "UP", "live": True})
    def test_scout_status_helper(self, mock_op, mock_agy, mock_py):
        """Verify scout_status generates structured probe payload 🦋"""
        res = server.scout_status(quick=True)
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn("lanes", res)
        self.assertIn("recommendations", res)

    @patch("tools.guard.audit")
    def test_guard_status_helper(self, mock_audit):
        """Verify guard_status executes guard audit 🦋"""
        mock_audit.return_value = {
            "auditor": "guard",
            "verdict": "PASS",
            "summary": {"files_scanned": 5, "files_passed": 5},
            "mark": WATERMARK,
        }
        res = server.guard_status()
        self.assertEqual(res.get("verdict"), "PASS")
        self.assertEqual(res.get("mark"), WATERMARK)

    def test_memory_status_helper(self):
        """Verify memory_status returns history, stats, and timeline 🦋"""
        res = server.memory_status()
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn("history", res)
        self.assertIn("stats", res)
        self.assertIn("timeline", res)

    def test_loop_status_helper(self):
        """Verify loop_status retrieves state.json and loop.log tail 🦋"""
        res = server.loop_status()
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn("round", res)
        self.assertIn("log_tail", res)

    def test_jarvis_status_helper(self):
        """Verify jarvis_status retrieves live state, vitals, queues and watermark 🦋"""
        res = server.jarvis_status()
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn("jarvis_state", res)
        self.assertIn("sentinel_vitals", res)
        self.assertIn("inbox_items", res)
        self.assertIn("outbox_items", res)

    def test_skills_status_helper(self):
        """Verify skills_status retrieves registered skills and validation 🦋"""
        res = server.skills_status()
        self.assertEqual(res.get("status"), "ok")
        self.assertEqual(res.get("mark"), WATERMARK)
        self.assertIn("skills", res)
        self.assertIn("total", res)
        self.assertIn("validation", res)
        self.assertGreaterEqual(res["total"], 5)


class TestServerHTTPEndpoints(unittest.TestCase):
    """Test live HTTP server endpoints and REST API methods 🦋"""

    @classmethod
    def setUpClass(cls):
        # Create temporary working directory for tests
        cls.temp_dir = tempfile.mkdtemp()
        cls.orig_tasks = server.TASKS
        server.TASKS = os.path.join(cls.temp_dir, "tasks.json")
        server.save_tasks([])

        # Spin up test HTTP server on ephemeral port (port 0)
        class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            allow_reuse_address = True
            daemon_threads = True

        cls.httpd = ThreadingTCPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.base_url = f"http://127.0.0.1:{cls.port}"

        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        server.TASKS = cls.orig_tasks
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _get_json(self, path: str):
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode("utf-8")
            return resp.status, resp.headers, json.loads(data)

    def test_get_api_health(self):
        """Verify GET /api/health returns up status with 🦋 watermark 🦋"""
        status, headers, body = self._get_json("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "up")
        self.assertEqual(body.get("service"), "xola")
        self.assertEqual(body.get("mark"), WATERMARK)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))

    def test_get_api_scout(self):
        """Verify GET /api/scout returns scout telemetry 🦋"""
        status, headers, body = self._get_json("/api/scout?quick=true")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("mark"), WATERMARK)
        self.assertIn("lanes", body)
        self.assertIn("recommendations", body)

    def test_get_api_guard(self):
        """Verify GET /api/guard returns guard audit results 🦋"""
        status, headers, body = self._get_json("/api/guard")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("auditor"), "guard")
        self.assertIn(body.get("verdict"), ("PASS", "WARN", "KILL"))
        self.assertEqual(body.get("mark"), WATERMARK)

    def test_get_api_memory(self):
        """Verify GET /api/memory returns history and analytics 🦋"""
        status, headers, body = self._get_json("/api/memory")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("mark"), WATERMARK)

    def test_get_api_loop(self):
        """Verify GET /api/loop returns autonomous loop state 🦋"""
        status, headers, body = self._get_json("/api/loop")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("mark"), WATERMARK)

    def test_get_api_brains(self):
        """Verify GET /api/brains returns twin brain configuration 🦋"""
        status, headers, body = self._get_json("/api/brains")
        self.assertEqual(status, 200)
        self.assertIn("agy", body)
        self.assertIn("muse_spark", body)
        self.assertEqual(body.get("mark"), WATERMARK)

    def test_get_api_lh(self):
        """Verify GET /api/lh returns LongHorizon harness status 🦋"""
        status, headers, body = self._get_json("/api/lh")
        self.assertEqual(status, 200)
        self.assertIn("workspace", body)
        self.assertEqual(body.get("mark"), WATERMARK)

    def test_tasks_api_lifecycle(self):
        """Verify GET /api/tasks and POST /api/tasks queuing lifecycle 🦋"""
        # 1. Initial tasks list should be empty or list
        status, headers, tasks = self._get_json("/api/tasks")
        self.assertEqual(status, 200)
        self.assertIsInstance(tasks, list)

        # 2. POST a new task
        post_url = f"{self.base_url}/api/tasks"
        payload = json.dumps({"task": "Deploy automated test suite 🦋"}).encode("utf-8")
        req = urllib.request.Request(
            post_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            created_task = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(created_task["task"], "Deploy automated test suite 🦋")
            self.assertEqual(created_task["status"], "queued")
            self.assertIn("created_at", created_task)

        # 3. GET /api/tasks should now contain the created task
        status, headers, updated_tasks = self._get_json("/api/tasks")
        self.assertEqual(len(updated_tasks), 1)
        self.assertEqual(updated_tasks[0]["task"], "Deploy automated test suite 🦋")

    def test_post_tasks_validation_errors(self):
        """Verify POST /api/tasks rejects empty or invalid requests with HTTP 400 🦋"""
        post_url = f"{self.base_url}/api/tasks"

        # Empty task string
        req_empty = urllib.request.Request(
            post_url,
            data=json.dumps({"task": "   "}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req_empty, timeout=5)
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_get_api_jarvis(self):
        """Verify GET /api/jarvis returns live state, queues, and sentinel metrics 🦋"""
        status, headers, body = self._get_json("/api/jarvis")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("mark"), WATERMARK)
        self.assertIn("jarvis_state", body)
        self.assertIn("sentinel_vitals", body)
        self.assertIn("inbox_items", body)
        self.assertIn("outbox_items", body)
        self.assertIn("telemetry_tail", body)

    def test_get_api_skills(self):
        """Verify GET /api/skills returns list of registered skills 🦋"""
        status, headers, body = self._get_json("/api/skills")
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("mark"), WATERMARK)
        self.assertIn("skills", body)
        self.assertIn("total", body)
        self.assertIn("validation", body)
        self.assertGreaterEqual(body["total"], 5)

    def test_post_api_jarvis_send(self):
        """Verify POST /api/jarvis/send queues a task into jarvis/inbox 🦋"""
        post_url = f"{self.base_url}/api/jarvis/send"
        payload = json.dumps({
            "prompt": "sys_info",
            "skill": "sys_info",
            "args": {"drive": "D:"},
            "action": "skill"
        }).encode("utf-8")
        req = urllib.request.Request(
            post_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(data["status"], "SUCCESS")
            self.assertTrue(data["submitted"])
            self.assertEqual(data["prompt"], "sys_info")
            self.assertEqual(data["mark"], WATERMARK)
            self.assertIn("task_id", data)
            self.assertIn("task_file", data)

    def test_post_api_jarvis_send_validation(self):
        """Verify POST /api/jarvis/send rejects empty prompt with HTTP 400 🦋"""
        post_url = f"{self.base_url}/api/jarvis/send"
        req_empty = urllib.request.Request(
            post_url,
            data=json.dumps({"prompt": "   "}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req_empty, timeout=5)
        self.assertEqual(cm.exception.code, 400)
        cm.exception.close()

    def test_options_cors_preflight(self):
        """Verify OPTIONS request returns CORS headers 🦋"""
        url = f"{self.base_url}/api/tasks"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            self.assertIsNone(resp.headers.get("Access-Control-Allow-Origin"))
            self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))

    def test_static_index_html_serving(self):
        """Verify root / serves index.html workbench 🦋"""
        url = f"{self.base_url}/"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 200)
            content = resp.read().decode("utf-8", errors="replace")
            self.assertTrue(len(content) > 100)


if __name__ == "__main__":
    unittest.main()
