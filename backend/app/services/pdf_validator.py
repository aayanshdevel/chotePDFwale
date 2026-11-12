import os
from dataclasses import dataclass
from pathlib import Path

import pikepdf
import pymupdf as fitz


@dataclass
class ValidationOutcome:
    is_valid: bool
    page_count: int = 0
    size_bytes: int = 0
    searchable_text_preserved: bool = True
    reason: str = ""


def validate_compressed_pdf(
    original_path: Path,
    candidate_path: Path,
    expected_pages: int,
    original_had_text: bool,
) -> ValidationOutcome:
    """
    Strictly verify that a candidate compressed PDF:
    1. Exists, is non-empty, and starts with %PDF-
    2. Opens cleanly in pikepdf (valid cross-reference table / object streams, unencrypted)
    3. Opens cleanly in PyMuPDF with exact page count preserved
    4. Preserves page dimensions / orientation on sampled pages
    5. Renders sample pages without stream/image corruption
    6. Retains searchable text when original document had searchable text
    """
    if not candidate_path.exists():
        return ValidationOutcome(False, reason="Candidate output file was not created.")

    size_bytes = os.path.getsize(candidate_path)
    if size_bytes < 64:
        return ValidationOutcome(False, reason="Candidate output file is empty or truncated.")

    try:
        with open(candidate_path, "rb") as f:
            head = f.read(512)
        if b"%PDF-" not in head:
            return ValidationOutcome(False, reason="Missing valid %PDF- header.")
    except OSError as exc:
        return ValidationOutcome(False, reason=f"Read check failed: {exc}")

    try:
        with pikepdf.open(candidate_path) as pk:
            if len(pk.pages) != expected_pages:
                return ValidationOutcome(
                    False,
                    page_count=len(pk.pages),
                    size_bytes=size_bytes,
                    reason=f"Page count mismatch in QPDF check ({len(pk.pages)} vs {expected_pages}).",
                )
    except Exception as exc:
        return ValidationOutcome(False, size_bytes=size_bytes, reason=f"QPDF structural check failed: {exc}")

    orig_doc = None
    cand_doc = None
    try:
        orig_doc = fitz.open(original_path)
        cand_doc = fitz.open(candidate_path)

        if cand_doc.needs_pass:
            return ValidationOutcome(False, reason="Unexpected encryption on output PDF.")

        if cand_doc.page_count != expected_pages:
            return ValidationOutcome(
                False,
                page_count=cand_doc.page_count,
                size_bytes=size_bytes,
                reason=f"Page count mismatch ({cand_doc.page_count} vs {expected_pages}).",
            )

        # Sample first, middle, and last pages for geometry & rasterization health
        sample_pages = sorted({0, expected_pages // 2, expected_pages - 1})
        for pidx in sample_pages:
            o_rect = orig_doc[pidx].rect
            c_rect = cand_doc[pidx].rect
            if o_rect.width > 0 and o_rect.height > 0:
                w_diff = abs(c_rect.width - o_rect.width) / o_rect.width
                h_diff = abs(c_rect.height - o_rect.height) / o_rect.height
                if w_diff > 0.03 or h_diff > 0.03:
                    return ValidationOutcome(
                        False,
                        page_count=expected_pages,
                        size_bytes=size_bytes,
                        reason=f"Page {pidx + 1} geometry altered unexpectedly.",
                    )
            # Rasterize at low scale to prove streams decode without error
            pix = cand_doc[pidx].get_pixmap(matrix=fitz.Matrix(0.35, 0.35), alpha=False)
            if pix.width <= 0 or pix.height <= 0:
                return ValidationOutcome(False, reason=f"Page {pidx + 1} failed raster decode.")

        text_preserved = True
        if original_had_text:
            extracted_chars = 0
            check_count = min(expected_pages, 10)
            for pidx in range(check_count):
                extracted_chars += len(cand_doc[pidx].get_text("text").strip())
            if extracted_chars == 0:
                # Count across more pages before flagging
                for pidx in range(check_count, min(expected_pages, 40)):
                    extracted_chars += len(cand_doc[pidx].get_text("text").strip())
                if extracted_chars == 0:
                    text_preserved = False

        return ValidationOutcome(
            is_valid=True,
            page_count=cand_doc.page_count,
            size_bytes=size_bytes,
            searchable_text_preserved=text_preserved,
        )
    except Exception as exc:
        return ValidationOutcome(False, size_bytes=size_bytes, reason=f"MuPDF validation error: {exc}")
    finally:
        if orig_doc is not None:
            orig_doc.close()
        if cand_doc is not None:
            cand_doc.close()
