from context_lab.cases import load_case
from context_lab.models import Budget
from context_lab.privacy import contains_pii, redact_pii
from context_lab.strategies import get_strategy


def test_redact_pii_replaces_phone_and_email() -> None:
    text = "Contact minji@example.com or 010-1234-5678."

    redacted, found = redact_pii(text)

    assert "minji@example.com" not in redacted
    assert "010-1234-5678" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert set(found) == {"email", "phone"}


def test_contains_pii_detects_korean_resident_number() -> None:
    assert contains_pii("주민등록번호는 900101-1234567 입니다.")


def test_privacy_strategy_filters_unsafe_memory() -> None:
    session, user_turn = load_case("privacy_memory")

    context = get_strategy("privacy").build(session, user_turn, Budget())
    rendered = context.render()

    assert "사용자는 간결한 한국어 답변을 선호합니다." in rendered
    assert "minji@example.com" not in rendered
    assert "010-9999-8888" not in rendered
    assert "[REDACTED_PHONE]" in rendered
