#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_builder.py # Automated tests for xola-builder 🦋"""

import io
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import tools.builder as builder

WATERMARK = "🦋"


class TestBuilderASTAnalyzer(unittest.TestCase):
    """Test AST static analysis of tool source files 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_analyze_nonexistent_file(self):
        """Verify analyze_tool_code returns error for missing files 🦋"""
        res = builder.analyze_tool_code(os.path.join(self.temp_dir, "ghost.py"))
        self.assertFalse(res["valid_ast"])
        self.assertIn("File not found", res["error"])

    def test_analyze_valid_tool_code(self):
        """Verify analyze_tool_code extracts metadata from compliant tool 🦋"""
        code = textwrap.dedent('''\
            #!/usr/bin/env python3
            """Usage: python sample_tool.py [--target PATH] # Sample tool 🦋"""

            import argparse
            import sys

            WATERMARK = "🦋"

            def sample_action(param: str) -> None:
                """Perform sample action."""
                pass

            class SampleClass:
                pass

            def main():
                parser = argparse.ArgumentParser()
                parser.parse_args()
                sys.exit(0)

            if __name__ == "__main__":
                main()
        ''')
        fpath = os.path.join(self.temp_dir, "sample_tool.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        res = builder.analyze_tool_code(fpath)
        self.assertTrue(res["valid_ast"])
        self.assertTrue(res["has_watermark"])
        self.assertTrue(res["has_usage_header"])
        self.assertTrue(res["has_argparse"])
        self.assertTrue(res["has_exit_calls"])
        self.assertEqual(res["external_imports"], [])
        self.assertIn("sample_action", [fn["name"] for fn in res["functions"]])
        self.assertIn("SampleClass", [c["name"] for c in res["classes"]])

    def test_analyze_syntax_error(self):
        """Verify analyze_tool_code catches Python syntax errors gracefully 🦋"""
        code = "def broken_func(:\n    pass\n"
        fpath = os.path.join(self.temp_dir, "broken.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        res = builder.analyze_tool_code(fpath)
        self.assertFalse(res["valid_ast"])
        self.assertIsNotNone(res["ast_error"])
        self.assertIn("SyntaxError", res["ast_error"])

    def test_analyze_external_imports(self):
        """Verify analyze_tool_code identifies non-stdlib external dependencies 🦋"""
        code = textwrap.dedent('''\
            import os
            import requests
            import numpy
            from bs4 import BeautifulSoup
        ''')
        fpath = os.path.join(self.temp_dir, "external_deps.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        res = builder.analyze_tool_code(fpath)
        self.assertTrue(res["valid_ast"])
        self.assertIn("requests", res["external_imports"])
        self.assertIn("numpy", res["external_imports"])
        self.assertIn("bs4", res["external_imports"])


class TestBuilderValidationRules(unittest.TestCase):
    """Test validation engine rules and smoke test integration 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_validate_nonexistent_tool(self):
        """Verify validate_tool fails immediately on missing target 🦋"""
        fpath = os.path.join(self.temp_dir, "nonexistent.py")
        val = builder.validate_tool(fpath)
        self.assertEqual(val["status"], "FAIL")
        self.assertFalse(val["passed"])

    def test_validate_missing_watermark(self):
        """Verify validate_tool fails when 🦋 watermark is omitted 🦋"""
        code = textwrap.dedent('''\
            #!/usr/bin/env python3
            """Usage: python no_mark.py"""
            import argparse
            import sys
            sys.exit(0)
        ''')
        fpath = os.path.join(self.temp_dir, "no_mark.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        val = builder.validate_tool(fpath, run_test=False)
        self.assertEqual(val["status"], "FAIL")
        watermark_chk = next(c for c in val["checks"] if c["name"] == "WATERMARK_MARK")
        self.assertEqual(watermark_chk["status"], "FAIL")

    def test_validate_missing_usage_header(self):
        """Verify validate_tool fails when usage docstring header is missing 🦋"""
        code = textwrap.dedent('''\
            #!/usr/bin/env python3
            """Module without usage header 🦋"""
            import argparse
            import sys
            sys.exit(0)
        ''')
        fpath = os.path.join(self.temp_dir, "no_usage.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        val = builder.validate_tool(fpath, run_test=False)
        self.assertEqual(val["status"], "FAIL")
        usage_chk = next(c for c in val["checks"] if c["name"] == "USAGE_HEADER")
        self.assertEqual(usage_chk["status"], "FAIL")

    def test_validate_external_dependency_fails(self):
        """Verify validate_tool fails when external libraries are detected 🦋"""
        code = textwrap.dedent('''\
            #!/usr/bin/env python3
            """Usage: python ext_dep.py 🦋"""
            import argparse
            import sys
            import requests
            sys.exit(0)
        ''')
        fpath = os.path.join(self.temp_dir, "ext_dep.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        val = builder.validate_tool(fpath, run_test=False)
        self.assertEqual(val["status"], "FAIL")
        stdlib_chk = next(c for c in val["checks"] if c["name"] == "PURE_STDLIB")
        self.assertEqual(stdlib_chk["status"], "FAIL")


class TestBuilderScaffolding(unittest.TestCase):
    """Test scaffolding all 4 templates and overwrite protection 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_scaffold_tool_template(self):
        """Verify scaffolding standard 'tool' template produces passing tool 🦋"""
        res = builder.scaffold_tool(
            name="data_cleaner",
            desc="clean and format data",
            template_type="tool",
            tools_dir=self.temp_dir,
            force=False,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["name"], "data_cleaner.py")
        self.assertTrue(os.path.exists(res["path"]))
        self.assertTrue(res["validation"]["passed"])

    def test_scaffold_prober_template(self):
        """Verify scaffolding 'prober' template produces passing prober tool 🦋"""
        res = builder.scaffold_tool(
            name="network_ping",
            desc="ping network lanes",
            template_type="prober",
            tools_dir=self.temp_dir,
            force=False,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["template"], "prober")
        self.assertTrue(res["validation"]["passed"])

    def test_scaffold_auditor_template(self):
        """Verify scaffolding 'auditor' template produces passing auditor tool 🦋"""
        res = builder.scaffold_tool(
            name="schema_audit",
            desc="audit json schemas",
            template_type="auditor",
            tools_dir=self.temp_dir,
            force=False,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["template"], "auditor")
        self.assertTrue(res["validation"]["passed"])

    def test_scaffold_distiller_template(self):
        """Verify scaffolding 'distiller' template produces passing distiller tool 🦋"""
        res = builder.scaffold_tool(
            name="log_distill",
            desc="distill execution logs",
            template_type="distiller",
            tools_dir=self.temp_dir,
            force=False,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["template"], "distiller")
        self.assertTrue(res["validation"]["passed"])

    def test_scaffold_file_exists_collision_without_force(self):
        """Verify scaffolding rejects collision when file exists without --force 🦋"""
        builder.scaffold_tool(
            name="duplicate_tool",
            desc="first instance",
            tools_dir=self.temp_dir,
            force=False,
        )
        # Attempt to scaffold same tool name again
        res = builder.scaffold_tool(
            name="duplicate_tool",
            desc="second instance",
            tools_dir=self.temp_dir,
            force=False,
        )
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("already exists", res["message"])

    def test_scaffold_overwrite_with_force(self):
        """Verify scaffolding overwrites existing tool when force=True 🦋"""
        builder.scaffold_tool(
            name="overwrite_me",
            desc="initial",
            tools_dir=self.temp_dir,
            force=False,
        )
        res = builder.scaffold_tool(
            name="overwrite_me",
            desc="overwritten",
            tools_dir=self.temp_dir,
            force=True,
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["description"], "overwritten")

    def test_scaffold_name_sanitization(self):
        """Verify tool names with dashes, spaces, and extensions are sanitized 🦋"""
        res = builder.scaffold_tool(
            name="My-Custom Tool.py",
            desc="sanitized tool",
            tools_dir=self.temp_dir,
        )
        self.assertEqual(res["name"], "my_custom_tool.py")


class TestBuilderListingAndInspection(unittest.TestCase):
    """Test listing, inspection, and multi-tool validation in directory 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Scaffold 2 tools in temp_dir
        builder.scaffold_tool("alpha", "alpha tool", tools_dir=self.temp_dir)
        builder.scaffold_tool("beta", "beta prober", template_type="prober", tools_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_tools(self):
        """Verify list_tools retrieves all python tools in alphabetical order 🦋"""
        tools = builder.list_tools(self.temp_dir)
        self.assertEqual(len(tools), 2)
        self.assertTrue(tools[0].endswith("alpha.py"))
        self.assertTrue(tools[1].endswith("beta.py"))

    def test_inspect_single_tool(self):
        """Verify inspect_tools single target mode 🦋"""
        res = builder.inspect_tools(target="alpha", tools_dir=self.temp_dir)
        self.assertTrue(res["single"])
        self.assertEqual(res["analysis"]["name"], "alpha.py")
        self.assertTrue(res["analysis"]["valid_ast"])

    def test_inspect_all_tools(self):
        """Verify inspect_tools multi-tool directory mode 🦋"""
        res = builder.inspect_tools(target=None, tools_dir=self.temp_dir)
        self.assertFalse(res["single"])
        self.assertEqual(res["count"], 2)

    def test_validate_all_tools(self):
        """Verify validate_all_tools aggregates check results across tools 🦋"""
        res = builder.validate_all_tools(tools_dir=self.temp_dir, run_test=True)
        self.assertEqual(res["total"], 2)
        self.assertEqual(res["passed_count"], 2)
        self.assertEqual(res["failed_count"], 0)
        self.assertTrue(res["all_passed"])

    def test_validate_live_tools_directory(self):
        """Verify live D:\\alox\\xola\\tools passes all X.O.L.A. standards 🦋"""
        live_tools_dir = os.path.join(PROJECT_ROOT, "tools")
        if os.path.exists(live_tools_dir):
            res = builder.validate_all_tools(tools_dir=live_tools_dir, run_test=False)
            self.assertGreater(res["total"], 0)
            self.assertTrue(res["all_passed"], f"Failures: {res['results']}")


class TestBuilderReportingAndCLI(unittest.TestCase):
    """Test renderers and CLI entrypoints 🦋"""

    def test_render_reports_contain_watermark(self):
        """Verify scaffold, inspect, and validate renderers contain 🦋 watermark 🦋"""
        dummy_scaffold = {
            "status": "SUCCESS",
            "name": "test.py",
            "path": "/tools/test.py",
            "template": "tool",
            "description": "test",
            "validation": {"status": "PASS", "checks": []},
        }
        r1 = builder.render_scaffold_report(dummy_scaffold)
        self.assertIn("🦋", r1)

        dummy_inspect = {
            "single": True,
            "analysis": {"file": "test.py", "size_bytes": 100, "loc": 10, "has_watermark": True},
        }
        r2 = builder.render_inspect_report(dummy_inspect)
        self.assertIn("🦋", r2)

        dummy_val = {
            "tools_dir": "/tools",
            "total": 1,
            "passed_count": 1,
            "failed_count": 0,
            "all_passed": True,
            "results": [{"tool": "test.py", "status": "PASS", "checks": []}],
        }
        r3 = builder.render_validate_report(dummy_val)
        self.assertIn("🦋", r3)

    def test_cli_list_json(self):
        """Verify CLI --list --json returns JSON output with tools and mark 🦋"""
        test_args = ["builder.py", "--list", "--json", "--tools-dir", os.path.join(PROJECT_ROOT, "tools")]
        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    builder.main()
                self.assertEqual(cm.exception.code, 0)
                data = json.loads(fake_out.getvalue())
                self.assertEqual(data.get("mark"), "🦋")
                self.assertIn("tools", data)


if __name__ == "__main__":
    unittest.main()
