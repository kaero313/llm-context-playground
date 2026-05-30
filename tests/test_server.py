from context_lab.server import case_payload, compare_payload, experiment_payload, options_payload, run_payload


def test_options_payload_contains_cases_and_strategies() -> None:
    payload = options_payload()

    assert "support_refund" in {item["id"] for item in payload["cases"]}
    assert "hybrid" in payload["strategies"]
    assert "sliding_window" in payload["defaultStrategies"]


def test_case_payload_contains_learning_material() -> None:
    payload = case_payload("support_refund")

    assert payload["id"] == "support_refund"
    assert payload["userTurn"]
    assert payload["transcript"]
    assert payload["documents"]


def test_run_payload_serializes_context_sections() -> None:
    payload = run_payload(
        {
            "case": ["support_refund"],
            "strategy": ["hybrid"],
            "mode": ["mock"],
        }
    )

    assert payload["passed"] is True
    assert payload["sections"]
    assert payload["answer"].startswith("Mock")
    assert payload["availableTokens"] == 700
    assert payload["tokenUtilization"] > 0
    assert "tokenShare" in payload["sections"][0]


def test_compare_payload_returns_multiple_results() -> None:
    payload = compare_payload(
        {
            "case": ["support_refund"],
            "strategies": ["sliding_window", "hybrid"],
            "mode": ["mock"],
        }
    )

    results = payload["results"]
    assert [result["strategy"] for result in results] == ["sliding_window", "hybrid"]
    assert results[0]["passed"] is False
    assert results[1]["passed"] is True


def test_experiment_payload_returns_learning_variants() -> None:
    payload = experiment_payload(
        {
            "case": ["support_refund"],
            "prompt": ["What refund context should I keep?"],
            "retentionTurns": ["4"],
            "compression": ["summary"],
            "retrieval": ["on"],
            "kvCache": ["static"],
        }
    )

    assert payload["settings"]["retentionTurns"] == 4
    assert payload["results"][0]["id"] == "current"
    assert {"recent_only", "summary", "hybrid"}.issubset({item["id"] for item in payload["results"]})
    assert "cachedTokens" in payload["results"][0]
    assert "apiPrompt" in payload["results"][0]
    assert payload["expectedFacts"]
    assert payload["guidance"]
