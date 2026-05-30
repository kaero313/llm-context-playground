from context_lab.evaluation import evaluate_case


def test_hybrid_support_refund_passes_mock_eval() -> None:
    result = evaluate_case("support_refund", "hybrid", mode="mock")

    assert result.passed
    assert result.missing_expected == ()
    assert result.unsafe_found == ()


def test_sliding_window_support_refund_reveals_context_loss() -> None:
    result = evaluate_case("support_refund", "sliding_window", mode="mock")

    assert not result.passed
    assert "INV-4431" in result.missing_expected


def test_tool_compaction_avoids_raw_ip_leakage() -> None:
    result = evaluate_case("tool_result_compaction", "tool_compaction", mode="mock")

    assert result.passed
    assert result.unsafe_found == ()


def test_privacy_case_passes_with_redaction_strategy() -> None:
    result = evaluate_case("privacy_memory", "privacy", mode="mock")

    assert result.passed
    assert result.unsafe_found == ()

