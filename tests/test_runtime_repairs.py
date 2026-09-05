"""Behavioral regression tests for the repaired assistant runtime. 🦋"""
import concurrent.futures
import contextlib
import http.client
import http.server
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch, Mock

import xola
from jarvis.brain import AutonomousBrain, BrainPlan, AGYReasoningBridge
from jarvis.hands import OSHands, write_file_safe, read_file_safe, list_processes
from jarvis.voice import EarsQueue, VoiceEngine
from tools.runtime import approvals
from tools.runtime.runtime_io import write_json
from tools.runtime.screen_context import observe_screen
from tools import vault
from tools.orchestrator import CoreOrchestrator, DAGNode, DAGPlan, TaskState
from tools.skills import SkillRegistry, Skill, Tier


class IsolatedRuntime(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(approvals, 'PENDING_FILE', str(self.root / 'approvals.json')))
        self.stack.enter_context(patch.object(approvals, 'AUTO_FILE', str(self.root / 'auto.json')))
        self.stack.enter_context(patch.object(xola, 'PENDING_QUESTIONS_FILE', str(self.root / 'approvals.json')))
        self.stack.enter_context(patch.object(xola, 'AUTO_ALLOW_STATE_FILE', str(self.root / 'auto.json')))
        for name, value in [('BASE', str(self.root / 'vault')), ('DB', str(self.root / 'vault/data.db')),
                            ('EPISODIC', str(self.root / 'vault/events.jsonl')), ('SNAPDIR', str(self.root / 'vault/snaps'))]:
            self.stack.enter_context(patch.object(vault, name, value))
        self.stack.enter_context(patch('jarvis.brain.PROJECT_ROOT', str(self.root)))
        self.stack.enter_context(patch.object(xola, 'STATE_FILE', str(self.root / 'state.json')))
        self.stack.enter_context(patch.object(xola, 'TELEMETRY_FILE', str(self.root / 'telemetry.jsonl')))
        self.stack.enter_context(patch('tools.orchestrator.SNAPSHOT_FILE', str(self.root / 'dag.json')))
        self.stack.enter_context(patch('tools.orchestrator.STATE_DIR', str(self.root)))
        self.stack.enter_context(patch('sys.stdin.isatty', return_value=False))
        self.stack.enter_context(patch.object(xola.JarvisHarness, 'record_task_to_memory'))

    def harness(self):
        harness = xola.JarvisHarness(inbox_dir=str(self.root / 'inbox'),
            outbox_dir=str(self.root / 'outbox'), ears_dir=str(self.root / 'ears'))
        harness.sentinel = Mock()
        return harness


class TestApprovalRepairs(IsolatedRuntime):
    def test_same_request_resumes_once(self):
        ok, qid = xola.gate_action('write report', 'task 1', auto_allow=False)
        self.assertFalse(ok)
        self.assertEqual(xola.gate_action('write report', 'task 1', False)[1], qid)
        approvals.answer(qid, 'yes')
        self.assertEqual(xola.gate_action('write report', 'task 1', False), (True, qid))
        self.assertFalse(xola.gate_action('write report', 'task 1', False)[0])

    def test_changed_args_do_not_share_approval(self):
        one = approvals.authorize_tool('hands.write', {'path': 'one'})
        approvals.answer(one['approval_id'], 'yes')
        two = approvals.authorize_tool('hands.write', {'path': 'two'})
        self.assertNotEqual(one['approval_id'], two['approval_id'])

    def test_concurrent_checks_reuse_one_question(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda _: approvals.request('same', 'scope'), range(20)))
        self.assertEqual(len({v[1] for v in values}), 1)
        self.assertEqual(len(approvals.read_records()), 1)

    def test_concurrent_consumption_executes_once(self):
        _, qid = approvals.request('same', 'scope')
        approvals.answer(qid, 'yes')
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            values = list(pool.map(lambda _: approvals.request('same', 'scope'), range(10)))
        self.assertEqual(sum(ok for ok, _ in values), 1)

    def test_high_stakes_ignore_auto_allow(self):
        write_json(approvals.AUTO_FILE, {'auto_allow': True})
        self.assertTrue(approvals.request('routine')[0])
        self.assertFalse(approvals.request('overwrite', high_stakes=True)[0])

    def test_explicit_denial(self):
        blocked = approvals.authorize_tool('hands.write', {'path': 'one'})
        approvals.answer(blocked['approval_id'], 'no')
        self.assertEqual(approvals.authorize_tool('hands.write', {'path': 'one'})['status'], 'DENIED')

    def test_red_skill_does_not_run_before_approval(self):
        calls = []
        reg = SkillRegistry('repair_test', audit_log_path=str(self.root / 'skills.log'))
        reg.register(Skill(name='sensitive', tier=Tier.RED, handler=lambda: calls.append(1)))
        blocked = reg.execute('sensitive')
        self.assertEqual(calls, [])
        approvals.answer(blocked['approval_id'], 'yes')
        self.assertEqual(reg.execute('sensitive')['status'], 'SUCCESS')
        self.assertEqual(calls, [1])

    def test_corrupt_approval_store_fails_closed(self):
        Path(approvals.PENDING_FILE).write_text('invalid json')
        with self.assertRaises(ValueError):
            approvals.request('write')


class TestExecutionRepairs(IsolatedRuntime):
    def test_hands_write_waits_and_verifies_bytes(self):
        hands = OSHands()
        path = self.root / 'report.txt'
        args = {'path': str(path), 'content': 'hello\nதமிழ்'}
        blocked = hands.execute_action('write', args)
        self.assertFalse(path.exists())
        approvals.answer(blocked['approval_id'], 'yes')
        result = hands.execute_action('write', args)
        self.assertTrue(result['verified'])
        self.assertEqual(path.read_text(), args['content'])
        self.assertEqual(len(result['sha256']), 64)

    def test_overwrite_requires_approval_even_with_auto_allow(self):
        path = self.root / 'report.txt'; path.write_text('old')
        write_json(approvals.AUTO_FILE, {'auto_allow': True})
        result = OSHands().execute_action('write', {'path': str(path), 'content': 'new'})
        self.assertEqual(result['status'], 'PENDING_APPROVAL')
        self.assertEqual(path.read_text(), 'old')

    def test_chain_resumes_without_repeating_completed_append(self):
        harness = self.harness()
        first = self.root / 'first.txt'; second = self.root / 'second.txt'
        task = xola.JarvisTask(task_id='chain1', action='chain', chain=[
            {'action': 'hands', 'skill': 'hands.write', 'args': {'path': str(first), 'content': 'one', 'append': True}},
            {'action': 'hands', 'skill': 'hands.write', 'args': {'path': str(second), 'content': 'two'}}])
        one = harness.execute_task(task)
        approvals.answer(one.result['approval_id'], 'yes')
        two = harness.execute_task(task)
        self.assertEqual(first.read_text(), 'one')
        approvals.answer(two.result['approval_id'], 'yes')
        final = harness.execute_task(task)
        self.assertEqual(final.status, 'SUCCESS')
        self.assertEqual(first.read_text(), 'one')
        self.assertEqual(second.read_text(), 'two')

    def test_read_summarize_save_pipeline(self):
        harness = self.harness()
        source = self.root / 'notes.txt'; target = self.root / 'summary.txt'
        source.write_text('Project: Xola. Next milestone: voice commands.')
        task = xola.JarvisTask(task_id='summary', action='chain', chain=[
            {'action': 'hands', 'skill': 'hands.read', 'args': {'path': str(source)}},
            {'action': 'auto', 'prompt': 'Summarize previous_result', 'args': {'_pipe_prev': True}},
            {'action': 'hands', 'skill': 'hands.write', 'args': {'path': str(target), '_pipe_prev': True}}])
        def planner(prompt, context=None, **kwargs):
            self.assertIn('voice commands', context['previous_result']['content'])
            return BrainPlan(prompt=prompt, action='answer', args={'text': 'Xola: finish voice commands.'})
        with patch.object(harness.brain, 'think', side_effect=planner) as model:
            blocked = harness.execute_task(task)
            self.assertEqual(blocked.status, 'PENDING_APPROVAL')
            approvals.answer(blocked.result['approval_id'], 'yes')
            result = harness.execute_task(task)
        self.assertEqual(result.status, 'SUCCESS')
        self.assertEqual(target.read_text(), 'Xola: finish voice commands.')
        self.assertEqual(model.call_count, 1)

    def test_pending_task_stays_in_inbox(self):
        harness = self.harness()
        path = harness.submit_task('hands.write', action='hands', args={'path': str(self.root / 'out.txt'), 'content': 'hello'})
        result = harness.process_single_task_file(path)
        self.assertEqual(result.status, 'PENDING_APPROVAL')
        self.assertTrue(Path(path).exists())
        approvals.answer(result.result['approval_id'], 'yes')
        self.assertEqual(harness.process_single_task_file(path).status, 'SUCCESS')
        self.assertFalse(Path(path).exists())

    def test_model_plan_is_stable_while_waiting_for_approval(self):
        brain = AutonomousBrain()
        path = self.root / 'result.txt'
        plan = BrainPlan(prompt='save', action='hands', skill='hands.write', args={'path': str(path), 'content': 'fixed plan'})
        with patch.object(brain, 'think', return_value=plan) as model:
            blocked = brain.think_and_execute('save')
            approvals.answer(blocked.output['approval_id'], 'yes')
            result = brain.think_and_execute('save')
        self.assertEqual(model.call_count, 1)
        self.assertEqual(result.status, 'SUCCESS')
        self.assertEqual(path.read_text(), 'fixed plan')

    def test_unknown_request_is_not_success(self):
        result = AutonomousBrain().execute_plan(BrainPlan(prompt='unknown', action='echo'))
        self.assertEqual(result.status, 'UNSUPPORTED')

    def test_hands_aliases_reach_the_approval_gate(self):
        for action in ('kill', 'spawn', 'focus'):
            with self.subTest(action=action):
                self.assertEqual(OSHands().execute_action(action, {})['status'], 'PENDING_APPROVAL')

    def test_process_fallback_without_ps(self):
        if not Path('/proc').is_dir():
            self.skipTest('Linux /proc test')
        with patch('jarvis.hands.subprocess.run', side_effect=FileNotFoundError):
            processes = list_processes(limit=200)
            self.assertTrue(processes)
            self.assertTrue(all(p.pid > 0 and p.name for p in processes))
            selected = list_processes(filter_name=processes[0].name, limit=200)
            self.assertTrue(selected)
            self.assertTrue(all(processes[0].name.lower() in p.name.lower() for p in selected))


class TestDAGRepairs(IsolatedRuntime):
    def test_real_worker_reads_file(self):
        path = self.root / 'input.txt'; path.write_text('actual bytes')
        dag = DAGPlan(); dag.add_node(DAGNode('read', 'hands.read', {'path': str(path)}))
        result = CoreOrchestrator().dispatch_dag(dag)
        self.assertEqual(result['status'], 'COMPLETE')
        self.assertEqual(result['results']['read']['output']['content'], 'actual bytes')

    def test_missing_dependency_rejected(self):
        dag = DAGPlan(); dag.add_node(DAGNode('one', 'echo', dependencies={'missing'}))
        with self.assertRaises(ValueError): CoreOrchestrator().dispatch_dag(dag)

    def test_failed_parent_blocks_child(self):
        dag = DAGPlan(); dag.add_node(DAGNode('bad', 'hands.read', {'path': str(self.root / 'missing')}))
        dag.add_node(DAGNode('child', 'echo', dependencies={'bad'}))
        result = CoreOrchestrator().dispatch_dag(dag)
        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(dag.nodes['child'].state, TaskState.ABORTED)

    def test_timeout_is_failure(self):
        dag = DAGPlan(); dag.add_node(DAGNode('one', 'echo'))
        with patch('tools.orchestrator.subprocess.run', side_effect=subprocess.TimeoutExpired('worker', .01)):
            result = CoreOrchestrator().dispatch_dag(dag, .01)
        self.assertEqual(result['status'], 'FAILED')

    def test_reuse_orchestrator_with_fresh_dag(self):
        orch = CoreOrchestrator()
        for text in ('first', 'second'):
            dag = DAGPlan(); dag.add_node(DAGNode(text, 'echo', {'text': text}))
            result = orch.dispatch_dag(dag)
            self.assertEqual(result['status'], 'COMPLETE')
            self.assertEqual(list(result['results']), [text])

    def test_duplicate_node_rejected(self):
        dag = DAGPlan(); dag.add_node(DAGNode('one', 'echo'))
        with self.assertRaises(ValueError): dag.add_node(DAGNode('one', 'echo'))


class TestVoiceMemoryScreenRepairs(IsolatedRuntime):
    def test_voice_request_becomes_executable_inbox_task(self):
        harness = self.harness()
        harness.ears.enqueue('check disk space', source='mic_command')
        harness.process_pending_inbox()
        tasks = list((self.root / 'inbox').glob('*.json'))
        self.assertEqual(len(tasks), 1)
        payload = json.loads(tasks[0].read_text())
        self.assertEqual(payload['action'], 'auto')
        self.assertEqual(payload['prompt'], 'check disk space')
        self.assertTrue(payload['args']['speak_response'])

    def test_voice_delivery_failure_retains_utterance(self):
        queue = EarsQueue(str(self.root / 'ears')); queue.enqueue('do something')
        def fail(_): raise IOError('queue unavailable')
        queue.process_queue(fail)
        self.assertEqual(len(queue.list_pending()), 1)

    def test_memory_returns_values_and_excludes_secrets(self):
        vault.remember('project milestone', 'complete voice pipeline')
        vault.remember('project secret', 'hidden', secret=True, passphrase='test-passphrase')
        rows = vault.recall('project', min_cos=.01)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['value'], 'complete voice pipeline')

    def test_memory_reaches_model_context(self):
        vault.remember('Xola milestone', 'voice capture')
        brain = AutonomousBrain()
        with patch.object(brain.agy_bridge, 'is_available', return_value=True), patch.object(
                brain.agy_bridge, 'plan_with_agy', return_value=BrainPlan('Xola milestone', 'answer', args={'text': 'voice capture'})) as model:
            brain.think('Xola milestone')
        self.assertEqual(model.call_args.kwargs['context']['relevant_memories'][0]['value'], 'voice capture')

    def test_missing_ocr_is_explicit(self):
        path = self.root / 'screen.png'; path.write_bytes(b'fixture')
        with patch('tools.runtime.screen_context.shutil.which', return_value=None), patch.dict(os.environ, {'XOLA_TESSERACT_BIN': ''}):
            self.assertEqual(observe_screen(str(path))['status'], 'UNSUPPORTED')

    def test_ocr_uses_observed_text(self):
        path = self.root / 'screen.png'; path.write_bytes(b'fixture')
        with patch('tools.runtime.screen_context.shutil.which', return_value='tesseract'), patch(
                'tools.runtime.screen_context.subprocess.run', return_value=subprocess.CompletedProcess([], 0, 'Editor: notes.txt', '')):
            result = observe_screen(str(path))
        self.assertEqual(result['text'], 'Editor: notes.txt')
        self.assertTrue(result['untrusted_content'])

    def test_non_windows_voice_reports_unsupported(self):
        with patch('jarvis.voice.sys.platform', 'linux'):
            self.assertEqual(VoiceEngine().speak('hello', log=False)['status'], 'UNSUPPORTED')


class TestLocalServerBoundaries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        res = conn.getresponse(); status = res.status; res.read(); conn.close(); return status

    def test_source_file_is_not_served(self):
        self.assertEqual(self.request('GET', '/xola.py'), 404)
        self.assertEqual(self.request('HEAD', '/tools/vault.py'), 404)

    def test_cross_origin_task_rejected(self):
        self.assertEqual(self.request('POST', '/api/tasks', '{"task":"test"}',
            {'Content-Type': 'application/json', 'Origin': 'https://untrusted.example'}), 403)

    def test_invalid_host_rejected(self):
        self.assertEqual(self.request('GET', '/api/health', headers={'Host': 'untrusted.example'}), 403)

    def test_non_object_json_rejected(self):
        self.assertEqual(self.request('POST', '/api/tasks', '[]', {'Content-Type': 'application/json'}), 400)

    def test_oversized_body_rejected(self):
        self.assertEqual(self.request('POST', '/api/tasks', '{}', {'Content-Type': 'application/json', 'Content-Length': '100000'}), 413)


if __name__ == '__main__':
    unittest.main()
