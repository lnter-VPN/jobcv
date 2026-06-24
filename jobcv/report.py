"""Resume health check — pure stdlib, no LLM, fully local and free.

Scores a resume on writing quality independent of any single job description:

* **Quantification** — share of experience bullets that contain a number
  (``提升 30%``, ``服务 10w+ 用户``). Recruiters weight quantified impact heavily.
* **Strong verbs** — bullets that open with an achievement verb (``主导``,
  ``重构``, ``led``, ``built``) vs. weak fillers (``负责``, ``参与``,
  ``responsible for``).
* **Length** — word/character count against a sane range.
* **Sections** — whether the usual blocks (education / experience / skills) and
  contact info (email / phone) are present.

Returns a 0..100 health score plus concrete, actionable suggestions. Bilingual
(Chinese + English) heuristics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# A "bullet" is a non-empty line; we treat the resume as line-oriented.
_NUM = re.compile(r"\d")
_PERCENT_OR_SCALE = re.compile(r"\d+\s*[%％]|\d+\s*[wWkK万亿]|\$\s*\d|\d{3,}")

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{6,}\d)(?!\d)")

# Strong achievement verbs (line openers). Bilingual.
_STRONG_VERBS = {
    "主导", "主持", "负责搭建", "搭建", "设计", "重构", "优化", "提升", "实现",
    "推动", "落地", "构建", "开发", "独立", "带领", "牵头", "攻克", "解决",
    "led", "built", "designed", "architected", "launched", "shipped",
    "improved", "increased", "reduced", "drove", "owned", "delivered",
    "created", "developed", "implemented", "scaled", "optimized", "founded",
}

# Weak / passive openers that dilute impact.
_WEAK_OPENERS = {
    "负责", "参与", "协助", "配合", "跟进", "辅助", "帮助",
    "responsible for", "worked on", "helped with", "involved in",
    "assisted with", "participated in", "tasked with",
}

# Section heading hints.
_SECTIONS = {
    "education": ("教育", "学历", "education", "academic"),
    "experience": ("经历", "经验", "工作", "项目", "experience", "employment", "projects"),
    "skills": ("技能", "技术栈", "专长", "skills", "technologies", "stack"),
}


@dataclass
class Issue:
    level: str  # "warn" | "tip"
    msg: str


@dataclass
class HealthReport:
    score: float
    word_count: int
    bullet_count: int
    quantified: int          # bullets containing a metric
    quantified_ratio: float  # 0..1
    strong_verb_bullets: int
    weak_opener_bullets: int
    sections_present: list[str]
    sections_missing: list[str]
    has_email: bool
    has_phone: bool
    issues: list[Issue] = field(default_factory=list)


def _bullets(text: str) -> list[str]:
    out = []
    for raw in text.splitlines():
        line = raw.strip().lstrip("•·-*◦▪●○ \t")
        if line:
            out.append(line)
    return out


def _word_count(text: str) -> int:
    en = re.findall(r"[A-Za-z][A-Za-z0-9+#./\-]*", text)
    cjk = re.findall(r"[一-鿿]", text)
    return len(en) + len(cjk)


def _opens_with(line: str, vocab: set[str]) -> bool:
    low = line.lower()
    for v in vocab:
        if v.isascii():
            if low.startswith(v):
                return True
        elif line.startswith(v):
            return True
    return False


def analyze(resume_text: str) -> HealthReport:
    bullets = _bullets(resume_text)
    wc = _word_count(resume_text)

    quantified = sum(1 for b in bullets if _PERCENT_OR_SCALE.search(b) or _NUM.search(b))
    strong = sum(1 for b in bullets if _opens_with(b, _STRONG_VERBS))
    weak = sum(1 for b in bullets if _opens_with(b, _WEAK_OPENERS))

    low_all = resume_text.lower()
    present, missing = [], []
    for name, hints in _SECTIONS.items():
        if any((h in low_all) if h.isascii() else (h in resume_text) for h in hints):
            present.append(name)
        else:
            missing.append(name)

    has_email = bool(_EMAIL.search(resume_text))
    has_phone = bool(_PHONE.search(resume_text))

    q_ratio = quantified / len(bullets) if bullets else 0.0

    # --- scoring (0..100) ---------------------------------------------------
    # quantification 35, strong-verb usage 25, length 15, sections 15, contact 10
    q_score = 35 * min(q_ratio / 0.5, 1.0)  # 50% quantified bullets = full marks
    denom = strong + weak
    verb_score = 25 * (strong / denom) if denom else 25 * 0.5
    if 250 <= wc <= 900:
        len_score = 15.0
    elif wc < 250:
        len_score = 15 * (wc / 250)
    else:
        len_score = max(0.0, 15 - (wc - 900) / 100)
    sec_score = 15 * (len(present) / len(_SECTIONS))
    contact_score = 5 * has_email + 5 * has_phone
    score = round(q_score + verb_score + len_score + sec_score + contact_score, 1)

    # --- suggestions --------------------------------------------------------
    issues: list[Issue] = []
    if q_ratio < 0.4:
        issues.append(Issue("warn",
            f"量化成果偏少（仅 {quantified}/{len(bullets)} 条含数字）。"
            "给关键经历补上指标：提升百分比、用户/QPS 规模、节省时长。"))
    if weak > strong:
        issues.append(Issue("warn",
            f"弱开头过多（{weak} 条以「负责/参与/responsible for」开头）。"
            "换成强动词：主导/重构/上线/led/built/shipped。"))
    if missing:
        zh = {"education": "教育", "experience": "工作/项目经历", "skills": "技能"}
        issues.append(Issue("warn",
            "缺少常规板块：" + "、".join(zh.get(m, m) for m in missing) + "。"))
    if not has_email and not has_phone:
        issues.append(Issue("warn", "没检测到联系方式（邮箱/电话），HR 无法联系你。"))
    elif not has_email:
        issues.append(Issue("tip", "建议补上邮箱。"))
    if wc < 250:
        issues.append(Issue("tip", f"内容偏短（约 {wc} 词），可补充项目细节与成果。"))
    elif wc > 1100:
        issues.append(Issue("tip", f"内容偏长（约 {wc} 词），精简到 1-2 页更易读。"))
    if not issues:
        issues.append(Issue("tip", "结构与表达都不错，可再针对具体岗位用 score/polish 微调。"))

    return HealthReport(
        score=score,
        word_count=wc,
        bullet_count=len(bullets),
        quantified=quantified,
        quantified_ratio=round(q_ratio, 3),
        strong_verb_bullets=strong,
        weak_opener_bullets=weak,
        sections_present=present,
        sections_missing=missing,
        has_email=has_email,
        has_phone=has_phone,
        issues=issues,
    )
