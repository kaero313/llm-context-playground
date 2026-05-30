from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from context_lab.tokenization import estimate_tokens


@dataclass(frozen=True)
class Budget:
    max_input_tokens: int = 900
    reserved_output_tokens: int = 200
    warning_threshold: float = 0.8

    @property
    def available_input_tokens(self) -> int:
        return max(0, self.max_input_tokens - self.reserved_output_tokens)


@dataclass(frozen=True)
class Message:
    role: str
    content: str
    kind: str = "message"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.content)


@dataclass(frozen=True)
class MemoryItem:
    id: str
    text: str
    tags: tuple[str, ...] = ()
    safe_to_store: bool = True
    contains_pii: bool = False


@dataclass(frozen=True)
class Document:
    id: str
    title: str
    body: str
    source: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RetrievalHit:
    document_id: str
    title: str
    snippet: str
    score: float
    source: str


@dataclass(frozen=True)
class ToolResult:
    name: str
    raw: str
    summary: str
    citations: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextSection:
    label: str
    content: str
    priority: int
    source: str = "internal"

    @property
    def tokens(self) -> int:
        return estimate_tokens(self.render())

    def render(self) -> str:
        return f"[{self.label}]\n{self.content}".strip()


@dataclass
class ContextBundle:
    strategy: str
    sections: list[ContextSection]
    warnings: list[str] = field(default_factory=list)
    latency_ms: float = 0.0

    @property
    def estimated_tokens(self) -> int:
        return sum(section.tokens for section in self.sections)

    def render(self) -> str:
        return "\n\n".join(section.render() for section in self.sections)

    def as_prompt_messages(self) -> list[dict[str, str]]:
        return [
            {
                "role": "user",
                "content": self.render(),
            }
        ]

    def section_labels(self) -> list[str]:
        return [section.label for section in self.sections]


@dataclass
class SessionStore:
    case_id: str
    transcript: list[Message]
    summary: str
    user_profile: dict[str, str]
    memory_items: list[MemoryItem]
    documents: list[Document]
    tool_results: list[ToolResult]
    policy: str
    expected_answer_contains: tuple[str, ...] = ()
    unsafe_answer_contains: tuple[str, ...] = ()
    notes: str = ""

    def safe_memory_items(self) -> list[MemoryItem]:
        return [
            item
            for item in self.memory_items
            if item.safe_to_store and not item.contains_pii
        ]

    def profile_lines(self) -> list[str]:
        return [f"{key}: {value}" for key, value in sorted(self.user_profile.items())]

    def transcript_text(self, messages: Iterable[Message] | None = None) -> str:
        selected = self.transcript if messages is None else list(messages)
        return "\n".join(f"{message.role}: {message.content}" for message in selected)

