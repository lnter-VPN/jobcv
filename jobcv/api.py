"""jobcv HTTP API — FastAPI backend wrapping the ats + llm core.

Serves a JSON API under /api and the static web UI at /. Keep this thin:
all real logic lives in `ats` and `llm` so the CLI and API stay in sync.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, ats, extract, llm, report
from .cli import COVER_SYSTEM, INTERVIEW_SYSTEM, POLISH_SYSTEM

_HERE = Path(__file__).resolve().parent
# Source layout keeps web/ at the repo root; the installed wheel ships it inside
# the package (see pyproject force-include). Use whichever exists.
WEB_DIR = next(
    (d for d in (_HERE / "web", _HERE.parent / "web") if d.is_dir()),
    _HERE / "web",
)

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
    priority: list[str]  # missing keywords the JD weights most, fix these first
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


class ReportIn(BaseModel):
    resume: str = Field(..., min_length=1)


class IssueOut(BaseModel):
    level: str
    msg: str


class ReportOut(BaseModel):
    score: float
    word_count: int
    bullet_count: int
    quantified: int
    quantified_ratio: float
    strong_verb_bullets: int
    weak_opener_bullets: int
    sections_present: list[str]
    sections_missing: list[str]
    has_email: bool
    has_phone: bool
    issues: list[IssueOut]


class RankIn(BaseModel):
    resume: str = Field(..., min_length=1)
    jds: dict[str, str] = Field(..., min_length=1)
    top: int = Field(40, ge=5, le=100)


class RankItemOut(BaseModel):
    label: str
    result: MatchOut


class RankOut(BaseModel):
    ranked: list[RankItemOut]


class GenIn(ScoreIn):
    backend: str = "deepseek"
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class GenOut(BaseModel):
    text: str
    backend: str
    model: str


class ExtractOut(BaseModel):
    text: str
    filename: str


# ---- helpers ---------------------------------------------------------------

def _match_out(r: ats.MatchResult) -> MatchOut:
    return MatchOut(score=r.score, matched=r.matched, missing=r.missing,
                    priority=r.top_missing(3), total=r.total)


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


@app.post("/api/report", response_model=ReportOut)
def report_endpoint(body: ReportIn) -> ReportOut:
    rep = report.analyze(body.resume)
    return ReportOut(
        score=rep.score,
        word_count=rep.word_count,
        bullet_count=rep.bullet_count,
        quantified=rep.quantified,
        quantified_ratio=rep.quantified_ratio,
        strong_verb_bullets=rep.strong_verb_bullets,
        weak_opener_bullets=rep.weak_opener_bullets,
        sections_present=rep.sections_present,
        sections_missing=rep.sections_missing,
        has_email=rep.has_email,
        has_phone=rep.has_phone,
        issues=[IssueOut(level=i.level, msg=i.msg) for i in rep.issues],
    )


@app.post("/api/match", response_model=RankOut)
def match_many(body: RankIn) -> RankOut:
    ranked = ats.rank(body.resume, body.jds, top=body.top)
    return RankOut(ranked=[
        RankItemOut(label=r.label, result=_match_out(r.result)) for r in ranked
    ])


@app.post("/api/extract", response_model=ExtractOut)
async def extract_endpoint(file: UploadFile = File(...)) -> ExtractOut:
    data = await file.read()
    try:
        text = extract.from_bytes(data, file.filename or "upload.txt")
    except extract.ExtractError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExtractOut(text=text, filename=file.filename or "")


def _gen(body: "GenIn", system: str) -> GenOut:
    try:
        cfg = llm.LLMConfig.from_backend(
            body.backend, model=body.model,
            base_url=body.base_url, api_key=body.api_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if cfg.api_key is None and body.backend == "deepseek":
        raise HTTPException(status_code=400,
            detail="缺少 API key：在请求中传 api_key 或设置环境变量 DEEPSEEK_API_KEY。")
    user = f"目标岗位 JD：\n{body.jd}\n\n候选人简历：\n{body.resume}"
    try:
        text = llm.chat(cfg, system, user)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return GenOut(text=text, backend=body.backend, model=cfg.model)


@app.post("/api/cover", response_model=GenOut)
def cover(body: GenIn) -> GenOut:
    return _gen(body, COVER_SYSTEM)


@app.post("/api/interview", response_model=GenOut)
def interview(body: GenIn) -> GenOut:
    return _gen(body, INTERVIEW_SYSTEM)


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
