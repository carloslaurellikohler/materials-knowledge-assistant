from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass


@dataclass
class RequestMetric:
    request_id: str
    retrieval_latency_ms: float
    llm_latency_ms: float
    cited: bool
    error: bool


class MetricsStore:
    def __init__(self, maxlen: int = 1000):
        self._buf: deque[RequestMetric] = deque(maxlen=maxlen)

    def add(self, metric: RequestMetric) -> None:
        self._buf.append(metric)

    def _field_values(self, field: str, exclude_errors: bool = True) -> list[float]:
        return [
            getattr(m, field)
            for m in self._buf
            if not (exclude_errors and m.error)
        ]

    def _percentile(self, values: list[float], p: int) -> float | None:
        if not values:
            return None
        sorted_vals = sorted(values)
        idx = max(0, math.ceil(len(sorted_vals) * p / 100) - 1)
        return round(sorted_vals[idx], 2)

    def get_summary(self) -> dict:
        total = len(self._buf)
        if total == 0:
            return {
                "retrieval_latency_ms_p50": None,
                "retrieval_latency_ms_p95": None,
                "llm_latency_ms_p50": None,
                "llm_latency_ms_p95": None,
                "citation_coverage": None,
                "error_rate": None,
                "sample_size": 0,
            }

        retrieval = self._field_values("retrieval_latency_ms")
        llm = self._field_values("llm_latency_ms")
        cited_count = sum(1 for m in self._buf if m.cited)
        error_count = sum(1 for m in self._buf if m.error)

        return {
            "retrieval_latency_ms_p50": self._percentile(retrieval, 50),
            "retrieval_latency_ms_p95": self._percentile(retrieval, 95),
            "llm_latency_ms_p50": self._percentile(llm, 50),
            "llm_latency_ms_p95": self._percentile(llm, 95),
            "citation_coverage": round(cited_count / total, 4),
            "error_rate": round(error_count / total, 4),
            "sample_size": total,
        }


_store = MetricsStore()


def get_store() -> MetricsStore:
    return _store
