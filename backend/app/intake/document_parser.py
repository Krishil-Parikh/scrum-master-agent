"""Text extraction for the four input formats the PRD calls out
(Markdown, TXT, PDF, DOCX). PDF/DOCX support degrades gracefully if the
optional library isn't installed, rather than hard-failing the whole
intake pipeline over a format the deployment doesn't need."""

from __future__ import annotations

import io
import logging

logger = logging.getLogger("ai_dev_pod.intake")


class UnsupportedDocumentError(ValueError):
    pass


def extract_text(filename: str, raw_bytes: bytes) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("md", "markdown", "txt", ""):
        return raw_bytes.decode("utf-8", errors="replace")

    if ext == "pdf":
        return _extract_pdf(raw_bytes)

    if ext == "docx":
        return _extract_docx(raw_bytes)

    raise UnsupportedDocumentError(
        f"Unsupported document type '.{ext}'. Supported: .md, .txt, .pdf, .docx"
    )


def _extract_pdf(raw_bytes: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise UnsupportedDocumentError(
            "PDF support requires the 'pypdf' package (pip install pypdf)."
        ) from exc
    reader = PdfReader(io.BytesIO(raw_bytes))
    return "\n\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_docx(raw_bytes: bytes) -> str:
    try:
        import docx
    except ImportError as exc:
        raise UnsupportedDocumentError(
            "DOCX support requires the 'python-docx' package (pip install python-docx)."
        ) from exc
    document = docx.Document(io.BytesIO(raw_bytes))
    return "\n".join(p.text for p in document.paragraphs)
