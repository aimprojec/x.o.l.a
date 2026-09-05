#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_skills.py # Automated unit test suite for dynamic Skills Registry 🦋"""

import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tools.skills as skills
from tools.skills import (
    GLOBAL_REGISTRY,
    Skill,
    SkillRegistry,
    Tier,
    register_skill,
    skill_code_ast_metrics,
    skill_file_patch,
    skill_http_probe,
    skill_sys_info,
    skill_text_format,
)

WATERMARK = "🦋"


class TestSkillDataclassAndTier(unittest.TestCase):
    """Test Skill dataclass initialization, matching semantics, and Tier enum 🦋."""

    def test_tier_enum_values(self):
        """Verify Tier enum defines GREEN, YELLOW, RED with proper string representation 🦋."""
        self.assertEqual(Tier.GREEN.value, "GREEN")
        self.assertEqual(Tier.YELLOW.value, "YELLOW")
        self.assertEqual(Tier.RED.value, "RED")
        self.assertEqual(str(Tier.GREEN), "GREEN")
        self.assertEqual(str(Tier.YELLOW), "YELLOW")
        self.assertEqual(str(Tier.RED), "RED")

    def test_skill_creation_and_defaults(self):
        """Verify Skill dataclass defaults and post-init tier normalization 🦋."""
        s = Skill(name="my_tool", description="A test tool")
        self.assertEqual(s.name, "my_tool")
        self.assertEqual(s.tier, Tier.GREEN)
        self.assertEqual(s.keywords, [])
        self.assertEqual(s.category, "General")
        self.assertFalse(s.prefix_match)
        self.assertEqual(s.mark, WATERMARK)

        # String tier conversion
        s2 = Skill(name="tool2", tier="YELLOW")
        self.assertEqual(s2.tier, Tier.YELLOW)
        s3 = Skill(name="tool3", tier="invalid_tier")
        self.assertEqual(s3.tier, Tier.GREEN)

    def test_skill_keyword_matching(self):
        """Verify Skill.matches handles keywords, casing, and direct name match 🦋."""
        s = Skill(
            name="system_specs",
            tier=Tier.GREEN,
            keywords=["specs", "diagnostics", "hardware info"],
            prefix_match=False,
        )
        self.assertTrue(s.matches("system_specs"))
        self.assertTrue(s.matches("System_Specs"))
        self.assertTrue(s.matches("please show system specs"))
        self.assertTrue(s.matches("run diagnostics now"))
        self.assertTrue(s.matches("HARDWARE INFO please"))
        self.assertFalse(s.matches("unrelated query"))
        self.assertFalse(s.matches(""))

    def test_skill_prefix_matching(self):
        """Verify Skill.matches with prefix_match=True checks prefixes only 🦋."""
        s = Skill(
            name="calc",
            tier=Tier.GREEN,
            keywords=["calc", "calculate", "math"],
            prefix_match=True,
        )
        self.assertTrue(s.matches("calc 2 + 2"))
        self.assertTrue(s.matches("calculate sum"))
        self.assertTrue(s.matches("math sqrt(16)"))
        # Substring in middle should not match prefix
        self.assertFalse(s.matches("do some calc now"))
        self.assertFalse(s.matches("advance math please"))

    def test_skill_to_dict_serialization(self):
        """Verify Skill.to_dict generates complete metadata payload with 🦋 mark 🦋."""
        def dummy_handler(x: int) -> int:
            return x * 2

        s = Skill(
            name="doubler",
            tier=Tier.YELLOW,
            keywords=["double", "multiply"],
            description="Doubles an integer",
            handler=dummy_handler,
            category="Math",
            prefix_match=True,
            args_schema={"x": "Integer to double"},
        )
        d = s.to_dict()
        self.assertEqual(d["name"], "doubler")
        self.assertEqual(d["tier"], "YELLOW")
        self.assertEqual(d["keywords"], ["double", "multiply"])
        self.assertEqual(d["description"], "Doubles an integer")
        self.assertEqual(d["category"], "Math")
        self.assertTrue(d["prefix_match"])
        self.assertTrue(d["has_handler"])
        self.assertEqual(d["args_schema"], {"x": "Integer to double"})
        self.assertEqual(d["mark"], WATERMARK)


class TestSkillRegistryCore(unittest.TestCase):
    """Test SkillRegistry registration, retrieval, matching priority, and filtering 🦋."""

    def setUp(self):
        self.registry = SkillRegistry(name="test_reg")

    def test_register_and_get(self):
        """Verify registering and retrieving skills in registry 🦋."""
        s = Skill(name="echo", handler=lambda text="": text)
        self.registry.register(s)
        self.assertEqual(len(self.registry), 1)
        self.assertIn("echo", self.registry)
        self.assertEqual(self.registry.get("echo"), s)
        self.assertIsNone(self.registry.get("nonexistent"))

    def test_register_invalid_types(self):
        """Verify registering invalid objects raises TypeError or ValueError 🦋."""
        with self.assertRaises(TypeError):
            self.registry.register("not_a_skill")  # type: ignore
        with self.assertRaises(ValueError):
            self.registry.register(Skill(name=""))

    def test_unregister(self):
        """Verify unregistering a skill from registry 🦋."""
        s = Skill(name="temp_skill")
        self.registry.register(s)
        self.assertTrue(self.registry.unregister("temp_skill"))
        self.assertFalse(self.registry.unregister("temp_skill"))
        self.assertEqual(len(self.registry), 0)

    def test_list_skills_with_filters(self):
        """Verify list_skills filters properly by category and tier 🦋."""
        s1 = Skill(name="s1", tier=Tier.GREEN, category="CatA")
        s2 = Skill(name="s2", tier=Tier.YELLOW, category="CatA")
        s3 = Skill(name="s3", tier=Tier.RED, category="CatB")
        self.registry.register(s1)
        self.registry.register(s2)
        self.registry.register(s3)

        all_skills = self.registry.list_skills()
        self.assertEqual(len(all_skills), 3)

        cat_a = self.registry.list_skills(category="CatA")
        self.assertEqual(len(cat_a), 2)
        self.assertEqual({s.name for s in cat_a}, {"s1", "s2"})

        red_skills = self.registry.list_skills(tier=Tier.RED)
        self.assertEqual(len(red_skills), 1)
        self.assertEqual(red_skills[0].name, "s3")

        yellow_by_str = self.registry.list_skills(tier="YELLOW")
        self.assertEqual(len(yellow_by_str), 1)
        self.assertEqual(yellow_by_str[0].name, "s2")

    def test_matching_priority_exact_then_prefix_then_keyword(self):
        """Verify matching priority: exact name > prefix match > keyword substring 🦋."""
        s_keyword = Skill(name="general_notes", keywords=["note", "write"], prefix_match=False)
        s_prefix = Skill(name="note_creator", keywords=["note"], prefix_match=True)
        s_exact = Skill(name="note", keywords=["something_else"])

        self.registry.register(s_keyword)
        self.registry.register(s_prefix)
        self.registry.register(s_exact)

        # 1. Exact match "note" -> s_exact
        self.assertEqual(self.registry.find_matching_skill("note"), s_exact)

        # 2. Prefix query "note please save this" -> s_prefix
        self.assertEqual(self.registry.find_matching_skill("note please save this"), s_prefix)

        # 3. Substring query "I want to write something" -> s_keyword
        self.assertEqual(self.registry.find_matching_skill("I want to write something"), s_keyword)

        # 4. No match
        self.assertIsNone(self.registry.find_matching_skill("completely unknown query"))

    def test_find_all_matching_skills(self):
        """Verify find_all_matching_skills returns all applicable skills 🦋."""
        s1 = Skill(name="file_read", keywords=["file", "read"])
        s2 = Skill(name="file_write", keywords=["file", "write"])
        s3 = Skill(name="net_fetch", keywords=["fetch", "network"])
        self.registry.register(s1)
        self.registry.register(s2)
        self.registry.register(s3)

        matches = self.registry.find_all_matching_skills("modify this file now")
        self.assertEqual(len(matches), 2)
        self.assertEqual({m.name for m in matches}, {"file_read", "file_write"})

    def test_clear_registry(self):
        """Verify clear() empties registry 🦋."""
        self.registry.register(Skill(name="temp"))
        self.assertEqual(len(self.registry), 1)
        self.registry.clear()
        self.assertEqual(len(self.registry), 0)


class TestRegisterSkillDecorator(unittest.TestCase):
    """Test @register_skill decorator functionality with global and local registries 🦋."""

    def test_register_decorator_custom_registry(self):
        """Verify @register_skill binds function with metadata into custom registry 🦋."""
        custom_reg = SkillRegistry(name="decorator_test")

        @register_skill(
            name="adder",
            tier=Tier.GREEN,
            keywords=["add", "sum"],
            description="Adds two numbers",
            category="Arithmetic",
            registry=custom_reg,
        )
        def my_adder(a: int, b: int) -> int:
            return a + b

        self.assertIn("adder", custom_reg)
        skill = custom_reg.get("adder")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "adder")
        self.assertEqual(skill.description, "Adds two numbers")
        self.assertEqual(skill.category, "Arithmetic")
        # Ensure decorated function remains directly callable
        self.assertEqual(my_adder(3, 4), 7)

    def test_register_decorator_docstring_fallback(self):
        """Verify @register_skill extracts first line of docstring when description is empty 🦋."""
        custom_reg = SkillRegistry(name="docstring_test")

        @register_skill(name="doc_func", registry=custom_reg)
        def func_with_doc():
            """Primary summary line from docstring.
            Additional detailed documentation here.
            """
            return True

        skill = custom_reg.get("doc_func")
        self.assertEqual(skill.description, "Primary summary line from docstring.")


class TestSkillExecutionAndGuardrails(unittest.TestCase):
    """Test 3-Tier Security Guardrail Enforcement in Skill Execution 🦋."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.audit_log = os.path.join(self.temp_dir, "test_audit.log")
        self.registry = SkillRegistry(name="guard_test", audit_log_path=self.audit_log)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_green_tier_silent_success(self):
        """Verify GREEN tier skill executes silently and returns SUCCESS status 🦋."""
        s = Skill(
            name="safe_probe",
            tier=Tier.GREEN,
            handler=lambda x=1: x * 10,
        )
        self.registry.register(s)

        res = self.registry.execute("safe_probe", args={"x": 5})
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["tier"], "GREEN")
        self.assertEqual(res["output"], 50)
        self.assertEqual(res["mark"], WATERMARK)
        self.assertGreaterEqual(res["latency_s"], 0.0)

    def test_execute_yellow_tier_audited(self):
        """Verify YELLOW tier skill executes and logs audit trail 🦋."""
        s = Skill(
            name="write_log",
            tier=Tier.YELLOW,
            handler=lambda msg: f"logged: {msg}",
        )
        self.registry.register(s)

        res = self.registry.execute("write_log", args={"msg": "hello yellow"})
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["tier"], "YELLOW")
        self.assertEqual(res["output"], "logged: hello yellow")
        self.assertTrue(res.get("audited"))

    def test_execute_red_tier_denied_when_unapproved(self):
        """Headless red actions wait for an explicit persisted approval. 🦋"""
        calls = []
        self.registry.register(Skill(name="nuke_all", tier=Tier.RED,
            description="Destructive system reset", handler=lambda: calls.append(True)))
        from tools.runtime import approvals
        with patch("sys.stdin.isatty", return_value=False), patch.object(
                approvals, "PENDING_FILE", os.path.join(self.temp_dir, "approvals.json")):
            res = self.registry.execute("nuke_all", auto_approve_red=False)
            self.assertEqual(res["status"], "PENDING_APPROVAL")
            self.assertEqual(res["tier"], "RED")
            self.assertTrue(res["approval_id"])
            self.assertEqual(calls, [])

    def test_execute_red_tier_auto_approved(self):
        """Verify RED tier skill executes successfully when auto_approve_red=True 🦋."""
        s = Skill(
            name="critical_op",
            tier=Tier.RED,
            handler=lambda val: val.upper(),
        )
        self.registry.register(s)

        res = self.registry.execute("critical_op", args={"val": "critical"}, auto_approve_red=True)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["tier"], "RED")
        self.assertEqual(res["output"], "CRITICAL")
        self.assertTrue(res.get("authorized"))

    def test_execute_red_tier_interactive_approval(self):
        """Verify RED tier skill queries interactive user input and executes when 'y' is given 🦋."""
        s = Skill(
            name="lock_screen",
            tier=Tier.RED,
            handler=lambda: "locked",
        )
        self.registry.register(s)

        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y"):
            res = self.registry.execute("lock_screen")
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["output"], "locked")

        with patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="n"):
            res_denied = self.registry.execute("lock_screen")
            self.assertEqual(res_denied["status"], "DENIED")

    def test_execute_nonexistent_skill(self):
        """Verify execute returns ERROR status for unknown skill 🦋."""
        res = self.registry.execute("unknown_skill")
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("not found in registry", res["error"])

    def test_execute_missing_handler(self):
        """Verify execute returns ERROR status when skill handler is None 🦋."""
        s = Skill(name="ghost_handler", handler=None)
        self.registry.register(s)
        res = self.registry.execute("ghost_handler")
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("callable execution handler", res["error"])

    def test_execute_handler_exception_handling(self):
        """Verify handler exceptions are caught and returned in ERROR payload 🦋."""
        def broken_func():
            raise RuntimeError("Division by zero in skill")

        s = Skill(name="broken", tier=Tier.GREEN, handler=broken_func)
        self.registry.register(s)

        res = self.registry.execute("broken")
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("Division by zero in skill", res["error"])


class TestBuiltinCoreSkills(unittest.TestCase):
    """Test all 5 built-in core skills (sys_info, file_patch, code_ast_metrics, http_probe, text_format) 🦋."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_skill_sys_info(self):
        """Verify sys_info returns OS, CPU cores, Python version, and timestamps 🦋."""
        res = skill_sys_info()
        self.assertIn("os", res)
        self.assertIn("cpu_count", res)
        self.assertIn("python", res)
        self.assertIn("disk", res)
        self.assertIn("timestamp_utc", res)
        self.assertIn("timestamp_local", res)
        self.assertEqual(res["mark"], WATERMARK)
        self.assertGreater(res["cpu_count"], 0)
        self.assertTrue(bool(res["python"]["version"]))

    def test_skill_file_patch_replace_mode(self):
        """Verify file_patch replace mode updates target substring in file 🦋."""
        test_file = os.path.join(self.temp_dir, "sample.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Hello old world!\nSecond line.\n")

        res = skill_file_patch(
            path=test_file,
            target_content="old world",
            replacement_content="new cosmos",
            mode="replace",
            create_backup=True,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["changes_count"], 1)

        with open(test_file, "r", encoding="utf-8") as f:
            new_text = f.read()
        self.assertIn("Hello new cosmos!", new_text)

        # Check backup created
        backup_file = f"{test_file}.bak"
        self.assertTrue(os.path.exists(backup_file))
        with open(backup_file, "r", encoding="utf-8") as bf:
            self.assertIn("Hello old world!", bf.read())

    def test_skill_file_patch_no_match(self):
        """Verify file_patch returns NO_MATCH when target substring is not found 🦋."""
        test_file = os.path.join(self.temp_dir, "sample.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Some text here.\n")

        res = skill_file_patch(
            path=test_file,
            target_content="nonexistent text",
            replacement_content="replacement",
            mode="replace",
        )
        self.assertEqual(res["status"], "NO_MATCH")
        self.assertEqual(res["changes_count"], 0)

    def test_skill_file_patch_append_and_overwrite(self):
        """Verify file_patch append, prepend, and overwrite modes 🦋."""
        test_file = os.path.join(self.temp_dir, "mutate.txt")
        # Overwrite
        res1 = skill_file_patch(path=test_file, content="Line 1\n", mode="overwrite")
        self.assertEqual(res1["status"], "SUCCESS")

        # Append
        res2 = skill_file_patch(path=test_file, content="Line 2", mode="append")
        self.assertEqual(res2["status"], "SUCCESS")

        # Prepend
        res3 = skill_file_patch(path=test_file, content="Line 0\n", mode="prepend")
        self.assertEqual(res3["status"], "SUCCESS")

        with open(test_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        self.assertEqual(lines, ["Line 0", "Line 1", "Line 2"])

    def test_skill_file_patch_error_cases(self):
        """Verify file_patch raises errors on invalid arguments or missing files 🦋."""
        with self.assertRaises(ValueError):
            skill_file_patch(path="")
        with self.assertRaises(FileNotFoundError):
            skill_file_patch(path=os.path.join(self.temp_dir, "ghost.txt"), mode="replace")
        with self.assertRaises(ValueError):
            skill_file_patch(path=os.path.join(self.temp_dir, "ghost.txt"), mode="invalid_mode")

    def test_skill_code_ast_metrics_code_string(self):
        """Verify code_ast_metrics parses Python code string and extracts functions, classes, imports 🦋."""
        code = textwrap.dedent('''\
            """Module docstring."""
            import os
            from sys import path

            def greet(name: str) -> str:
                """Greet someone."""
                return f"Hello {name}"

            class Engine:
                """Engine class."""
                def start(self):
                    pass
        ''')
        res = skill_code_ast_metrics(code=code)
        self.assertTrue(res["valid_syntax"])
        self.assertEqual(res["functions_count"], 2)  # greet, start
        self.assertEqual(res["classes_count"], 1)    # Engine
        self.assertIn("os", res["imports"])
        self.assertIn("sys", res["imports"])
        self.assertTrue(res["module_docstring"])
        self.assertEqual(res["mark"], WATERMARK)

    def test_skill_code_ast_metrics_file_and_syntax_error(self):
        """Verify code_ast_metrics analyzes file and handles syntax errors gracefully 🦋."""
        good_file = os.path.join(self.temp_dir, "good.py")
        with open(good_file, "w", encoding="utf-8") as f:
            f.write("x = 10\ny = 20\n")
        res_good = skill_code_ast_metrics(path=good_file)
        self.assertTrue(res_good["valid_syntax"])
        self.assertEqual(res_good["loc"], 2)

        bad_file = os.path.join(self.temp_dir, "bad.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("def broken(\n")
        res_bad = skill_code_ast_metrics(path=bad_file)
        self.assertFalse(res_bad["valid_syntax"])
        self.assertIn("syntax_error", res_bad)

    def test_skill_http_probe_mock(self):
        """Verify http_probe performs request and captures status, headers, body snippet 🦋."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.reason = "OK"
        mock_response.headers.items.return_value = [("Content-Type", "application/json")]
        mock_response.read.return_value = b'{"status": "ok", "service": "xola"}'

        mock_urlopen = MagicMock()
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with patch("urllib.request.urlopen", mock_urlopen):
            res = skill_http_probe(url="http://127.0.0.1:8101/api/health")
            self.assertEqual(res["status"], "UP")
            self.assertEqual(res["http_status"], 200)
            self.assertEqual(res["reason"], "OK")
            self.assertIn("xola", res["body_snippet"])
            self.assertEqual(res["mark"], WATERMARK)

    def test_skill_http_probe_errors(self):
        """Verify http_probe catches URLError and HTTPError cleanly 🦋."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
            res = skill_http_probe(url="http://127.0.0.1:9999/unreachable")
            self.assertEqual(res["status"], "DOWN")
            self.assertIn("Connection refused", res["error"])

        with self.assertRaises(ValueError):
            skill_http_probe(url="")

    def test_skill_text_format_actions(self):
        """Verify text_format actions: wrap, slugify, truncate, json_pretty, table, upper, lower 🦋."""
        # Wrap
        res_wrap = skill_text_format(text="Word " * 25, action="wrap", width=30)
        self.assertIn("\n", res_wrap["output"])

        # Slugify
        res_slug = skill_text_format(text="Hello World! Special #Chars", action="slugify")
        self.assertEqual(res_slug["output"], "hello-world-special-chars")

        # Truncate
        res_trunc = skill_text_format(text="A very long sentence here", action="truncate", max_len=10)
        self.assertEqual(res_trunc["output"], "A very ...")

        # JSON Pretty
        raw_json = '{"a":1,"b":[2,3]}'
        res_json = skill_text_format(text=raw_json, action="json_pretty", indent=2)
        self.assertIn("\n  ", res_json["output"])

        # Upper / Lower
        res_up = skill_text_format(text="hello", action="upper")
        self.assertEqual(res_up["output"], "HELLO")
        res_low = skill_text_format(text="WORLD", action="lower")
        self.assertEqual(res_low["output"], "world")

        # Table
        table_input = json.dumps([{"col1": "val1", "col2": "val2"}, {"col1": "val3", "col2": "val4"}])
        res_tbl = skill_text_format(text=table_input, action="table")
        self.assertIn("| col1 | col2 |", res_tbl["output"])
        self.assertIn("| val1 | val2 |", res_tbl["output"])


class TestRegistryValidationAndCLI(unittest.TestCase):
    """Test registry validation suite and standalone CLI execution 🦋."""

    def test_validate_skills_global_registry(self):
        """Verify GLOBAL_REGISTRY passes integrity validation with 100% clean status 🦋."""
        val = GLOBAL_REGISTRY.validate_skills()
        self.assertTrue(val["all_passed"])
        self.assertGreaterEqual(val["total"], 5)
        self.assertEqual(val["failed_count"], 0)
        self.assertEqual(val["passed_count"], val["total"])
        self.assertEqual(val["mark"], WATERMARK)

    def test_validate_skills_flags_invalid_skill(self):
        """Verify validate_skills catches invalid skills without handlers or names 🦋."""
        reg = SkillRegistry(name="bad_reg")
        bad_skill = Skill(name="broken_skill", handler=None)
        reg.register(bad_skill)

        val = reg.validate_skills()
        self.assertFalse(val["all_passed"])
        self.assertEqual(val["failed_count"], 1)

    def test_cli_list_action(self):
        """Verify CLI main() dispatches --list output cleanly 🦋."""
        with patch("sys.argv", ["skills.py", "--list"]):
            out = io.StringIO()
            with patch("sys.stdout", out), patch("sys.exit") as mock_exit:
                skills.main()
                mock_exit.assert_called_with(0)
            self.assertIn("Skills Registry", out.getvalue())
            self.assertIn(WATERMARK, out.getvalue())

    def test_cli_list_json_action(self):
        """Verify CLI main() outputs structured JSON under --json 🦋."""
        with patch("sys.argv", ["skills.py", "--list", "--json"]):
            out = io.StringIO()
            with patch("sys.stdout", out), patch("sys.exit") as mock_exit:
                skills.main()
                mock_exit.assert_called_with(0)
            data = json.loads(out.getvalue())
            self.assertEqual(data["command"], "skills")
            self.assertEqual(data["action"], "list")
            self.assertEqual(data["mark"], WATERMARK)

    def test_cli_info_action(self):
        """Verify CLI main() --info displays single skill details 🦋."""
        with patch("sys.argv", ["skills.py", "--info", "sys_info"]):
            out = io.StringIO()
            with patch("sys.stdout", out), patch("sys.exit") as mock_exit:
                skills.main()
                mock_exit.assert_called_with(0)
            self.assertIn("Skill Inspector: 'sys_info'", out.getvalue())

    def test_cli_run_action(self):
        """Verify CLI main() --run executes target skill with arguments 🦋."""
        args_payload = json.dumps({"text": "test-cli-run", "action": "upper"})
        with patch("sys.argv", ["skills.py", "--run", "text_format", "--args", args_payload]):
            out = io.StringIO()
            with patch("sys.stdout", out), patch("sys.exit") as mock_exit:
                skills.main()
                mock_exit.assert_called_with(0)
            self.assertIn("Skill Execution: text_format [SUCCESS]", out.getvalue())
            self.assertIn("TEST-CLI-RUN", out.getvalue())

    def test_cli_validate_action(self):
        """Verify CLI main() --validate succeeds with exit code 0 🦋."""
        with patch("sys.argv", ["skills.py", "--validate"]):
            out = io.StringIO()
            with patch("sys.stdout", out), patch("sys.exit") as mock_exit:
                skills.main()
                mock_exit.assert_called_with(0)
            self.assertIn("Validation [ALL PASSED]", out.getvalue())


if __name__ == "__main__":
    unittest.main()
