#!/usr/bin/env python3
"""Usage: python -m unittest tests/test_conversation.py # Tests for the Jarvis conversational shell 🦋"""

import json
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from jarvis import conversation as convo_mod
from jarvis.conversation import FactStore, JarvisConversation, handle_chat_request

WATERMARK = "🦋"


class TestFactStore(unittest.TestCase):
    """Fact book persistence and recall 🦋"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "facts.json")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_remember_and_recall(self):
        store = FactStore(self.path)
        norm = store.remember("deploy key", "blue")
        self.assertTrue(norm)
        hits = store.recall("what is my deploy key")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["value"], "blue")

    def test_recall_miss_returns_empty(self):
        store = FactStore(self.path)
        self.assertEqual(store.recall("something never stored"), [])

    def test_forget(self):
        store = FactStore(self.path)
        store.remember("tempest", "storm")
        self.assertTrue(store.forget("the tempest"))
        self.assertEqual(store.recall("tempest"), [])

    def test_persists_across_instances(self):
        FactStore(self.path).remember("captain", "Alox")
        hits = FactStore(self.path).recall("captain")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["value"], "Alox")


class TestConversationBasics(unittest.TestCase):
    """Small talk, identity, help, session control 🦋"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.convo = JarvisConversation(
            fact_path=os.path.join(self.tmp, "facts.json"), use_llm=False)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_greeting(self):
        out = self.convo.reply("hello jarvis")
        self.assertEqual(out["status"], "SUCCESS")
        self.assertIn("sir", out["response"].lower())
        self.assertEqual(out["mark"], WATERMARK)

    def test_identity(self):
        out = self.convo.reply("who are you?")
        self.assertEqual(out["status"], "SUCCESS")
        self.assertIn("Jarvis", out["response"])

    def test_help(self):
        out = self.convo.reply("help")
        self.assertEqual(out["status"], "SUCCESS")
        self.assertIn("Status", out["response"])

    def test_empty_prompt(self):
        out = self.convo.reply("   ")
        self.assertEqual(out["status"], "ERROR")

    def test_farewell_ends_session(self):
        out = self.convo.reply("bye")
        self.assertEqual(out["status"], "SUCCESS")
        self.assertTrue(out.get("end_session"))

    def test_thanks(self):
        out = self.convo.reply("thanks!")
        self.assertEqual(out["status"], "SUCCESS")

    def test_time(self):
        out = self.convo.reply("what time is it?")
        self.assertEqual(out["status"], "SUCCESS")

    def test_unknown_is_graceful(self):
        out = self.convo.reply("blorp snorp zzz")
        self.assertIn(out["status"], ("SUCCESS", "PROPOSED"))
        self.assertTrue(out["response"].strip())

    def test_history_grows(self):
        self.convo.reply("hello")
        self.convo.reply("help")
        self.assertGreaterEqual(len(self.convo.history), 4)


class TestConversationMemory(unittest.TestCase):
    """Remember / recall / forget through the dialogue loop 🦋"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.convo = JarvisConversation(
            fact_path=os.path.join(self.tmp, "facts.json"), use_llm=False)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_remember_recall_roundtrip(self):
        out = self.convo.reply("remember that the deploy key is blue")
        self.assertEqual(out["status"], "SUCCESS")
        out2 = self.convo.reply("what is my deploy key?")
        self.assertEqual(out2["status"], "SUCCESS")
        self.assertIn("blue", out2["response"])

    def test_my_form_remember(self):
        self.convo.reply("my ship is called the Ember")
        out = self.convo.reply("recall ship")
        self.assertIn("ember", out["response"].lower())

    def test_forget_flow(self):
        self.convo.reply("remember that the code is 1234")
        out = self.convo.reply("forget the code")
        self.assertEqual(out["status"], "SUCCESS")
        out2 = self.convo.reply("what is my code?")
        self.assertNotIn("1234", out2["response"])


class TestConversationSafety(unittest.TestCase):
    """Mutations are proposed, never executed from chat 🦋"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.convo = JarvisConversation(
            fact_path=os.path.join(self.tmp, "facts.json"), use_llm=False)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_kill_is_proposed_not_executed(self):
        out = self.convo.reply("kill process 1234")
        self.assertEqual(out["status"], "PROPOSED")
        self.assertFalse(out["executed"])
        self.assertIsNotNone(self.convo.pending)

    def test_write_is_proposed_and_no_file_created(self):
        target = os.path.join(self.tmp, "should_not_exist.txt")
        out = self.convo.reply(f"write file {target} with hello")
        self.assertEqual(out["status"], "PROPOSED")
        self.assertFalse(os.path.exists(target))

    def test_proceed_reexplains_gate(self):
        self.convo.reply("kill process 1234")
        out = self.convo.reply("proceed")
        self.assertEqual(out["status"], "PROPOSED")
        self.assertIn("gate", out["response"].lower())

    def test_proceed_with_nothing_pending(self):
        out = self.convo.reply("proceed")
        self.assertEqual(out["status"], "SUCCESS")


class TestConversationReads(unittest.TestCase):
    """Read-only machine queries execute offline via heuristics 🦋"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.convo = JarvisConversation(
            fact_path=os.path.join(self.tmp, "facts.json"), use_llm=False)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_disk_query_executes(self):
        out = self.convo.reply("how much disk space is free?")
        self.assertEqual(out["status"], "SUCCESS")
        self.assertTrue(out["executed"])

    def test_process_list_executes(self):
        out = self.convo.reply("list running processes")
        self.assertEqual(out["status"], "SUCCESS")
        self.assertTrue(out["executed"])

    def test_status_brief(self):
        out = self.convo.reply("give me a status report")
        self.assertEqual(out["status"], "SUCCESS")
        self.assertIn("CPU", out["response"])


class TestChatRequestHandler(unittest.TestCase):
    """HTTP plumbing validation for /api/jarvis/chat 🦋"""

    def test_rejects_non_dict(self):
        code, payload = handle_chat_request("hello")
        self.assertEqual(code, 400)

    def test_rejects_empty_prompt(self):
        code, _ = handle_chat_request({"prompt": "   "})
        self.assertEqual(code, 400)

    def test_accepts_prompt(self):
        path = os.path.join(tempfile.mkdtemp(), "facts.json")
        code, payload = handle_chat_request(
            {"prompt": "hello", "session": "test-basic"}, fact_path=path)
        self.assertEqual(code, 200)
        self.assertIn("response", payload)
        self.assertEqual(payload["mark"], WATERMARK)


if __name__ == "__main__":
    unittest.main()
