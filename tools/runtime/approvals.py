"""Persistent, one-use approval records shared by all agent dispatchers. 🦋"""
import contextvars
import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from tools.runtime.runtime_io import transaction, write_json

ROOT = Path(__file__).resolve().parents[2]
PENDING_FILE = str(ROOT / 'loop' / 'pending_questions.json')
AUTO_FILE = str(ROOT / 'loop' / 'auto_allow.json')
SCOPE = contextvars.ContextVar('xola_approval_scope', default='manual')


def read_records(path=None):
    try:
        with open(path or PENDING_FILE, encoding='utf-8') as stream:
            data = json.load(stream)
        if not isinstance(data, dict):
            raise ValueError('Invalid approval store')
        return data
    except FileNotFoundError:
        return {}


def auto_enabled():
    try:
        with open(AUTO_FILE, encoding='utf-8') as stream:
            return json.load(stream).get('auto_allow') is True
    except (OSError, ValueError):
        return False


def request(description, context='', *, high_stakes=False, auto_allow=None, path=None):
    path = path or PENDING_FILE
    if not high_stakes and (auto_enabled() if auto_allow is None else auto_allow):
        return True, None
    fingerprint = hashlib.sha256(json.dumps([description, context], ensure_ascii=False).encode()).hexdigest()
    with transaction(path):
        records = read_records(path)
        for qid, entry in records.items():
            if entry.get('fingerprint') != fingerprint or entry.get('consumed_at'):
                continue
            if time.time() - entry.get('created_ts', 0) > 86400:
                continue
            answer = str(entry.get('answer') or '').lower().strip()
            if answer in ('yes', 'allow', 'y', 'approve'):
                entry['consumed_at'] = time.time()
                write_json(path, records)
                return True, qid
            return False, qid
        qid = uuid.uuid4().hex[:12]
        records[qid] = dict(id=qid, fingerprint=fingerprint, description=description,
                            question=('HIGH-STAKES: ' if high_stakes else '') + description,
                            context=context, created_ts=time.time(), answer=None,
                            high_stakes=high_stakes)
        write_json(path, records)
        return False, qid


def answer(qid, value, path=None):
    value = value.strip().lower()
    if value not in ('yes', 'allow', 'y', 'approve', 'no', 'deny', 'n', 'reject'):
        raise ValueError('Answer must be yes or no')
    path = path or PENDING_FILE
    with transaction(path):
        records = read_records(path)
        if qid not in records:
            raise ValueError('Unknown approval ID')
        if records[qid].get('consumed_at'):
            raise ValueError('Approval already consumed')
        records[qid].update(answer=value, answered_at=time.time())
        write_json(path, records)


def authorize_tool(name, args, *, high_stakes=False):
    description = name + ' ' + json.dumps(args, sort_keys=True, ensure_ascii=False)
    allowed, qid = request(description, SCOPE.get(), high_stakes=high_stakes)
    if allowed:
        return None
    records = read_records()
    denied = str(records.get(qid, {}).get('answer') or '').lower() in ('no', 'deny', 'n', 'reject')
    status = 'DENIED' if denied else 'PENDING_APPROVAL'
    return {'status': status, 'approval_id': qid,
            'error': f'{status}: {name}. Review with --pending; answer with --answer {qid} yes|no.'}
