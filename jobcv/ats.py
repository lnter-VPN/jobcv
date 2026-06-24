"""ATS keyword matching — pure stdlib, no LLM, fully testable.

Extracts candidate keywords from a job description and measures how well a
resume covers them. Improvements over a naive bag-of-words matcher:

* **Synonym/skill dictionary** — ``k8s`` matches ``kubernetes``, ``js`` matches
  ``javascript``, ``机器学习`` matches ``ML``, etc. (see ``SYNONYM_GROUPS``).
* **Frequency weighting** — a term the JD repeats counts for more than one it
  mentions once, so the score reflects what the role actually emphasises.
* **Word-boundary matching** for English, so ``go`` no longer matches ``good``
  and ``ai`` no longer matches ``training`` (a real bug in substring matching).

Handles English tokens and CJK (Chinese) terms.
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
    "required", "require", "must", "should", "knowledge", "skills", "skill",
    "years", "year", "including", "include", "using", "use", "well", "able",
    "need", "needs", "looking", "seeking", "candidate", "candidates", "position",
    "join", "help", "build", "building", "across", "within", "into", "more",
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

# Synonym / skill groups. The first item in each group is the canonical form
# that shows up in matched/missing output; every other item is an alias that
# counts as the same skill. Keep aliases unambiguous — avoid bare words like
# "go"/"r" that collide with ordinary prose.
SYNONYM_GROUPS: list[tuple[str, ...]] = [
    ("kubernetes", "k8s"),
    ("javascript", "js"),
    ("typescript", "ts"),
    ("postgresql", "postgres", "psql"),
    ("nodejs", "node.js"),
    ("golang", "go-lang"),
    ("react", "reactjs", "react.js"),
    ("vue", "vuejs", "vue.js"),
    ("ci/cd", "cicd", "ci-cd", "持续集成", "持续交付"),
    ("docker", "容器化", "containerization"),
    ("microservices", "microservice", "微服务"),
    ("distributed-systems", "distributed", "分布式", "分布式系统"),
    ("high-concurrency", "高并发"),
    ("machine-learning", "ml", "机器学习"),
    ("deep-learning", "dl", "深度学习"),
    ("artificial-intelligence", "人工智能"),
    ("nlp", "自然语言处理"),
    ("aws", "amazon-web-services"),
    ("gcp", "google-cloud"),
    ("rest", "restful", "restful-api"),
]

_ALIAS_TO_CANON: dict[str, str] = {}
_CANON_TO_SURFACES: dict[str, set[str]] = {}
for _group in SYNONYM_GROUPS:
    _canon = _group[0]
    _CANON_TO_SURFACES[_canon] = set(_group)
    for _alias in _group:
        _ALIAS_TO_CANON[_alias] = _canon

# Multi-char CJK skill surfaces, longest first, pulled out of a run before
# segmentation so jieba can't split e.g. 机器学习 into 机器 / 学习.
_CJK_SURFACES = sorted(
    (s for s in _ALIAS_TO_CANON if not s.isascii()), key=len, reverse=True
)

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


def _canon(term: str) -> str:
    """Map a surface term to its canonical skill name (itself if unknown)."""
    return _ALIAS_TO_CANON.get(term, term)


def keyword_weights(text: str, top: int = 40) -> dict[str, int]:
    """Return canonical keyword -> weight (frequency), most frequent first.

    Aliases are folded into their canonical form so e.g. a JD that says both
    "kubernetes" and "k8s" contributes a single weighted keyword.
    """
    norm = _normalize(text)
    counts: dict[str, int] = {}

    for m in _EN_TOKEN.findall(norm):
        if len(m) < 2 or m in _STOPWORDS:
            continue
        key = _canon(m)
        counts[key] = counts.get(key, 0) + 1

    # CJK: pull known skill surfaces out first, then segment the rest.
    for run in _CJK_RUN.findall(text):
        remaining = run
        for surface in _CJK_SURFACES:
            if surface in remaining:
                key = _ALIAS_TO_CANON[surface]
                counts[key] = counts.get(key, 0) + remaining.count(surface)
                remaining = remaining.replace(surface, "　")  # full-width space
        for term in _cjk_terms(remaining):
            key = _canon(term)
            counts[key] = counts.get(key, 0) + 1

    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return dict(ordered[:top])


def extract_keywords(text: str, top: int = 40) -> list[str]:
    """Return candidate canonical keywords from text, most frequent first."""
    return list(keyword_weights(text, top=top))


def _present(canon: str, resume_norm: str, resume_raw: str) -> bool:
    """True if the keyword (or any of its aliases) appears in the resume.

    English terms match on word boundaries (so "go" != "good"); CJK terms
    match as substrings (segmentation already gave us meaningful units).
    """
    for surface in _CANON_TO_SURFACES.get(canon, {canon}):
        if surface.isascii():
            pat = r"(?<![a-z0-9])" + re.escape(surface) + r"(?![a-z0-9])"
            if re.search(pat, resume_norm):
                return True
        elif surface in resume_raw:
            return True
    return False


@dataclass
class MatchResult:
    score: float  # 0..100, frequency-weighted
    matched: list[str]
    missing: list[str]

    @property
    def total(self) -> int:
        return len(self.matched) + len(self.missing)


def match(resume_text: str, jd_text: str, top: int = 40) -> MatchResult:
    """Score how well a resume covers the keywords in a job description.

    The score is frequency-weighted: keywords the JD emphasises count for more.
    """
    weights = keyword_weights(jd_text, top=top)
    resume_norm = _normalize(resume_text)

    matched, missing = [], []
    got_weight = 0
    total_weight = 0
    for kw, w in weights.items():
        total_weight += w
        if _present(kw, resume_norm, resume_text):
            matched.append(kw)
            got_weight += w
        else:
            missing.append(kw)

    score = round(100 * got_weight / total_weight, 1) if total_weight else 0.0
    return MatchResult(score=score, matched=matched, missing=missing)
