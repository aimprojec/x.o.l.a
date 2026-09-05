#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_guard.py # Automated tests for xola-guard 🦋"""

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

import tools.guard as guard

WATERMARK = "🦋"


class TestGuardSyntaxAndAST(unittest.TestCase):
    """Test AST compilation and syntax verification rules 🦋"""

    def test_python_valid_syntax(self):
        """Verify valid Python code produces zero syntax findings 🦋"""
        code = "def hello():\n    return 'world 🦋'\n"
        findings = guard.check_syntax_and_ast("test.py", code)
        self.assertEqual(len(findings), 0)

    def test_python_syntax_error(self):
        """Verify Python syntax errors are caught as KILL severity 🦋"""
        code = "def bad_syntax(\n    return 42\n"
        findings = guard.check_syntax_and_ast("test.py", code)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "AST_SYNTAX_ERROR")
        self.assertEqual(findings[0]["severity"], "KILL")
        self.assertIn("SyntaxError", findings[0]["message"])

    def test_json_valid_syntax(self):
        """Verify valid JSON produces zero syntax findings 🦋"""
        content = json.dumps({"status": "UP", "mark": "🦋"})
        findings = guard.check_syntax_and_ast("data.json", content)
        self.assertEqual(len(findings), 0)

    def test_json_syntax_error(self):
        """Verify invalid JSON produces JSON_SYNTAX_ERROR with KILL severity 🦋"""
        content = '{"status": "UP", mark: invalid_json}'
        findings = guard.check_syntax_and_ast("bad.json", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "JSON_SYNTAX_ERROR")
        self.assertEqual(findings[0]["severity"], "KILL")

    def test_non_code_files_skip_syntax_ast(self):
        """Verify markdown and text files skip AST/JSON syntax checks 🦋"""
        findings = guard.check_syntax_and_ast("notes.md", "# Heading without python syntax")
        self.assertEqual(len(findings), 0)


class TestGuardSecretLeakDetection(unittest.TestCase):
    """Test credential and secret leak scanner across known API patterns 🦋"""

    def test_redact_secret_utility(self):
        """Verify redact_secret masks token contents safely 🦋"""
        test_val = "sk-" + "1234567890abcdef1234567890"
        masked = guard.redact_secret(test_val)
        self.assertTrue(masked.startswith("sk-1"))
        self.assertTrue(masked.endswith("[len 29]"))
        self.assertIn("****", masked)

    def test_openai_key_leak(self):
        """Verify detection of hardcoded OpenAI API key 🦋"""
        key_str = "sk-" + "abcdef1234567890abcdef1234567890"
        content = f'client = OpenAI(api_key="{key_str}")'
        findings = guard.check_secret_leaks("api.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_OPENAI_KEY", rules)
        self.assertTrue(any(f["severity"] == "KILL" for f in findings))

    def test_anthropic_key_leak(self):
        """Verify detection of hardcoded Anthropic API key 🦋"""
        key_str = "sk-ant-" + "api03-abcdef1234567890abcdef1234567890"
        content = f'anthropic_key = "{key_str}"'
        findings = guard.check_secret_leaks("agent.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_ANTHROPIC_KEY", rules)
        self.assertTrue(any(f["severity"] == "KILL" for f in findings))

    def test_google_key_leak(self):
        """Verify detection of hardcoded Google AI Key 🦋"""
        key_str = "AIza" + ("B" * 35)
        content = f'GEMINI_KEY = "{key_str}"'
        findings = guard.check_secret_leaks("config.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_GOOGLE_KEY", rules)

    def test_aws_key_id_leak(self):
        """Verify detection of AWS Access Key ID 🦋"""
        key_str = "AKIA" + "1234567890ABCDEF"
        content = f'AWS_KEY = "{key_str}"'
        findings = guard.check_secret_leaks("deploy.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_AWS_KEY_ID", rules)

    def test_aws_secret_key_leak(self):
        """Verify detection of AWS Secret Key assignment 🦋"""
        content = 'aws_secret_access_key = "' + ('1234567890' * 4) + '"'
        findings = guard.check_secret_leaks("deploy.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_AWS_SECRET_KEY", rules)

    def test_github_token_leak(self):
        """Verify detection of GitHub personal access tokens 🦋"""
        token_str = "ghp_" + "1234567890abcdefghijklmnopqrstuvwxyz"
        content = f'gh_pat = "{token_str}"'
        findings = guard.check_secret_leaks("git.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_GITHUB_TOKEN", rules)

    def test_slack_token_leak(self):
        """Verify detection of Slack bot / user tokens 🦋"""
        token_str = "xoxb-" + "123456789012-1234567890123-abcdefghijklmnopqrstuv"
        content = f'slack_bot = "{token_str}"'
        findings = guard.check_secret_leaks("notify.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_SLACK_TOKEN", rules)

    def test_private_key_header_leak(self):
        """Verify detection of raw RSA/EC private keys 🦋"""
        header_str = "-----BEGIN " + "RSA PRIVATE KEY-----"
        content = f"{header_str}\nMIIEowIBAAKCAQEA0...\n-----END RSA PRIVATE KEY-----"
        findings = guard.check_secret_leaks("id_rsa", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_PRIVATE_KEY", rules)

    def test_generic_api_key_and_password_leak(self):
        """Verify detection of hardcoded api_key and password assignments 🦋"""
        content = 'secret_key = "' + ('supersecretgenericsecrettoken12345') + '"\npassword = "' + ('VerySecretPassword123!') + '"'
        findings = guard.check_secret_leaks("creds.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_GENERIC_KEY", rules)
        self.assertIn("SECRET_HARDCODED_PASSWORD", rules)

    def test_bearer_token_leak(self):
        """Verify detection of hardcoded Bearer tokens 🦋"""
        auth_str = "Bearer " + "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abcdef"
        content = f'headers = {{"Authorization": "{auth_str}"}}'
        findings = guard.check_secret_leaks("fetch.py", content)
        rules = [f["rule"] for f in findings]
        self.assertIn("SECRET_BEARER_TOKEN", rules)

    def test_benign_placeholder_filter(self):
        """Verify dummy placeholders and environment lookups are not flagged as leaks 🦋"""
        content = textwrap.dedent('''\
            api_key = os.environ.get("API_KEY", "your_api_key_here")
            dummy_token = "replace_me"
            test_key = "sk-proj-test"
            empty_key = "default"
        ''')
        findings = guard.check_secret_leaks("sample.py", content)
        self.assertEqual(len(findings), 0)


class TestGuardWatermarkVerification(unittest.TestCase):
    """Test 🦋 watermark verification rule 🦋"""

    def test_watermark_present(self):
        """Verify presence of 🦋 produces no watermark findings 🦋"""
        content = "#!/usr/bin/env python3\n# X.O.L.A. component 🦋\n"
        findings = guard.check_watermark_presence("tool.py", content)
        self.assertEqual(len(findings), 0)

    def test_watermark_missing(self):
        """Verify missing 🦋 produces WARN severity finding 🦋"""
        content = "#!/usr/bin/env python3\n# No mark here\n"
        findings = guard.check_watermark_presence("tool.py", content)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["rule"], "WATERMARK_MISSING")
        self.assertEqual(findings[0]["severity"], "WARN")


class TestGuardDependencyAuditing(unittest.TestCase):
    """Test dependency auditor enforcing stdlib and killing paid SDKs 🦋"""

    def test_pure_stdlib_imports(self):
        """Verify standard library imports produce no findings 🦋"""
        content = "import os\nimport sys\nimport json\nimport urllib.request\nfrom datetime import datetime\n"
        findings = guard.check_dependencies("tool.py", content)
        self.assertEqual(len(findings), 0)

    def test_unauthorized_paid_sdk_openai(self):
        """Verify importing paid OpenAI SDK triggers KILL severity 🦋"""
        content = "import openai\nfrom openai import OpenAI\n"
        findings = guard.check_dependencies("ai.py", content)
        self.assertGreater(len(findings), 0)
        self.assertEqual(findings[0]["rule"], "UNAUTHORIZED_PAID_DEPENDENCY")
        self.assertEqual(findings[0]["severity"], "KILL")

    def test_unauthorized_paid_sdk_anthropic_and_google(self):
        """Verify importing Anthropic and Google SDKs triggers KILL severity 🦋"""
        content = "import anthropic\nimport google.generativeai as genai\n"
        findings = guard.check_dependencies("ai.py", content)
        self.assertEqual(len(findings), 2)
        rules = [f["rule"] for f in findings]
        self.assertEqual(rules, ["UNAUTHORIZED_PAID_DEPENDENCY", "UNAUTHORIZED_PAID_DEPENDENCY"])

    def test_external_non_stdlib_warns(self):
        """Verify non-stdlib third-party package triggers WARN severity 🦋"""
        content = "import requests\nfrom bs4 import BeautifulSoup\n"
        findings = guard.check_dependencies("scraper.py", content)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["rule"], "EXTERNAL_NON_STDLIB_DEPENDENCY")
        self.assertEqual(findings[0]["severity"], "WARN")


class TestGuardAutoFixEngine(unittest.TestCase):
    """Test auto-remediation engine injecting missing 🦋 watermarks 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_apply_fix_python_docstring(self):
        """Verify watermark is cleanly injected into Python module docstring 🦋"""
        orig_code = '"""Usage: python test.py"""\n\nimport os\n'
        fpath = os.path.join(self.temp_dir, "test.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(orig_code)

        findings = guard.check_watermark_presence(fpath, orig_code)
        fixed_content, fixes = guard.apply_fixes(fpath, orig_code, findings)

        self.assertIn(WATERMARK, fixed_content)
        self.assertEqual(len(fixes), 1)
        # Verify file on disk was updated
        with open(fpath, "r", encoding="utf-8") as f:
            disk_content = f.read()
        self.assertIn(WATERMARK, disk_content)

    def test_apply_fix_markdown_header(self):
        """Verify watermark is appended to Markdown top header 🦋"""
        orig_md = "# Project Mission\n\nDetails here.\n"
        fpath = os.path.join(self.temp_dir, "mission.md")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(orig_md)

        findings = guard.check_watermark_presence(fpath, orig_md)
        fixed_content, fixes = guard.apply_fixes(fpath, orig_md, findings)

        self.assertIn(WATERMARK, fixed_content)
        self.assertTrue(fixed_content.startswith(f"# Project Mission {WATERMARK}"))

    def test_apply_fix_json_object(self):
        """Verify watermark mark key is added to JSON objects 🦋"""
        orig_json = '{"round": 1, "status": "PASS"}'
        fpath = os.path.join(self.temp_dir, "state.json")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(orig_json)

        findings = guard.check_watermark_presence(fpath, orig_json)
        fixed_content, fixes = guard.apply_fixes(fpath, orig_json, findings)

        data = json.loads(fixed_content)
        self.assertEqual(data.get("mark"), WATERMARK)


class TestGuardAuditSuiteAndCLI(unittest.TestCase):
    """Test full file and directory recursive audit engine 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_audit_clean_directory_pass(self):
        """Verify compliant directory yields PASS verdict 🦋"""
        code = textwrap.dedent(f'''\
            #!/usr/bin/env python3
            """Usage: python clean.py # {WATERMARK}"""
            import sys
            sys.exit(0)
        ''')
        fpath = os.path.join(self.temp_dir, "clean.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        res = guard.audit(self.temp_dir, strict=False)
        self.assertEqual(res["verdict"], "PASS")
        self.assertEqual(res["summary"]["files_passed"], 1)
        self.assertEqual(res["summary"]["files_killed"], 0)

    def test_audit_critical_finding_kills(self):
        """Verify critical syntax or secret error yields KILL verdict 🦋"""
        bad_code = "def syntax_err(:\n    pass\n"
        fpath = os.path.join(self.temp_dir, "bad.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(bad_code)

        res = guard.audit(self.temp_dir, strict=False)
        self.assertEqual(res["verdict"], "KILL")
        self.assertGreater(res["summary"]["critical_count"], 0)

    def test_audit_warning_strict_vs_non_strict(self):
        """Verify warnings result in WARN in non-strict mode and KILL in strict mode 🦋"""
        warn_code = textwrap.dedent('''\
            #!/usr/bin/env python3
            """No watermark docstring"""
            import os
        ''')
        fpath = os.path.join(self.temp_dir, "warn.py")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(warn_code)

        res_non_strict = guard.audit(self.temp_dir, strict=False)
        self.assertEqual(res_non_strict["verdict"], "WARN")

        res_strict = guard.audit(self.temp_dir, strict=True)
        self.assertEqual(res_strict["verdict"], "KILL")

    def test_render_report_formatting(self):
        """Verify report string contains butterfly banner and summary metrics 🦋"""
        dummy_res = {
            "auditor": "guard",
            "target": "/test",
            "verdict": "PASS",
            "strict": False,
            "latency_s": 0.05,
            "summary": {
                "files_scanned": 1,
                "files_passed": 1,
                "files_warned": 0,
                "files_killed": 0,
                "total_findings": 0,
                "critical_count": 0,
                "warning_count": 0,
                "fixes_applied": 0,
            },
            "checks": {
                "syntax_ast": {"passed": 1, "failed": 0},
                "secret_detection": {"passed": 1, "failed": 0},
                "watermark": {"passed": 1, "failed": 0},
                "dependencies": {"passed": 1, "failed": 0},
                "smoke_tests": {"passed": 0, "failed": 0, "skipped": 1},
            },
            "findings": [],
        }
        rep = guard.render_report(dummy_res)
        self.assertIn("🦋", rep)
        self.assertIn("X.O.L.A. Red-Team Auditor", rep)
        self.assertIn("Verdict: PASS", rep)

    def test_audit_nonexistent_target(self):
        """Verify audit handles non-existent target gracefully with KILL verdict 🦋"""
        res = guard.audit(os.path.join(self.temp_dir, "nonexistent_dir"))
        self.assertEqual(res["verdict"], "KILL")
        self.assertEqual(res["summary"]["files_killed"], 1)


if __name__ == "__main__":
    unittest.main()
