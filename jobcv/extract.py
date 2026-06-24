"""Extract plain text from uploaded resume files (PDF / DOCX / TXT).

PDF and DOCX support are optional — install ``jobcv[files]`` (pypdf +
python-docx). Plain text and markdown always work with zero dependencies.
"""

from __future__ import annotations

from pathlib import Path

SUPPORTED = (".txt", ".md", ".pdf", ".docx")


class ExtractError(RuntimeError):
    pass


def from_bytes(data: bytes, filename: str) -> str:
    """Extract text from raw file bytes, dispatching on the filename suffix."""
    suffix = Path(filename).suffix.lower()
    if suffix in (".txt", ".md", ""):
        return data.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        return _from_pdf(data)
    if suffix == ".docx":
        return _from_docx(data)
    raise ExtractError(f"不支持的文件类型：{suffix or '(无后缀)'}，支持 {', '.join(SUPPORTED)}")


def from_path(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise ExtractError(f"文件不存在：{path}")
    return from_bytes(p.read_bytes(), p.name)


def _from_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ExtractError("解析 PDF 需要依赖：pip install 'jobcv[files]'（pypdf）。")
    import io

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    if not text.strip():
        raise ExtractError("PDF 没提取到文字（可能是扫描件/图片版，需 OCR）。")
    return text


def _from_docx(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError:
        raise ExtractError("解析 DOCX 需要依赖：pip install 'jobcv[files]'（python-docx）。")
    import io

    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)
