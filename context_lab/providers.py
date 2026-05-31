from __future__ import annotations

import os
from dataclasses import dataclass
from time import perf_counter

from context_lab.models import ContextBundle


@dataclass(frozen=True)
class Generation:
    text: str
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None


class LLMProvider:
    def generate(
        self,
        context: ContextBundle,
        mode: str = "mock",
        max_output_tokens: int | None = None,
    ) -> Generation:
        if mode == "mock":
            return MockLLMProvider().generate(context)
        if mode == "openai":
            return OpenAIProvider().generate(context, max_output_tokens=max_output_tokens)
        raise ValueError("mode must be 'mock' or 'openai'")


class MockLLMProvider:
    model = "deterministic-rule-model"

    def generate(self, context: ContextBundle) -> Generation:
        rendered = context.render()
        lower = rendered.lower()
        facts: list[str] = []

        if "inv-4431" in lower:
            facts.append("context 안에서 invoice INV-4431을 찾았습니다.")
        if "korean" in lower or "한국어" in rendered:
            facts.append("응답 언어 선호도는 한국어입니다.")
        if ("30" in lower and ("refund" in lower or "환불" in rendered)) or "30 calendar days" in lower:
            facts.append("환불 정책은 30일 기준을 언급합니다.")
        if "enterprise" in lower:
            facts.append("Enterprise 전환으로 인한 중복 결제가 관련되어 있습니다.")
        if "500" in lower and ("reimbursement" in lower or "상환" in rendered or "장비" in rendered):
            facts.append("최신 정책 기준 장비 상환 한도는 500 USD입니다.")
        if "manager approval" in lower or "관리자 승인" in rendered:
            facts.append("일부 상환에는 관리자 승인이 필요합니다.")
        if "250" in lower and ("monitor" in lower or "모니터" in rendered):
            facts.append("모니터는 연간 한도 안에서 250 USD까지 사전 승인합니다.")
        if ("11" in lower and "failed" in lower) or ("11" in lower and "실패" in rendered):
            facts.append("audit 요약에는 실패 로그인 이벤트 11건이 있습니다.")
        if "raw ip" in lower:
            facts.append("상위 대응이 필요하지 않다면 raw IP 목록은 포함하지 않는 편이 안전합니다.")
        if "[redacted_phone]" in lower or "[redacted_email]" in lower:
            facts.append("PII가 redaction되었고 장기 memory로 저장하면 안 됩니다.")
        if "apac first" in lower:
            facts.append("최종 출시 지역은 APAC first입니다.")
        if "rollback owner" in lower:
            facts.append("출시 요약에는 rollback owner가 포함되어야 합니다.")
        if "manual state" in lower:
            facts.append("Manual state 방식이 매 요청마다 선택한 context를 직접 보내는 방식입니다.")
        if "stored conversation" in lower:
            facts.append("Stored conversation은 provider 쪽에 대화 상태를 저장해 client payload를 줄이는 방식입니다.")
        if "context window" in lower:
            facts.append("Context window 안에 들어간 token만 응답에 영향을 줄 수 있습니다.")
        if "compaction" in lower:
            facts.append("Compaction은 overflow 전에 context를 요약해 압축하는 방식입니다.")

        if not facts:
            facts.append("context 근거가 부족하므로 누락된 출처나 정보를 요청해야 합니다.")

        text = "Mock 답변:\n" + "\n".join(f"- {fact}" for fact in facts)
        return Generation(text=text, provider="mock", model=self.model)


class OpenAIProvider:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    def generate(
        self,
        context: ContextBundle,
        max_output_tokens: int | None = None,
    ) -> Generation:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --mode openai.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Install the optional dependency first: pip install -e .[openai]"
            ) from exc

        request = {
            "model": self.model,
            "input": context.as_prompt_messages(),
        }
        if max_output_tokens:
            request["max_output_tokens"] = max_output_tokens

        client = OpenAI(api_key=api_key)
        started_at = perf_counter()
        response = client.responses.create(**request)
        latency_ms = round((perf_counter() - started_at) * 1000, 1)

        text = getattr(response, "output_text", None) or str(response)
        usage = getattr(response, "usage", None)
        return Generation(
            text=text,
            provider="openai",
            model=self.model,
            input_tokens=_usage_value(usage, "input_tokens"),
            output_tokens=_usage_value(usage, "output_tokens"),
            total_tokens=_usage_value(usage, "total_tokens"),
            latency_ms=latency_ms,
        )


def _usage_value(usage: object, name: str) -> int | None:
    if usage is None:
        return None
    if isinstance(usage, dict):
        value = usage.get(name)
    else:
        value = getattr(usage, name, None)
    return int(value) if isinstance(value, int | float) else None
