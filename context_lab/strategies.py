from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from context_lab.models import Budget, ContextBundle, ContextSection, Message, SessionStore
from context_lab.privacy import redact_pii
from context_lab.retrieval import Retriever


class ContextStrategy(ABC):
    name: str

    def build(self, session: SessionStore, user_turn: str, budget: Budget) -> ContextBundle:
        started = time.perf_counter()
        sections = self._build_sections(session, user_turn, budget)
        warnings: list[str] = []
        sections, dropped = trim_to_budget(sections, budget)
        if dropped:
            warnings.append(f"dropped_sections={','.join(dropped)}")
        bundle = ContextBundle(strategy=self.name, sections=sections, warnings=warnings)
        if bundle.estimated_tokens > budget.available_input_tokens * budget.warning_threshold:
            bundle.warnings.append("near_context_budget")
        bundle.latency_ms = (time.perf_counter() - started) * 1000
        return bundle

    @abstractmethod
    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        raise NotImplementedError


class FullHistoryStrategy(ContextStrategy):
    name = "full_history"

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("full_transcript", session.transcript_text(), priority=40),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


class SlidingWindowStrategy(ContextStrategy):
    name = "sliding_window"

    def __init__(self, window_messages: int = 4):
        self.window_messages = window_messages

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        recent = session.transcript[-self.window_messages :]
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("recent_transcript", session.transcript_text(recent), priority=80),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


class SummaryStrategy(ContextStrategy):
    name = "summary"

    def __init__(self, recent_messages: int = 3):
        self.recent_messages = recent_messages

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        recent = session.transcript[-self.recent_messages :]
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("running_summary", session.summary, priority=90),
            ContextSection("recent_transcript", session.transcript_text(recent), priority=80),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


class StructuredStateStrategy(ContextStrategy):
    name = "structured"

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        memory = "\n".join(f"- {item.text}" for item in session.safe_memory_items())
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("user_profile", "\n".join(session.profile_lines()), priority=95),
            ContextSection("safe_memory", memory, priority=85),
            ContextSection("running_summary", session.summary, priority=80),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


class RagStrategy(ContextStrategy):
    name = "rag"

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        retriever = Retriever(session.documents, session.safe_memory_items())
        hits = retriever.search(user_turn, limit=4)
        retrieved = "\n\n".join(
            f"- {hit.title} ({hit.source}, score={hit.score:.2f}): {hit.snippet}"
            for hit in hits
        )
        recent = session.transcript[-2:]
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("retrieved_context", retrieved, priority=95, source="retriever"),
            ContextSection("recent_transcript", session.transcript_text(recent), priority=70),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


class ToolCompactionStrategy(ContextStrategy):
    name = "tool_compaction"

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        summaries = "\n".join(
            f"- {result.name}: {result.summary} citations={list(result.citations)}"
            for result in session.tool_results
        )
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("tool_result_summaries", summaries, priority=90),
            ContextSection("running_summary", session.summary, priority=80),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


class PrivacyStrategy(ContextStrategy):
    name = "privacy"

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        redacted_turn, found = redact_pii(user_turn)
        safe_transcript_lines: list[str] = []
        for message in session.transcript[-5:]:
            redacted, _ = redact_pii(message.content)
            safe_transcript_lines.append(f"{message.role}: {redacted}")
        warnings = "Detected PII types: " + ", ".join(found) if found else "No PII detected."
        memory = "\n".join(f"- {item.text}" for item in session.safe_memory_items())
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("privacy_filter", warnings, priority=100),
            ContextSection("safe_memory", memory, priority=85),
            ContextSection("redacted_recent_transcript", "\n".join(safe_transcript_lines), priority=80),
            ContextSection("current_user_turn", redacted_turn, priority=100),
        ]


class OpenAIStateStrategy(ContextStrategy):
    name = "openai_state"

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        state_notes = (
            "Manual state: 앱이 선택한 이전 메시지를 매 턴 직접 보냅니다.\n"
            "Stored conversation: provider 쪽 대화 상태를 사용해 client payload를 줄일 수 있습니다.\n"
            "Context window: 활성 모델 window에 들어간 token만 답변에 영향을 줄 수 있습니다.\n"
            "Compaction/truncation: overflow 전에 낮은 가치의 context를 요약하거나 제외합니다.\n"
            "운영 규칙: stored state를 쓰더라도 정책과 현재 사용자 질문은 명시적으로 유지합니다."
        )
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("openai_state_options", state_notes, priority=95),
            ContextSection("running_summary", session.summary, priority=80),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


class HybridStrategy(ContextStrategy):
    name = "hybrid"

    def _build_sections(
        self, session: SessionStore, user_turn: str, budget: Budget
    ) -> list[ContextSection]:
        retriever = Retriever(session.documents, session.safe_memory_items())
        hits = retriever.search(user_turn + " " + session.summary, limit=3)
        retrieved = "\n\n".join(
            f"- {hit.title} ({hit.source}): {hit.snippet}" for hit in hits
        )
        tool_summaries = "\n".join(
            f"- {result.name}: {result.summary}" for result in session.tool_results
        )
        recent = session.transcript[-3:]
        return [
            ContextSection("policy", session.policy, priority=100),
            ContextSection("user_profile", "\n".join(session.profile_lines()), priority=95),
            ContextSection("running_summary", session.summary, priority=90),
            ContextSection("retrieved_context", retrieved, priority=90, source="retriever"),
            ContextSection("tool_result_summaries", tool_summaries, priority=75),
            ContextSection("recent_transcript", session.transcript_text(recent), priority=70),
            ContextSection("current_user_turn", user_turn, priority=100),
        ]


def trim_to_budget(
    sections: list[ContextSection], budget: Budget
) -> tuple[list[ContextSection], list[str]]:
    kept = list(sections)
    dropped: list[str] = []
    while sum(section.tokens for section in kept) > budget.available_input_tokens:
        candidates = [
            (index, section)
            for index, section in enumerate(kept)
            if section.priority < 100
        ]
        if not candidates:
            break
        index, section = min(candidates, key=lambda item: (item[1].priority, -item[0]))
        dropped.append(section.label)
        del kept[index]
    return kept, dropped


_STRATEGIES: dict[str, Callable[[], ContextStrategy]] = {
    "full_history": FullHistoryStrategy,
    "sliding_window": SlidingWindowStrategy,
    "summary": SummaryStrategy,
    "structured": StructuredStateStrategy,
    "rag": RagStrategy,
    "tool_compaction": ToolCompactionStrategy,
    "privacy": PrivacyStrategy,
    "openai_state": OpenAIStateStrategy,
    "hybrid": HybridStrategy,
}


def available_strategies() -> list[str]:
    return sorted(_STRATEGIES)


def get_strategy(name: str) -> ContextStrategy:
    try:
        return _STRATEGIES[name]()
    except KeyError as exc:
        known = ", ".join(available_strategies())
        raise ValueError(f"알 수 없는 strategy입니다: '{name}'. 사용 가능: {known}") from exc
