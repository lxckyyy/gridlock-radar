"""Load a plan document as a list of page texts (index 0 = page 1)."""

from __future__ import annotations

import re
from pathlib import Path

SUPPORTED = {".txt", ".pdf"}
PAGE_MARK = re.compile(r"^=== Page (\d+) ===\s*$", re.M)


def load_pages(path: Path) -> list[str]:
    if path.suffix.lower() == ".pdf":
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            return [page.extract_text() or "" for page in pdf.pages]

    # Plain-text stand-ins for PDFs mark page breaks with "=== Page N ===".
    parts = PAGE_MARK.split(path.read_text())
    if len(parts) == 1:
        return [parts[0]]
    return [parts[i + 1] for i in range(1, len(parts), 2)]


def utility_name(pages: list[str], fallback: str) -> str:
    for page in pages:
        m = re.search(r"^\s*Utility:\s*(.+?)\s*$", page, re.M)
        if m:
            return m[1]
    return fallback


def list_documents(folder: Path) -> list[Path]:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in SUPPORTED)
