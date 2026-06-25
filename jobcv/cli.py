"""jobcv command-line interface."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from . import __version__, ats, extract, llm, report

POLISH_SYSTEM = (
    "你是资深简历优化顾问。根据目标岗位 JD，重写用户简历，使其更贴合岗位、"
    "用量化成果和强动词、自然融入 JD 关键词，但严禁编造未提供的经历或数据。"
    "保持原有事实，只优化表达与结构。用与原简历相同的语言输出，只输出优化后的简历正文。"
)

COVER_SYSTEM = (
    "你是求职信写作专家。基于用户简历和目标岗位 JD，写一封简洁有力的求职信（cover letter）："
    "开头点明应聘岗位与匹配亮点，主体用简历中的真实经历与量化成果证明胜任，"
    "结尾礼貌表达意向。严禁编造经历，只用简历里有的事实。控制在 250-400 字，"
    "用与简历相同的语言，只输出信件正文。"
)

INTERVIEW_SYSTEM = (
    "你是该岗位的资深面试官。根据 JD 和候选人简历，预测最可能被问到的面试题，"
    "覆盖：技术/专业题、项目深挖题、行为题。每题给出【考察点】和【作答方向提示】，"
    "但不要替候选人编造具体经历。按类别分组，用 Markdown 输出 8-12 题。"
    "用与 JD 相同的语言。"
)


def _read(path: str) -> str:
    """Read a resume/JD file, auto-extracting text from PDF/DOCX when needed."""
    try:
        return extract.from_path(path)
    except extract.ExtractError as e:
        sys.exit(str(e))


def _emit_json(payload: object) -> None:
    """Print a JSON document to stdout (machine-readable mode)."""
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def cmd_score(args: argparse.Namespace) -> int:
    resume = _read(args.resume)
    jd = _read(args.jd)
    r = ats.match(resume, jd, top=args.top)
    if args.json:
        _emit_json({
            "score": r.score,
            "matched": r.matched,
            "missing": r.missing,
            "priority": r.top_missing(3),
            "total": r.total,
        })
        return 0
    print(f"ATS 匹配分: {r.score}/100  ({len(r.matched)}/{r.total} 关键词命中)\n")
    print("✅ 命中:", "  ".join(r.matched) or "(无)")
    print("\n❌ 缺失:", "  ".join(r.missing) or "(无)")
    if r.missing:
        print(f"\n建议: 优先补这几个 JD 最看重的缺失词（属实的）→ {'  '.join(r.top_missing(3))}")
        print("把它们自然写进简历，可显著提升过筛率。")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    rep = report.analyze(_read(args.resume))
    if args.json:
        _emit_json(dataclasses.asdict(rep))
        return 0
    print(f"简历体检分: {rep.score}/100\n")
    print(f"  字数        : {rep.word_count}")
    print(f"  经历条目    : {rep.bullet_count}")
    print(f"  量化条目    : {rep.quantified}/{rep.bullet_count} ({round(rep.quantified_ratio*100)}%)")
    print(f"  强动词开头  : {rep.strong_verb_bullets}   弱开头: {rep.weak_opener_bullets}")
    print(f"  含板块      : {'、'.join(rep.sections_present) or '(无)'}")
    print(f"  联系方式    : 邮箱 {'✓' if rep.has_email else '✗'}  电话 {'✓' if rep.has_phone else '✗'}")
    print("\n改进建议:")
    for it in rep.issues:
        print(f"  {'⚠️ ' if it.level == 'warn' else '💡 '}{it.msg}")
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    resume = _read(args.resume)
    jds = {Path(p).stem: _read(p) for p in args.jds}
    ranked = ats.rank(resume, jds, top=args.top)
    if args.json:
        _emit_json([
            {
                "label": rj.label,
                "score": rj.result.score,
                "matched": rj.result.matched,
                "missing": rj.result.missing,
                "priority": rj.result.top_missing(3),
                "total": rj.result.total,
            }
            for rj in ranked
        ])
        return 0
    print(f"一份简历 × {len(ranked)} 个岗位，按匹配度排序:\n")
    for i, rj in enumerate(ranked, 1):
        r = rj.result
        print(f"{i}. {rj.label:<24} {r.score:>5}/100  ({len(r.matched)}/{r.total} 命中)")
    best = ranked[0].result
    print(f"\n最匹配: 「{ranked[0].label}」，优先补的缺失词:",
          "  ".join(best.top_missing(5)) or "(无)")
    return 0


def _ai_generate(args: argparse.Namespace, system: str) -> str:
    resume = _read(args.resume)
    jd = _read(args.jd)
    cfg = llm.LLMConfig.from_backend(
        args.backend, model=args.model, base_url=args.base_url, api_key=args.api_key
    )
    if cfg.api_key is None and args.backend == "deepseek":
        sys.exit("缺少 API key：设置环境变量 DEEPSEEK_API_KEY 或用 --api-key 传入。")
    print(f"[调用 {args.backend} / {cfg.model}] 生成中…", file=sys.stderr)
    user = f"目标岗位 JD：\n{jd}\n\n候选人简历：\n{resume}"
    return llm.chat(cfg, system, user)


def cmd_cover(args: argparse.Namespace) -> int:
    text = _ai_generate(args, COVER_SYSTEM)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(text)
    return 0


def cmd_interview(args: argparse.Namespace) -> int:
    print(_ai_generate(args, INTERVIEW_SYSTEM))
    return 0


def cmd_polish(args: argparse.Namespace) -> int:
    resume = _read(args.resume)
    jd = _read(args.jd)
    before = ats.match(resume, jd, top=args.top)

    cfg = llm.LLMConfig.from_backend(
        args.backend, model=args.model, base_url=args.base_url, api_key=args.api_key
    )
    if cfg.api_key is None and args.backend == "deepseek":
        sys.exit("缺少 API key：设置环境变量 DEEPSEEK_API_KEY 或用 --api-key 传入。")

    user = f"目标岗位 JD：\n{jd}\n\n当前简历：\n{resume}"
    print(f"[调用 {args.backend} / {cfg.model}] 优化中…", file=sys.stderr)
    polished = llm.chat(cfg, POLISH_SYSTEM, user)

    after = ats.match(polished, jd, top=args.top)
    if args.out:
        Path(args.out).write_text(polished, encoding="utf-8")
        print(f"已写入 {args.out}", file=sys.stderr)
    else:
        print(polished)
    print(
        f"\nATS 匹配分: {before.score} → {after.score}  (+{round(after.score - before.score, 1)})",
        file=sys.stderr,
    )
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        sys.exit("缺少依赖：pip install 'jobcv[api]'（FastAPI + uvicorn），即可启动网页版。")
    print(f"jobcv 网页版: http://{args.host}:{args.port}", file=sys.stderr)
    uvicorn.run("jobcv.api:app", host=args.host, port=args.port, reload=args.reload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobcv", description="AI 简历优化 + ATS 匹配")
    p.add_argument("--version", action="version", version=f"jobcv {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("score", help="只算 ATS 关键词匹配分（不调用 LLM）")
    sc.add_argument("--resume", required=True)
    sc.add_argument("--jd", required=True)
    sc.add_argument("--top", type=int, default=40)
    sc.add_argument("--json", action="store_true", help="输出 JSON，便于脚本/CI 集成")
    sc.set_defaults(func=cmd_score)

    rp = sub.add_parser("report", help="简历体检：量化率/强动词/板块/联系方式（纯本地，免 key）")
    rp.add_argument("--resume", required=True)
    rp.add_argument("--json", action="store_true", help="输出 JSON，便于脚本/CI 集成")
    rp.set_defaults(func=cmd_report)

    mt = sub.add_parser("match", help="一份简历对多个 JD，排出最匹配岗位（纯本地）")
    mt.add_argument("--resume", required=True)
    mt.add_argument("--jds", required=True, nargs="+", help="多个 JD 文件路径")
    mt.add_argument("--top", type=int, default=40)
    mt.add_argument("--json", action="store_true", help="输出 JSON，便于脚本/CI 集成")
    mt.set_defaults(func=cmd_match)

    cv = sub.add_parser("cover", help="生成求职信（调用 LLM）")
    cv.add_argument("--resume", required=True)
    cv.add_argument("--jd", required=True)
    cv.add_argument("--backend", default="deepseek")
    cv.add_argument("--model", default=None)
    cv.add_argument("--base-url", default=None)
    cv.add_argument("--api-key", default=None)
    cv.add_argument("--out", default=None)
    cv.set_defaults(func=cmd_cover)

    iv = sub.add_parser("interview", help="预测面试题 + 考点（调用 LLM）")
    iv.add_argument("--resume", required=True)
    iv.add_argument("--jd", required=True)
    iv.add_argument("--backend", default="deepseek")
    iv.add_argument("--model", default=None)
    iv.add_argument("--base-url", default=None)
    iv.add_argument("--api-key", default=None)
    iv.set_defaults(func=cmd_interview)

    po = sub.add_parser("polish", help="按 JD 优化简历（调用 LLM）")
    po.add_argument("--resume", required=True)
    po.add_argument("--jd", required=True)
    po.add_argument("--backend", default="deepseek", help="deepseek | ollama | 自定义")
    po.add_argument("--model", default=None)
    po.add_argument("--base-url", default=None, help="自定义 OpenAI 兼容地址")
    po.add_argument("--api-key", default=None)
    po.add_argument("--out", default=None, help="输出文件，不填则打印到终端")
    po.add_argument("--top", type=int, default=40)
    po.set_defaults(func=cmd_polish)

    sv = sub.add_parser("serve", help="启动网页版（需要 jobcv[api]）")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    sv.add_argument("--reload", action="store_true", help="开发模式：改代码自动重载")
    sv.set_defaults(func=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
