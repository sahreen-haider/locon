"""Bundled fictional documents. Plain text and .docx are parsed to text."""

from __future__ import annotations

from pathlib import Path

from app.config import DATA_DIR

TITLES = {
    "memo_small": "Board memo (fictional)",
    "memo_large": "Board memo, large (fictional)",
    "proposal_poisoned": "Supplier proposal with hidden instruction (fictional)",
}
SUFFIXES = (".txt", ".docx")


class DocumentNotFound(KeyError):
    pass


def _bundled() -> dict[str, Path]:
    return {p.stem: p for p in sorted(DATA_DIR.iterdir()) if p.suffix in SUFFIXES and p.is_file()}


def list_documents() -> list[dict]:
    return [
        {"id": doc_id, "title": TITLES.get(doc_id, doc_id), "bytes": path.stat().st_size}
        for doc_id, path in _bundled().items()
    ]


def load_document(doc_id: str) -> str:
    path = _bundled().get(doc_id)
    if path is None:
        raise DocumentNotFound(doc_id)
    if path.suffix == ".docx":
        import docx

        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    return path.read_text(encoding="utf-8")
