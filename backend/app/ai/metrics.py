"""Per-message pipeline statistics: one structured log line per turn plus in-process aggregate metrics.

The log line carries ids, routing decision, timings and counts only - never message text, names, emails or tokens.
`pipeline_metrics.snapshot()` powers GET /ai/metrics (route mix, latency per route, LLM calls per message,
retrieval operations/failures, escalation and cache rates).
"""
import json
import threading
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

from loguru import logger


@dataclass
class TurnStats:
    route: str = "UNKNOWN"
    intent: str = "UNKNOWN"
    router_confidence: float = 0.0
    router_source: str = "rules"
    router_reason: str = ""
    rag_invoked: bool = False
    retrieved_docs: int = 0
    top_relevance: float | None = None
    retrieval_ms: int = 0
    llm_calls: int = 0
    llm_ms: int = 0
    tools: list[str] = field(default_factory=list)
    cache_hit: bool = False
    escalated: bool = False
    status: str = "ok"            # ok | fallback | escalated | error
    total_ms: int = 0
    grounded: bool | None = None
    conflict: bool = False


class PipelineMetrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with getattr(self, "_lock", threading.Lock()):
            self.total = 0
            self.routes: Counter[str] = Counter()
            self.intents: Counter[str] = Counter()
            self.sources: Counter[str] = Counter()
            self.latency_sum: dict[str, int] = defaultdict(int)
            self.latency_n: dict[str, int] = defaultdict(int)
            self.llm_calls = 0
            self.rag_ops = 0
            self.rag_empty = 0
            self.escalations = 0
            self.cache_hits = 0
            self.cache_lookups = 0
            self.retrieval_ms = 0
            self.conflicts = 0

    def record(self, s: TurnStats) -> None:
        with self._lock:
            self.total += 1
            self.routes[s.route] += 1
            self.intents[s.intent] += 1
            self.sources[s.router_source] += 1
            self.latency_sum[s.route] += s.total_ms
            self.latency_n[s.route] += 1
            self.llm_calls += s.llm_calls
            if s.rag_invoked:
                self.rag_ops += 1
                self.retrieval_ms += s.retrieval_ms
                if s.retrieved_docs == 0:
                    self.rag_empty += 1
            if s.escalated:
                self.escalations += 1
            if s.cache_hit:
                self.cache_hits += 1
            if s.conflict:
                self.conflicts += 1

    def note_cache_lookup(self) -> None:
        with self._lock:
            self.cache_lookups += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            n = max(self.total, 1)
            return {
                "messages": self.total,
                "route_distribution": dict(self.routes),
                "route_share": {k: round(v / n, 3) for k, v in self.routes.items()},
                "intent_distribution": dict(self.intents),
                "router_source": dict(self.sources),
                "avg_latency_ms_by_route": {k: round(self.latency_sum[k] / self.latency_n[k]) for k in self.latency_n},
                "avg_llm_calls_per_message": round(self.llm_calls / n, 2),
                "retrieval_operations": self.rag_ops,
                "retrieval_failure_rate": round(self.rag_empty / self.rag_ops, 3) if self.rag_ops else 0.0,
                "avg_retrieval_ms": round(self.retrieval_ms / self.rag_ops) if self.rag_ops else 0,
                "escalation_rate": round(self.escalations / n, 3),
                "cache_hit_rate": round(self.cache_hits / self.cache_lookups, 3) if self.cache_lookups else 0.0,
                "policy_conflicts": self.conflicts,
            }


pipeline_metrics = PipelineMetrics()


def log_turn(stats: TurnStats, *, conversation_id: Any, message_id: Any = None) -> None:
    """Record the turn and emit one structured line explaining why it was routed the way it was."""
    pipeline_metrics.record(stats)
    payload = {"conversation_id": str(conversation_id), "message_id": str(message_id) if message_id else None, **asdict(stats)}
    logger.info("pipeline_turn " + json.dumps(payload, default=str, separators=(",", ":")))
