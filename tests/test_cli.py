import json

from jobcv import cli


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_score_json(tmp_path, capsys):
    resume = _write(tmp_path, "resume.txt", "Built Python services with Docker.")
    jd = _write(tmp_path, "jd.txt", "Python and Docker and Kubernetes required.")
    rc = cli.main(["score", "--resume", resume, "--jd", jd, "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["matched"] and data["missing"]
    assert "kubernetes" in data["missing"]
    assert data["total"] == len(data["matched"]) + len(data["missing"])
    assert 0 < data["score"] < 100


def test_report_json(tmp_path, capsys):
    resume = _write(
        tmp_path,
        "resume.txt",
        "张伟 zhangwei@example.com 138-0000-0000\n"
        "工作经历\n主导支付重构，QPS 提升 300%\n技能\nPython\n教育\n本科\n",
    )
    rc = cli.main(["report", "--resume", resume, "--json"])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["has_email"] is True
    assert isinstance(data["issues"], list)
    assert 0 <= data["score"] <= 100


def test_match_json_sorted(tmp_path, capsys):
    resume = _write(tmp_path, "r.txt", "Python Docker Kubernetes microservices.")
    backend = _write(tmp_path, "backend.txt", "Python Docker Kubernetes microservices.")
    frontend = _write(tmp_path, "frontend.txt", "React TypeScript CSS Figma.")
    rc = cli.main(
        ["match", "--resume", resume, "--jds", backend, frontend, "--json"]
    )
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert [d["label"] for d in data][0] == "backend"
    assert data[0]["score"] >= data[1]["score"]
