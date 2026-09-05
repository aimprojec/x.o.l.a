#!/usr/bin/env python3
"""tests/test_upgrades.py — Regression tests for the 100x upgrade pack 🦋

Covers:
1. Guard incremental audit cache (warm reuse + edit invalidation + bypass)
2. Guard dotfile collection hygiene
3. Server API TTL cache helper semantics
4. Cross-platform disk_space mount fallback
Pure stdlib. Zero external dependencies. 🦋
"""

import io
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

# Ensure project root in sys.path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(TESTS_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools import guard  # noqa: E402
import server  # noqa: E402
from jarvis.hands import disk_space  # noqa: E402

WATERMARK = "🦋"


class TestGuardAuditCache(unittest.TestCase):
    """Verify the incremental .guard_cache.json accelerator 🦋"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="xola_guard_cache_")
        self.good = os.path.join(self.tmp, "good_tool.py")
        with open(self.good, "w", encoding="utf-8") as f:
            f.write(
                '#!/usr/bin/env python3\n'
                '"""Usage: python good_tool.py [--json] # xola-good: cache test 🦋"""\n'
                "import argparse\n"
                "import sys\n"
                "\n"
                'WATERMARK = "🦋"\n'
                "\n"
                "if __name__ == '__main__':\n"
                "    sys.exit(0)\n"
            )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_warm_cache_reuses_results(self):
        """Second audit of unchanged files hits the cache with identical verdict 🦋"""
        r1 = guard.audit(self.tmp, strict=False, fix=False, smoke=False)
        self.assertEqual(r1["summary"]["cache_hits"], 0)
        r2 = guard.audit(self.tmp, strict=False, fix=False, smoke=False)
        self.assertEqual(r2["verdict"], r1["verdict"])
        self.assertEqual(r2["summary"]["cache_hits"], r1["summary"]["files_scanned"])
        self.assertTrue(os.path.exists(os.path.join(self.tmp, guard.AUDIT_CACHE_FILENAME)))

    def test_cache_invalidated_on_edit(self):
        """Editing a file must re-audit it and surface the new finding 🦋"""
        r1 = guard.audit(self.tmp, strict=False, fix=False, smoke=False)
        self.assertEqual(r1["verdict"], "PASS")

        # Corrupt the file: syntax error + missing watermark → re-audit sees it
        with open(self.good, "w", encoding="utf-8") as f:
            f.write("def broken(:\n    pass\n")
        # Force a distinct mtime tick so coarse filesystems invalidate too
        stat_before = os.stat(self.good)
        os.utime(self.good, ns=(stat_before.st_atime_ns, stat_before.st_mtime_ns + 1_000_000))

        r2 = guard.audit(self.tmp, strict=False, fix=False, smoke=False)
        self.assertEqual(r2["summary"]["cache_hits"], 0)
        self.assertEqual(r2["verdict"], "KILL")

    def test_no_cache_bypass(self):
        """use_cache=False must recompute every file and leave no cache hits 🦋"""
        guard.audit(self.tmp, strict=False, fix=False, smoke=False)
        r = guard.audit(self.tmp, strict=False, fix=False, smoke=False, use_cache=False)
        self.assertEqual(r["summary"]["cache_hits"], 0)

    def test_dotfiles_never_collected(self):
        """Hidden dotfiles (incl. the cache itself) are excluded from audits 🦋"""
        dotfile = os.path.join(self.tmp, ".hidden_broken.json")
        with open(dotfile, "w", encoding="utf-8") as f:
            f.write('{"not": "audited"}')
        files = guard.collect_files(self.tmp)
        self.assertNotIn(os.path.abspath(dotfile), files)
        self.assertFalse(any(os.path.basename(p).startswith(".") for p in files))


class TestServerTTLCache(unittest.TestCase):
    """Verify the _cached_json dashboard accelerator 🦋"""

    def setUp(self):
        server._API_CACHE.clear()

    def test_miss_then_hit(self):
        """First call produces, second call within TTL serves from cache 🦋"""
        calls = {"n": 0}

        def produce():
            calls["n"] += 1
            return {"value": 42, "mark": WATERMARK}

        a = server._cached_json("unit", 60.0, produce)
        b = server._cached_json("unit", 60.0, produce)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(a["value"], b["value"])
        self.assertFalse(a["cache"]["hit"])
        self.assertTrue(b["cache"]["hit"])
        self.assertGreaterEqual(b["cache"]["age_s"], 0.0)

    def test_expired_entry_recomputed(self):
        """After the TTL window elapses the producer runs again 🦋"""
        calls = {"n": 0}

        def produce():
            calls["n"] += 1
            return {"n": calls["n"], "mark": WATERMARK}

        server._cached_json("unit2", -1.0, produce)  # already expired
        server._cached_json("unit2", -1.0, produce)
        self.assertEqual(calls["n"], 2)

    def test_distinct_keys_isolated(self):
        """Different cache keys never cross-contaminate 🦋"""
        server._cached_json("k1", 60.0, lambda: {"who": "k1", "mark": WATERMARK})
        out = server._cached_json("k2", 60.0, lambda: {"who": "k2", "mark": WATERMARK})
        self.assertEqual(out["who"], "k2")


class TestDiskSpaceCrossPlatform(unittest.TestCase):
    """Verify disk_space mount fallback keeps autonomous queries alive 🦋"""

    def test_invalid_drive_falls_back(self):
        """A bogus drive on POSIX resolves to the primary mount, not an error 🦋"""
        if sys.platform == "win32":
            self.skipTest("POSIX fallback path only")
        res = disk_space("Q:")
        self.assertIn("total_gb", res)
        self.assertIn("free_gb", res)
        self.assertNotIn("error", res)
        self.assertEqual(res["mount"], "/")

    def test_valid_mount_reported(self):
        """A real mount path is reported back with a mount field 🦋"""
        target = os.sep
        res = disk_space(target)
        self.assertIn("total_gb", res)
        self.assertEqual(res.get("mount"), target)
        self.assertEqual(res.get("mark"), WATERMARK)


if __name__ == "__main__":
    unittest.main()
