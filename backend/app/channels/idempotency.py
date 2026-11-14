"""Telegram update de-duplication and per-chat serialisation.

Telegram may deliver the same update more than once (webhook retries when a response is slow, or a re-sent
update after a timeout), and a customer can send two messages quickly. Without protection both of these produce
duplicate answers or interleaved conversation state.

  UpdateDeduper.claim(key)   atomic "first one wins": True for the first caller, False for every duplicate
  UpdateDeduper.release(key) a failed attempt gives the key back so Telegram's retry is processed, not dropped
  ChatLocks.guard(chat_id)   one message per chat is processed at a time, so state is loaded after the previous
                             turn has finished and a second identical delivery cannot race the first

Scope: in-process (a single API / bot process). Running several webhook workers needs a shared store (Redis
SET NX with a TTL) behind the same two-method interface.
"""
import threading
import time
from collections import OrderedDict
from contextlib import contextmanager


class UpdateDeduper:
    def __init__(self, ttl_seconds: int = 3600, max_entries: int = 20000) -> None:
        self._lock = threading.Lock()
        self._seen: OrderedDict[str, float] = OrderedDict()
        self.ttl, self.max_entries = ttl_seconds, max_entries

    def claim(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            ts = self._seen.get(key)
            if ts is not None and now - ts < self.ttl:
                return False
            self._seen[key] = now
            self._seen.move_to_end(key)
            while len(self._seen) > self.max_entries:
                self._seen.popitem(last=False)
            return True

    def release(self, key: str) -> None:
        with self._lock:
            self._seen.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()


class ChatLocks:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    @contextmanager
    def guard(self, chat_id: str):
        with self._guard:
            lock = self._locks.setdefault(str(chat_id), threading.Lock())
        with lock:
            yield


deduper = UpdateDeduper()
chat_locks = ChatLocks()
