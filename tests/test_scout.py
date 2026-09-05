#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_scout.py # Automated tests for xola-scout 🦋"""

import io
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tools.scout as scout

WATERMARK = "🦋"


class TestScoutExecutableResolution(unittest.TestCase):
    """Test executable and binary resolution mechanisms 🦋"""

    @patch("shutil.which")
    @patch("os.path.exists")
    def test_find_executable_shutil_success(self, mock_exists, mock_which):
        """Verify find_executable returns path when found in PATH 🦋"""
        mock_which.return_value = r"C:\Windows\System32\python.exe"
        mock_exists.return_value = True

        result = scout.find_executable("python")
        self.assertEqual(result, r"C:\Windows\System32\python.exe")
        mock_which.assert_called_once_with("python")

    @patch("shutil.which", return_value=None)
    @patch("os.path.exists")
    def test_find_executable_fallback_success(self, mock_exists, mock_which):
        """Verify find_executable falls back to known fallback paths 🦋"""
        def exists_side_effect(path):
            return "agy_real.exe" in path

        mock_exists.side_effect = exists_side_effect
        result = scout.find_executable("agy")
        self.assertIsNotNone(result)
        self.assertTrue("agy_real.exe" in result)

    @patch("shutil.which", return_value=None)
    @patch("os.path.exists", return_value=False)
    def test_find_executable_not_found(self, mock_exists, mock_which):
        """Verify find_executable returns None when not in PATH or fallbacks 🦋"""
        result = scout.find_executable("nonexistent_binary_xyz")
        self.assertIsNone(result)


class TestScoutRunCommand(unittest.TestCase):
    """Test safe command runner with timeouts and error handling 🦋"""

    @patch("subprocess.run")
    def test_run_cmd_success(self, mock_run):
        """Verify run_cmd returns ok=True and captured output 🦋"""
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "hello world\n"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc

        ok, out, err, lat = scout.run_cmd(["echo", "hello"], timeout=5)
        self.assertTrue(ok)
        self.assertEqual(out, "hello world")
        self.assertEqual(err, "")
        self.assertGreaterEqual(lat, 0.0)

    @patch("subprocess.run")
    def test_run_cmd_failure_code(self, mock_run):
        """Verify run_cmd returns ok=False on non-zero exit 🦋"""
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = ""
        mock_proc.stderr = "command failed"
        mock_run.return_value = mock_proc

        ok, out, err, lat = scout.run_cmd(["false"], timeout=5)
        self.assertFalse(ok)
        self.assertEqual(err, "command failed")

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=["test"], timeout=1.0))
    def test_run_cmd_timeout(self, mock_run):
        """Verify run_cmd handles subprocess.TimeoutExpired gracefully 🦋"""
        ok, out, err, lat = scout.run_cmd(["sleep", "10"], timeout=1.0)
        self.assertFalse(ok)
        self.assertEqual(out, "")
        self.assertEqual(err, "TIMEOUT")

    @patch("subprocess.run", side_effect=OSError("File not found"))
    def test_run_cmd_os_error(self, mock_run):
        """Verify run_cmd handles OS launch errors cleanly 🦋"""
        ok, out, err, lat = scout.run_cmd(["invalid_cmd"], timeout=1.0)
        self.assertFalse(ok)
        self.assertTrue(err.startswith("LAUNCH-FAIL:"))


class TestScoutPythonProbing(unittest.TestCase):
    """Test Python runtime probing and performance metrics 🦋"""

    def test_probe_python_live(self):
        """Verify live Python probe returns UP on current working interpreter 🦋"""
        res = scout.probe_python()
        self.assertEqual(res.get("lane"), "python")
        self.assertIn(res.get("status"), ("UP", "DEGRADED"))
        self.assertTrue(os.path.exists(res.get("path")))
        self.assertTrue(res.get("version").startswith("Python 3."))
        self.assertIsInstance(res.get("latency_s"), float)

    @patch("sys.executable", None)
    @patch("tools.scout.find_executable", return_value=None)
    def test_probe_python_not_found(self, mock_find):
        """Verify Python probe reports DOWN if executable cannot be resolved 🦋"""
        res = scout.probe_python()
        self.assertEqual(res.get("status"), "DOWN")
        self.assertEqual(res.get("path"), "NOT_FOUND")


class TestScoutAgyProbing(unittest.TestCase):
    """Test AGY CLI probing in quick and full LLM response modes 🦋"""

    @patch("tools.scout.find_executable", return_value=None)
    def test_probe_agy_not_found(self, mock_find):
        """Verify AGY probe reports DOWN when agy binary is missing 🦋"""
        res = scout.probe_agy()
        self.assertEqual(res.get("lane"), "agy")
        self.assertEqual(res.get("status"), "DOWN")
        self.assertEqual(res.get("path"), "NOT_FOUND")

    @patch("tools.scout.find_executable", return_value=r"C:\agy\agy.cmd")
    @patch("tools.scout.run_cmd")
    def test_probe_agy_version_fail(self, mock_run, mock_find):
        """Verify AGY probe reports DOWN when --version fails 🦋"""
        mock_run.return_value = (False, "", "Execution error", 0.05)
        res = scout.probe_agy()
        self.assertEqual(res.get("status"), "DOWN")
        self.assertEqual(res.get("version"), "error")

    @patch("tools.scout.find_executable", return_value=r"C:\agy\agy.cmd")
    @patch("tools.scout.run_cmd")
    def test_probe_agy_quick_success(self, mock_run, mock_find):
        """Verify AGY quick probe succeeds without invoking active LLM call 🦋"""
        mock_run.return_value = (True, "agy 1.2.3", "", 0.02)
        res = scout.probe_agy(quick=True)
        self.assertEqual(res.get("status"), "UP")
        self.assertEqual(res.get("version"), "agy 1.2.3")
        self.assertFalse(res.get("live"))
        self.assertEqual(mock_run.call_count, 1)

    @patch("tools.scout.find_executable", return_value=r"C:\agy\agy.cmd")
    @patch("tools.scout.run_cmd")
    def test_probe_agy_full_llm_success(self, mock_run, mock_find):
        """Verify AGY full probe succeeds when LLM responds with 'up' 🦋"""
        json_output = json.dumps({
            "status": "SUCCESS",
            "duration_seconds": 1.45,
            "response": "up",
        })
        mock_run.side_effect = [
            (True, "agy 1.2.3", "", 0.02),
            (True, json_output, "", 1.45),
        ]
        res = scout.probe_agy(quick=False)
        self.assertEqual(res.get("status"), "UP")
        self.assertTrue(res.get("live"))
        self.assertIn("response: 'up'", res.get("details"))

    @patch("tools.scout.find_executable", return_value=r"C:\agy\agy.cmd")
    @patch("tools.scout.run_cmd")
    def test_probe_agy_full_llm_degraded_response(self, mock_run, mock_find):
        """Verify AGY full probe marks DEGRADED when LLM returns error status or wrong response 🦋"""
        json_output = json.dumps({
            "status": "RATE_LIMITED",
            "response": "quota exceeded",
        })
        mock_run.side_effect = [
            (True, "agy 1.2.3", "", 0.02),
            (True, json_output, "", 0.5),
        ]
        res = scout.probe_agy(quick=False)
        self.assertEqual(res.get("status"), "DEGRADED")
        self.assertFalse(res.get("live"))


class TestScoutOpenCodeProbing(unittest.TestCase):
    """Test OpenCode CLI probing and live server PONG verification 🦋"""

    @patch("tools.scout.find_executable", return_value=None)
    def test_probe_opencode_not_found(self, mock_find):
        """Verify OpenCode probe reports DOWN when binary is not found 🦋"""
        res = scout.probe_opencode()
        self.assertEqual(res.get("lane"), "opencode")
        self.assertEqual(res.get("status"), "DOWN")
        self.assertFalse(res.get("live"))

    @patch("tools.scout.find_executable", return_value=r"C:\npm\opencode.cmd")
    @patch("tools.scout.run_cmd")
    def test_probe_opencode_quick(self, mock_run, mock_find):
        """Verify OpenCode quick probe returns UP on valid CLI version 🦋"""
        mock_run.return_value = (True, "opencode 0.4.1", "", 0.03)
        res = scout.probe_opencode(quick=True)
        self.assertEqual(res.get("status"), "UP")
        self.assertEqual(res.get("version"), "opencode 0.4.1")
        self.assertFalse(res.get("live"))

    @patch("tools.scout.find_executable", return_value=r"C:\npm\opencode.cmd")
    @patch("tools.scout.run_cmd")
    def test_probe_opencode_live_pong_success(self, mock_run, mock_find):
        """Verify OpenCode full probe succeeds when live server responds with PONG 🦋"""
        mock_run.side_effect = [
            (True, "opencode 0.4.1", "", 0.03),
            (True, '{"response": "PONG"}', "", 1.12),
        ]
        res = scout.probe_opencode(quick=False)
        self.assertEqual(res.get("status"), "UP")
        self.assertTrue(res.get("live"))
        self.assertIn("answered PONG", res.get("details"))

    @patch("tools.scout.find_executable", return_value=r"C:\npm\opencode.cmd")
    @patch("tools.scout.run_cmd")
    def test_probe_opencode_live_server_error_json(self, mock_run, mock_find):
        """Verify OpenCode full probe catches server error payload and marks DOWN 🦋"""
        mock_run.side_effect = [
            (True, "opencode 0.4.1", "", 0.03),
            (False, '{"type": "error", "error": "server connection refused"}', "", 0.15),
        ]
        res = scout.probe_opencode(quick=False)
        self.assertEqual(res.get("status"), "DOWN")
        self.assertFalse(res.get("live"))
        self.assertIn("SERVER FAILING", res.get("details"))


class TestScoutTopologyRecommendations(unittest.TestCase):
    """Test execution topology assignment based on probed lane health 🦋"""

    def test_recommend_agy_healthy_and_opencode_live(self):
        """Verify ideal topology: agy executor, opencode manager/auditor 🦋"""
        lanes = {
            "python": {"status": "UP"},
            "agy": {"status": "UP", "live": True},
            "opencode": {"status": "UP", "live": True},
        }
        recs = scout.recommend_execution_plan(lanes)
        self.assertIn("agy (gemini-3.8-flash-high)", recs["executor"])
        self.assertIn("opencode", recs["manager"])
        self.assertIn("opencode", recs["auditor"])

    def test_recommend_agy_up_but_opencode_down(self):
        """Verify fallback when OpenCode is down: agy takes executor, manager, and auditor 🦋"""
        lanes = {
            "python": {"status": "UP"},
            "agy": {"status": "UP", "live": True},
            "opencode": {"status": "DOWN", "live": False},
        }
        recs = scout.recommend_execution_plan(lanes)
        self.assertIn("agy (gemini-3.8-flash-high)", recs["executor"])
        self.assertIn("agy (gemini-3.8-flash-high)", recs["manager"])
        self.assertIn("agy (gemini-3.8-flash-high)", recs["auditor"])

    def test_recommend_agy_degraded(self):
        """Verify agy degraded fallback assignment 🦋"""
        lanes = {
            "python": {"status": "UP"},
            "agy": {"status": "DEGRADED", "live": False},
            "opencode": {"status": "UP", "live": True},
        }
        recs = scout.recommend_execution_plan(lanes)
        self.assertIn("DEGRADED FALLBACK", recs["executor"])
        self.assertIn("opencode", recs["manager"])
        self.assertIn("opencode", recs["auditor"])

    def test_recommend_all_down(self):
        """Verify topology assignment when all lanes are down 🦋"""
        lanes = {
            "python": {"status": "DOWN"},
            "agy": {"status": "DOWN", "live": False},
            "opencode": {"status": "DOWN", "live": False},
        }
        recs = scout.recommend_execution_plan(lanes)
        self.assertIn("NONE", recs["executor"])
        self.assertIn("NONE", recs["manager"])
        self.assertIn("NONE", recs["auditor"])


class TestScoutReportingAndCLI(unittest.TestCase):
    """Test report rendering and CLI entrypoint flags 🦋"""

    def test_render_report_contains_watermarks_and_sections(self):
        """Verify report string contains 🦋 watermarks, lane statuses, and topology 🦋"""
        lanes = {
            "python": {"status": "UP", "version": "Python 3.14.0", "latency_s": 0.01, "details": "ok"},
            "agy": {"status": "UP", "version": "1.0", "latency_s": 0.5, "details": "ok"},
            "opencode": {"status": "UP", "version": "0.4", "latency_s": 0.8, "details": "ok"},
        }
        recs = {
            "executor": "agy (gemini-3.8-flash-high)",
            "manager": "opencode",
            "auditor": "opencode",
        }
        report = scout.render_report(lanes, recs, quick=True)
        self.assertIn("🦋", report)
        self.assertIn("X.O.L.A. Scout", report)
        self.assertIn("Recommended Execution Topology:", report)
        self.assertIn("Executor : agy", report)

    @patch("tools.scout.probe_python", return_value={"status": "UP", "latency_s": 0.01, "version": "3.14", "details": "ok"})
    @patch("tools.scout.probe_opencode", return_value={"status": "UP", "latency_s": 0.02, "version": "0.4", "details": "ok", "live": False})
    @patch("tools.scout.probe_agy", return_value={"status": "UP", "latency_s": 0.03, "version": "1.0", "details": "ok", "live": False})
    def test_main_json_flag(self, mock_agy, mock_op, mock_py):
        """Verify main() with --json outputs valid JSON payload with 🦋 mark 🦋"""
        test_args = ["scout.py", "--quick", "--json"]
        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    scout.main()
                self.assertEqual(cm.exception.code, 0)
                output_str = fake_out.getvalue()
                data = json.loads(output_str)
                self.assertIn("lanes", data)
                self.assertIn("recommendations", data)
                self.assertEqual(data.get("mark"), "🦋")


if __name__ == "__main__":
    unittest.main()
