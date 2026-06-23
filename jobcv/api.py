"""jobcv HTTP API — FastAPI backend wrapping the ats + llm core.

Serves a JSON API under /api and the static web UI at /. Keep this thin:
all real logic lives in `ats` and `llm` so the CLI and API stay in sync.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, ats, llm
from .cli import POLISH_SYSTEM

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="jobcv", version=__version__)


# ---- schemas ---------------------------------------------------------------

class ScoreIn(BaseModel):
    resume: str = Field(..., min_length=1)
    jd: str = Field(..., min_length=1)
    top: int = Field(40, ge=5, le=100)


class MatchOut(BaseModel):
    score: float
    matched: list[str]
    missing: list[str]
    total: int


class PolishIn(ScoreIn):
    backend: str = "deepseek"
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    temperature: float = Field(0.4, ge=0.0, le=1.0)


class PolishOut(BaseModel):
    polished: str
    before: MatchOut
    after: MatchOut
    backend: str
    model: str


# ---- helpers ---------------------------------------------------------------

def _match_out(r: ats.MatchResult) -> MatchOut:
    return MatchOut(score=r.score, matched=r.matched, missing=r.missing, total=r.total)


# ---- API -------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.get("/api/backends")
def backends() -> dict:
    return {
        "backends": [
            {"name": name, "base_url": url, "model": model, "needs_key": bool(env)}
            for name, (url, model, env) in llm.BACKENDS.items()
        ]
    }


@app.post("/api/score", response_model=MatchOut)
def score(body: ScoreIn) -> MatchOut:
    return _match_out(ats.match(body.resume, body.jd, top=body.top))


@app.post("/api/polish", response_model=PolishOut)
def polish(body: PolishIn) -> PolishOut:
    before = ats.match(body.resume, body.jd, top=body.top)
    try:
        cfg = llm.LLMConfig.from_backend(
            body.backend, model=body.model,
            base_url=body.base_url, api_key=body.api_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if cfg.api_key is None and body.backend == "deepseek":
        raise HTTPException(
            status_code=400,
            detail="缺少 API key：在请求中传 api_key 或设置环境变量 DEEPSEEK_API_KEY。",
        )

    user = f"目标岗位 JD：\n{body.jd}\n\n当前简历：\n{body.resume}"
    try:
        polished = llm.chat(cfg, POLISH_SYSTEM, user, temperature=body.temperature)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    after = ats.match(polished, body.jd, top=body.top)
    return PolishOut(
        polished=polished,
        before=_match_out(before),
        after=_match_out(after),
        backend=body.backend,
        model=cfg.model,
    )


# ---- static web UI (mounted last so /api wins) -----------------------------

if WEB_DIR.is_dir():
    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
