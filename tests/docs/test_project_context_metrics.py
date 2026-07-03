from docmancer.docs.application.project_context_service import _token_savings_metrics


def test_token_savings_metrics_are_aggregate_not_chunk_metadata() -> None:
    metrics = _token_savings_metrics(2_180_304, 17_128)

    assert metrics["savings_percent"] == 99.2
    assert metrics["used_percent"] == 0.8
    assert metrics["agentic_runway_multiplier"] == 127.29


def test_token_savings_metrics_handle_zero_raw_docs() -> None:
    metrics = _token_savings_metrics(0, 100)

    assert metrics["raw_docs_tokens"] == 0
    assert metrics["context_pack_tokens"] == 100
    assert metrics["savings_percent"] is None
    assert metrics["used_percent"] is None
