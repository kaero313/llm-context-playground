from context_lab.server import case_payload, compare_payload, experiment_payload, options_payload, run_payload


def test_options_payload_contains_cases_and_strategies() -> None:
    payload = options_payload()

    assert "support_refund" in {item["id"] for item in payload["cases"]}
    assert "hybrid" in payload["strategies"]
    assert "sliding_window" in payload["defaultStrategies"]
    assert "enabled" in payload["openai"]
    assert payload["openai"]["model"]
    assert payload["cases"][0]["guideTitle"]


def test_case_payload_contains_learning_material() -> None:
    payload = case_payload("support_refund")

    assert payload["id"] == "support_refund"
    assert payload["userTurn"]
    assert payload["transcript"]
    assert payload["documents"]
    assert payload["guide"]["title"].startswith("환불 문의")
    assert len(payload["guide"]["recommended"]) >= 4


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
    assert payload["results"][0]["provider"] == "mock"
    assert payload["results"][0]["model"]
    assert payload["expectedFacts"]
    assert payload["guidance"]


def test_experiment_retrieval_toggle_controls_retrieved_context() -> None:
    base = {
        "case": ["support_refund"],
        "prompt": ["환불 가능 여부와 다음에 제출해야 할 정보를 한국어로 정리해줘."],
        "retentionTurns": ["4"],
        "compression": ["hybrid"],
        "kvCache": ["static"],
    }

    with_retrieval = experiment_payload({**base, "retrieval": ["on"]})["results"][0]
    without_retrieval = experiment_payload({**base, "retrieval": ["off"]})["results"][0]

    assert any(section["source"] == "retriever" for section in with_retrieval["sections"])
    assert not any(section["source"] == "retriever" for section in without_retrieval["sections"])
    assert with_retrieval["apiPrompt"] != without_retrieval["apiPrompt"]
    assert with_retrieval["tokens"] > without_retrieval["tokens"]


def test_experiment_payload_live_current_only_uses_openai_for_current(monkeypatch) -> None:
    import context_lab.server as server
    from context_lab.providers import Generation

    calls = []

    class FakeProvider:
        def generate(self, context, mode="mock", max_output_tokens=None):
            calls.append((mode, max_output_tokens))
            return Generation(
                text="Mock 답변:\n- invoice INV-4431\n- 30일\n- Enterprise",
                provider=mode,
                model="fake-model",
                input_tokens=11 if mode == "openai" else None,
                output_tokens=7 if mode == "openai" else None,
                total_tokens=18 if mode == "openai" else None,
                latency_ms=123.4 if mode == "openai" else None,
            )

    monkeypatch.setattr(server, "LLMProvider", lambda: FakeProvider())
    payload = experiment_payload(
        {
            "case": ["support_refund"],
            "prompt": ["What refund context should I keep?"],
            "mode": ["openai"],
            "liveVariants": ["current"],
        }
    )

    assert [mode for mode, _ in calls] == ["openai", "mock", "mock", "mock"]
    assert payload["results"][0]["mode"] == "openai"
    assert payload["results"][0]["actualTotalTokens"] == 18
    assert payload["results"][1]["mode"] == "mock"
