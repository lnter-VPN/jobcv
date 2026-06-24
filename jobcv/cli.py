"""jobcv command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, ats, llm

POLISH_SYSTEM = (
    "你是资深简历优化顾问。根据目标岗位 JD，重写用户简历，使其更贴合岗位、"
    "用量化成果和强动词、自然融入 JD 关键词，但严禁编造未提供的经历或数据。"
    "保持原有事实，只优化表达与结构。用与原简历相同的语言输出，只输出优化后的简历正文。"
)


def _read(path: str) -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"file not found: {path}")
    return p.read_text(encoding="utf-8", errors="replace")


def cmd_score(args: argparse.Namespace) -> int:
    resume = _read(args.resume)
    jd = _read(args.jd)
    r = ats.match(resume, jd, top=args.top)
    print(f"ATS 匹配分: {r.score}/100  ({len(r.matched)}/{r.total} 关键词命中)\n")
    print("✅ 命中:", "  ".join(r.matched) or "(无)")
    print("\n❌ 缺失:", "  ".join(r.missing) or "(无)")
    if r.missing:
        print("\n建议: 把上面缺失的关键词（属实的）自然写进简历，可显著提升过筛率。")
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
    sc.set_defaults(func=cmd_score)

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
