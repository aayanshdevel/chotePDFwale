import base64
import math
import os
import statistics
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pikepdf
import pymupdf as fitz

from app.core.config import settings
from app.core.exceptions import (
    CorruptedPDFError,
    EmptyPDFError,
    InvalidPDFError,
    PageLimitExceededError,
    PasswordProtectedPDFError,
    UnsupportedEncryptionError,
)
from app.models.schemas import (
    FontAnalysisSummary,
    ImageAnalysisSummary,
    PDFAnalysisResponse,
)


def format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} B"
    kb = num_bytes / 1024.0
    if kb < 1024:
        return f"{kb:.1f} KB"
    mb = kb / 1024.0
    return f"{mb:.2f} MB"


def _paper_label(width_pt: float, height_pt: float) -> str:
    w, h = sorted([width_pt, height_pt])
    if abs(w - 595) <= 6 and abs(h - 842) <= 6:
        name = "A4"
    elif abs(w - 612) <= 6 and abs(h - 792) <= 6:
        name = "US Letter"
    elif abs(w - 612) <= 6 and abs(h - 1008) <= 6:
        name = "US Legal"
    elif abs(w - 420) <= 6 and abs(h - 595) <= 6:
        name = "A5"
    else:
        name = f"{width_pt / 72.0:.1f} × {height_pt / 72.0:.1f} in"
    orientation = "Landscape" if width_pt > height_pt else "Portrait"
    return f"{int(round(width_pt))} × {int(round(height_pt))} pt ({name}, {orientation})"


def _detect_pdf_header_version(pdf_path: Path) -> str:
    try:
        with open(pdf_path, "rb") as f:
            head = f.read(1024)
        idx = head.find(b"%PDF-")
        if idx == -1:
            raise InvalidPDFError()
        ver_bytes = head[idx + 5 : idx + 8].decode("ascii", errors="ignore").strip()
        if ver_bytes and ver_bytes[0].isdigit():
            return f"PDF {ver_bytes}"
        return "PDF 1.7"
    except InvalidPDFError:
        raise
    except Exception as exc:
        raise CorruptedPDFError() from exc


def analyze_pdf_file(
    pdf_path: Path,
    file_id: str,
    original_filename: str,
    include_thumbnail: bool = True,
) -> PDFAnalysisResponse:
    """Inspect a PDF file thoroughly and compute realistic compression potential."""
    if not pdf_path.exists():
        raise EmptyPDFError("Uploaded PDF file does not exist.")

    size_bytes = os.path.getsize(pdf_path)
    if size_bytes == 0:
        raise EmptyPDFError()

    pdf_version = _detect_pdf_header_version(pdf_path)

    # First check encryption & structural integrity with pikepdf
    has_js = False
    try:
        with pikepdf.open(pdf_path) as pk:
            if pk.is_encrypted:
                # pikepdf opened with empty user password (owner-only restriction), check if readable
                pass
            if "/Names" in pk.Root and "/JavaScript" in pk.Root["/Names"]:
                has_js = True
            if "/OpenAction" in pk.Root and isinstance(pk.Root["/OpenAction"], pikepdf.Dictionary):
                if pk.Root["/OpenAction"].get("/S") == "/JavaScript":
                    has_js = True
    except pikepdf.PasswordError as exc:
        raise PasswordProtectedPDFError() from exc
    except pikepdf.PdfError as exc:
        msg = str(exc).lower()
        if "encrypt" in msg or "security handler" in msg or "password" in msg:
            raise UnsupportedEncryptionError() from exc
        raise CorruptedPDFError(
            "The uploaded PDF has a damaged cross-reference table or corrupted object structure."
        ) from exc

    # Open with PyMuPDF for deep content, image, font, text, and vector inspection
    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise CorruptedPDFError() from exc

    try:
        if doc.needs_pass:
            raise PasswordProtectedPDFError()

        page_count = doc.page_count
        if page_count == 0:
            raise EmptyPDFError("The uploaded PDF contains 0 pages.")
        if page_count > settings.MAX_PAGE_COUNT:
            raise PageLimitExceededError(page_count, settings.MAX_PAGE_COUNT)

        first_rect = doc[0].rect
        width_pt = float(first_rect.width)
        height_pt = float(first_rect.height)
        mixed_sizes = False

        # Sample pages for large PDFs so 200+ page documents analyze in < 400ms
        sample_step = 1 if page_count <= 40 else max(1, page_count // 30)
        sampled_indices = list(range(0, page_count, sample_step))
        scale_factor = page_count / max(1, len(sampled_indices))

        seen_image_xrefs: Dict[int, Tuple[int, int, str, int]] = {}  # xref -> (w, h, cs, smask)
        xref_max_dpi: Dict[int, float] = {}
        font_xrefs: Set[int] = set()
        embedded_font_xrefs: Set[int] = set()
        subset_font_xrefs: Set[int] = set()

        total_text_chars = 0
        pages_with_full_bleed_image = 0
        total_vector_paths = 0

        for idx in range(page_count):
            page = doc[idx]
            r = page.rect
            if abs(r.width - width_pt) > 8 or abs(r.height - height_pt) > 8:
                mixed_sizes = True

            # Image enumeration across all pages (fast metadata lookup)
            imgs = page.get_images(full=True)
            page_area = max(1.0, r.width * r.height)
            page_has_large_img = False

            for img in imgs:
                xref, smask, w, h, bpc, colorspace = (
                    img[0],
                    img[1],
                    img[2],
                    img[3],
                    img[4],
                    str(img[5] or ""),
                )
                if xref <= 0:
                    continue
                if xref not in seen_image_xrefs:
                    seen_image_xrefs[xref] = (w, h, colorspace, smask)

                if idx in sampled_indices or xref not in xref_max_dpi:
                    try:
                        rects = page.get_image_rects(xref)
                    except Exception:
                        rects = []
                    for ir in rects:
                        if ir.width > 2 and ir.height > 2:
                            dpi_x = w / (ir.width / 72.0)
                            dpi_y = h / (ir.height / 72.0)
                            eff_dpi = max(dpi_x, dpi_y)
                            if eff_dpi > xref_max_dpi.get(xref, 0.0):
                                xref_max_dpi[xref] = min(2400.0, eff_dpi)
                            if (ir.width * ir.height) / page_area >= 0.65:
                                page_has_large_img = True

            if page_has_large_img:
                pages_with_full_bleed_image += 1

            # Fonts
            for f_item in page.get_fonts(full=True):
                fxref = f_item[0]
                fext = str(f_item[1] or "")
                fname = str(f_item[3] or "")
                if fxref > 0:
                    font_xrefs.add(fxref)
                    if fext and fext != "n/a":
                        embedded_font_xrefs.add(fxref)
                    if "+" in fname:
                        subset_font_xrefs.add(fxref)

            # Text and vectors on sampled pages
            if idx in sampled_indices:
                txt = page.get_text("text")
                total_text_chars += len(txt.strip())
                try:
                    drawings = page.get_drawings()
                    total_vector_paths += len(drawings)
                except Exception:
                    pass

        est_total_text_chars = int(total_text_chars * scale_factor)
        est_vector_paths = int(total_vector_paths * scale_factor)

        # Measure raw compressed stream size of unique images & fonts
        image_stream_bytes = 0
        has_color = False
        has_alpha = False
        min_extreme_image_bytes = 0.0
        rec_image_bytes = 0.0

        for xref, (w, h, cs, smask) in seen_image_xrefs.items():
            try:
                raw_stream = doc.xref_stream_raw(xref)
                s_len = len(raw_stream) if raw_stream else 0
            except Exception:
                s_len = 0
            image_stream_bytes += s_len
            cs_upper = cs.upper()
            if "RGB" in cs_upper or "CMYK" in cs_upper or "ICC" in cs_upper or "LAB" in cs_upper:
                has_color = True
            if smask and smask > 0:
                has_alpha = True
                try:
                    sm_raw = doc.xref_stream_raw(smask)
                    if sm_raw:
                        image_stream_bytes += len(sm_raw)
                except Exception:
                    pass

            eff_dpi = xref_max_dpi.get(xref, 150.0)
            # Estimate pixel count after extreme (60 DPI) and recommended (130 DPI) downsampling
            scale_ext = min(1.0, 60.0 / max(1.0, eff_dpi))
            scale_rec = min(1.0, 130.0 / max(1.0, eff_dpi))
            ext_pixels = max(256.0, (w * scale_ext) * (h * scale_ext))
            rec_pixels = max(256.0, (w * scale_rec) * (h * scale_rec))
            # JPEG Q25 averages ~0.12-0.18 bytes/pixel; Q72 averages ~0.35-0.45 bytes/pixel
            min_extreme_image_bytes += min(s_len, max(900.0, ext_pixels * 0.14))
            rec_image_bytes += min(s_len, max(1800.0, rec_pixels * 0.36))

        font_stream_bytes = 0
        for fxref in embedded_font_xrefs:
            try:
                # Inspect FontDescriptor stream bytes roughly
                obj_str = doc.xref_object(fxref)
                for token in obj_str.split():
                    if token.isdigit():
                        cand = int(token)
                        if 0 < cand < doc.xref_length() and doc.xref_is_stream(cand):
                            raw_f = doc.xref_stream_raw(cand)
                            if raw_f:
                                font_stream_bytes += len(raw_f)
            except Exception:
                pass

        dpi_values: List[float] = [v for v in xref_max_dpi.values() if v > 0]
        max_dpi = int(round(max(dpi_values))) if dpi_values else 0
        median_dpi = int(round(statistics.median(dpi_values))) if dpi_values else 0

        image_share = min(99.5, round((image_stream_bytes / max(1, size_bytes)) * 100.0, 1))

        # Classify content profile
        has_searchable_text = est_total_text_chars >= 25
        has_vectors = est_vector_paths >= 10
        if pages_with_full_bleed_image >= max(1, int(page_count * 0.7)) and est_total_text_chars < page_count * 40:
            content_profile = "scanned"
        elif image_share >= 60.0 and not has_searchable_text:
            content_profile = "image_heavy"
        elif image_share >= 35.0 and has_searchable_text:
            content_profile = "mixed"
        elif len(seen_image_xrefs) == 0 and has_vectors and est_vector_paths > page_count * 35:
            content_profile = "vector_rich"
        elif image_share >= 50.0:
            content_profile = "image_heavy"
        else:
            content_profile = "text_heavy"

        # Structural + text + font floor calculation
        non_image_bytes = max(512, size_bytes - image_stream_bytes)
        # Subsetted fonts + Flate object streams typically shrink non-image overhead to ~40%-75%
        structural_floor = max(
            int(page_count * 650 + 1200),
            int(non_image_bytes * (0.42 if font_stream_bytes > 20000 else 0.58)),
        )
        estimated_min_bytes = min(
            size_bytes,
            max(1500, int(structural_floor + min_extreme_image_bytes)),
        )
        recommended_min_bytes = min(
            size_bytes,
            max(estimated_min_bytes, int(structural_floor * 1.15 + rec_image_bytes)),
        )

        high_red = max(0.0, min(96.0, (1.0 - (estimated_min_bytes / max(1, size_bytes))) * 100.0))
        low_red = max(0.0, min(high_red, (1.0 - (recommended_min_bytes / max(1, size_bytes))) * 100.0))

        # Render Page 1 preview thumbnail safely
        thumbnail_data_url = None
        if include_thumbnail:
            try:
                p0 = doc[0]
                scale = min(1.5, 360.0 / max(1.0, p0.rect.width))
                pix = p0.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                png_bytes = pix.tobytes("png")
                b64 = base64.b64encode(png_bytes).decode("ascii")
                thumbnail_data_url = f"data:image/png;base64,{b64}"
            except Exception:
                thumbnail_data_url = None

        dim_label = _paper_label(width_pt, height_pt)
        if mixed_sizes:
            dim_label += " · Mixed page sizes"

        return PDFAnalysisResponse(
            file_id=file_id,
            filename=original_filename,
            original_size_bytes=size_bytes,
            original_size_formatted=format_bytes(size_bytes),
            page_count=page_count,
            pdf_version=pdf_version,
            page_dimensions=dim_label,
            width_pt=round(width_pt, 2),
            height_pt=round(height_pt, 2),
            content_profile=content_profile,
            has_searchable_text=has_searchable_text,
            has_vector_graphics=has_vectors,
            had_javascript_stripped=has_js,
            images=ImageAnalysisSummary(
                unique_images=len(seen_image_xrefs),
                image_bytes_estimate=image_stream_bytes,
                image_share_percent=image_share,
                max_effective_dpi=max_dpi,
                median_effective_dpi=median_dpi,
                has_color_images=has_color,
                has_alpha_images=has_alpha,
            ),
            fonts=FontAnalysisSummary(
                total_fonts=len(font_xrefs),
                embedded_fonts=len(embedded_font_xrefs),
                subset_fonts=len(subset_font_xrefs),
            ),
            estimated_min_size_bytes=estimated_min_bytes,
            recommended_min_size_bytes=recommended_min_bytes,
            estimated_reduction_percent_low=round(low_red, 1),
            estimated_reduction_percent_high=round(high_red, 1),
            thumbnail_data_url=thumbnail_data_url,
            expires_in_minutes=settings.FILE_RETENTION_MINUTES,
        )
    finally:
        doc.close()
