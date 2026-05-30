from __future__ import annotations

import math
import re

_WORD_RE = re.compile(r"[A-Za-z0-9_]+|[가-힣]+|[^\sA-Za-z0-9_가-힣]")


def estimate_tokens(text: str) -> int:
    """Stable dependency-free token estimator for relative strategy comparison."""

    if not text:
        return 0
    pieces = _WORD_RE.findall(text)
    if not pieces:
        return max(1, math.ceil(len(text) / 4))

    total = 0
    for piece in pieces:
        if re.fullmatch(r"[가-힣]+", piece):
            total += max(1, math.ceil(len(piece) / 2))
        elif re.fullmatch(r"[A-Za-z0-9_]+", piece):
            total += max(1, math.ceil(len(piece) / 4))
        else:
            total += 1
    return total
