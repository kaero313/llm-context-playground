from context_lab.cases import load_case
from context_lab.models import Budget
from context_lab.strategies import available_strategies, get_strategy


def test_all_planned_strategies_are_available() -> None:
    assert {
        "full_history",
        "sliding_window",
        "summary",
        "structured",
        "rag",
        "hybrid",
        "tool_compaction",
        "privacy",
        "openai_state",
    }.issubset(set(available_strategies()))


def test_hybrid_context_orders_high_priority_sections() -> None:
    session, user_turn = load_case("support_refund")

    context = get_strategy("hybrid").build(session, user_turn, Budget())

    assert context.section_labels()[0] == "policy"
    assert context.section_labels()[-1] == "current_user_turn"
    assert "retrieved_context" in context.section_labels()
    assert "user_profile" in context.section_labels()


def test_small_budget_drops_low_priority_sections_but_keeps_critical_context() -> None:
    session, user_turn = load_case("long_running_session")

    context = get_strategy("full_history").build(
        session,
        user_turn,
        Budget(max_input_tokens=120, reserved_output_tokens=20),
    )

    assert "policy" in context.section_labels()
    assert "current_user_turn" in context.section_labels()
    assert "full_transcript" not in context.section_labels()
    assert "full_transcript" in ",".join(context.warnings)


def test_summary_strategy_preserves_old_decision_when_window_would_drop_it() -> None:
    session, user_turn = load_case("support_refund")

    summary = get_strategy("summary").build(session, user_turn, Budget()).render()
    window = get_strategy("sliding_window").build(session, user_turn, Budget()).render()

    assert "INV-4431" in summary
    assert "INV-4431" not in window

