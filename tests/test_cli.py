#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_cli.py # Automated tests for unified xola-cli 🦋"""

import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import cli

WATERMARK = "🦋"


class TestCLIParser(unittest.TestCase):
    """Test top-level CLI argument parsing and subcommands 🦋"""

    def setUp(self):
        self.parser = cli.build_parser()

    def test_parser_subcommands_present(self):
        """Verify all required subcommands are defined in parser 🦋"""
        subparser_actions = [
            action for action in self.parser._actions
            if isinstance(action, cli.argparse._SubParsersAction)
        ]
        self.assertEqual(len(subparser_actions), 1)
        subparsers = subparser_actions[0].choices
        expected = ["status", "scout", "build", "builder", "guard", "memory", "skills", "skill", "test", "server", "jarvis"]
        for cmd in expected:
            self.assertIn(cmd, subparsers)

    def test_parse_status_args(self):
        """Verify parsing status arguments 🦋"""
        args = self.parser.parse_args(["status", "--quick", "--json", "-v"])
        self.assertEqual(args.subcommand, "status")
        self.assertTrue(args.quick)
        self.assertTrue(args.json)
        self.assertTrue(args.verbose)

    def test_parse_scout_args(self):
        """Verify parsing scout arguments 🦋"""
        args = self.parser.parse_args(["scout", "--quick", "--model", "custom-model", "--timeout", "12.5", "--json"])
        self.assertEqual(args.subcommand, "scout")
        self.assertTrue(args.quick)
        self.assertEqual(args.model, "custom-model")
        self.assertEqual(args.timeout, 12.5)
        self.assertTrue(args.json)

    def test_parse_build_args(self):
        """Verify parsing build arguments and aliases 🦋"""
        args1 = self.parser.parse_args(["build", "validate", "--no-run-test", "--json"])
        self.assertEqual(args1.subcommand, "build")
        self.assertEqual(args1.action, "validate")
        self.assertTrue(args1.no_run_test)
        self.assertTrue(args1.json)

        args2 = self.parser.parse_args(["builder", "--scaffold", "my_tool", "--template", "auditor"])
        self.assertEqual(args2.subcommand, "builder")
        self.assertEqual(args2.flag_scaffold, "my_tool")
        self.assertEqual(args2.template, "auditor")

    def test_parse_guard_args(self):
        """Verify parsing guard arguments 🦋"""
        args = self.parser.parse_args(["guard", "--target", "tools", "--strict", "--fix", "--smoke", "-v", "--json"])
        self.assertEqual(args.subcommand, "guard")
        self.assertEqual(args.target, "tools")
        self.assertTrue(args.strict)
        self.assertTrue(args.fix)
        self.assertTrue(args.smoke)
        self.assertTrue(args.verbose)
        self.assertTrue(args.json)

    def test_parse_memory_args(self):
        """Verify parsing memory arguments 🦋"""
        args = self.parser.parse_args([
            "memory", "--append", "--round", "5", "--step", "test step",
            "--verdict", "PASS", "--evidence", "outputs ok", "--tags", "t1,t2", "--json"
        ])
        self.assertEqual(args.subcommand, "memory")
        self.assertTrue(args.append)
        self.assertEqual(args.round, 5)
        self.assertEqual(args.step, "test step")
        self.assertEqual(args.verdict, "PASS")
        self.assertEqual(args.tags, "t1,t2")
        self.assertTrue(args.json)

    def test_parse_skills_args(self):
        """Verify parsing skills arguments and aliases 🦋"""
        args1 = self.parser.parse_args(["skills", "--list", "--category", "Diagnostics", "--json"])
        self.assertEqual(args1.subcommand, "skills")
        self.assertTrue(args1.list)
        self.assertEqual(args1.category, "Diagnostics")
        self.assertTrue(args1.json)

        args2 = self.parser.parse_args(["skill", "--run", "sys_info", "--args", '{"drive": "C:"}', "--auto-approve"])
        self.assertEqual(args2.subcommand, "skill")
        self.assertEqual(args2.run, "sys_info")
        self.assertEqual(args2.args, '{"drive": "C:"}')
        self.assertTrue(args2.auto_approve)

    def test_parse_test_args(self):
        """Verify parsing test arguments 🦋"""
        args = self.parser.parse_args(["test", "--suite", "guard", "--failfast", "-q", "--json"])
        self.assertEqual(args.subcommand, "test")
        self.assertEqual(args.suite, "guard")
        self.assertTrue(args.failfast)
        self.assertTrue(args.quiet)
        self.assertTrue(args.json)

    def test_parse_server_args(self):
        """Verify parsing server arguments 🦋"""
        args = self.parser.parse_args(["server", "--port", "9000", "--check", "--timeout", "5.0", "--json"])
        self.assertEqual(args.subcommand, "server")
        self.assertEqual(args.port, 9000)
        self.assertTrue(args.check)
        self.assertEqual(args.timeout, 5.0)
        self.assertTrue(args.json)

    def test_parse_jarvis_args(self):
        """Verify parsing jarvis arguments 🦋"""
        args1 = self.parser.parse_args(["jarvis", "status", "--json"])
        self.assertEqual(args1.subcommand, "jarvis")
        self.assertEqual(args1.action, "status")
        self.assertTrue(args1.json)

        args2 = self.parser.parse_args(["jarvis", "send", "--task", "sys_info", "--args", '{"drive":"D:"}'])
        self.assertEqual(args2.subcommand, "jarvis")
        self.assertEqual(args2.action, "send")
        self.assertEqual(args2.task, "sys_info")
        self.assertEqual(args2.args, '{"drive":"D:"}')

        args3 = self.parser.parse_args(["jarvis", "tick", "--json"])
        self.assertEqual(args3.subcommand, "jarvis")
        self.assertEqual(args3.action, "tick")

        args4 = self.parser.parse_args(["jarvis", "sentinel", "--tail", "10"])
        self.assertEqual(args4.subcommand, "jarvis")
        self.assertEqual(args4.action, "sentinel")
        self.assertEqual(args4.tail, 10)


class TestCLIStatusCommand(unittest.TestCase):
    """Test holistic system status retrieval and reporting 🦋"""

    @patch("tools.scout.probe_python", return_value={"status": "UP", "version": "Python 3.14.0", "latency_s": 0.01})
    @patch("tools.scout.probe_agy", return_value={"status": "UP", "version": "1.0", "latency_s": 0.02})
    @patch("tools.scout.probe_opencode", return_value={"status": "UP", "version": "0.4", "latency_s": 0.03, "live": True})
    @patch("tools.builder.validate_all_tools", return_value={"total": 4, "passed_count": 4, "failed_count": 0, "all_passed": True})
    @patch("tools.guard.audit", return_value={"verdict": "PASS", "summary": {"files_scanned": 10, "total_findings": 0, "critical_count": 0, "warning_count": 0}})
    @patch("tools.memory.compute_stats", return_value={"total_rounds": 10, "verdicts": {"pass_rate_pct": 100.0}, "latency_stats": {"avg_round_duration_s": 2.5}})
    @patch("server.loop_status", return_value={"round": 10, "started": 12345, "notes": ["n1"]})
    @patch("server.load_tasks", return_value=[{"id": 1, "task": "task1", "status": "queued"}])
    @patch("cli.get_jarvis_status", return_value={"status": "HEALTHY", "inbox_queue_count": 0, "outbox_total_count": 5, "tasks_processed_total": 10, "tasks_succeeded": 10, "tasks_failed": 0, "last_task_id": "t1", "last_task_time": "2026-09-03", "sentinel_health": {"status": "HEALTHY", "cpu": {"used_percent": 10.0}, "ram": {"used_percent": 45.0}, "disk": {"max_used_percent": 30.0}}})
    def test_get_system_status_healthy(self, m_jarvis, m_tasks, m_loop, m_mem, m_guard, m_build, m_op, m_agy, m_py):
        """Verify get_system_status returns HEALTHY when all components pass 🦋"""
        status_res = cli.get_system_status(quick=True)
        self.assertEqual(status_res["command"], "status")
        self.assertEqual(status_res["status"], "HEALTHY")
        self.assertEqual(status_res["mark"], WATERMARK)
        self.assertIn("scout", status_res)
        self.assertIn("builder", status_res)
        self.assertIn("guard", status_res)
        self.assertIn("memory", status_res)
        self.assertIn("loop", status_res)
        self.assertIn("tasks", status_res)
        self.assertIn("jarvis", status_res)
        self.assertEqual(status_res["jarvis"]["status"], "HEALTHY")
        self.assertEqual(status_res["tasks"]["total_tasks"], 1)

    @patch("tools.scout.probe_python", return_value={"status": "DOWN", "latency_s": 0.01})
    @patch("tools.scout.probe_agy", return_value={"status": "DOWN", "latency_s": 0.02})
    @patch("tools.scout.probe_opencode", return_value={"status": "DOWN", "latency_s": 0.03})
    @patch("tools.builder.validate_all_tools", return_value={"total": 4, "passed_count": 4, "failed_count": 0, "all_passed": True})
    @patch("tools.guard.audit", return_value={"verdict": "PASS", "summary": {"files_scanned": 10, "total_findings": 0, "critical_count": 0, "warning_count": 0}})
    @patch("tools.memory.compute_stats", return_value={"total_rounds": 0, "verdicts": {"pass_rate_pct": 0.0}, "latency_stats": {"avg_round_duration_s": 0.0}})
    @patch("server.loop_status", return_value={"round": 0, "started": 0, "notes": []})
    @patch("server.load_tasks", return_value=[])
    def test_get_system_status_critical_when_all_lanes_down(self, m_tasks, m_loop, m_mem, m_guard, m_build, m_op, m_agy, m_py):
        """Verify get_system_status marks CRITICAL when all scout lanes are DOWN 🦋"""
        status_res = cli.get_system_status(quick=True)
        self.assertEqual(status_res["status"], "CRITICAL")

    def test_render_status_report_contains_butterfly_and_sections(self):
        """Verify render_status_report produces formatted output with 🦋 watermark 🦋"""
        sample_res = {
            "status": "HEALTHY",
            "timestamp": "2026-09-03T12:00:00",
            "scout": {
                "lanes": {
                    "python": {"status": "UP", "version": "3.14", "latency_s": 0.001},
                    "agy": {"status": "UP", "version": "1.0", "latency_s": 0.02},
                    "opencode": {"status": "UP", "version": "0.4", "latency_s": 0.03},
                },
                "recommendations": {
                    "executor": "agy (gemini-3.8-flash-high)",
                    "manager": "opencode",
                    "auditor": "opencode",
                },
            },
            "builder": {"tools_count": 4, "passed_count": 4, "failed_count": 0, "all_passed": True},
            "guard": {"verdict": "PASS", "files_scanned": 20, "findings_count": 0, "critical_count": 0, "warning_count": 0},
            "memory": {"total_rounds": 5, "pass_rate_pct": 100.0, "avg_latency_s": 1.2},
            "loop": {"round": 5, "started": 12345, "notes_count": 5},
            "tasks": {"total_tasks": 2, "queued_tasks": 1},
            "jarvis": {
                "status": "HEALTHY",
                "inbox_queue_count": 1,
                "outbox_total_count": 2,
                "tasks_processed_total": 5,
                "sentinel": {"status": "HEALTHY", "cpu_pct": 12.0, "ram_pct": 50.0, "disk_pct": 40.0}
            }
        }
        report = cli.render_status_report(sample_res)
        self.assertIn(WATERMARK, report)
        self.assertIn("X.O.L.A. System Status Overview", report)
        self.assertIn("1. Free Execution Lanes (Scout):", report)
        self.assertIn("2. Tooling & Standards (Builder):", report)
        self.assertIn("3. Red-Team Integrity (Guard):", report)
        self.assertIn("4. Memory & Long Horizon (Memory):", report)
        self.assertIn("5. Dynamic Skills Engine (Skills):", report)
        self.assertIn("6. Mission Control & Loop State (Server):", report)
        self.assertIn("7. Jarvis Autonomous Harness & Sentinel:", report)


class TestCLIScoutCommand(unittest.TestCase):
    """Test scout subcommand execution and JSON output 🦋"""

    @patch("tools.scout.probe_python", return_value={"status": "UP", "latency_s": 0.001, "version": "3.14"})
    @patch("tools.scout.probe_opencode", return_value={"status": "UP", "latency_s": 0.01, "version": "0.4", "live": False})
    @patch("tools.scout.probe_agy", return_value={"status": "UP", "latency_s": 0.02, "version": "1.0", "live": False})
    def test_execute_scout_cmd_text_output(self, mock_agy, mock_op, mock_py):
        """Verify scout subcommand renders text report with exit code 0 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_scout_cmd(quick=True, json_mode=False)
            self.assertEqual(code, 0)
            output = fake_out.getvalue()
            self.assertIn(WATERMARK, output)
            self.assertIn("X.O.L.A. Scout", output)

    @patch("tools.scout.probe_python", return_value={"status": "UP", "latency_s": 0.001, "version": "3.14"})
    @patch("tools.scout.probe_opencode", return_value={"status": "UP", "latency_s": 0.01, "version": "0.4", "live": False})
    @patch("tools.scout.probe_agy", return_value={"status": "UP", "latency_s": 0.02, "version": "1.0", "live": False})
    def test_execute_scout_cmd_json_output(self, mock_agy, mock_op, mock_py):
        """Verify scout subcommand outputs valid JSON with 🦋 watermark 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_scout_cmd(quick=True, json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["command"], "scout")
            self.assertEqual(data["mark"], WATERMARK)
            self.assertIn("lanes", data)
            self.assertIn("recommendations", data)

    @patch("tools.scout.probe_python", return_value={"status": "DOWN"})
    @patch("tools.scout.probe_opencode", return_value={"status": "DOWN"})
    @patch("tools.scout.probe_agy", return_value={"status": "DOWN"})
    def test_execute_scout_cmd_all_down_exit_1(self, mock_agy, mock_op, mock_py):
        """Verify scout subcommand returns exit code 1 when all lanes are DOWN 🦋"""
        with patch("sys.stdout", new=io.StringIO()):
            code = cli.execute_scout_cmd(quick=True, json_mode=False)
            self.assertEqual(code, 1)


class TestCLIBuildCommand(unittest.TestCase):
    """Test build / builder subcommand operations 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_build_scaffold_action(self):
        """Verify build scaffold creates a compliant tool in target directory 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_build_cmd(
                action="scaffold",
                scaffold_name="test_worker",
                desc="test utility tool",
                template="tool",
                tools_dir=self.temp_dir,
                json_mode=True,
            )
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "SUCCESS")
            self.assertEqual(data["mark"], WATERMARK)
            self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "test_worker.py")))

    def test_build_validate_action_success(self):
        """Verify build validate succeeds on valid tools 🦋"""
        # Scaffold a valid tool first
        with patch("sys.stdout", new=io.StringIO()):
            cli.execute_build_cmd(
                action="scaffold",
                scaffold_name="test_val_tool",
                tools_dir=self.temp_dir,
                json_mode=True,
            )

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_build_cmd(
                action="validate",
                target=None,
                no_run_test=True,
                tools_dir=self.temp_dir,
                json_mode=False,
            )
            self.assertEqual(code, 0)
            output = fake_out.getvalue()
            self.assertIn(WATERMARK, output)
            self.assertIn("ALL STANDARDS PASSED", output)

    def test_build_inspect_action(self):
        """Verify build inspect outputs tool details 🦋"""
        with patch("sys.stdout", new=io.StringIO()):
            cli.execute_build_cmd(
                action="scaffold",
                scaffold_name="test_inspect_tool",
                tools_dir=self.temp_dir,
                json_mode=True,
            )
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_build_cmd(
                action="inspect",
                target="test_inspect_tool",
                tools_dir=self.temp_dir,
                json_mode=True,
            )
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["mark"], WATERMARK)
            self.assertTrue(data.get("single"))


class TestCLIGuardCommand(unittest.TestCase):
    """Test guard subcommand and strict mode 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_guard_pass_clean_file(self):
        """Verify guard passes on clean file with 🦋 watermark 🦋"""
        clean_file = os.path.join(self.temp_dir, "clean.py")
        with open(clean_file, "w", encoding="utf-8") as f:
            f.write('"""Clean file 🦋"""\nimport os\n\ndef run():\n    pass\n')

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_guard_cmd(target=clean_file, strict=False, json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["verdict"], "PASS")
            self.assertEqual(data["mark"], WATERMARK)

    def test_guard_strict_kill_on_watermark_missing(self):
        """Verify guard returns code 1 under --strict when watermark is missing 🦋"""
        slop_file = os.path.join(self.temp_dir, "slop.py")
        with open(slop_file, "w", encoding="utf-8") as f:
            f.write('"""Missing watermark docstring"""\nimport os\n')

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_guard_cmd(target=slop_file, strict=True, json_mode=True)
            self.assertEqual(code, 1)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["verdict"], "KILL")


class TestCLIMemoryCommand(unittest.TestCase):
    """Test memory subcommand actions: append, distill, query, timeline, stats 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mem_dir = os.path.join(self.temp_dir, "memory")
        self.loop_dir = os.path.join(self.temp_dir, "loop")
        os.makedirs(self.mem_dir, exist_ok=True)
        os.makedirs(self.loop_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_memory_append_and_stats(self):
        """Verify appending round and computing stats 🦋"""
        # Append round
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code_app = cli.execute_memory_cmd(
                append=True,
                round_idx=1,
                step="Execute CLI integration",
                evidence="Tests all passed",
                verdict="PASS",
                lessons="Stdlib keeps it lean",
                tags="cli,unified",
                memory_dir=self.mem_dir,
                loop_dir=self.loop_dir,
                json_mode=True,
            )
            self.assertEqual(code_app, 0)
            data_app = json.loads(fake_out.getvalue())
            self.assertEqual(data_app["status"], "SUCCESS")
            self.assertEqual(data_app["round"], 1)
            self.assertEqual(data_app["mark"], WATERMARK)

        # Compute stats
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code_stats = cli.execute_memory_cmd(
                stats=True,
                memory_dir=self.mem_dir,
                loop_dir=self.loop_dir,
                json_mode=True,
            )
            self.assertEqual(code_stats, 0)
            data_stats = json.loads(fake_out.getvalue())
            self.assertEqual(data_stats["total_rounds"], 1)
            self.assertEqual(data_stats["verdicts"]["pass"], 1)

    def test_memory_query_and_timeline(self):
        """Verify querying memory and generating timeline 🦋"""
        # Seed memory
        with patch("sys.stdout", new=io.StringIO()):
            cli.execute_memory_cmd(
                append=True,
                round_idx=2,
                step="Scout prober optimization",
                verdict="PASS",
                memory_dir=self.mem_dir,
                loop_dir=self.loop_dir,
                json_mode=True,
            )

        # Query
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code_q = cli.execute_memory_cmd(
                query="optimization",
                memory_dir=self.mem_dir,
                loop_dir=self.loop_dir,
                json_mode=True,
            )
            self.assertEqual(code_q, 0)
            data_q = json.loads(fake_out.getvalue())
            self.assertEqual(data_q["total_matches"], 1)
            self.assertEqual(data_q["matches"][0]["round"], 2)

        # Timeline
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code_tl = cli.execute_memory_cmd(
                timeline=True,
                memory_dir=self.mem_dir,
                loop_dir=self.loop_dir,
                json_mode=True,
            )
            self.assertEqual(code_tl, 0)
            data_tl = json.loads(fake_out.getvalue())
            self.assertEqual(data_tl["total_rounds"], 1)


class TestCLISkillsCommand(unittest.TestCase):
    """Test skills subcommand actions (list, info, run, validate) 🦋"""

    def test_execute_skills_cmd_list_json(self):
        """Verify execute_skills_cmd outputs list of skills in JSON mode 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_skills_cmd(action="list", json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["command"], "skills")
            self.assertEqual(data["action"], "list")
            self.assertGreaterEqual(data["total"], 5)
            self.assertEqual(data["mark"], WATERMARK)

    def test_execute_skills_cmd_info_action(self):
        """Verify execute_skills_cmd displays info for specific skill 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_skills_cmd(action="info", name="sys_info", json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["name"], "sys_info")
            self.assertEqual(data["tier"], "GREEN")
            self.assertEqual(data["mark"], WATERMARK)

    def test_execute_skills_cmd_run_action(self):
        """Verify execute_skills_cmd executes target skill with arguments 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_skills_cmd(
                action="run",
                name="text_format",
                args_json='{"text": "xola skills cli", "action": "slugify"}',
                json_mode=True,
            )
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "SUCCESS")
            self.assertEqual(data["output"]["output"], "xola-skills-cli")

    def test_execute_skills_cmd_validate_action(self):
        """Verify execute_skills_cmd validates registry integrity 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_skills_cmd(validate=True, json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertTrue(data["all_passed"])
            self.assertGreaterEqual(data["total"], 5)


class TestCLITestCommand(unittest.TestCase):
    """Test test runner subcommand and JSON reporting 🦋"""

    def test_get_available_test_modules(self):
        """Verify get_available_test_modules loads test suites 🦋"""
        mods = cli.get_available_test_modules()
        names = [n for n, _ in mods]
        self.assertIn("xola-scout", names)
        self.assertIn("xola-builder", names)
        self.assertIn("xola-guard", names)
        self.assertIn("xola-memory", names)
        self.assertIn("xola-skills", names)
        self.assertIn("xola-server", names)
        self.assertIn("xola-jarvis", names)

    def test_execute_test_cmd_single_suite(self):
        """Verify running a single suite (e.g. scout) 🦋"""
        with patch("sys.stdout", new=io.StringIO()):
            code = cli.execute_test_cmd(suite_name="scout", quiet=True, json_mode=False)
            self.assertEqual(code, 0)

    def test_execute_test_cmd_json_mode(self):
        """Verify test command outputs structured JSON results with 🦋 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_test_cmd(suite_name="scout", quiet=True, json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["command"], "test")
            self.assertEqual(data["status"], "PASS")
            self.assertEqual(data["mark"], WATERMARK)
            self.assertIn("summary", data)
            self.assertIn("suites", data)
            self.assertGreater(data["summary"]["total_tests"], 0)

    def test_execute_test_cmd_invalid_suite_error(self):
        """Verify test command returns code 1 for non-existent suite 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_test_cmd(suite_name="nonexistent_xyz", json_mode=True)
            self.assertEqual(code, 1)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "ERROR")


class TestCLIServerCommand(unittest.TestCase):
    """Test server subcommand check mode and health verification 🦋"""

    @patch("urllib.request.urlopen")
    def test_server_check_up(self, mock_urlopen):
        """Verify server check reports UP when HTTP health returns 200 🦋"""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"status": "up", "service": "xola", "mark": WATERMARK}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_server_cmd(port=8101, check=True, json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "UP")
            self.assertEqual(data["mark"], WATERMARK)

    @patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused"))
    def test_server_check_down(self, mock_urlopen):
        """Verify server check reports DOWN and returns 1 on connection failure 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_server_cmd(port=8101, check=True, json_mode=True)
            self.assertEqual(code, 1)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "DOWN")
            self.assertIn("Connection refused", data["error"])
            self.assertEqual(data["mark"], WATERMARK)


class TestCLIJarvisCommand(unittest.TestCase):
    """Test jarvis subcommand: status, send, tick, sentinel, smoke 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_jarvis_status_text_and_json(self):
        """Verify jarvis status returns health state in text and JSON mode 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_jarvis_cmd(action="status", json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["command"], "jarvis")
            self.assertEqual(data["action"], "status")
            self.assertEqual(data["mark"], WATERMARK)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_jarvis_cmd(action="status", json_mode=False)
            self.assertEqual(code, 0)
            output = fake_out.getvalue()
            self.assertIn(WATERMARK, output)
            self.assertIn("Jarvis Autonomous Harness Status", output)

    def test_execute_jarvis_send_task(self):
        """Verify jarvis send drops a new task into inbox 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_jarvis_cmd(action="send", task="sys_info", args_json='{"drive":"D:"}', json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["status"], "SUCCESS")
            self.assertTrue(data["submitted"])
            self.assertEqual(data["prompt"], "sys_info")
            self.assertEqual(data["mark"], WATERMARK)

    def test_execute_jarvis_tick(self):
        """Verify jarvis tick processes inbox tasks 🦋"""
        # Drop a task first
        with patch("sys.stdout", new=io.StringIO()):
            cli.execute_jarvis_cmd(action="send", task="sys_info", json_mode=True)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_jarvis_cmd(action="tick", json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["command"], "jarvis")
            self.assertEqual(data["action"], "tick")
            self.assertEqual(data["mark"], WATERMARK)
            self.assertGreaterEqual(data["processed_count"], 1)

    def test_execute_jarvis_sentinel(self):
        """Verify jarvis sentinel returns diagnostic vitals 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_jarvis_cmd(action="sentinel", json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["action"], "sentinel")
            self.assertEqual(data["mark"], WATERMARK)
            self.assertIn("health", data)

    def test_execute_jarvis_smoke(self):
        """Verify jarvis smoke test runs end-to-end 🦋"""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = cli.execute_jarvis_cmd(smoke=True, json_mode=True)
            self.assertEqual(code, 0)
            data = json.loads(fake_out.getvalue())
            self.assertEqual(data["smoke_test"], "PASSED")
            self.assertEqual(data["mark"], WATERMARK)


class TestCLIMainRouter(unittest.TestCase):
    """Test top-level cli.main() router and error handling 🦋"""

    @patch("cli.get_system_status", return_value={"status": "HEALTHY", "mark": WATERMARK})
    def test_main_default_to_status(self, mock_status):
        """Verify main() defaults to status overview when no subcommand is given 🦋"""
        with patch.object(sys, "argv", ["cli.py", "--json"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    cli.main()
                self.assertEqual(cm.exception.code, 0)
                data = json.loads(fake_out.getvalue())
                self.assertEqual(data["status"], "HEALTHY")

    @patch("cli.execute_scout_cmd", return_value=0)
    def test_main_dispatch_scout(self, mock_scout):
        """Verify main() dispatches to scout subcommand 🦋"""
        with patch.object(sys, "argv", ["cli.py", "scout", "--quick"]):
            with self.assertRaises(SystemExit) as cm:
                cli.main()
            self.assertEqual(cm.exception.code, 0)
            mock_scout.assert_called_once()

    @patch("cli.execute_jarvis_cmd", return_value=0)
    def test_main_dispatch_jarvis(self, mock_jarvis):
        """Verify main() dispatches to jarvis subcommand 🦋"""
        with patch.object(sys, "argv", ["cli.py", "jarvis", "status", "--json"]):
            with self.assertRaises(SystemExit) as cm:
                cli.main()
            self.assertEqual(cm.exception.code, 0)
            mock_jarvis.assert_called_once()

    @patch("cli.execute_guard_cmd", side_effect=KeyboardInterrupt)
    def test_main_keyboard_interrupt_handling(self, mock_guard):
        """Verify main() catches KeyboardInterrupt and exits cleanly with 130 🦋"""
        with patch.object(sys, "argv", ["cli.py", "guard"]):
            with patch("sys.stderr", new=io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    cli.main()
                self.assertEqual(cm.exception.code, 130)

    @patch("cli.execute_memory_cmd", side_effect=RuntimeError("Disk failure"))
    def test_main_exception_graceful_handling(self, mock_mem):
        """Verify main() catches unhandled exceptions and outputs JSON/error banner without crashing 🦋"""
        with patch.object(sys, "argv", ["cli.py", "memory", "--json"]):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    cli.main()
                self.assertEqual(cm.exception.code, 1)
                data = json.loads(fake_out.getvalue())
                self.assertEqual(data["status"], "ERROR")
                self.assertIn("Disk failure", data["error"])
                self.assertEqual(data["mark"], WATERMARK)


if __name__ == "__main__":
    unittest.main()
