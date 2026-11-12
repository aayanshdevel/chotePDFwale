import os
import re
import uuid
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import (
    EmptyPDFError,
    FileTooLargeError,
    InvalidPDFError,
)

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/x-pdf",
    "application/acrobat",
    "applications/vnd.pdf",
    "text/pdf",
    "text/x-pdf",
    "application/octet-stream",  # Some browsers/OS drag-drop report octet-stream; magic bytes still enforced
}

SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._\- ()\[\]]+")
UUID_HEX_RE = re.compile(r"^[a-f0-9]{32}$")


def sanitize_filename(filename: str | None) -> str:
    """Sanitize user-supplied filename, preventing path traversal and control characters."""
    if not filename:
        return "document.pdf"
    # Strip any path components from Unix or Windows paths
    base = os.path.basename(filename.replace("\\", "/")).strip()
    # Remove null bytes and unsafe characters
    cleaned = SAFE_FILENAME_RE.sub("_", base).strip(" ._")
    if not cleaned:
        cleaned = "document"
    if cleaned.lower().endswith(".pdf"):
        stem = cleaned[:-4][:120] or "document"
    else:
        stem = cleaned[:120]
    return f"{stem}.pdf"


def validate_token_id(token: str) -> str:
    """Ensure job/file IDs are strictly 32-char lowercase hex UUIDs to prevent path traversal."""
    cleaned = (token or "").strip().lower().replace("-", "")
    if not UUID_HEX_RE.match(cleaned):
        raise InvalidPDFError("Invalid identifier format.")
    return cleaned


def create_isolated_job_dir(job_id: str | None = None) -> Tuple[str, Path]:
    """Create an isolated workspace directory inside STORAGE_DIR with a randomized UUID."""
    jid = validate_token_id(job_id) if job_id else uuid.uuid4().hex
    root = Path(settings.STORAGE_DIR).resolve()
    target = (root / jid).resolve()
    if root not in target.parents:
        raise InvalidPDFError("Unsafe storage path resolution blocked.")
    target.mkdir(parents=True, exist_ok=True)
    return jid, target


def resolve_job_dir(job_id: str) -> Path:
    jid = validate_token_id(job_id)
    root = Path(settings.STORAGE_DIR).resolve()
    target = (root / jid).resolve()
    if root not in target.parents:
        raise InvalidPDFError("Unsafe storage path resolution blocked.")
    return target


def validate_pdf_magic_bytes(header_bytes: bytes) -> None:
    """Check PDF magic signature (%PDF-1.x or %PDF-2.x) within first 1024 bytes."""
    if not header_bytes:
        raise EmptyPDFError()
    idx = header_bytes.find(b"%PDF-")
    if idx == -1 or idx > 1024:
        raise InvalidPDFError(
            "File signature verification failed: missing '%PDF-' magic header. Only genuine PDF documents are accepted."
        )


async def stream_upload_to_disk(upload: UploadFile, destination: Path) -> int:
    """
    Stream an uploaded file to disk chunk-by-chunk while validating:
    1. MIME type allowlist
    2. Non-empty body
    3. %PDF- magic header signature
    4. Strict MAX_UPLOAD_SIZE_MB byte ceiling
    """
    content_type = (upload.content_type or "").lower().split(";")[0].strip()
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        raise InvalidPDFError(
            f"Unsupported MIME type '{content_type}'. Please upload a valid PDF document."
        )

    total_bytes = 0
    first_chunk_checked = False
    header_buffer = bytearray()

    try:
        with open(destination, "wb") as out_f:
            while True:
                chunk = await upload.read(settings.UPLOAD_CHUNK_SIZE_BYTES)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.max_upload_bytes:
                    raise FileTooLargeError(settings.MAX_UPLOAD_SIZE_MB)

                if not first_chunk_checked:
                    header_buffer.extend(chunk[:2048])
                    if len(header_buffer) >= 8:
                        validate_pdf_magic_bytes(bytes(header_buffer))
                        first_chunk_checked = True

                out_f.write(chunk)

        if total_bytes == 0:
            raise EmptyPDFError()
        if not first_chunk_checked:
            validate_pdf_magic_bytes(bytes(header_buffer))

        return total_bytes
    except Exception:
        if destination.exists():
            try:
                destination.unlink()
            except OSError:
                pass
        raise
    finally:
        await upload.close()
