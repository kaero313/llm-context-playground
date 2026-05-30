from __future__ import annotations

from dataclasses import dataclass

from context_lab.cases import load_case
from context_lab.models import Budget, ContextBundle
from context_lab.privacy import redact_pii
from context_lab.providers import Generation, LLMProvider
from context_lab.strategies import get_strategy


@dataclass(frozen=True)
class EvaluationResult:
    case_id: str
    strategy: str
    mode: str
    context: ContextBundle
    generation: Generation
    passed: bool
    missing_expected: tuple[str, ...]
    unsafe_found: tuple[str, ...]

    def row(self) -> dict[str, str | int | float | bool]:
        return {
            "case": self.case_id,
            "strategy": self.strategy,
            "mode": self.mode,
            "tokens": self.context.estimated_tokens,
            "latency_ms": round(self.context.latency_ms, 2),
            "passed": self.passed,
            "missing": ", ".join(self.missing_expected),
            "unsafe": ", ".join(self.unsafe_found),
            "warnings": ", ".join(self.context.warnings),
        }


def evaluate_case(
    case_id: str,
    strategy_name: str,
    mode: str = "mock",
    budget: Budget | None = None,
) -> EvaluationResult:
    budget = budget or Budget()
    session, user_turn = load_case(case_id)
    if strategy_name == "privacy":
        user_turn, _ = redact_pii(user_turn)
    context = get_strategy(strategy_name).build(session, user_turn, budget)
    generation = LLMProvider().generate(context, mode=mode)
    combined = context.render() + "\n" + generation.text
    missing = tuple(
        expected
        for expected in session.expected_answer_contains
        if expected.lower() not in combined.lower()
    )
    unsafe = tuple(
        marker
        for marker in session.unsafe_answer_contains
        if marker and marker.lower() in combined.lower()
    )
    return EvaluationResult(
        case_id=case_id,
        strategy=strategy_name,
        mode=mode,
        context=context,
        generation=generation,
        passed=not missing and not unsafe,
        missing_expected=missing,
        unsafe_found=unsafe,
    )


def compare_strategies(
    case_id: str,
    strategies: list[str],
    mode: str = "mock",
    budget: Budget | None = None,
) -> list[EvaluationResult]:
    return [
        evaluate_case(case_id, strategy_name, mode=mode, budget=budget)
        for strategy_name in strategies
    ]

