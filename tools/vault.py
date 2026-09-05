#!/usr/bin/env python3
"""Usage: python vault.py [--smoke] [--json] # X.O.L.A. Memory Vault 🦋

Layer 2 (todo items 26-55): three-tier memory — ephemeral dict (working),
JSONL episodic log, SQLite semantic vault — plus decay, dedup, deprecation,
conflict resolve, snapshots, purge, encryption-at-rest (keystream+HMAC),
migrations, verification, relevance prune, thresholding, benchmarks.
Pure stdlib (sqlite3). No keys. Base on D. 🦋
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WATERMARK = "🦋"
BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "loop", "lh10", "vault")
DB = os.path.join(BASE, "vault.db")
EPISODIC = os.path.join(BASE, "episodic.jsonl")
SNAPDIR = os.path.join(BASE, "snapshots")
SCHEMA_V = 2

# 42: working-memory scratchpad (tier 0) 🦋
scratchpad: Dict[str, Any] = {}


def _db(ro: bool = False) -> sqlite3.Connection:
    """55: read-only sandbox connections for analytics."""
    os.makedirs(BASE, exist_ok=True)
    if ro:
        uri = "file:" + DB.replace("\\", "/") + "?mode=ro"
        return sqlite3.connect(uri, uri=True)
    cx = sqlite3.connect(DB)
    cx.execute("PRAGMA journal_mode=WAL")
    return cx


# 46: forward-only migrations 🦋
MIGRATIONS = {
    1: ["CREATE TABLE IF NOT EXISTS facts(key TEXT PRIMARY KEY, value TEXT, "
        "tag TEXT, conf REAL, updated REAL, superseded_by TEXT, verify_due REAL)"],
    2: ["CREATE TABLE IF NOT EXISTS prefs(key TEXT PRIMARY KEY, value TEXT)",
        "CREATE INDEX IF NOT EXISTS idx_facts_updated ON facts(updated)"],
}


def migrate() -> int:
    cx = _db()
    try:
        try:
            v = cx.execute("PRAGMA user_version").fetchone()[0]
        except Exception:
            v = 0
        for ver in sorted(MIGRATIONS):
            if ver > v:
                for sql in MIGRATIONS[ver]:
                    cx.execute(sql)
                cx.execute(f"PRAGMA user_version={ver}")
        cx.commit()
        return cx.execute("PRAGMA user_version").fetchone()[0]
    finally:
        cx.close()


# 45: encryption at rest — SHA-256 keystream + HMAC (stdlib, no AES) 🦋
def _keystream(key: bytes, nonce: bytes, n: int) -> bytes:
    out = b""
    i = 0
    while len(out) < n:
        out += hashlib.sha256(key + nonce + i.to_bytes(4, "big")).digest()
        i += 1
    return out[:n]


def seal(secret: str, passphrase: str) -> str:
    nonce = os.urandom(8)
    key = hashlib.sha256(passphrase.encode()).digest()
    raw = secret.encode()
    ct = bytes(a ^ b for a, b in zip(raw, _keystream(key, nonce, len(raw))))
    tag = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return base64.b64encode(nonce + tag + ct).decode()


def unseal(blob: str, passphrase: str) -> str:
    data = base64.b64decode(blob.encode())
    nonce, tag, ct = data[:8], data[8:40], data[40:]
    key = hashlib.sha256(passphrase.encode()).digest()
    if not hmac.compare_digest(tag, hmac.new(key, nonce + ct, hashlib.sha256).digest()):
        raise ValueError("HMAC mismatch — wrong passphrase or tampered")
    ks = _keystream(key, nonce, len(ct))
    return bytes(a ^ b for a, b in zip(ct, ks)).decode()


# 26/32: three-tier write with explicit/inferred tag 🦋
def remember(key: str, value: str, tag: str = "explicit", conf: float = 1.0,
             secret: bool = False, passphrase: str = "") -> dict:
    migrate()
    if secret:
        value = "sealed:" + seal(value, passphrase)
    cx = _db()
    try:
        cx.execute("INSERT OR REPLACE INTO facts(key,value,tag,conf,updated,superseded_by,verify_due)"
                   " VALUES(?,?,?,?,?,?,?)",
                   (key, value, tag, conf, time.time(), None, time.time() + 90 * 86400))
        cx.commit()
    finally:
        cx.close()
    episodic({"event": "remember", "key": key, "tag": tag})  # 28
    return {"key": key, "tag": tag, "mark": WATERMARK}


# 28: append-only episodic JSONL 🦋
def episodic(event: dict) -> None:
    os.makedirs(BASE, exist_ok=True)
    event = dict(event)
    event.setdefault("ts", time.time())
    # 39: temporal index — epoch + UTC + calendar 🦋
    event["utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(event["ts"]))
    with open(EPISODIC, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


# 30/51: cosine store over token sets + strict threshold 🦋
def _vec(text: str) -> Dict[str, int]:
    v: Dict[str, int] = {}
    for w in re.findall(r"[^\W_]{2,}", text.lower(), re.UNICODE):
        if w in {"the", "a", "an", "is", "to", "of", "and", "my", "what", "are", "me"}:
            continue
        v[w] = v.get(w, 0) + 1
    return v


def _cos(a: Dict[str, int], b: Dict[str, int]) -> float:
    dot = sum(a[w] * b.get(w, 0) for w in a)
    na = sum(x * x for x in a.values()) ** 0.5
    nb = sum(x * x for x in b.values()) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def recall(query: str, limit: int = 5, min_cos: float = 0.2) -> List[dict]:
    migrate()
    cx = _db(ro=True)
    try:
        rows = cx.execute("SELECT key,value,tag,conf FROM facts WHERE superseded_by IS NULL").fetchall()
    finally:
        cx.close()
    q = _vec(query)
    scored = [(k, _cos(q, _vec(k + " " + v)), t, c, v) for k, v, t, c in rows if not v.startswith("sealed:")]
    # 48: relevance prune against immediate prompt 🦋
    return [{"key": k, "score": round(s, 3), "tag": t, "conf": c, "value": v}
            for k, s, t, c, v in sorted(scored, key=lambda r: r[1], reverse=True)
            if s >= min_cos][:limit]


# 29: deprecation pointer / 36: conflict resolver (newer explicit wins) 🦋
def deprecate(key: str, by: str) -> dict:
    migrate()
    cx = _db()
    try:
        cx.execute("UPDATE facts SET superseded_by=? WHERE key=?", (by, key))
        cx.commit()
        return {"key": key, "superseded_by": by, "mark": WATERMARK}
    finally:
        cx.close()


def resolve(key: str, value: str, tag: str = "explicit") -> dict:
    old = recall(key, limit=1, min_cos=0.0)
    if old and tag == "explicit":
        deprecate(key, key + "#new")
    return remember(key, value, tag)


# 31: decay for unconfirmed inferred facts 🦋
def decay(now: Optional[float] = None) -> int:
    migrate()
    now = now or time.time()
    cx = _db()
    try:
        rows = cx.execute("SELECT key,conf,updated FROM facts WHERE tag='inferred'").fetchall()
        n = 0
        for k, c, u in rows:
            age_days = (now - u) / 86400
            nc = round(c * max(0.0, 1.0 - 0.05 * age_days), 3)
            if nc != c:
                cx.execute("UPDATE facts SET conf=? WHERE key=?", (nc, k))
                n += 1
        cx.commit()
        return n
    finally:
        cx.close()


# 47: verification engine — re-confirm after 90d 🦋
def due_for_verify() -> List[str]:
    migrate()
    cx = _db(ro=True)
    try:
        return [r[0] for r in cx.execute("SELECT key FROM facts WHERE verify_due < ?", (time.time(),))]
    finally:
        cx.close()


# 33: graph traversal — related keys share tokens 🦋
def traverse(key: str, depth: int = 2) -> Dict[str, List[str]]:
    seen = {key}
    frontier = [key]
    for _ in range(depth):
        nxt = []
        for k in frontier:
            for r in recall(k, limit=5, min_cos=0.15):
                if r["key"] not in seen:
                    seen.add(r["key"])
                    nxt.append(r["key"])
        frontier = nxt
    seen.discard(key)
    return {"from": key, "related": sorted(seen), "mark": WATERMARK}


# 38: entity linker — aliases to canonical id 🦋
ALIASES = {"xola": "xola", "alox": "alox", "jarvis": "jarvis", "lh10": "lh10"}


def link_entity(text: str) -> List[str]:
    found = []
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9_-]{2,}", text):
        w = m.group(0).lower()
        if w in ALIASES and ALIASES[w] not in found:
            found.append(ALIASES[w])
    return found


# 34: hydration — rebuild working state from disk 🦋
def hydrate() -> dict:
    migrate()
    cx = _db(ro=True)
    try:
        facts = cx.execute("SELECT COUNT(*) FROM facts WHERE superseded_by IS NULL").fetchone()[0]
        prefs = cx.execute("SELECT COUNT(*) FROM prefs").fetchone()[0]
    finally:
        cx.close()
    try:
        with open(EPISODIC, encoding="utf-8") as fh:
            eps = sum(1 for _ in fh)
    except Exception:
        eps = 0
    return {"facts": facts, "prefs": prefs, "episodic_events": eps, "mark": WATERMARK}


# 37: snapshot/restore 🦋
def snapshot() -> str:
    os.makedirs(SNAPDIR, exist_ok=True)
    migrate()
    fn = os.path.join(SNAPDIR, f"snap_{time.strftime('%Y%m%d_%H%M%S')}.json")
    cx = _db(ro=True)
    try:
        facts = [dict(zip(["key", "value", "tag", "conf", "updated", "superseded_by", "verify_due"],
                           r)) for r in cx.execute("SELECT * FROM facts")]
    finally:
        cx.close()
    with open(fn, "w", encoding="utf-8") as fh:
        json.dump({"facts": facts, "ts": time.time(), "mark": WATERMARK}, fh, ensure_ascii=False)
    return fn


# 40: selective purge / 44: dedup / 43: vacuum 🦋
def purge(key_or_prefix: str) -> int:
    migrate()
    cx = _db()
    try:
        cur = cx.execute("DELETE FROM facts WHERE key=? OR key LIKE ?", (key_or_prefix, key_or_prefix + "%"))
        cx.commit()
        return cur.rowcount
    finally:
        cx.close()


def dedup_episodic() -> Dict[str, int]:
    try:
        with open(EPISODIC, encoding="utf-8") as fh:
            lines = fh.readlines()
    except Exception:
        return {"before": 0, "after": 0}
    seen: Dict[str, int] = {}
    for l in lines:
        seen[l] = seen.get(l, 0) + 1
    with open(EPISODIC, "w", encoding="utf-8") as fh:
        for l, c in seen.items():
            fh.write(l if c == 1 else l.rstrip("\n") + f' //x{c}\n')
    return {"before": len(lines), "after": len(seen)}


def vacuum() -> None:
    cx = _db()
    try:
        cx.execute("VACUUM")
        cx.commit()
    finally:
        cx.close()


# 49: preference registry 🦋
def set_pref(key: str, value: str) -> dict:
    migrate()
    cx = _db()
    try:
        cx.execute("INSERT OR REPLACE INTO prefs(key,value) VALUES(?,?)", (key, value))
        cx.commit()
        return {"key": key, "mark": WATERMARK}
    finally:
        cx.close()


# 54: retrieval benchmark 🦋
def benchmark(n: int = 200) -> Dict[str, float]:
    t0 = time.perf_counter()
    for i in range(n):
        recall("test query benchmark", limit=3)
    dt = (time.perf_counter() - t0) / n * 1000
    return {"avg_lookup_ms": round(dt, 2), "n": n, "mark": WATERMARK}


def smoke() -> Dict[str, Any]:
    os.makedirs(BASE, exist_ok=True)
    c: Dict[str, Any] = {}
    c["migrate_v"] = migrate()
    remember("smoke_fact", "vault works", tag="explicit")
    remember("smoke_guess", "maybe", tag="inferred", conf=0.6)
    c["recall"] = recall("vault works")
    c["resolve"] = resolve("smoke_fact", "vault works v2")["key"]
    c["decay_n"] = decay()
    c["traverse"] = traverse("smoke_fact")["related"]
    c["link"] = link_entity("xola and jarvis built lh10")
    scratchpad["tmp"] = 1
    c["scratch"] = scratchpad.get("tmp")
    blob = seal("s3cret", "pw")
    c["seal_ok"] = unseal(blob, "pw") == "s3cret"
    set_pref("tone", "blunt")
    c["hydrate"] = hydrate()
    c["snap"] = os.path.basename(snapshot())
    c["dedup"] = dedup_episodic()
    c["bench_ms"] = benchmark(50)["avg_lookup_ms"]
    c["due"] = due_for_verify()
    vacuum()
    c["purged"] = purge("smoke_")
    c["mark"] = WATERMARK
    passed = (c["recall"] and c["recall"][0]["key"] == "smoke_fact" and c["seal_ok"]
              and c["scratch"] == 1 and c["migrate_v"] == SCHEMA_V)
    c["smoke"] = "PASS" if passed else "FAIL"
    return c


def main() -> int:
    ap = argparse.ArgumentParser(description="X.O.L.A. Memory Vault 🦋")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    res = smoke()
    print(json.dumps(res, indent=2, ensure_ascii=False) if args.json else
          f"🦋 Vault smoke: {res['smoke']} 🦋")
    return 0 if res["smoke"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
