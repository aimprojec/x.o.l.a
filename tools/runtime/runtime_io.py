"""Atomic persistence and cross-process file transactions. 🦋"""
import contextlib
import json
import os
import tempfile
import threading

_LOCK = threading.RLock()


def atomic_write(path, content, encoding='utf-8'):
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.xola-', dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, 'w', encoding=encoding, newline='') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path, data):
    atomic_write(path, json.dumps(data, indent=2, ensure_ascii=False))


@contextlib.contextmanager
def transaction(path):
    """Serialize read/modify/write across threads and cooperating processes."""
    with _LOCK:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(str(path) + '.lock', 'a+b') as lock:
            lock.seek(0, 2)
            if not lock.tell():
                lock.write(b'0')
                lock.flush()
            lock.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                lock.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock, fcntl.LOCK_UN)
