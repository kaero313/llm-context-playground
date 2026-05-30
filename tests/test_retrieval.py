from context_lab.cases import load_case
from context_lab.retrieval import Retriever


def test_retriever_prefers_current_policy_for_reimbursement() -> None:
    session, _ = load_case("internal_policy")
    retriever = Retriever(session.documents, session.safe_memory_items())

    hits = retriever.search("current monitor chair reimbursement cap", limit=2)

    assert hits
    assert hits[0].document_id == "policy_remote_2026"
    assert "500 USD" in hits[0].snippet


def test_retriever_excludes_unsafe_memory() -> None:
    session, _ = load_case("privacy_memory")
    retriever = Retriever(session.documents, session.memory_items)

    hits = retriever.search("email minji", limit=5)

    assert all("minji@example.com" not in hit.snippet for hit in hits)

