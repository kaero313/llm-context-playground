from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from context_lab.cases import available_cases, load_case
from context_lab.evaluation import compare_strategies, evaluate_case
from context_lab.models import Budget, ContextBundle, ContextSection
from context_lab.providers import LLMProvider
from context_lab.retrieval import Retriever
from context_lab.strategies import available_strategies, trim_to_budget

WEB_DIR = Path(__file__).with_name("web")
DEFAULT_STRATEGIES = [
    "full_history",
    "sliding_window",
    "summary",
    "structured",
    "rag",
    "hybrid",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m context_lab.server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    server = ThreadingHTTPServer((args.host, args.port), ContextLabHandler)
    host, port = server.server_address
    print(f"LLM Context Playground UI running at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


class ContextLabHandler(BaseHTTPRequestHandler):
    server_version = "ContextLabHTTP/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed.path, parse_qs(parsed.query))
            return
        self._serve_static(parsed.path)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _handle_api(self, path: str, params: dict[str, list[str]]) -> None:
        try:
            if path == "/api/options":
                self._send_json(options_payload())
            elif path == "/api/case":
                self._send_json(case_payload(_one(params, "case", "support_refund")))
            elif path == "/api/run":
                self._send_json(run_payload(params))
            elif path == "/api/compare":
                self._send_json(compare_payload(params))
            elif path == "/api/experiment":
                self._send_json(experiment_payload(params))
            else:
                self._send_error(HTTPStatus.NOT_FOUND, "Unknown API route")
        except Exception as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        target = (WEB_DIR / relative).resolve()
        if not str(target).startswith(str(WEB_DIR.resolve())) or not target.is_file():
            self._send_error(HTTPStatus.NOT_FOUND, "Static file not found")
            return

        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if target.suffix in {".html", ".css", ".js"}:
            content_type += "; charset=utf-8"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def options_payload() -> dict[str, Any]:
    cases = []
    for case_id in available_cases():
        session, user_turn = load_case(case_id)
        cases.append({"id": case_id, "notes": session.notes, "userTurn": user_turn})
    return {
        "cases": cases,
        "strategies": available_strategies(),
        "defaultStrategies": DEFAULT_STRATEGIES,
    }


def case_payload(case_id: str) -> dict[str, Any]:
    session, user_turn = load_case(case_id)
    return {
        "id": case_id,
        "notes": session.notes,
        "userTurn": user_turn,
        "summary": session.summary,
        "profile": session.user_profile,
        "transcript": [
            {"role": message.role, "content": message.content, "tokens": message.tokens}
            for message in session.transcript
        ],
        "documents": [
            {
                "id": document.id,
                "title": document.title,
                "source": document.source,
                "tags": list(document.tags),
            }
            for document in session.documents
        ],
        "toolResults": [
            {
                "name": result.name,
                "summary": result.summary,
                "citations": list(result.citations),
            }
            for result in session.tool_results
        ],
        "expected": list(session.expected_answer_contains),
        "unsafe": list(session.unsafe_answer_contains),
    }


def run_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    budget = _budget(params)
    result = evaluate_case(
        _one(params, "case", "support_refund"),
        _one(params, "strategy", "hybrid"),
        mode=_one(params, "mode", "mock"),
        budget=budget,
    )
    return result_payload(result, budget)


def compare_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    strategies = _many(params, "strategies") or DEFAULT_STRATEGIES
    budget = _budget(params)
    results = compare_strategies(
        _one(params, "case", "support_refund"),
        strategies,
        mode=_one(params, "mode", "mock"),
        budget=budget,
    )
    return {"results": [result_payload(result, budget) for result in results]}


def experiment_payload(params: dict[str, list[str]]) -> dict[str, Any]:
    case_id = _one(params, "case", "support_refund")
    session, default_prompt = load_case(case_id)
    prompt = _one(params, "prompt", default_prompt).strip() or default_prompt
    budget = _budget(params)
    base_config = {
        "retentionTurns": _int(params, "retentionTurns", 4),
        "compression": _choice(params, "compression", "hybrid", {"none", "summary", "structured", "hybrid"}),
        "retrieval": _choice(params, "retrieval", "on", {"off", "on"}),
        "kvCache": _choice(params, "kvCache", "static", {"off", "static", "conversation"}),
    }
    variants = [
        ("current", "현재 설정", "지금 선택한 실험 조건입니다.", base_config),
        (
            "recent_only",
            "최근 대화만",
            "요약과 검색 없이 최근 대화만 유지하는 기준선입니다.",
            {**base_config, "compression": "none", "retrieval": "off", "kvCache": "off"},
        ),
        (
            "summary",
            "요약 전략",
            "오래된 대화는 요약으로 보존하고 최근 대화는 직접 유지합니다.",
            {
                **base_config,
                "compression": "summary",
                "retrieval": "off",
                "kvCache": "static",
                "retentionTurns": min(base_config["retentionTurns"], 4),
            },
        ),
        (
            "hybrid",
            "추천 조합",
            "요약, 구조화 상태, 검색 근거, 최근 대화를 함께 사용합니다.",
            {
                **base_config,
                "compression": "hybrid",
                "retrieval": "on",
                "kvCache": "conversation",
                "retentionTurns": max(base_config["retentionTurns"], 4),
            },
        ),
    ]
    results = [
        experiment_result_payload(
            session=session,
            prompt=prompt,
            budget=budget,
            variant_id=variant_id,
            name=name,
            description=description,
            config=config,
            mode=_one(params, "mode", "mock"),
        )
        for variant_id, name, description, config in variants
    ]
    selected = results[0]
    return {
        "case": case_id,
        "caseNotes": session.notes,
        "prompt": prompt,
        "defaultPrompt": default_prompt,
        "settings": {
            **base_config,
            "maxInputTokens": budget.max_input_tokens,
            "reservedOutputTokens": budget.reserved_output_tokens,
            "availableTokens": budget.available_input_tokens,
        },
        "expectedFacts": list(session.expected_answer_contains),
        "unsafeFacts": list(session.unsafe_answer_contains),
        "results": results,
        "selectedId": selected["id"],
        "guidance": experiment_guidance(selected, session),
        "capture": capture_summary(selected, results),
    }


def experiment_result_payload(
    *,
    session,
    prompt: str,
    budget: Budget,
    variant_id: str,
    name: str,
    description: str,
    config: dict[str, Any],
    mode: str,
) -> dict[str, Any]:
    context = build_experiment_context(session, prompt, budget, config, variant_id)
    generation = LLMProvider().generate(context, mode=mode)
    combined = context.render() + "\n" + generation.text
    missing = [
        expected
        for expected in session.expected_answer_contains
        if expected.lower() not in combined.lower()
    ]
    unsafe = [
        marker
        for marker in session.unsafe_answer_contains
        if marker and marker.lower() in combined.lower()
    ]
    cached_tokens = cached_token_estimate(context, config["kvCache"])
    reusable_ratio = round((cached_tokens / max(1, context.estimated_tokens)) * 100, 1)
    billable_tokens = max(0, context.estimated_tokens - round(cached_tokens * 0.5))
    estimated_latency = estimated_latency_ms(context, config, cached_tokens)
    utilization = (
        round((context.estimated_tokens / budget.available_input_tokens) * 100, 1)
        if budget.available_input_tokens
        else 0
    )
    quality = quality_score(missing, unsafe, context.warnings, utilization)
    return {
        "id": variant_id,
        "name": name,
        "description": description,
        "mode": mode,
        "settings": dict(config),
        "tokens": context.estimated_tokens,
        "billableTokens": billable_tokens,
        "cachedTokens": cached_tokens,
        "cacheReuseRatio": reusable_ratio,
        "maxInputTokens": budget.max_input_tokens,
        "reservedOutputTokens": budget.reserved_output_tokens,
        "availableTokens": budget.available_input_tokens,
        "tokenUtilization": utilization,
        "latencyMs": estimated_latency,
        "qualityScore": quality,
        "passed": not missing and not unsafe,
        "missing": missing,
        "unsafe": unsafe,
        "warnings": list(context.warnings),
        "sections": context_sections(context),
        "apiPrompt": context.render(),
        "apiMessages": context.as_prompt_messages(),
        "answer": generation.text,
        "lesson": lesson_for_result(config, missing, unsafe, utilization, cached_tokens),
    }


def build_experiment_context(
    session,
    prompt: str,
    budget: Budget,
    config: dict[str, Any],
    strategy_name: str,
) -> ContextBundle:
    sections = [ContextSection("정책", session.policy, priority=100)]
    compression = config["compression"]
    retrieval = config["retrieval"] == "on"
    retention_turns = max(0, min(_message_count(session), int(config["retentionTurns"])))

    if compression in {"summary", "hybrid"}:
        sections.append(ContextSection("실행 요약", session.summary, priority=90))
    if compression in {"structured", "hybrid"}:
        sections.append(ContextSection("사용자 프로필", "\n".join(session.profile_lines()), priority=95))
        memory = "\n".join(f"- {item.text}" for item in session.safe_memory_items())
        sections.append(ContextSection("안전 memory", memory, priority=85))
    if retrieval or compression == "hybrid":
        retriever = Retriever(session.documents, session.safe_memory_items())
        hits = retriever.search(prompt + " " + session.summary, limit=4)
        retrieved = "\n\n".join(
            f"- {hit.title} (출처={hit.source}, 점수={hit.score:.2f}): {hit.snippet}"
            for hit in hits
        )
        sections.append(ContextSection("검색 근거", retrieved, priority=92, source="retriever"))
    if compression == "hybrid" and session.tool_results:
        tool_summaries = "\n".join(f"- {result.name}: {result.summary}" for result in session.tool_results)
        sections.append(ContextSection("도구 결과 요약", tool_summaries, priority=76, source="tool"))
    if retention_turns:
        recent = session.transcript[-retention_turns:]
        sections.append(ContextSection("최근 대화", session.transcript_text(recent), priority=70))
    sections.append(ContextSection("현재 사용자 질문", prompt, priority=100))

    kept, dropped = trim_to_budget(sections, budget)
    warnings = []
    if dropped:
        warnings.append(f"dropped_sections={','.join(dropped)}")
    bundle = ContextBundle(strategy=strategy_name, sections=kept, warnings=warnings)
    if bundle.estimated_tokens > budget.available_input_tokens * budget.warning_threshold:
        bundle.warnings.append("near_context_budget")
    return bundle


def cached_token_estimate(context: ContextBundle, cache_mode: str) -> int:
    if cache_mode == "off":
        return 0
    static_labels = {
        "policy",
        "user_profile",
        "safe_memory",
        "running_summary",
        "retrieved_context",
        "tool_result_summaries",
        "정책",
        "사용자 프로필",
        "안전 memory",
        "실행 요약",
        "검색 근거",
        "도구 결과 요약",
    }
    conversation_labels = static_labels | {"recent_transcript", "최근 대화"}
    labels = conversation_labels if cache_mode == "conversation" else static_labels
    return sum(section.tokens for section in context.sections if section.label in labels)


def estimated_latency_ms(context: ContextBundle, config: dict[str, Any], cached_tokens: int) -> float:
    retrieval_cost = 55 if config["retrieval"] == "on" else 0
    compression_cost = 35 if config["compression"] in {"summary", "hybrid"} else 0
    cache_discount = cached_tokens * 0.08
    return round(max(40, 90 + context.estimated_tokens * 0.32 + retrieval_cost + compression_cost - cache_discount), 1)


def quality_score(missing: list[str], unsafe: list[str], warnings: list[str], utilization: float) -> int:
    score = 100
    score -= len(missing) * 18
    score -= len(unsafe) * 35
    score -= len(warnings) * 8
    score -= max(0, utilization - 80) * 0.4
    return max(5, min(100, round(score)))


def lesson_for_result(
    config: dict[str, Any],
    missing: list[str],
    unsafe: list[str],
    utilization: float,
    cached_tokens: int,
) -> str:
    if unsafe:
        return "민감 정보가 답변 경로에 포함되었습니다. privacy 필터와 안전한 memory 분리가 필요합니다."
    if missing and config["compression"] == "none":
        return "최근 대화만으로는 오래된 결정이나 문서 근거가 빠질 수 있습니다. 요약 또는 RAG를 추가해 보세요."
    if missing:
        return "필수 근거가 아직 부족합니다. 유지 턴 수를 늘리거나 검색 근거를 켜서 비교해 보세요."
    if utilization > 80:
        return "답변은 가능하지만 token 예산에 가깝습니다. 요약 전략과 KV 캐시 재사용을 실험할 구간입니다."
    if cached_tokens:
        return "반복되는 정책, 요약, 프로필을 cache prefix로 두면 다음 턴의 계산 부담을 줄일 수 있습니다."
    return "현재 설정은 기준선으로 좋습니다. 유지 턴 수를 줄이거나 압축을 켜서 비용 변화를 비교해 보세요."


def experiment_guidance(result: dict[str, Any], session) -> list[str]:
    retention = result["settings"]["retentionTurns"]
    guidance = [
        f"현재 설정은 최근 {retention}개 메시지를 직접 유지합니다.",
        result["lesson"],
    ]
    if result["cachedTokens"]:
        guidance.append(
            f"KV 캐시 후보는 약 {result['cachedTokens']} token입니다. 정책과 요약처럼 반복되는 prefix에 적합합니다."
        )
    else:
        guidance.append("KV 캐시를 끄면 매 턴 같은 정책과 요약을 다시 처리한다고 가정합니다.")
    if _message_count(session) > retention:
        guidance.append("오래된 대화에 중요한 결정이 있으면 최근 대화만 유지하는 방식은 실패할 수 있습니다.")
    return guidance


def capture_summary(selected: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    best_quality = max(results, key=lambda item: item["qualityScore"])
    lowest_tokens = min(results, key=lambda item: item["tokens"])
    best_cache = max(results, key=lambda item: item["cachedTokens"])
    return {
        "headline": f"{selected['name']} 실험 요약",
        "selected": selected["name"],
        "bestQuality": best_quality["name"],
        "lowestTokens": lowest_tokens["name"],
        "bestCache": best_cache["name"],
        "takeaway": selected["lesson"],
    }


def _message_count(session) -> int:
    return len(session.transcript)


def result_payload(result, budget: Budget) -> dict[str, Any]:
    available_tokens = budget.available_input_tokens
    token_utilization = (
        round((result.context.estimated_tokens / available_tokens) * 100, 1)
        if available_tokens
        else 0
    )
    return {
        "case": result.case_id,
        "strategy": result.strategy,
        "mode": result.mode,
        "tokens": result.context.estimated_tokens,
        "maxInputTokens": budget.max_input_tokens,
        "reservedOutputTokens": budget.reserved_output_tokens,
        "availableTokens": available_tokens,
        "tokenUtilization": token_utilization,
        "latencyMs": round(result.context.latency_ms, 2),
        "passed": result.passed,
        "missing": list(result.missing_expected),
        "unsafe": list(result.unsafe_found),
        "warnings": list(result.context.warnings),
        "sections": context_sections(result.context),
        "answer": result.generation.text,
    }


def context_sections(context: ContextBundle) -> list[dict[str, Any]]:
    total_tokens = max(1, context.estimated_tokens)
    return [
        {
            "label": section.label,
            "content": section.content,
            "tokens": section.tokens,
            "tokenShare": round((section.tokens / total_tokens) * 100, 1),
            "priority": section.priority,
            "source": section.source,
        }
        for section in context.sections
    ]


def _budget(params: dict[str, list[str]]) -> Budget:
    return Budget(
        max_input_tokens=int(_one(params, "maxInputTokens", "900")),
        reserved_output_tokens=int(_one(params, "reservedOutputTokens", "200")),
    )


def _one(params: dict[str, list[str]], name: str, default: str) -> str:
    values = params.get(name)
    return values[0] if values else default


def _many(params: dict[str, list[str]], name: str) -> list[str]:
    values = params.get(name, [])
    if len(values) == 1 and "," in values[0]:
        return [value for value in values[0].split(",") if value]
    return values


def _int(params: dict[str, list[str]], name: str, default: int) -> int:
    try:
        return int(_one(params, name, str(default)))
    except ValueError:
        return default


def _choice(params: dict[str, list[str]], name: str, default: str, choices: set[str]) -> str:
    value = _one(params, name, default)
    return value if value in choices else default


if __name__ == "__main__":
    raise SystemExit(main())
