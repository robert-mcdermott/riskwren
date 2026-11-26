"""Files, stored by what they contain.

A file is kept under the SHA-256 of its bytes, in a directory that nothing serves from. Its
type is judged by its content, never by its name, and only kinds on a short list are taken.
A file is only ever handed back as a download, through a route that has checked the person
may see something it is attached to.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from riskwren.core.errors import Invalid

MAX_BYTES = 25 * 1024 * 1024
EXECUTABLE = (b"MZ", b"\x7fELF", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa", b"#!")
TEXT = {"txt", "csv", "tsv", "json", "log", "md", "yaml", "yml"}
OFFICE = {
    "word/": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "xl/": ("xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "ppt/": ("pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
}
KINDS = (
    "PDF, PNG, JPEG, GIF, or WebP images, Word, Excel, or PowerPoint documents, and plain "
    "text such as CSV, JSON, or a log"
)


@dataclass(frozen=True)
class Kind:
    extension: str
    media_type: str


def _office(data: bytes) -> Kind | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
    except (zipfile.BadZipFile, OSError):
        return None
    if "[Content_Types].xml" not in names:
        return None
    for prefix, (extension, media_type) in OFFICE.items():
        if any(name.startswith(prefix) for name in names):
            return Kind(extension, media_type)
    return None


def sniff(data: bytes) -> Kind | None:
    """What kind of file this is, from its content. None if it is not a kind that is taken."""
    if data.startswith(b"%PDF-"):
        return Kind("pdf", "application/pdf")
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return Kind("png", "image/png")
    if data.startswith(b"\xff\xd8\xff"):
        return Kind("jpg", "image/jpeg")
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return Kind("gif", "image/gif")
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return Kind("webp", "image/webp")
    if data.startswith(b"PK\x03\x04"):
        return _office(data)
    if any(data.startswith(magic) for magic in EXECUTABLE) or b"\x00" in data[:8192]:
        return None
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    # Text of any kind, markup included. It is only ever sent back as a download of plain
    # text, so a page or a drawing that was uploaded cannot run.
    return Kind("txt", "text/plain")


def check(data: bytes) -> Kind:
    """Refuse what is empty, too large, or not a kind that is taken."""
    if not data:
        raise Invalid("The file was not stored.", {"file": "The file is empty."})
    if len(data) > MAX_BYTES:
        limit = MAX_BYTES // (1024 * 1024)
        raise Invalid("The file was not stored.", {"file": f"Files can be up to {limit} MB."})
    kind = sniff(data)
    if kind is None:
        raise Invalid(
            "The file was not stored.", {"file": f"That kind of file is not taken. Send {KINDS}."}
        )
    return kind


def path_of(root: Path, digest: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("not a SHA-256 digest")
    return root / digest[:2] / digest[2:4] / digest


def save(root: Path, data: bytes) -> tuple[str, Kind]:
    """Store a file under its digest and return the digest and its kind. Storing the same
    bytes again changes nothing."""
    kind = check(data)
    digest = hashlib.sha256(data).hexdigest()
    target = path_of(root, digest)
    if not target.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(f"{digest}.{os.getpid()}.part")
        partial.write_bytes(data)
        partial.replace(target)
    return digest, kind


def safe_name(name: str | None, kind: Kind) -> str:
    """A name to offer when the file is downloaded: the one it came with, tidied, with the
    extension its content calls for."""
    last = re.split(r"[\\/]", (name or "").strip())[-1]
    base = re.sub(r"[^\w .()-]+", "_", last).strip(" .") or "file"
    stem, _, ending = base.rpartition(".") if "." in base else (base, "", "")
    # Plain text keeps a harmless ending it came with, so a CSV is still called one.
    extension = (
        ending.lower() if kind.extension == "txt" and ending.lower() in TEXT else kind.extension
    )
    return f"{stem[:120] or 'file'}.{extension}"
