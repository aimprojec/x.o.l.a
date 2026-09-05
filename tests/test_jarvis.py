#!/usr/bin/env python3
"""Usage: python -m unittest tests.test_jarvis # Automated Test Suite for Jarvis Harness, Brain, Voice & Sentinel Nudges 🦋"""

import datetime
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

# Ensure project root is in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

WATERMARK = "🦋"

import jarvis
from jarvis.sentinel import (
    Sentinel,
    SentinelCheck,
    NudgeSchedule,
    get_system_health,
    probe_cpu,
    probe_disk,
    probe_ram,
    probe_services,
    read_sentinel_log,
    run_sentinel_once,
    execute_scheduled_nudges,
    nudge_health_monitor,
    nudge_guard_audit,
    nudge_scout_probe,
    run_nudge_by_name,
)
from jarvis.hands import (
    OSHands,
    capture_screenshot,
    disk_space,
    file_tree,
    find_files,
    find_process,
    list_processes,
    list_windows,
    read_file_safe,
    write_file_safe,
    get_sysinfo,
)
from jarvis.brain import (
    AutonomousBrain,
    AGYReasoningBridge,
    HeuristicPlanner,
    BrainPlan,
    BrainExecutionResult,
    think,
    think_and_execute,
    get_brain_engine,
)
from jarvis.voice import (
    VoiceEngine,
    EarsQueue,
    Utterance,
    VoiceLogEntry,
    speak,
    enqueue_utterance,
    read_voice_log,
    process_ears_queue,
)
from jarvis.jarvis import (
    JarvisHarness,
    JarvisResponse,
    JarvisTask,
    get_jarvis_status,
    run_smoke_test,
)


class TestJarvisPackageExports(unittest.TestCase):
    """Verify package initialization and export definitions 🦋"""

    def test_package_metadata_and_watermark(self):
        """Verify package version, watermark and exports 🦋"""
        self.assertEqual(jarvis.WATERMARK, "🦋")
        self.assertEqual(jarvis.VERSION, "1.0.0")
        self.assertTrue(hasattr(jarvis, "Sentinel"))
        self.assertTrue(hasattr(jarvis, "OSHands"))
        self.assertTrue(hasattr(jarvis, "JarvisHarness"))
        self.assertTrue(hasattr(jarvis, "AutonomousBrain"))
        self.assertTrue(hasattr(jarvis, "VoiceEngine"))
        self.assertTrue(hasattr(jarvis, "EarsQueue"))


class TestSentinelSubsystem(unittest.TestCase):
    """Verify Sentinel system watcher, probes, and logging 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test_sentinel.log")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_probe_ram(self):
        """Verify RAM probe returns total, used, and free metrics 🦋"""
        ram = probe_ram()
        self.assertIn("total_gb", ram)
        self.assertIn("used_gb", ram)
        self.assertIn("free_gb", ram)
        self.assertIn("used_percent", ram)
        self.assertGreater(ram["total_gb"], 0)

    def test_probe_cpu(self):
        """Verify CPU probe returns valid load percentage and core count 🦋"""
        cpu = probe_cpu()
        self.assertIn("used_percent", cpu)
        self.assertIn("cores", cpu)
        self.assertGreaterEqual(cpu["cores"], 1)

    def test_probe_disk(self):
        """Verify disk probe returns drive breakdown and max utilization 🦋"""
        disk = probe_disk()
        self.assertIn("drives", disk)
        self.assertIn("max_used_percent", disk)
        self.assertGreater(len(disk["drives"]), 0)

    def test_probe_services(self):
        """Verify service heartbeat probe gathers queue and loop state 🦋"""
        srv = probe_services()
        self.assertIn("jarvis_queues", srv)
        self.assertIn("loop_state", srv)
        self.assertIn("workbench_server", srv)

    def test_get_system_health(self):
        """Verify holistic system health snapshot structure and watermark 🦋"""
        health = get_system_health()
        self.assertIsInstance(health, SentinelCheck)
        self.assertIn(health.status, ("HEALTHY", "WARNING", "CRITICAL"))
        self.assertEqual(health.mark, WATERMARK)
        h_dict = health.to_dict()
        self.assertIn("timestamp", h_dict)
        self.assertIn("alerts", h_dict)

    def test_sentinel_log_write_and_tail(self):
        """Verify Sentinel logs structured entries and can tail recent lines 🦋"""
        sentinel = Sentinel(log_path=self.log_path)
        chk = sentinel.check_and_log()
        self.assertTrue(os.path.exists(self.log_path))

        lines = read_sentinel_log(tail_n=5, log_path=self.log_path)
        self.assertEqual(len(lines), 1)
        self.assertIn(WATERMARK, lines[0])
        self.assertIn(chk.status, lines[0])


class TestSentinelNudges(unittest.TestCase):
    """Verify Scheduled Periodic Nudges Subsystem 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.temp_dir, "test_nudges_sentinel.log")

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_nudge_schedule_dataclass(self):
        """Verify NudgeSchedule is_due calculation and intervals 🦋"""
        sched = NudgeSchedule(name="test_nudge", interval_s=5.0, last_run=0.0)
        self.assertTrue(sched.is_due(current_time=10.0))
        sched.last_run = 8.0
        self.assertFalse(sched.is_due(current_time=10.0))
        self.assertEqual(sched.mark, WATERMARK)

    def test_nudge_health_monitor(self):
        """Verify health monitor scheduled nudge execution and logging 🦋"""
        res = nudge_health_monitor(log_path=self.log_path)
        self.assertEqual(res["nudge"], "health_monitor")
        self.assertIn(res["status"], ("HEALTHY", "WARNING", "CRITICAL"))
        self.assertTrue(os.path.exists(self.log_path))

        lines = read_sentinel_log(tail_n=5, log_path=self.log_path)
        self.assertEqual(len(lines), 1)
        self.assertIn("[NUDGE] [HEALTH_MONITOR]", lines[0])
        self.assertIn(WATERMARK, lines[0])

    def test_nudge_guard_audit(self):
        """Verify guard audit scheduled nudge execution and logging 🦋"""
        res = nudge_guard_audit(target_dir=PROJECT_ROOT, log_path=self.log_path)
        self.assertEqual(res["nudge"], "guard_audit")
        self.assertIn(res["verdict"], ("PASS", "WARN", "KILL"))
        self.assertTrue(os.path.exists(self.log_path))

        lines = read_sentinel_log(tail_n=5, log_path=self.log_path)
        self.assertGreaterEqual(len(lines), 1)
        self.assertIn("[NUDGE] [GUARD_AUDIT]", lines[-1])

    def test_nudge_scout_probe(self):
        """Verify scout probe scheduled nudge execution and logging 🦋"""
        res = nudge_scout_probe(log_path=self.log_path)
        self.assertEqual(res["nudge"], "scout_probe")
        self.assertIn(res["status"], ("UP", "DOWN", "ERROR"))
        self.assertTrue(os.path.exists(self.log_path))

        lines = read_sentinel_log(tail_n=5, log_path=self.log_path)
        self.assertGreaterEqual(len(lines), 1)
        self.assertIn("[NUDGE] [SCOUT_PROBE]", lines[-1])

    def test_run_nudge_by_name(self):
        """Verify running individual nudges by name alias 🦋"""
        res_health = run_nudge_by_name("health", log_path=self.log_path)
        self.assertEqual(res_health["nudge"], "health_monitor")

        res_guard = run_nudge_by_name("guard", log_path=self.log_path)
        self.assertEqual(res_guard["nudge"], "guard_audit")

        res_scout = run_nudge_by_name("scout", log_path=self.log_path)
        self.assertEqual(res_scout["nudge"], "scout_probe")

    def test_execute_scheduled_nudges(self):
        """Verify execute_scheduled_nudges helper runs all nudges when forced 🦋"""
        results = execute_scheduled_nudges(force=True, log_path=self.log_path)
        self.assertEqual(len(results), 3)
        nudge_names = [r["nudge"] for r in results]
        self.assertIn("health_monitor", nudge_names)
        self.assertIn("guard_audit", nudge_names)
        self.assertIn("scout_probe", nudge_names)


class TestVoiceSubsystem(unittest.TestCase):
    """Verify zero-dependency Windows Speech Synthesis and Ears Queue 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.ears_dir = os.path.join(self.temp_dir, "ears")
        self.log_path = os.path.join(self.temp_dir, "test_voice.log")
        self.voice = VoiceEngine(log_path=self.log_path)
        self.ears = EarsQueue(ears_dir=self.ears_dir)

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_voice_log_entry_and_file_append(self):
        """Verify VoiceLogEntry dataclass formatting and log file persistence 🦋"""
        entry = VoiceLogEntry(
            timestamp=datetime.datetime.now().isoformat(),
            text="Hello from XOLA Test Suite",
            rate=0,
            volume=100,
            latency_s=0.123,
            status="SUCCESS",
        )
        self.voice.log_entry(entry)
        self.assertTrue(os.path.exists(self.log_path))

        lines = read_voice_log(tail_n=5, log_path=self.log_path)
        self.assertEqual(len(lines), 1)
        self.assertIn("Hello from XOLA Test Suite", lines[0])
        self.assertIn(WATERMARK, lines[0])

    def test_voice_speech_script_builder(self):
        """Verify PowerShell System.Speech script construction and quote escaping 🦋"""
        script = self.voice._build_powershell_tts_script(
            text="Testing 'quoted' string `tick`",
            rate=2,
            volume=90,
            voice="Microsoft Zira",
        )
        self.assertIn("System.Speech.Synthesis.SpeechSynthesizer", script)
        self.assertIn("Rate = 2", script)
        self.assertIn("Volume = 90", script)
        self.assertIn("Testing ''quoted'' string", script)
        self.assertIn("Microsoft Zira", script)

    def test_voice_speak_execution(self):
        """Verify speak execution returns structured result with latency and watermark 🦋"""
        res = self.voice.speak("Hello XOLA", wait=True, log=True)
        self.assertIn(res["status"], ("SUCCESS", "ERROR", "MUTED", "UNSUPPORTED"))
        self.assertEqual(res["mark"], WATERMARK)
        self.assertTrue(os.path.exists(self.log_path))

    def test_voice_speak_async(self):
        """Verify non-blocking async speech synthesis queuing 🦋"""
        res = self.voice.speak("Async test message", wait=False, log=False)
        self.assertEqual(res["status"], "ASYNC_QUEUED")
        self.assertEqual(res["mark"], WATERMARK)

    def test_ears_queue_enqueue_peek_dequeue(self):
        """Verify EarsQueue lifecycle: enqueue utterance, peek queue, and dequeue into archive 🦋"""
        utt = self.ears.enqueue(
            text="Initiate system diagnostic probe",
            source="user",
            speaker="alice",
            metadata={"priority": "high"},
        )
        self.assertTrue(utt.id.startswith("ears_"))
        self.assertEqual(utt.speaker, "alice")
        self.assertEqual(utt.mark, WATERMARK)

        # Peek
        pending = self.ears.peek()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0].text, "Initiate system diagnostic probe")

        # Process queue
        processed = self.ears.process_queue()
        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0]["utterance"]["id"], utt.id)

        # Verify archive
        self.assertEqual(len(self.ears.peek()), 0)
        archived_files = os.listdir(self.ears.archive_dir)
        self.assertEqual(len(archived_files), 1)

    def test_ears_global_helpers(self):
        """Verify global top-level functional helpers for voice and ears 🦋"""
        u_id = enqueue_utterance("Global utterance test", ears_dir=self.ears_dir)
        self.assertTrue(u_id.startswith("ears_"))

        proc = process_ears_queue(ears_dir=self.ears_dir)
        self.assertEqual(len(proc), 1)
        self.assertEqual(proc[0]["utterance"]["text"], "Global utterance test")


class TestBrainSubsystem(unittest.TestCase):
    """Verify Autonomous Thinking Engine, AGY Reasoning Bridge, and Heuristic Planner 🦋"""

    def setUp(self):
        self.brain = AutonomousBrain()
        self.planner = HeuristicPlanner()
        self.agy_bridge = AGYReasoningBridge()

    def test_brain_plan_dataclass(self):
        """Verify BrainPlan dataclass attributes, serialization, and watermark 🦋"""
        plan = BrainPlan(
            prompt="check disk space",
            action="hands",
            skill="hands.disk",
            args={"drive": "D:"},
            thought="Inspect disk capacity",
            source="heuristic",
            confidence=0.95,
        )
        self.assertEqual(plan.mark, WATERMARK)
        p_dict = plan.to_dict()
        self.assertEqual(p_dict["action"], "hands")
        self.assertEqual(p_dict["args"]["drive"], "D:")

    def test_heuristic_planner_disk_intent(self):
        """Verify heuristic planner parses storage and drive queries 🦋"""
        plan = self.planner.plan("check available disk space on drive D:")
        self.assertEqual(plan.action, "hands")
        self.assertEqual(plan.skill, "hands.disk")
        self.assertEqual(plan.args.get("drive"), "D:")
        self.assertEqual(plan.source, "heuristic")
        self.assertEqual(plan.mark, WATERMARK)

    def test_heuristic_planner_process_intent(self):
        """Verify heuristic planner parses process listing queries 🦋"""
        plan = self.planner.plan("list running processes")
        self.assertEqual(plan.action, "hands")
        self.assertEqual(plan.skill, "hands.ps")
        self.assertEqual(plan.source, "heuristic")

    def test_heuristic_planner_screenshot_intent(self):
        """Verify heuristic planner parses screenshot and eyes capture queries 🦋"""
        plan = self.planner.plan("take a screenshot of the desktop")
        self.assertEqual(plan.action, "hands")
        self.assertEqual(plan.skill, "hands.screenshot")

    def test_heuristic_planner_scout_intent(self):
        """Verify heuristic planner parses scout lane triage queries 🦋"""
        plan = self.planner.plan("probe scout execution lanes")
        self.assertEqual(plan.action, "scout")
        self.assertEqual(plan.skill, "tools.scout")

    def test_heuristic_planner_guard_intent(self):
        """Verify heuristic planner parses guard security audit queries 🦋"""
        plan = self.planner.plan("run guard security audit on codebase")
        self.assertEqual(plan.action, "guard")
        self.assertEqual(plan.skill, "tools.guard")

    def test_heuristic_planner_voice_intent(self):
        """Verify heuristic planner parses voice speech requests 🦋"""
        plan = self.planner.plan("speak hello world")
        self.assertEqual(plan.action, "voice")
        self.assertEqual(plan.skill, "voice.speak")
        self.assertEqual(plan.args.get("text"), "hello world")

    def test_heuristic_planner_skills_match(self):
        """Verify heuristic planner matches registered dynamic skills 🦋"""
        plan = self.planner.plan("sys_info")
        self.assertEqual(plan.action, "skill")
        self.assertEqual(plan.skill, "sys_info")

    def test_agy_bridge_binary_resolution(self):
        """Verify AGY reasoning bridge resolves binary or gracefully handles missing CLI 🦋"""
        bin_path = self.agy_bridge._resolve_binary()
        is_avail = self.agy_bridge.is_available()
        self.assertIsInstance(is_avail, bool)

    def test_brain_think_and_execute_pipeline(self):
        """Verify AutonomousBrain think_and_execute pipeline produces BrainExecutionResult 🦋"""
        result = self.brain.think_and_execute("check drive D: storage space")
        self.assertIsInstance(result, BrainExecutionResult)
        self.assertEqual(result.status, "SUCCESS")
        self.assertIn("drive", result.output)
        self.assertEqual(result.mark, WATERMARK)
        self.assertTrue(result.formatted_response)

    def test_global_think_helper(self):
        """Verify global think and think_and_execute helper functions 🦋"""
        plan = think("list active processes", use_llm=False)
        self.assertEqual(plan.skill, "hands.ps")
        self.assertEqual(plan.mark, WATERMARK)


class TestHandsSubsystem(unittest.TestCase):
    """Verify zero-dependency OS hands, eyes, and filesystem helpers 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_list_processes(self):
        """Verify listing OS processes returns structured ProcessInfo records 🦋"""
        procs = list_processes(limit=10)
        self.assertGreater(len(procs), 0)
        p0 = procs[0]
        self.assertGreater(p0.pid, -1)
        self.assertTrue(p0.name)
        self.assertEqual(p0.mark, WATERMARK)

    def test_find_process_by_name(self):
        """Verify finding processes matching filter query 🦋"""
        procs = find_process("python")
        self.assertIsInstance(procs, list)

    def test_list_windows(self):
        """Verify window listing returns window items with watermark 🦋"""
        wins = list_windows(visible_only=True)
        self.assertIsInstance(wins, list)

    def test_filesystem_tree_and_read_write(self):
        """Verify file_tree, write_file_safe, and read_file_safe helpers 🦋"""
        sample_file = os.path.join(self.temp_dir, "nested", "test_file.txt")
        test_content = f"Hello Jarvis Hands {WATERMARK}"

        # Write
        w_res = write_file_safe(sample_file, test_content)
        self.assertEqual(w_res["status"], "SUCCESS")
        self.assertTrue(os.path.exists(sample_file))

        # Read
        r_res = read_file_safe(sample_file)
        self.assertEqual(r_res["status"], "SUCCESS")
        self.assertEqual(r_res["content"], test_content)

        # Tree
        tree_res = file_tree(self.temp_dir, max_depth=3)
        self.assertIn("entries", tree_res)
        self.assertGreaterEqual(tree_res["total_scanned"], 1)

        # Find files
        found = find_files(self.temp_dir, pattern="*.txt")
        self.assertEqual(len(found), 1)

    def test_disk_space(self):
        """Verify disk_space returns usage for target drive 🦋"""
        drive = "D:" if sys.platform == "win32" and os.path.exists("D:\\") else "C:"
        d_res = disk_space(drive)
        self.assertIn("total_gb", d_res)
        self.assertIn("free_gb", d_res)

    def test_capture_screenshot(self):
        """Verify screenshot capture execution via PowerShell 🦋"""
        out_img = os.path.join(self.temp_dir, "test_shot.png")
        res = capture_screenshot(output_path=out_img)
        self.assertIn(res["status"], ("SUCCESS", "ERROR"))
        self.assertEqual(res["mark"], WATERMARK)
        if res["status"] == "SUCCESS":
            self.assertTrue(os.path.exists(out_img))
            self.assertGreater(os.path.getsize(out_img), 0)

    def test_sysinfo(self):
        """Verify get_sysinfo returns structured OS, memory, and disk telemetry 🦋"""
        res = get_sysinfo()
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["action"], "sysinfo")
        self.assertIn("os", res)
        self.assertIn("cpu_count", res)
        self.assertIn("python", res)
        self.assertIn("disk", res)
        self.assertEqual(res["mark"], WATERMARK)


class TestJarvisHarnessCore(unittest.TestCase):
    """Verify Jarvis core harness, task processing, outbox, and telemetry 🦋"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.inbox_dir = os.path.join(self.temp_dir, "inbox")
        self.outbox_dir = os.path.join(self.temp_dir, "outbox")
        self.ears_dir = os.path.join(self.temp_dir, "ears")
        self.harness = JarvisHarness(
            inbox_dir=self.inbox_dir,
            outbox_dir=self.outbox_dir,
            ears_dir=self.ears_dir,
        )

    def tearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_submit_and_parse_json_task(self):
        """Verify task submission, JSON serialization, and parsing in inbox 🦋"""
        task_path = self.harness.submit_task(
            prompt_or_skill="sys_info",
            args={"drive": "D:"},
            action="skill",
        )
        self.assertTrue(os.path.exists(task_path))

        parsed_task = self.harness.parse_task_file(task_path)
        self.assertIsNotNone(parsed_task)
        self.assertEqual(parsed_task.skill, "sys_info")
        self.assertEqual(parsed_task.args.get("drive"), "D:")

    def test_submit_and_parse_txt_task(self):
        """Verify plain text task parsing fallback in inbox 🦋"""
        raw_txt_path = os.path.join(self.inbox_dir, "plain_prompt.txt")
        with open(raw_txt_path, "w", encoding="utf-8") as f:
            f.write(f"Check system status and specs {WATERMARK}")

        parsed_task = self.harness.parse_task_file(raw_txt_path)
        self.assertIsNotNone(parsed_task)
        self.assertIn("system status", parsed_task.prompt)

    def test_process_single_task_and_outbox_response(self):
        """Verify end-to-end execution of inbox task, writing to outbox, and archiving 🦋"""
        task_path = self.harness.submit_task(
            prompt_or_skill="sys_info",
            args={"drive": "D:"},
            action="skill",
        )

        resp = self.harness.process_single_task_file(task_path)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.skill_used, "sys_info")
        self.assertEqual(resp.mark, WATERMARK)

        # Verify task is archived from inbox
        self.assertFalse(os.path.exists(task_path))
        archived_files = os.listdir(self.harness.archive_dir)
        self.assertEqual(len(archived_files), 1)

        # Verify outbox response file
        outbox_files = [f for f in os.listdir(self.outbox_dir) if f.endswith(".json")]
        self.assertEqual(len(outbox_files), 1)
        out_json_path = os.path.join(self.outbox_dir, outbox_files[0])
        with open(out_json_path, "r", encoding="utf-8") as f:
            out_data = json.load(f)
        self.assertEqual(out_data["task_id"], resp.task_id)
        self.assertEqual(out_data["status"], "SUCCESS")
        self.assertIn("telemetry", out_data)

    def test_process_brain_auto_task(self):
        """Verify task execution routing through Autonomous Brain natural language reasoning 🦋"""
        task_path = self.harness.submit_task(
            prompt_or_skill="check disk space on drive D:",
            action="auto",
        )
        resp = self.harness.process_single_task_file(task_path)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status, "SUCCESS")
        self.assertEqual(resp.skill_used, "hands.disk")

    def test_process_hands_action_task(self):
        """Verify task execution routing to OS hands subsystem 🦋"""
        task_path = self.harness.submit_task(
            prompt_or_skill="hands.disk",
            args={"drive": "D:"},
            action="hands.disk",
        )
        resp = self.harness.process_single_task_file(task_path)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.status, "SUCCESS")
        self.assertIn("drive", resp.result)

    def test_get_jarvis_status(self):
        """Verify get_jarvis_status returns holistic state payload including ears and nudges 🦋"""
        status_info = get_jarvis_status()
        self.assertIn("status", status_info)
        self.assertIn("inbox_queue_count", status_info)
        self.assertIn("outbox_total_count", status_info)
        self.assertIn("ears_queue_count", status_info)
        self.assertEqual(status_info["mark"], WATERMARK)

    def test_run_smoke_test(self):
        """Verify global run_smoke_test function execution and verification 🦋"""
        smoke_res = run_smoke_test()
        self.assertIn("smoke_test", smoke_res)
        self.assertEqual(smoke_res["smoke_test"], "PASSED")
        self.assertEqual(smoke_res["mark"], WATERMARK)


if __name__ == "__main__":
    unittest.main()
