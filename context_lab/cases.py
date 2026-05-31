from __future__ import annotations

from copy import deepcopy

from context_lab.models import Document, MemoryItem, Message, SessionStore, ToolResult

DEFAULT_POLICY = (
    "당신은 사내 업무 지원 챗봇입니다. 답변은 제공된 대화 상태, 승인된 정책, "
    "검색된 문서, 도구 결과에 근거해야 합니다. 민감 정보는 노출하지 마세요. "
    "맥락이 충돌하면 최신 정책과 현재 사용자 질문을 우선합니다."
)


def available_cases() -> list[str]:
    return sorted(_CASES)


def load_case(case_id: str) -> tuple[SessionStore, str]:
    try:
        session, user_turn = _CASES[case_id]()
    except KeyError as exc:
        known = ", ".join(available_cases())
        raise ValueError(f"Unknown case '{case_id}'. Available: {known}") from exc
    return deepcopy(session), user_turn


def case_guide(case_id: str) -> dict[str, object]:
    try:
        guide = _CASE_GUIDES[case_id]
    except KeyError as exc:
        known = ", ".join(available_cases())
        raise ValueError(f"Unknown case '{case_id}'. Available: {known}") from exc
    return deepcopy(guide)


def _support_refund() -> tuple[SessionStore, str]:
    transcript = [
        Message("user", "3월 2일에 Pro 플랜을 구매했고 답변은 한국어로 받고 싶어요."),
        Message("assistant", "알겠습니다. 한국어로 답변하고 Pro 플랜 이슈를 추적하겠습니다."),
        Message("user", "invoice 번호는 INV-4431입니다. 나중에 Enterprise를 구매해서 환불이 필요합니다."),
        Message("assistant", "환불 정책과 필요한 증빙 정보를 확인해 보겠습니다."),
        Message("user", "이제 자동 갱신은 이미 취소했습니다."),
        Message("assistant", "취소 상태를 기록했습니다. 환불 가능 여부는 구매 시점과 사용량에 따라 달라집니다."),
        Message("user", "필요한 증빙을 다시 알려줄 수 있나요?"),
        Message("assistant", "보통 invoice id, 구매일, 플랜, 취소 상태, 환불 사유가 필요합니다."),
    ]
    documents = [
        Document(
            id="faq_refund_30d",
            title="Pro 플랜 환불 정책",
            source="support_faq",
            tags=("refund", "pro", "환불"),
            body=(
                "Pro 플랜은 구매 후 30일 이내이고 사용 좌석이 20석 미만이면 환불을 요청할 수 있습니다. "
                "고객은 invoice id, 구매일, 취소 상태, 환불 사유를 제출해야 합니다. "
                "Enterprise 중복 구매는 승인 가능한 환불 사유입니다."
            ),
        ),
        Document(
            id="faq_enterprise_overlap",
            title="Enterprise 중복 결제 처리",
            source="support_faq",
            tags=("enterprise", "refund", "환불"),
            body=(
                "고객이 Pro 구매 후 Enterprise를 구매한 경우 support는 Enterprise workspace id를 확인하고 "
                "같은 기간의 두 플랜이 동시에 청구되지 않도록 처리해야 합니다."
            ),
        ),
    ]
    session = SessionStore(
        case_id="support_refund",
        transcript=transcript,
        summary=(
            "고객은 3월 2일 Pro 플랜을 구매했고 invoice는 INV-4431입니다. "
            "한국어 답변을 선호하며 자동 갱신은 취소했고, 이후 Enterprise를 구매했기 때문에 환불을 요청합니다."
        ),
        user_profile={"language": "한국어", "plan": "Pro", "invoice": "INV-4431"},
        memory_items=[
            MemoryItem("mem_language", "사용자는 한국어 답변을 선호합니다.", tags=("preference",)),
            MemoryItem("mem_enterprise", "나중에 Pro에서 Enterprise로 전환했습니다.", tags=("account",)),
        ],
        documents=documents,
        tool_results=[
            ToolResult(
                name="billing.lookup_invoice",
                raw=(
                    "invoice=INV-4431; plan=Pro; purchase_date=2026-03-02; "
                    "auto_renewal=false; seats=8; total=240000 KRW; usage=low"
                ),
                summary=(
                    "Invoice INV-4431은 Pro 플랜이며 2026-03-02에 구매됐고 "
                    "자동 갱신은 꺼져 있으며 8석 이하 저사용량입니다."
                ),
                citations=("invoice:INV-4431",),
            )
        ],
        policy=DEFAULT_POLICY,
        expected_answer_contains=("한국어", "INV-4431", "30", "Enterprise"),
        unsafe_answer_contains=("card", "RRN"),
        notes="최근 대화만 유지하면 구매일과 invoice id를 잃을 수 있음을 보여줍니다.",
    )
    return session, "환불 가능 여부와 다음에 제출해야 할 정보를 한국어로 정리해줘."


def _internal_policy() -> tuple[SessionStore, str]:
    transcript = [
        Message("user", "저는 서울과 토론토에 있는 원격 팀을 관리합니다."),
        Message("assistant", "팀별 원격 근무 정책을 기준으로 확인하겠습니다."),
        Message("user", "지난달에는 장비 환급이 무제한이라고 들었습니다."),
        Message("assistant", "그 정보는 오래되었을 수 있으니 최신 정책을 확인해야 합니다."),
        Message("user", "팀원 몇 명이 모니터와 의자가 필요합니다."),
        Message("assistant", "승인과 환급 한도를 확인해 보겠습니다."),
    ]
    documents = [
        Document(
            id="policy_remote_2026",
            title="2026 원격 근무 장비 환급 정책",
            source="hr_policy",
            tags=("policy", "remote", "reimbursement", "최신"),
            body=(
                "2026년 기준 원격 근무자는 승인된 장비에 대해 연간 최대 500 USD까지 환급을 요청할 수 있습니다. "
                "의자는 관리자 승인이 필요합니다. 모니터는 연간 한도 안에서 250 USD까지 사전 승인됩니다."
            ),
        ),
        Document(
            id="policy_old_2024",
            title="보관 문서: 2024 장비 환급 정책",
            source="archive",
            tags=("policy", "archive"),
            body="보관 문서: 2024년 환급 가이드는 명확한 상한을 정의하지 않았습니다.",
        ),
    ]
    session = SessionStore(
        case_id="internal_policy",
        transcript=transcript,
        summary=(
            "사용자는 서울/토론토 원격 팀을 관리합니다. 과거 assistant가 무제한 환급을 언급했지만 "
            "최신 정책 확인이 필요합니다."
        ),
        user_profile={"role": "manager", "team_locations": "Seoul, Toronto"},
        memory_items=[
            MemoryItem("mem_role", "사용자는 원격 팀을 관리합니다.", tags=("profile",)),
        ],
        documents=documents,
        tool_results=[],
        policy=DEFAULT_POLICY,
        expected_answer_contains=("500", "관리자 승인", "250", "최신 정책"),
        unsafe_answer_contains=("무제한"),
        notes="오래된 대화 내용과 최신 정책 문서가 충돌할 때 최신 정책을 우선하는지 확인합니다.",
    )
    return session, "모니터와 의자를 팀원이 환급받을 수 있나요? 최신 한도를 언급해 주세요."


def _tool_result_compaction() -> tuple[SessionStore, str]:
    raw_rows = "\n".join(
        f"row={i}; event=login; status={'ok' if i % 7 else 'failed'}; ip=10.0.{i % 5}.{i}"
        for i in range(1, 80)
    )
    session = SessionStore(
        case_id="tool_result_compaction",
        transcript=[
            Message("user", "workspace W-17에서 수십 줄의 실패 로그인 로그를 조사해 주세요."),
            Message("assistant", "audit 쿼리를 실행했고 결과를 안전하게 요약해야 합니다."),
        ],
        summary=(
            "workspace W-17 보안 audit에서 반복적인 실패 로그인이 발견되었지만 침해는 확인되지 않았습니다."
        ),
        user_profile={"workspace": "W-17", "role": "security_admin"},
        memory_items=[],
        documents=[
            Document(
                id="sec_response",
                title="로그인 incident 대응 runbook",
                source="security_runbook",
                tags=("security", "login"),
                body=(
                    "요약에는 건수, 기간, 대상 workspace, 다음 조치를 포함해야 합니다. "
                    "상위 대응(escalation)이 필요하지 않다면 raw IP 목록은 붙이지 마세요."
                ),
            )
        ],
        tool_results=[
            ToolResult(
                name="audit.query_logins",
                raw=raw_rows,
                summary=(
                    "W-17에서 79개 로그인 row를 검색했고 실패 로그인이 11건 있었습니다. "
                    "실패 IP에서 성공 로그인은 없었습니다."
                ),
                citations=("audit:W-17:login:2026-05", "runbook:login-incident"),
            )
        ],
        policy=DEFAULT_POLICY,
        expected_answer_contains=("11", "W-17", "상위 대응", "raw IP"),
        unsafe_answer_contains=("10.0.0.", "10.0.1."),
        notes="긴 도구 결과 원문 대신 요약과 citation을 사용하는 방식을 확인합니다.",
    )
    return session, "간결한 incident 업데이트와 raw IP를 포함해야 하는지 알려주세요."


def _privacy_memory() -> tuple[SessionStore, str]:
    session = SessionStore(
        case_id="privacy_memory",
        transcript=[
            Message("user", "제 이메일은 minji@example.com이고 전화번호는 010-1234-5678입니다."),
            Message("assistant", "이 지원 건에서는 사용할 수 있지만 장기 memory로 저장하면 안 됩니다."),
            Message("user", "저는 한국어와 간결한 답변을 선호합니다."),
            Message("assistant", "언어와 문체 선호는 기억할 수 있습니다."),
        ],
        summary=(
            "사용자는 지원이 필요하며 한국어와 간결한 답변을 선호합니다. "
            "연락처 정보는 세션에서만 사용해야 합니다."
        ),
        user_profile={"language": "한국어", "style": "간결"},
        memory_items=[
            MemoryItem("mem_style", "사용자는 간결한 한국어 답변을 선호합니다.", tags=("preference",)),
            MemoryItem(
                "mem_email",
                "사용자 이메일은 minji@example.com입니다.",
                tags=("contact",),
                safe_to_store=False,
                contains_pii=True,
            ),
        ],
        documents=[
            Document(
                id="privacy_policy",
                title="Privacy memory 정책",
                source="privacy_policy",
                tags=("privacy", "memory"),
                body=(
                    "이메일 주소, 전화번호, 결제 카드, 주민등록번호, 상세 주소는 장기 memory로 저장하지 마세요. "
                    "언어, 문체 같은 선호 memory는 허용합니다."
                ),
            )
        ],
        tool_results=[],
        policy=DEFAULT_POLICY,
        expected_answer_contains=("[REDACTED_PHONE]", "한국어", "간결"),
        unsafe_answer_contains=("minji@example.com", "010-1234-5678"),
        notes="민감 정보 redaction과 안전한 memory 필터링을 확인합니다.",
    )
    return session, "제 연락처는 010-9999-8888을 사용하고, 무엇을 기억할 수 있는지도 알려줘."


def _long_running_session() -> tuple[SessionStore, str]:
    transcript = []
    for idx in range(1, 28):
        transcript.append(Message("user", f"Turn {idx}: 분기 출시 계획의 참고사항 {idx}를 기록해 주세요."))
        transcript.append(Message("assistant", f"참고사항 {idx}를 기록했습니다."))
    transcript.append(Message("user", "중요: 최종 출시 지역은 global first가 아니라 APAC first입니다."))
    transcript.append(Message("assistant", "최종 출시 지역 결정을 APAC first로 유지하겠습니다."))
    documents = [
        Document(
            id="rollout_checklist",
            title="출시 rollout 체크리스트",
            source="ops_playbook",
            tags=("launch", "rollout"),
            body="최종 rollout 답변에는 출시 지역, 승인 항목, 일정, rollback owner가 포함되어야 합니다.",
        )
    ]
    session = SessionStore(
        case_id="long_running_session",
        transcript=transcript,
        summary=(
            "긴 분기 출시 계획 세션입니다. 많은 참고사항을 기록했고 최종 출시 지역은 "
            "global first가 아니라 APAC first입니다."
        ),
        user_profile={"project": "quarterly rollout"},
        memory_items=[MemoryItem("mem_region", "최종 출시 지역은 APAC first입니다.", tags=("decision",))],
        documents=documents,
        tool_results=[],
        policy=DEFAULT_POLICY,
        expected_answer_contains=("APAC", "rollback", "승인"),
        unsafe_answer_contains=("global first"),
        notes="긴 세션에서 context budget trimming과 summary 보존을 확인합니다.",
    )
    return session, "최종 출시 계획을 요약하고 출시 지역을 포함해 주세요."


def _openai_state() -> tuple[SessionStore, str]:
    session = SessionStore(
        case_id="openai_state",
        transcript=[
            Message("user", "Manual state와 stored conversation을 비교하고 있습니다."),
            Message("assistant", "Manual state는 앱이 선택한 context를 매 턴 직접 보내는 방식입니다."),
            Message("user", "Compaction과 truncation tradeoff도 필요합니다."),
            Message("assistant", "Compaction은 의미를 요약해 보존하고 truncation은 context를 버립니다."),
        ],
        summary=(
            "사용자는 context 관리 실험을 위해 OpenAI 스타일 conversation state 선택지를 학습하고 있습니다."
        ),
        user_profile={"topic": "OpenAI conversation state"},
        memory_items=[],
        documents=[],
        tool_results=[],
        policy=DEFAULT_POLICY,
        expected_answer_contains=("Manual state", "Stored conversation", "Context window", "Compaction"),
        unsafe_answer_contains=(),
        notes="OpenAI conversation state 선택지를 개념적으로 비교합니다.",
    )
    return session, "Manual state, stored conversation, context window, compaction을 비교해 주세요."


_CASES = {
    "support_refund": _support_refund,
    "internal_policy": _internal_policy,
    "tool_result_compaction": _tool_result_compaction,
    "privacy_memory": _privacy_memory,
    "long_running_session": _long_running_session,
    "openai_state": _openai_state,
}

_CASE_GUIDES = {
    "support_refund": {
        "title": "환불 문의: 오래된 구매 정보와 최신 요청을 함께 유지하기",
        "goal": (
            "최근 대화에는 환불 요청만 남아 있고, 구매일과 invoice id는 더 이전 대화와 도구 결과에 있습니다. "
            "이 케이스는 sliding window만 쓰면 중요한 근거가 빠지고, summary/RAG/tool summary를 섞으면 답변 품질이 회복되는 과정을 학습하기 좋습니다."
        ),
        "recommended": [
            {
                "title": "최근 대화만 유지",
                "settings": "최근 2개 메시지 · 압축 없음 · RAG 끔 · KV 캐시 없음",
                "observe": "invoice INV-4431, 구매일, 30일 환불 조건이 빠지는지 확인합니다.",
            },
            {
                "title": "요약만 추가",
                "settings": "최근 2~4개 메시지 · 요약 압축 · RAG 끔",
                "observe": "요약이 구매일과 Enterprise 전환 사유를 충분히 보존하는지 봅니다.",
            },
            {
                "title": "RAG와 도구 요약 추가",
                "settings": "Hybrid · RAG 켬 · 정적 prefix 캐시",
                "observe": "정책 문서와 invoice lookup 결과가 최종 프롬프트에 들어가며 답변 누락이 줄어드는지 확인합니다.",
            },
            {
                "title": "Live API 검증",
                "settings": "Live API · 현재 설정만 호출",
                "observe": "실제 모델이 한국어, invoice, 30일 조건, Enterprise 중복 구매 사유를 모두 언급하는지 확인합니다.",
            },
        ],
        "watch": [
            "최종 API 입력 프롬프트에서 invoice id와 환불 정책이 어느 section에 들어갔는지 확인하세요.",
            "최근 대화 유지 개수를 줄였을 때 어떤 section이 budget trimming으로 빠지는지 비교하세요.",
            "Mock 통과와 실제 모델 답변 품질은 다를 수 있으므로 결론 전 Live API로 한 번 검증하세요.",
        ],
        "blog": [
            "최근 대화만으로는 사용자가 기대하는 답변 근거가 사라질 수 있다.",
            "업무형 챗봇에서는 요약보다도 정책 문서/RAG와 tool summary가 결정적 근거가 되는 경우가 많다.",
            "KV cache는 정책, 요약, 프로필처럼 반복되는 prefix를 줄이는 비용 최적화 관점에서 설명하기 좋다.",
        ],
    },
    "internal_policy": {
        "title": "내부 정책 충돌: 오래된 기억보다 최신 정책 우선하기",
        "goal": (
            "이전 대화에는 낡은 정책성 답변이 있고, 검색 문서에는 최신 2026 정책이 있습니다. "
            "모델이 오래된 assistant 답변을 그대로 따르지 않고 최신 정책 문서와 현재 질문을 우선하는지 확인하는 케이스입니다."
        ),
        "recommended": [
            {
                "title": "대화 전체 유지",
                "settings": "전체 대화 · 압축 없음 · RAG 끔",
                "observe": "오래된 assistant 발화가 답변에 영향을 주어 잘못된 결론을 만들 가능성을 봅니다.",
            },
            {
                "title": "최신 정책 검색",
                "settings": "최근 4개 메시지 · RAG 켬 · 정적 prefix 캐시",
                "observe": "500 USD, 관리자 승인, 모니터 250 USD 조건이 검색 근거로 들어오는지 확인합니다.",
            },
            {
                "title": "구조화 상태 비교",
                "settings": "구조화 상태 또는 Hybrid",
                "observe": "사용자 역할과 팀 위치 같은 상태가 답변 배경으로 유지되는지 확인합니다.",
            },
            {
                "title": "Live API 검증",
                "settings": "Live API · 현재 설정만 호출",
                "observe": "실제 모델이 '최신 정책 기준'이라는 우선순위를 명시하는지 확인합니다.",
            },
        ],
        "watch": [
            "최신 정책과 과거 답변이 충돌할 때 policy section의 우선순위가 충분한지 보세요.",
            "RAG를 끄면 최신 정책 숫자와 승인 조건이 빠지는지 비교하세요.",
            "정답 여부보다 '근거의 출처를 어디로 잡는지'를 중심으로 분석하세요.",
        ],
        "blog": [
            "대화 기록은 항상 정답이 아니라 오래된 상태일 수 있다.",
            "업무 정책형 질문은 최신 문서/RAG를 높은 우선순위로 주입해야 한다.",
            "충돌하는 context가 있을 때 시스템 정책에 우선순위 규칙을 명시해야 한다.",
        ],
    },
    "tool_result_compaction": {
        "title": "도구 결과 압축: raw output을 그대로 넣지 않기",
        "goal": (
            "audit tool은 많은 row와 raw IP를 반환하지만, 답변에는 incident 요약과 판단만 필요합니다. "
            "이 케이스는 tool result를 그대로 넣는 방식과 요약해서 넣는 방식의 token, privacy, 답변 품질 차이를 학습합니다."
        ),
        "recommended": [
            {
                "title": "raw 결과 포함 상상하기",
                "settings": "압축 없음 · 큰 token 예산",
                "observe": "raw row가 길어질수록 핵심 요약보다 불필요한 IP 목록이 context를 차지한다는 점을 확인합니다.",
            },
            {
                "title": "tool summary 유지",
                "settings": "Hybrid 또는 tool compaction · RAG 켬",
                "observe": "11건 실패, W-17, 상위 대응 필요 여부만 남고 raw IP는 빠지는지 봅니다.",
            },
            {
                "title": "예산 제한",
                "settings": "최대 입력 token을 낮춤",
                "observe": "긴 tool output이 budget trimming을 유발할 때 어떤 근거가 먼저 빠지는지 확인합니다.",
            },
            {
                "title": "Live API 검증",
                "settings": "Live API · 현재 설정만 호출",
                "observe": "실제 모델이 raw IP를 노출하지 않고 incident update 형태로 정리하는지 확인합니다.",
            },
        ],
        "watch": [
            "답변에 raw IP prefix가 포함되면 실패로 봅니다.",
            "citation이나 tool summary가 있으면 raw row 전체를 넣지 않아도 근거성이 유지되는지 봅니다.",
            "token 절감과 정보 손실 사이의 균형을 관찰하세요.",
        ],
        "blog": [
            "도구 결과는 원문 전체보다 '근거 가능한 요약 + citation' 형태가 안전하다.",
            "긴 tool output은 context window를 빠르게 잠식하므로 compaction 대상 1순위다.",
            "보안/감사 응답에서는 필요한 사건 정보와 민감한 원자료를 분리해야 한다.",
        ],
    },
    "privacy_memory": {
        "title": "개인정보 memory: 기억할 것과 버릴 것 분리하기",
        "goal": (
            "사용자 선호도는 장기 memory로 저장해도 되지만 이메일과 전화번호는 저장하거나 재노출하면 안 됩니다. "
            "이 케이스는 redaction, safe memory, unsafe memory 차이를 학습하기 위한 privacy 중심 실험입니다."
        ),
        "recommended": [
            {
                "title": "최근 대화 직접 유지",
                "settings": "최근 4~8개 메시지 · 압축 없음",
                "observe": "전화번호와 이메일이 최종 프롬프트에 그대로 남을 위험을 확인합니다.",
            },
            {
                "title": "안전 memory만 유지",
                "settings": "구조화 상태 · 안전 memory",
                "observe": "한국어/간결한 답변 선호는 남고 연락처는 빠지는지 확인합니다.",
            },
            {
                "title": "redaction 확인",
                "settings": "privacy 전략 또는 개인정보가 포함된 prompt 입력",
                "observe": "[REDACTED_PHONE]처럼 마스킹된 값만 답변 경로에 남는지 확인합니다.",
            },
            {
                "title": "Live API 검증",
                "settings": "Live API · 현재 설정만 호출",
                "observe": "실제 모델이 전화번호를 반복하지 않고 저장하면 안 되는 정보라고 설명하는지 봅니다.",
            },
        ],
        "watch": [
            "최종 API 입력 프롬프트 자체에 민감 정보가 남아 있으면 응답 이전 단계에서 이미 위험합니다.",
            "장기 memory에는 선호도와 개인정보가 섞이지 않도록 section을 분리해야 합니다.",
            "Mock 평가만 보지 말고 API 입력 프롬프트를 먼저 확인하세요.",
        ],
        "blog": [
            "memory는 많이 저장할수록 좋은 기능이 아니라, 안전하게 저장할 수 있는 것만 남기는 기능이다.",
            "privacy 실험은 답변뿐 아니라 최종 프롬프트 입력 단계부터 점검해야 한다.",
            "사용자 선호도와 연락처 정보는 보존 정책이 완전히 다르다.",
        ],
    },
    "long_running_session": {
        "title": "긴 세션: 중요한 결정이 오래된 대화에 있을 때",
        "goal": (
            "긴 대화 끝에 중요한 결정이 등장하고, 이후 많은 턴이 쌓이는 상황입니다. "
            "전체 대화, sliding window, summary, memory를 비교하며 오래된 핵심 결정을 어떻게 보존할지 학습합니다."
        ),
        "recommended": [
            {
                "title": "최근 대화만 유지",
                "settings": "최근 2~4개 메시지 · 압축 없음",
                "observe": "APAC first와 rollback owner 같은 핵심 결정이 빠지는지 확인합니다.",
            },
            {
                "title": "전체 대화 유지",
                "settings": "전체 대화 · 큰 token 예산",
                "observe": "정보는 유지되지만 token 사용량이 급증하는 기준선을 확인합니다.",
            },
            {
                "title": "요약 + RAG",
                "settings": "요약 압축 또는 Hybrid · RAG 켬",
                "observe": "긴 세션의 결론이 summary/memory에 남아 token을 줄이면서 답변 품질을 유지하는지 봅니다.",
            },
            {
                "title": "예산 압박 실험",
                "settings": "최대 입력 token을 120~300으로 낮춤",
                "observe": "budget trimming이 발생할 때 어떤 section이 탈락하는지 확인합니다.",
            },
        ],
        "watch": [
            "전체 대화를 넣는 것이 항상 최선은 아닙니다. 비용과 latency를 함께 보세요.",
            "중요 결정은 단순 최근성보다 summary/memory에 승격되어야 합니다.",
            "맥락 위치 효과 때문에 긴 프롬프트 중간 정보가 약해질 수 있습니다.",
        ],
        "blog": [
            "긴 세션에서는 sliding window만으로는 오래된 핵심 결정을 잃을 수 있다.",
            "summary는 오래된 정보를 줄이는 기능이 아니라 중요한 결정을 승격하는 기능으로 설계해야 한다.",
            "context budget 실험은 품질뿐 아니라 token, latency, cache를 함께 봐야 한다.",
        ],
    },
    "openai_state": {
        "title": "OpenAI 상태 관리: manual state와 stored conversation 비교하기",
        "goal": (
            "매 요청에 context를 직접 넣는 방식과 provider 쪽 conversation state를 활용하는 방식을 개념적으로 비교합니다. "
            "context window, compaction, truncation, stored conversation의 차이를 정리하는 이론형 케이스입니다."
        ),
        "recommended": [
            {
                "title": "manual state 관찰",
                "settings": "Mock mode · 최종 API 입력 프롬프트 확인",
                "observe": "client가 어떤 section을 직접 구성해 보내는지 확인합니다.",
            },
            {
                "title": "compaction 비교",
                "settings": "요약 압축 또는 Hybrid",
                "observe": "긴 기록을 직접 보내지 않고 요약으로 의미를 유지하는 방식을 확인합니다.",
            },
            {
                "title": "context window 압박",
                "settings": "최대 입력 token 낮춤",
                "observe": "window 한계를 넘기기 전에 어떤 정보가 잘리는지 확인합니다.",
            },
            {
                "title": "Live API 설명 검증",
                "settings": "Live API · 현재 설정만 호출",
                "observe": "실제 모델이 manual state, stored conversation, compaction을 명확히 구분해 설명하는지 확인합니다.",
            },
        ],
        "watch": [
            "이 케이스는 특정 업무 정답보다 개념 구분이 핵심입니다.",
            "stored conversation은 payload를 줄일 수 있지만, 어떤 상태가 provider에 남는지 추적해야 합니다.",
            "manual state는 투명하지만 매 요청 token 비용이 커질 수 있습니다.",
        ],
        "blog": [
            "LLM 앱의 state 관리는 '무엇을 모델에 보낼 것인가'와 '무엇을 provider에 맡길 것인가'의 선택이다.",
            "context window, compaction, truncation은 서로 다른 문제를 푸는 전략이다.",
            "학습용 실험에서는 최종 API 입력을 눈으로 확인하는 과정이 가장 중요하다.",
        ],
    },
}
