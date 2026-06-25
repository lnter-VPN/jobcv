from jobcv import ats


def test_english_keywords_and_score():
    jd = "We need a Python backend engineer with Docker, Kubernetes and PostgreSQL."
    resume = "Built Python services deployed with Docker on Kubernetes clusters."
    r = ats.match(resume, jd)
    assert "python" in r.matched
    assert "docker" in r.matched
    assert "kubernetes" in r.matched
    assert "postgresql" in r.missing
    assert 0 < r.score < 100


def test_synonyms_match():
    # JD uses full names, resume uses abbreviations — should still match.
    jd = "Kubernetes, JavaScript and PostgreSQL required."
    resume = "Shipped apps on k8s, wrote js frontends, stored data in postgres."
    r = ats.match(resume, jd)
    assert r.matched == ["kubernetes", "javascript", "postgresql"] or set(
        r.matched
    ) == {"kubernetes", "javascript", "postgresql"}
    assert r.missing == []
    assert r.score == 100.0


def test_cross_language_synonym():
    jd = "要求熟悉机器学习与微服务架构。"
    resume = "Built ML pipelines and microservices in production."
    r = ats.match(resume, jd)
    assert "machine-learning" in r.matched
    assert "microservices" in r.matched


def test_word_boundary_no_false_positive():
    # "go" must not match inside "good"; "ai" must not match inside "training".
    jd = "Go and AI experience."
    resume = "I did good work and enjoy training models."
    r = ats.match(resume, jd)
    assert "good" not in r.matched
    # neither golang nor ai should be counted as present
    assert r.score == 0.0


def test_frequency_weighting():
    # python mentioned 3x, rust 1x. Matching only python should score high.
    jd = "Python python python and rust."
    resume = "Strong Python developer."
    r = ats.match(resume, jd)
    assert "python" in r.matched
    assert "rust" in r.missing
    # Sublinear TF (1 + log2 tf): python weighs 1+log2(3)=2.585, rust 1.0.
    # So python's 3 mentions still beat a flat 1-of-2 (50), but a repeated
    # word can't run away with the whole score the way linear weighting would
    # (which gave 3/4 = 75). 2.585 / 3.585 = 72.1%.
    assert r.score == 72.1
    # Strictly between naive-flat (50) and linear-TF (75).
    assert 50.0 < r.score < 75.0


def test_cjk_terms():
    jd = "招聘后端工程师，要求熟悉分布式系统与高并发架构。"
    resume = "负责分布式系统设计，处理高并发请求。"
    r = ats.match(resume, jd)
    assert "distributed-systems" in r.matched  # 分布式系统 canonicalized
    assert "high-concurrency" in r.matched  # 高并发 canonicalized
    # "招聘" is recruiting filler — dropped as a stopword, never a keyword.
    assert "招聘" not in r.matched and "招聘" not in r.missing


def test_stopwords_excluded():
    kws = ats.extract_keywords("the and for you our team work role")
    assert kws == []


def test_perfect_and_zero():
    assert ats.match("python docker", "python docker").score == 100.0
    assert ats.match("nothing here", "rust golang").score == 0.0
