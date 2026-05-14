import pytest

from app.core.metrics_store import MetricsStore, RequestMetric


def _metric(retrieval_ms: float = 100.0, llm_ms: float = 500.0, cited: bool = True, error: bool = False) -> RequestMetric:
    return RequestMetric(
        request_id="req-test",
        retrieval_latency_ms=retrieval_ms,
        llm_latency_ms=llm_ms,
        cited=cited,
        error=error,
    )


def test_empty_store_returns_none_values():
    store = MetricsStore()
    summary = store.get_summary()
    assert summary["retrieval_latency_ms_p50"] is None
    assert summary["llm_latency_ms_p50"] is None
    assert summary["citation_coverage"] is None
    assert summary["error_rate"] is None
    assert summary["sample_size"] == 0


def test_single_metric_summary():
    store = MetricsStore()
    store.add(_metric(retrieval_ms=120.0, llm_ms=800.0, cited=True))
    summary = store.get_summary()
    assert summary["retrieval_latency_ms_p50"] == 120.0
    assert summary["llm_latency_ms_p50"] == 800.0
    assert summary["citation_coverage"] == 1.0
    assert summary["error_rate"] == 0.0
    assert summary["sample_size"] == 1


def test_citation_coverage_calculation():
    store = MetricsStore()
    store.add(_metric(cited=True))
    store.add(_metric(cited=True))
    store.add(_metric(cited=False))
    store.add(_metric(cited=False))

    summary = store.get_summary()
    assert summary["citation_coverage"] == 0.5
    assert summary["sample_size"] == 4


def test_error_rate_calculation():
    store = MetricsStore()
    store.add(_metric(error=False))
    store.add(_metric(error=False))
    store.add(_metric(error=True))

    summary = store.get_summary()
    assert round(summary["error_rate"], 4) == round(1 / 3, 4)


def test_percentile_p50_with_odd_count():
    store = MetricsStore()
    for ms in [100.0, 200.0, 300.0, 400.0, 500.0]:
        store.add(_metric(retrieval_ms=ms))

    summary = store.get_summary()
    # p50 of [100,200,300,400,500] = 300
    assert summary["retrieval_latency_ms_p50"] == 300.0


def test_percentile_p95():
    store = MetricsStore()
    for ms in range(1, 101):  # 1..100
        store.add(_metric(retrieval_ms=float(ms)))

    summary = store.get_summary()
    # p95 index = int(100 * 95 / 100) - 1 = 94 → value = 95.0
    assert summary["retrieval_latency_ms_p95"] == 95.0


def test_maxlen_ring_buffer():
    store = MetricsStore(maxlen=3)
    for i in range(5):
        store.add(_metric(retrieval_ms=float(i * 100)))

    summary = store.get_summary()
    assert summary["sample_size"] == 3


def test_errors_excluded_from_latency_percentiles():
    store = MetricsStore()
    store.add(_metric(retrieval_ms=100.0, error=False))
    store.add(_metric(retrieval_ms=9999.0, error=True))

    summary = store.get_summary()
    # The error metric should not pollute retrieval latency
    assert summary["retrieval_latency_ms_p50"] == 100.0
    assert summary["sample_size"] == 2
    assert summary["error_rate"] == 0.5
