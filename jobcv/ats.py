"""ATS keyword matching — pure stdlib, no LLM, fully testable.

Extracts candidate keywords from a job description and measures how many
appear in a resume. Handles English tokens and CJK (Chinese) terms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Common English stopwords + filler words that should never count as keywords.
_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "have",
    "has", "had", "this", "that", "from", "but", "not", "all", "can", "out",
    "who", "what", "when", "where", "how", "why", "a", "an", "to", "of", "in",
    "on", "at", "by", "is", "be", "as", "or", "we", "us", "it", "its", "their",
    "they", "them", "he", "she", "his", "her", "i", "me", "my", "do", "does",
    "job", "work", "role", "team", "company", "experience", "responsibilities",
    "requirements", "preferred", "plus", "etc", "ability", "strong", "good",
}

# English word (>=2 chars, may contain + # . - like c++, node.js, ci/cd parts)
_EN_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+#./\-]*[A-Za-z0-9+#]|[A-Za-z]{2,}")
# Runs of CJK characters
_CJK_RUN = re.compile(r"[一-鿿]{2,}")

# Chinese single-char particles/verbs that are noise even after segmentation.
_CJK_STOP = {
    "的", "了", "和", "与", "及", "或", "在", "是", "有", "要求", "负责", "熟悉",
    "熟练", "掌握", "具备", "拥有", "以及", "等", "对", "并", "能", "需",
}

try:  # optional, better Chinese segmentation: pip install jobcv[zh]
    import jieba

    jieba.setLogLevel(60)
    _HAS_JIEBA = True
except Exception:  # pragma: no cover
    _HAS_JIEBA = False


def _cjk_terms(run: str) -> list[str]:
    if _HAS_JIEBA:
        return [
            w for w in jieba.lcut(run)
            if len(w) >= 2 and w not in _CJK_STOP
        ]
    # fallback: 2- and 3-grams
    grams = []
    for n in (2, 3):
        grams += [run[i : i + n] for i in range(len(run) - n + 1)]
    return grams


def _normalize(text: str) -> str:
    return text.lower()


def extract_keywords(text: str, top: int = 40) -> list[str]:
    """Return candidate keywords from text, most frequent first."""
    norm = _normalize(text)
    counts: dict[str, int] = {}

    for m in _EN_TOKEN.findall(norm):
        if len(m) < 2 or m in _STOPWORDS:
            continue
        counts[m] = counts.get(m, 0) + 1

    # CJK: segment each run into candidate terms.
    for run in _CJK_RUN.findall(text):
        for term in _cjk_terms(run):
            counts[term] = counts.get(term, 0) + 1

    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [k for k, _ in ordered[:top]]


@dataclass
class MatchResult:
    score: float  # 0..100
    matched: list[str]
    missing: list[str]

    @property
    def total(self) -> int:
        return len(self.matched) + len(self.missing)


def match(resume_text: str, jd_text: str, top: int = 40) -> MatchResult:
    """Score how well a resume covers the keywords in a job description."""
    keywords = extract_keywords(jd_text, top=top)
    resume_norm = _normalize(resume_text)

    matched, missing = [], []
    for kw in keywords:
        # CJK grams: substring match on raw resume; English: substring on lower.
        hit = kw in resume_norm if kw.isascii() else kw in resume_text
        (matched if hit else missing).append(kw)

    score = round(100 * len(matched) / len(keywords), 1) if keywords else 0.0
    return MatchResult(score=score, matched=matched, missing=missing)
