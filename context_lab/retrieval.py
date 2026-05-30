from __future__ import annotations

import math
import re
from collections import Counter

from context_lab.models import Document, MemoryItem, RetrievalHit

_TERM_RE = re.compile(r"[A-Za-z0-9가-힣]+")


def tokenize(text: str) -> list[str]:
    return [term.lower() for term in _TERM_RE.findall(text)]


class Retriever:
    """Small lexical retriever for deterministic RAG experiments."""

    def __init__(self, documents: list[Document], memories: list[MemoryItem] | None = None):
        self.documents = documents
        self.memories = memories or []

    def search(self, query: str, limit: int = 3) -> list[RetrievalHit]:
        query_terms = Counter(tokenize(query))
        if not query_terms:
            return []

        hits: list[RetrievalHit] = []
        for document in self.documents:
            searchable = " ".join((document.title, document.body, document.source, *document.tags))
            score = self._score(query_terms, searchable)
            score *= self._document_weight(document)
            if score > 0:
                hits.append(
                    RetrievalHit(
                        document_id=document.id,
                        title=document.title,
                        snippet=self._snippet(document.body, query_terms),
                        score=score,
                        source=document.source,
                    )
                )

        for memory in self.memories:
            if not memory.safe_to_store or memory.contains_pii:
                continue
            score = self._score(query_terms, memory.text)
            if score > 0:
                hits.append(
                    RetrievalHit(
                        document_id=memory.id,
                        title="장기 memory",
                        snippet=memory.text,
                        score=score * 0.9,
                        source="memory",
                    )
                )

        hits.sort(key=lambda hit: (-hit.score, hit.document_id))
        return hits[:limit]

    @staticmethod
    def _score(query_terms: Counter[str], text: str) -> float:
        doc_terms = Counter(tokenize(text))
        if not doc_terms:
            return 0.0
        overlap = set(query_terms) & set(doc_terms)
        if not overlap:
            return 0.0
        raw = sum(query_terms[term] * doc_terms[term] for term in overlap)
        norm = math.sqrt(sum(v * v for v in doc_terms.values()))
        return raw / norm

    @staticmethod
    def _document_weight(document: Document) -> float:
        marker = " ".join((document.title, document.source, *document.tags)).lower()
        if "archive" in marker or "archived" in marker or "보관" in marker:
            return 0.35
        if "current" in marker or "2026" in marker or "최신" in marker:
            return 1.25
        return 1.0

    @staticmethod
    def _snippet(text: str, query_terms: Counter[str], width: int = 260) -> str:
        lower = text.lower()
        positions = [lower.find(term) for term in query_terms if lower.find(term) >= 0]
        if not positions:
            return text[:width].strip()
        start = max(0, min(positions) - 80)
        end = min(len(text), start + width)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"
