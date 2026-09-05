#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_memory.py # Automated tests for xola-memory 🦋"""

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

import tools.memory as memory

WATERMARK = "🦋"


class TestMemoryParsingEngine(unittest.TestCase):
    """Test memory markdown section and file parsing 🦋"""

    def test_parse_memory_section_structured(self):
        """Verify parsing a structured markdown round section 🦋"""
        section = textwrap.dedent(f'''\
            ## 14:20 loop round (Round 5: PASS) {WATERMARK}
            - **Round**: 5
            - **Verdict**: PASS
            - **Step**: Implement memory query engine.
            - **Evidence**: Query tests executed cleanly with 100% pass rate.
            - **Guard Audit Verdict**: PASS
            - **Key Lessons**: Strict tag indexing speeds up searches.
            - **Next Step**: Build timeline reporter.
            - **Tags**: memory, query, search
            - **Timestamp**: 2026-09-03 14:20:00
            - **Mark**: {WATERMARK}
        ''')
        rec = memory.parse_memory_section(section, source_file="2026-09-03.md", date_str="2026-09-03")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["round"], 5)
        self.assertEqual(rec["verdict"], "PASS")
        self.assertEqual(rec["step"], "Implement memory query engine.")
        self.assertIn("100% pass rate", rec["evidence"])
        self.assertEqual(rec["lessons"], "Strict tag indexing speeds up searches.")
        self.assertEqual(rec["next_step"], "Build timeline reporter.")
        self.assertEqual(rec["tags"], ["memory", "query", "search"])

    def test_parse_memory_section_fallback_unstructured(self):
        """Verify fallback parsing on unstructured round section 🦋"""
        section = textwrap.dedent(f'''\
            ## Round 2: KILL {WATERMARK}
            First line is the goal of round.
            Second line is additional evidence of failure.
        ''')
        rec = memory.parse_memory_section(section, source_file="test.md", date_str="2026-09-03")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["round"], 2)
        self.assertEqual(rec["verdict"], "KILL")
        self.assertIn("First line", rec["step"])

    def test_parse_memory_file(self):
        """Verify parsing multi-round markdown memory file 🦋"""
        temp_dir = tempfile.mkdtemp()
        try:
            fpath = os.path.join(temp_dir, "2026-09-03.md")
            content = textwrap.dedent(f'''\
                # Memory Log 2026-09-03 {WATERMARK}

                ## 10:00 loop round (Round 1: PASS) {WATERMARK}
                - **Round**: 1
                - **Verdict**: PASS
                - **Step**: Scout environment lanes.
                - **Evidence**: agy and opencode UP.

                ## 11:00 loop round (Round 2: PASS) {WATERMARK}
                - **Round**: 2
                - **Verdict**: PASS
                - **Step**: Build guard auditor.
                - **Evidence**: AST checker passed.
            ''')
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(content)

            records = memory.parse_memory_file(fpath)
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["round"], 1)
            self.assertEqual(records[1]["round"], 2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestMemoryLoopLogParser(unittest.TestCase):
    """Test parsing raw execution traces in loop.log 🦋"""

    def test_parse_loop_log(self):
        """Verify parse_loop_log extracts structured execution events 🦋"""
        temp_dir = tempfile.mkdtemp()
        try:
            log_path = os.path.join(temp_dir, "loop.log")
            log_content = textwrap.dedent('''\
                2026-09-03 12:00:00 === ROUND 1 ===
                2026-09-03 12:00:01 SCOUT: agy UP, opencode UP
                2026-09-03 12:00:05 MANAGER via=opencode ok=True chars=320
                2026-09-03 12:00:10 EXECUTOR ok=True chars=540
                2026-09-03 12:00:12 AUDIT pass=True
                2026-09-03 12:00:15 === ROUND 2 ===
                2026-09-03 12:00:16 SCOUT: python UP
                2026-09-03 12:00:20 MANAGER via=agy ok=True chars=250
                2026-09-03 12:00:25 EXECUTOR ok=False chars=100
                2026-09-03 12:00:26 AUDIT pass=False
            ''')
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(log_content)

            rounds = memory.parse_loop_log(log_path)
            self.assertEqual(len(rounds), 2)
            r1 = rounds[0]
            self.assertEqual(r1["round"], 1)
            self.assertEqual(r1["verdict"], "PASS")
            self.assertIn("opencode UP", r1["scout"])
            self.assertEqual(r1["manager"]["chars"], 320)
            self.assertEqual(r1["executor"]["chars"], 540)
            self.assertEqual(r1["duration_s"], 12.0)

            r2 = rounds[1]
            self.assertEqual(r2["round"], 2)
            self.assertEqual(r2["verdict"], "KILL")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestMemoryAppendEngine(unittest.TestCase):
    """Test --append round recorder 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_append_single_round(self):
        """Verify append_round writes valid structured markdown entry with 🦋 🦋"""
        res = memory.append_round(
            round_idx=1,
            step="Build scout prober",
            evidence="Prober passed all tests",
            verdict="PASS",
            lessons="Fallback paths are critical on Windows",
            next_step="Build builder tool",
            tags=["scout", "triage"],
            lane="agy",
            latency=1.23,
            memory_dir=self.temp_dir,
            target_date="2026-09-03",
        )
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["round"], 1)
        self.assertEqual(res["verdict"], "PASS")
        self.assertTrue(os.path.exists(res["file"]))

        with open(res["file"], "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn(f"Round 1: PASS) {WATERMARK}", content)
        self.assertIn("- **Step**: Build scout prober", content)
        self.assertIn("- **Tags**: scout, triage, lane:agy", content)
        self.assertIn(f"- **Mark**: {WATERMARK}", content)

    def test_append_auto_increment_round(self):
        """Verify round index auto-increments if round_idx is omitted 🦋"""
        memory.append_round(round_idx=1, step="Round 1", memory_dir=self.temp_dir, target_date="2026-09-03")
        res2 = memory.append_round(round_idx=None, step="Round 2", memory_dir=self.temp_dir, target_date="2026-09-03")
        self.assertEqual(res2["round"], 2)


class TestMemoryDistillEngine(unittest.TestCase):
    """Test --distill log compressor 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_distill_loop_log(self):
        """Verify distill_logs compresses loop.log into high-signal summaries 🦋"""
        log_path = os.path.join(self.temp_dir, "loop.log")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent('''\
                2026-09-03 12:00:00 === ROUND 1 ===
                2026-09-03 12:00:02 SCOUT: python UP
                2026-09-03 12:00:05 MANAGER via=agy ok=True chars=100
                2026-09-03 12:00:08 EXECUTOR ok=True chars=200
                2026-09-03 12:00:10 AUDIT pass=True
            '''))

        out_path = os.path.join(self.temp_dir, "distilled.md")
        res = memory.distill_logs(input_path=log_path, output_path=out_path)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["rounds_distilled"], 1)
        self.assertTrue(os.path.exists(out_path))

        with open(out_path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn(WATERMARK, text)
        self.assertIn("Round 01 [PASS]", text)

    def test_distill_arbitrary_text_file(self):
        """Verify distill_logs extracts signals from arbitrary execution logs 🦋"""
        text_path = os.path.join(self.temp_dir, "run.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write("Line 1: init\nLine 2: PASS completed successfully 🦋\nLine 3: finished\n")

        res = memory.distill_logs(input_path=text_path)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIn("PASS completed", res["summary_text"])


class TestMemoryQueryEngine(unittest.TestCase):
    """Test --query search filters across history 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        # Seed memory files with distinct markers
        memory.append_round(round_idx=1, step="Scout network lanes", verdict="PASS", lessons="Scouting ok", tags=["scout", "network"], memory_dir=self.temp_dir, target_date="2026-09-02")
        memory.append_round(round_idx=2, step="Implement security auditor", verdict="KILL", lessons="Auditor blocked", tags=["guard", "security"], memory_dir=self.temp_dir, target_date="2026-09-03")
        memory.append_round(round_idx=3, step="Fix security regex rules", verdict="PASS", lessons="Regex updated", tags=["guard", "security"], memory_dir=self.temp_dir, target_date="2026-09-03")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_query_keyword(self):
        """Verify query searches across step, evidence, and tags 🦋"""
        res = memory.query_memory(pattern="security", memory_dir=self.temp_dir)
        self.assertEqual(res["total_matches"], 2)
        self.assertEqual(res["pass_matches"], 1)
        self.assertEqual(res["kill_matches"], 1)

    def test_query_with_verdict_filter(self):
        """Verify query filters results by verdict 🦋"""
        res = memory.query_memory(pattern="security", verdict_filter="PASS", memory_dir=self.temp_dir)
        self.assertEqual(res["total_matches"], 1)
        self.assertEqual(res["matches"][0]["round"], 3)

    def test_query_with_tag_filter(self):
        """Verify query filters results by tag 🦋"""
        res = memory.query_memory(pattern=".*", tag_filter="network", memory_dir=self.temp_dir)
        self.assertEqual(res["total_matches"], 1)
        self.assertEqual(res["matches"][0]["round"], 1)

    def test_query_with_date_filter(self):
        """Verify query filters results by date 🦋"""
        res = memory.query_memory(pattern=".*", date_filter="2026-09-02", memory_dir=self.temp_dir)
        self.assertEqual(res["total_matches"], 1)
        self.assertEqual(res["matches"][0]["round"], 1)


class TestMemoryTimelineAndStats(unittest.TestCase):
    """Test --timeline and --stats performance analytics 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.loop_dir = tempfile.mkdtemp()
        memory.append_round(round_idx=1, step="Scout prober", verdict="PASS", memory_dir=self.temp_dir, target_date="2026-09-03")
        memory.append_round(round_idx=2, step="Builder forge", verdict="PASS", memory_dir=self.temp_dir, target_date="2026-09-03")
        memory.append_round(round_idx=3, step="Guard red-team", verdict="KILL", memory_dir=self.temp_dir, target_date="2026-09-03")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        shutil.rmtree(self.loop_dir, ignore_errors=True)

    def test_generate_timeline(self):
        """Verify timeline formats chronological rounds 🦋"""
        res = memory.generate_timeline(memory_dir=self.temp_dir, loop_dir=self.loop_dir)
        self.assertEqual(res["total_rounds"], 3)
        self.assertEqual(res["timeline"][0]["round"], 1)
        self.assertEqual(res["timeline"][2]["round"], 3)
        self.assertEqual(res["timeline"][2]["verdict"], "KILL")

    def test_compute_stats(self):
        """Verify compute_stats computes pass rates and module coverage 🦋"""
        res = memory.compute_stats(memory_dir=self.temp_dir, loop_dir=self.loop_dir)
        self.assertEqual(res["total_rounds"], 3)
        self.assertEqual(res["verdicts"]["pass"], 2)
        self.assertEqual(res["verdicts"]["kill"], 1)
        self.assertAlmostEqual(res["verdicts"]["pass_rate_pct"], 66.67, places=1)

        cov = res["module_coverage"]
        self.assertTrue(cov["scout"]["covered"])
        self.assertTrue(cov["builder"]["covered"])
        self.assertTrue(cov["guard"]["covered"])
        self.assertFalse(cov["hermes"]["covered"])


class TestMemoryReportsAndCLI(unittest.TestCase):
    """Test renderers and CLI dispatch 🦋"""

    def test_render_reports_contain_watermarks(self):
        """Verify all report renderers include 🦋 watermark 🦋"""
        app_rep = memory.render_append_report({"status": "SUCCESS", "round": 1, "verdict": "PASS", "file": "x.md", "bytes_written": 100, "timestamp": "now", "latency_s": 0.1})
        self.assertIn("🦋", app_rep)

        dist_rep = memory.render_distill_report({"status": "SUCCESS", "input": "in.log", "rounds_distilled": 1, "latency_s": 0.1, "distillation": ["signal 1"]})
        self.assertIn("🦋", dist_rep)

        query_rep = memory.render_query_report({"pattern": "test", "total_records_scanned": 1, "total_matches": 0, "pass_matches": 0, "kill_matches": 0, "latency_s": 0.1, "memory_dir": "/mem", "matches": []})
        self.assertIn("🦋", query_rep)

        time_rep = memory.render_timeline_report({"total_rounds": 1, "memory_dir": "/mem", "latency_s": 0.1, "timeline": [{"round": 1, "verdict": "PASS", "step_summary": "init"}]})
        self.assertIn("🦋", time_rep)

        stats_rep = memory.render_stats_report({"total_rounds": 1, "verdicts": {"pass": 1, "kill": 0, "warn": 0, "pass_rate_pct": 100.0}, "latency_stats": {}, "module_coverage": {}, "latency_s": 0.1})
        self.assertIn("🦋", stats_rep)

    def test_cli_stats_json(self):
        """Verify CLI --stats --json returns valid JSON with 🦋 🦋"""
        test_args = ["memory.py", "--stats", "--json", "--memory-dir", os.path.join(PROJECT_ROOT, "memory")]
        with patch.object(sys, "argv", test_args):
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                with self.assertRaises(SystemExit) as cm:
                    memory.main()
                self.assertEqual(cm.exception.code, 0)
                data = json.loads(fake_out.getvalue())
                self.assertEqual(data.get("mark"), "🦋")
                self.assertIn("verdicts", data)


if __name__ == "__main__":
    unittest.main()
