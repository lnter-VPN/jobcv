from jobcv import ats, extract, report


def test_report_rewards_quantified_strong_resume():
    resume = (
        "张伟  zhangwei@example.com  138-0000-0000\n"
        "工作经历\n"
        "主导支付系统重构，QPS 提升 300%，故障率下降 60%\n"
        "重构订单服务，接口耗时从 800ms 优化到 120ms\n"
        "上线风控模型，拦截欺诈交易 1.2 万笔\n"
        "技能\n"
        "Python, Go, Kubernetes\n"
        "教育\n"
        "某大学 计算机 本科\n"
    )
    rep = report.analyze(resume)
    assert rep.has_email and rep.has_phone
    assert rep.quantified >= 3
    assert rep.strong_verb_bullets >= 2
    assert set(rep.sections_present) == {"education", "experience", "skills"}
    assert rep.score > 70


def test_report_flags_weak_resume():
    resume = (
        "负责一些日常工作\n"
        "参与项目开发\n"
        "协助团队完成任务\n"
    )
    rep = report.analyze(resume)
    assert rep.weak_opener_bullets >= rep.strong_verb_bullets
    assert rep.sections_missing  # no clear sections
    assert not rep.has_email
    assert rep.score < 60
    assert any(i.level == "warn" for i in rep.issues)


def test_rank_orders_jds_best_first():
    resume = "Python backend with Docker and Kubernetes, built microservices."
    jds = {
        "backend": "Python, Docker, Kubernetes, microservices required.",
        "frontend": "React, TypeScript, CSS and Figma needed.",
    }
    ranked = ats.rank(resume, jds)
    assert ranked[0].label == "backend"
    assert ranked[0].result.score > ranked[1].result.score


def test_extract_plain_text():
    text = extract.from_bytes("hello 简历".encode(), "resume.txt")
    assert "简历" in text


def test_extract_unsupported_suffix():
    import pytest

    with pytest.raises(extract.ExtractError):
        extract.from_bytes(b"x", "resume.xyz")
