"""Which files may be uploaded, checked by their content and not only their name.

A file is accepted when its extension is on the list and its first bytes match what that
kind of file starts with. Downloads always go out as attachments with this content type,
so a browser never runs an uploaded file as a page.
"""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import PurePosixPath

from app.core.errors import Invalid

MAX_SIZE = 10 * 1024 * 1024

ZIP = b"PK\x03\x04"
KINDS: dict[str, tuple[str, tuple[bytes, ...] | None]] = {
    # extension: (content type, accepted leading bytes; None = UTF-8 text)
    ".pdf": ("application/pdf", (b"%PDF-",)),
    ".docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", (ZIP,)),
    ".xlsx": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", (ZIP,)),
    ".pptx": ("application/vnd.openxmlformats-officedocument.presentationml.presentation", (ZIP,)),
    ".odt": ("application/vnd.oasis.opendocument.text", (ZIP,)),
    ".png": ("image/png", (b"\x89PNG\r\n\x1a\n",)),
    ".jpg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".jpeg": ("image/jpeg", (b"\xff\xd8\xff",)),
    ".txt": ("text/plain; charset=utf-8", None),
    ".md": ("text/markdown; charset=utf-8", None),
    ".csv": ("text/csv; charset=utf-8", None),
}


def clean_name(filename: str) -> str:
    """A safe display name: no folders, no control characters, at most 200 characters."""
    name = PurePosixPath(filename.replace("\\", "/")).name
    name = "".join(ch for ch in unicodedata.normalize("NFC", name) if unicodedata.category(ch)[0] != "C")
    name = name.strip(" .")
    if not name:
        raise Invalid("The file needs a name.", code="file_name")
    stem, dot, ext = name.rpartition(".")
    if len(name) > 200:
        name = f"{stem[: 195 - len(ext)]}.{ext}" if dot else name[:200]
    return name


def check(filename: str, data: bytes) -> tuple[str, str, str]:
    """(clean name, content type, sha256) or a clear refusal."""
    name = clean_name(filename)
    if not data:
        raise Invalid("The file is empty.", code="file_empty")
    if len(data) > MAX_SIZE:
        raise Invalid("Files can be up to 10 MB.", code="file_too_large")
    ext = PurePosixPath(name.lower()).suffix
    kind = KINDS.get(ext)
    if kind is None:
        raise Invalid(
            "Upload a PDF, Word, Excel, PowerPoint, OpenDocument, image or text file.", code="file_type"
        )
    content_type, magic = kind
    if magic is None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Invalid("This text file isn't UTF-8.", code="file_type") from exc
        if b"\x00" in data:
            raise Invalid("This doesn't look like a text file.", code="file_type")
    elif not any(data.startswith(m) for m in magic):
        raise Invalid(f"This doesn't look like a {ext[1:].upper()} file.", code="file_type")
    return name, content_type, hashlib.sha256(data).hexdigest()
