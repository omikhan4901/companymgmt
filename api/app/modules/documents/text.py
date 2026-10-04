"""Plain text from uploaded files, and passages for search.

PDF, Word (.docx), PowerPoint (.pptx), text, Markdown and CSV are read; anything else
(images, spreadsheets) has no searchable text. Every step is capped, so a hostile file
can't take the server down: pages, unpacked size and characters are all limited, and a
file that fails to parse simply isn't searchable.
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from xml.etree import ElementTree

log = logging.getLogger(__name__)

MAX_PAGES = 300
MAX_UNPACKED = 20 * 1024 * 1024
MAX_CHARS = 400_000
PASSAGE = 900
OVERLAP = 150
MAX_PASSAGES = 600


def _xml_text(data: bytes, tag: str, block: str) -> str:
    """Text of every `tag` element, a line break after each `block` element."""
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        return ""  # real Office files never declare these; refusing them stops entity tricks
    root = ElementTree.fromstring(data)  # noqa: S314  (DTDs and entities refused above)
    lines: list[str] = []
    for node in root.iter():
        if node.tag.endswith(block):
            words = "".join(t.text or "" for t in node.iter() if t.tag.endswith(tag))
            if words.strip():
                lines.append(words)
    return "\n".join(lines)


def _ooxml(data: bytes, parts: list[str], tag: str, block: str) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if sum(i.file_size for i in archive.infolist()) > MAX_UNPACKED:
            return ""
        names = [n for n in archive.namelist() if any(re.fullmatch(p, n) for p in parts)]
        names.sort(key=lambda n: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)])
        return "\n\n".join(_xml_text(archive.read(n), tag, block) for n in names)


def extract(filename: str, data: bytes) -> str:
    name = filename.lower()
    try:
        if name.endswith(".pdf"):
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            text = "\n\n".join((page.extract_text() or "") for page in reader.pages[:MAX_PAGES])
        elif name.endswith(".docx"):
            text = _ooxml(data, [r"word/document\.xml"], "}t", "}p")
        elif name.endswith(".pptx"):
            text = _ooxml(data, [r"ppt/slides/slide\d+\.xml"], "}t", "}p")
        elif name.endswith((".txt", ".md", ".csv")):
            text = data.decode("utf-8", errors="replace")
        else:
            return ""
    except Exception as exc:  # a broken or hostile file: just not searchable
        log.info("no text from file", extra={"filename": filename, "error": type(exc).__name__})
        return ""
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()[:MAX_CHARS]


def passages(text: str) -> list[str]:
    """Overlapping passages of about PASSAGE characters, cut at paragraph or sentence ends."""
    out: list[str] = []
    start = 0
    while start < len(text) and len(out) < MAX_PASSAGES:
        end = min(len(text), start + PASSAGE)
        if end < len(text):
            cut = max(
                text.rfind("\n\n", start, end), text.rfind(". ", start, end), text.rfind("। ", start, end)
            )
            if cut > start + PASSAGE // 2:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)
    return out
