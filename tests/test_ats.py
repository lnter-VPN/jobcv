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


def test_cjk_terms():
    jd = "招聘后端工程师，要求熟悉分布式系统与高并发架构。"
    resume = "负责分布式系统设计，处理高并发请求。"
    r = ats.match(resume, jd)
    # jieba segments these as real terms; both appear in the resume.
    assert "分布式系统" in r.matched
    assert "并发" in r.matched
    assert "招聘" in r.missing  # JD-only noise correctly flagged missing


def test_stopwords_excluded():
    kws = ats.extract_keywords("the and for you our team work role")
    assert kws == []


def test_perfect_and_zero():
    assert ats.match("python docker", "python docker").score == 100.0
    assert ats.match("nothing here", "rust golang").score == 0.0
