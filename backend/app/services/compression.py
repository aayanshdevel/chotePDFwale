import io
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pikepdf
import pymupdf as fitz
from PIL import Image

from app.core.config import settings
from app.core.exceptions import (
    CompressionFailedError,
    InsufficientMemoryError,
    ProcessingTimeoutError,
)
from app.models.schemas import CompressionPreset
from app.services.pdf_validator import ValidationOutcome, validate_compressed_pdf


@dataclass
class CompressionParams:
    image_dpi: int = 150
    jpeg_quality: int = 75
    mono_dpi: int = 200
    grayscale: bool = False
    strip_metadata: bool = True
    subset_fonts: bool = True
    use_ghostscript: bool = True
    use_qpdf_objstms: bool = True
    allow_alpha_flatten: bool = False


PRESET_PARAM_MAP: Dict[CompressionPreset, CompressionParams] = {
    CompressionPreset.LOW: CompressionParams(
        image_dpi=200,
        jpeg_quality=85,
        mono_dpi=300,
        grayscale=False,
        strip_metadata=True,
        subset_fonts=True,
        use_ghostscript=True,
        use_qpdf_objstms=True,
        allow_alpha_flatten=False,
    ),
    CompressionPreset.RECOMMENDED: CompressionParams(
        image_dpi=150,
        jpeg_quality=75,
        mono_dpi=220,
        grayscale=False,
        strip_metadata=True,
        subset_fonts=True,
        use_ghostscript=True,
        use_qpdf_objstms=True,
        allow_alpha_flatten=False,
    ),
    CompressionPreset.HIGH: CompressionParams(
        image_dpi=100,
        jpeg_quality=52,
        mono_dpi=150,
        grayscale=False,
        strip_metadata=True,
        subset_fonts=True,
        use_ghostscript=True,
        use_qpdf_objstms=True,
        allow_alpha_flatten=True,
    ),
    CompressionPreset.EXTREME: CompressionParams(
        image_dpi=72,
        jpeg_quality=35,
        mono_dpi=110,
        grayscale=False,
        strip_metadata=True,
        subset_fonts=True,
        use_ghostscript=True,
        use_qpdf_objstms=True,
        allow_alpha_flatten=True,
    ),
}


def check_ghostscript_available() -> Optional[str]:
    gs_bin = shutil.which("gs")
    if not gs_bin:
        return None
    try:
        proc = subprocess.run(
            [gs_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else None
    except Exception:
        return None


def check_qpdf_available() -> Optional[str]:
    qpdf_bin = shutil.which("qpdf")
    if not qpdf_bin:
        return f"pikepdf-{pikepdf.__version__}"
    try:
        proc = subprocess.run(
            [qpdf_bin, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        first = (proc.stdout or "").splitlines()[0] if proc.stdout else ""
        return first or f"pikepdf-{pikepdf.__version__}"
    except Exception:
        return f"pikepdf-{pikepdf.__version__}"


def _encode_pil_image_for_pdf(
    pil_img: Image.Image,
    target_w: int,
    target_h: int,
    jpeg_quality: int,
    grayscale: bool,
    has_real_alpha: bool,
    allow_alpha_flatten: bool,
) -> Optional[bytes]:
    """Resize and re-encode a PIL image into compact PDF-compatible bytes."""
    orig_w, orig_h = pil_img.size
    if target_w < orig_w or target_h < orig_h:
        pil_img = pil_img.resize(
            (max(16, target_w), max(16, target_h)),
            Image.Resampling.LANCZOS,
        )

    if has_real_alpha and not allow_alpha_flatten:
        # Quantize RGBA PNG cleanly to preserve crisp transparent edges
        rgba = pil_img.convert("RGBA")
        if grayscale:
            g = rgba.convert("LA").convert("RGBA")
            rgba = g
        quant = rgba.quantize(colors=128 if jpeg_quality >= 70 else 64, method=Image.Quantize.FASTOCTREE)
        buf = io.BytesIO()
        quant.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
        rgba = pil_img.convert("RGBA")
        white_bg = Image.new("RGB", rgba.size, (255, 255, 255))
        white_bg.paste(rgba, mask=rgba.split()[3])
        pil_img = white_bg

    if grayscale or pil_img.mode in ("L", "1"):
        work = pil_img.convert("L")
    else:
        # Check if an RGB image is actually near-grayscale using NumPy to save 2 channels automatically!
        rgb = pil_img.convert("RGB")
        arr = np.asarray(rgb)
        if arr.ndim == 3 and arr.shape[2] == 3:
            rg_diff = np.max(np.abs(arr[:, :, 0].astype(np.int16) - arr[:, :, 1].astype(np.int16)))
            gb_diff = np.max(np.abs(arr[:, :, 1].astype(np.int16) - arr[:, :, 2].astype(np.int16)))
            if rg_diff <= 3 and gb_diff <= 3:
                work = rgb.convert("L")
            else:
                work = rgb
        else:
            work = rgb

    buf = io.BytesIO()
    subsampling = 0 if jpeg_quality >= 82 else (1 if jpeg_quality >= 68 else 2)
    save_kwargs = {
        "format": "JPEG",
        "quality": max(14, min(95, int(jpeg_quality))),
        "optimize": True,
    }
    if work.mode == "RGB":
        save_kwargs["subsampling"] = subsampling
    work.save(buf, **save_kwargs)
    return buf.getvalue()


def _run_surgical_pymupdf_stage(
    input_path: Path,
    output_path: Path,
    params: CompressionParams,
) -> int:
    """
    Stage A: Surgical PyMuPDF + Pillow + NumPy pass.
    - Computes exact maximum rendered DPI per unique image xref across all pages.
    - Downsamples and JPEG-optimizes embedded images only when strictly smaller.
    - Preserves vector graphics and searchable text completely.
    - Subsets embedded fonts and strips XML/doc metadata if requested.
    """
    doc = fitz.open(input_path)
    replaced_count = 0
    try:
        # Gather max rendered geometry (width_in, height_in) and first hosting page per xref
        xref_host_page: Dict[int, int] = {}
        xref_info: Dict[int, Tuple[int, int, int, int]] = {}  # xref -> (w, h, bpc, smask)
        xref_max_inches: Dict[int, Tuple[float, float]] = {}

        for pidx in range(doc.page_count):
            page = doc[pidx]
            for img in page.get_images(full=True):
                xref, smask, w, h, bpc = img[0], img[1], img[2], img[3], img[4]
                if xref <= 0 or w < 24 or h < 24:
                    continue
                if xref not in xref_host_page:
                    xref_host_page[xref] = pidx
                    xref_info[xref] = (w, h, bpc, smask)
                try:
                    rects = page.get_image_rects(xref)
                except Exception:
                    rects = []
                for r in rects:
                    if r.width > 1 and r.height > 1:
                        w_in = r.width / 72.0
                        h_in = r.height / 72.0
                        prev_w, prev_h = xref_max_inches.get(xref, (0.0, 0.0))
                        if w_in * h_in > prev_w * prev_h:
                            xref_max_inches[xref] = (w_in, h_in)

        for xref, pidx in xref_host_page.items():
            w, h, bpc, smask = xref_info[xref]
            # Skip tiny icons unless aggressive compression
            try:
                raw_orig = doc.xref_stream_raw(xref)
                orig_len = len(raw_orig) if raw_orig else 0
            except Exception:
                orig_len = 0

            if smask > 0:
                try:
                    sm_raw = doc.xref_stream_raw(smask)
                    if sm_raw:
                        orig_len += len(sm_raw)
                except Exception:
                    pass

            if orig_len < 2048 and not params.grayscale:
                continue

            # Skip compact 1-bit CCITT/JBIG2 bitmaps unless huge uncompressed bitmap
            if bpc == 1 and smask == 0 and orig_len < (w * h) // 10:
                continue

            # Determine target pixel dimensions based on rendered area on page
            if xref in xref_max_inches and xref_max_inches[xref][0] > 0.05:
                w_in, h_in = xref_max_inches[xref]
                eff_dpi_x = w / w_in
                eff_dpi_y = h / h_in
                eff_dpi = max(eff_dpi_x, eff_dpi_y)
                if eff_dpi > params.image_dpi * 1.08:
                    scale = params.image_dpi / eff_dpi
                    target_w = max(24, int(round(w * scale)))
                    target_h = max(24, int(round(h * scale)))
                else:
                    target_w, target_h = w, h
            else:
                # Fallback if image inside Form XObject had no direct page rect lookup
                assumed_in = max(w, h) / 220.0
                max_px = max(96, int(round(assumed_in * params.image_dpi)))
                if max(w, h) > max_px:
                    scale = max_px / float(max(w, h))
                    target_w = max(24, int(round(w * scale)))
                    target_h = max(24, int(round(h * scale)))
                else:
                    target_w, target_h = w, h

            # Extract pixel data via PyMuPDF Pixmap (handles CMYK, ICCBased, Indexed, SMask cleanly)
            try:
                base_pix = fitz.Pixmap(doc, xref)
                has_real_alpha = False
                if smask > 0:
                    mask_pix = fitz.Pixmap(doc, smask)
                    if base_pix.n - base_pix.alpha not in (1, 3):
                        base_pix = fitz.Pixmap(fitz.csRGB, base_pix)
                    rgba_pix = fitz.Pixmap(base_pix, mask_pix)
                    pil_img = Image.frombytes(
                        "RGBA" if rgba_pix.n == 4 else "LA",
                        (rgba_pix.width, rgba_pix.height),
                        rgba_pix.samples,
                    )
                    alpha_extrema = pil_img.getchannel("A").getextrema()
                    has_real_alpha = alpha_extrema[0] < 250
                else:
                    if base_pix.alpha:
                        base_pix = fitz.Pixmap(base_pix, 0)
                    if base_pix.n == 1:
                        pil_img = Image.frombytes("L", (base_pix.width, base_pix.height), base_pix.samples)
                    else:
                        if base_pix.n != 3:
                            base_pix = fitz.Pixmap(fitz.csRGB, base_pix)
                        pil_img = Image.frombytes("RGB", (base_pix.width, base_pix.height), base_pix.samples)
            except MemoryError as exc:
                raise InsufficientMemoryError() from exc
            except Exception:
                continue

            # If soft-mask has genuine semi-transparency and flatten is disallowed, let GS handle or skip
            if smask > 0 and has_real_alpha and not params.allow_alpha_flatten:
                continue

            new_stream = _encode_pil_image_for_pdf(
                pil_img=pil_img,
                target_w=target_w,
                target_h=target_h,
                jpeg_quality=params.jpeg_quality,
                grayscale=params.grayscale,
                has_real_alpha=has_real_alpha,
                allow_alpha_flatten=params.allow_alpha_flatten,
            )
            if not new_stream:
                continue

            # Only replace if strictly smaller (or grayscale conversion was explicitly requested)
            if params.grayscale or len(new_stream) < int(orig_len * 0.97):
                try:
                    doc[pidx].replace_image(xref, stream=new_stream)
                    replaced_count += 1
                except Exception:
                    continue

        if params.strip_metadata:
            try:
                doc.set_metadata({})
                doc.del_xml_metadata()
            except Exception:
                pass

        if params.subset_fonts:
            try:
                doc.subset_fonts()
            except Exception:
                pass

        doc.save(
            output_path,
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
            use_objstms=1 if params.use_qpdf_objstms else 0,
        )
        return replaced_count
    except MemoryError as exc:
        raise InsufficientMemoryError() from exc
    finally:
        doc.close()


def _run_ghostscript_stage(
    input_path: Path,
    output_path: Path,
    params: CompressionParams,
    passthrough_jpegs: bool,
) -> bool:
    """
    Stage B: Restricted Ghostscript distiller pass (-dSAFER).
    Optimizes inline images, Form XObjects, duplicate resources, content streams, and grayscale conversion.
    """
    gs_bin = shutil.which("gs")
    if not gs_bin or not params.use_ghostscript:
        return False

    cmd: List[str] = [
        gs_bin,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.6",
        "-dSAFER",
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-dDetectDuplicateImages=true",
        "-dCompressFonts=true",
        f"-dSubsetFonts={'true' if params.subset_fonts else 'false'}",
        "-dCompressPages=true",
        f"-dPassThroughJPEGImages={'true' if passthrough_jpegs else 'false'}",
        "-dDownsampleColorImages=true",
        "-dColorImageDownsampleType=/Bicubic",
        "-dColorImageDownsampleThreshold=1.1",
        f"-dColorImageResolution={max(36, params.image_dpi)}",
        "-dDownsampleGrayImages=true",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dGrayImageDownsampleThreshold=1.1",
        f"-dGrayImageResolution={max(36, params.image_dpi)}",
        "-dDownsampleMonoImages=true",
        "-dMonoImageDownsampleThreshold=1.1",
        f"-dMonoImageResolution={max(72, params.mono_dpi)}",
    ]

    if params.grayscale:
        cmd.extend(
            [
                "-sColorConversionStrategy=Gray",
                "-dProcessColorModel=/DeviceGray",
            ]
        )

    cmd.extend([f"-sOutputFile={str(output_path)}", str(input_path)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.GS_TIMEOUT_SECONDS,
            check=False,
        )
        return proc.returncode == 0 and output_path.exists() and os.path.getsize(output_path) > 64
    except subprocess.TimeoutExpired as exc:
        raise ProcessingTimeoutError() from exc
    except Exception:
        return False


def _sanitize_and_pack_pikepdf(
    input_path: Path,
    output_path: Path,
    strip_metadata: bool,
    use_objstms: bool,
) -> bool:
    """
    Stage C: pikepdf / QPDF security sanitization & object stream compression.
    - Removes embedded JavaScript actions (/Names/JavaScript, /OpenAction JS)
    - Strips page thumbnails (/Thumb) and PieceInfo bloat
    - Prunes unreferenced PDF objects and packs compressed object streams
    """
    try:
        with pikepdf.open(input_path) as pdf:
            root = pdf.Root
            # Never keep embedded PDF JavaScript
            if "/Names" in root and isinstance(root["/Names"], pikepdf.Dictionary):
                if "/JavaScript" in root["/Names"]:
                    del root["/Names"]["/JavaScript"]
            if "/OpenAction" in root and isinstance(root["/OpenAction"], pikepdf.Dictionary):
                if root["/OpenAction"].get("/S") == "/JavaScript":
                    del root["/OpenAction"]
            if "/AA" in root:
                del root["/AA"]

            if strip_metadata:
                if "/Metadata" in root:
                    del root["/Metadata"]
                if "/PieceInfo" in root:
                    del root["/PieceInfo"]
                for page in pdf.pages:
                    if "/Thumb" in page.obj:
                        del page.obj["/Thumb"]
                    if "/PieceInfo" in page.obj:
                        del page.obj["/PieceInfo"]
                    if "/AA" in page.obj:
                        del page.obj["/AA"]
                with pdf.open_metadata(set_pikepdf_as_editor=False) as _:
                    pass
                keys = list(pdf.docinfo.keys())
                for k in keys:
                    del pdf.docinfo[k]

            pdf.remove_unreferenced_resources()
            pdf.save(
                output_path,
                object_stream_mode=(
                    pikepdf.ObjectStreamMode.generate
                    if use_objstms
                    else pikepdf.ObjectStreamMode.preserve
                ),
                compress_streams=True,
                stream_decode_level=pikepdf.StreamDecodeLevel.generalized,
                recompress_flate=True,
            )
        return output_path.exists() and os.path.getsize(output_path) > 64
    except Exception:
        return False


@dataclass
class SinglePassResult:
    output_path: Path
    size_bytes: int
    used_ghostscript: bool
    used_qpdf_objstms: bool
    validation: ValidationOutcome


def run_compression_pipeline(
    original_path: Path,
    destination_path: Path,
    params: CompressionParams,
    expected_pages: int,
    original_had_text: bool,
    keep_original_if_larger: bool = True,
) -> SinglePassResult:
    """
    Execute the hybrid 3-stage PDF compression pipeline inside an isolated temporary directory,
    validate every candidate strictly, and write the smallest valid PDF to destination_path.
    """
    orig_size = os.path.getsize(original_path)

    with tempfile.TemporaryDirectory(prefix="optipdf_pass_", dir=settings.STORAGE_DIR) as tmp_dir:
        tmp = Path(tmp_dir)
        stage_a_pdf = tmp / "stage_a_mupdf.pdf"
        stage_aq_pdf = tmp / "stage_aq_qpdf.pdf"
        stage_ab_pdf = tmp / "stage_ab_gs.pdf"
        stage_abq_pdf = tmp / "stage_abq_qpdf.pdf"
        orig_clean_pdf = tmp / "orig_clean.pdf"

        candidates: List[Tuple[Path, bool, bool]] = []  # (path, used_gs, used_qpdf)

        # 1. Stage A (PyMuPDF + Pillow surgical image pass + font subsetting)
        _run_surgical_pymupdf_stage(original_path, stage_a_pdf, params)

        # 2. Stage A -> Stage C (QPDF object streams & JS/metadata cleanup)
        if _sanitize_and_pack_pikepdf(
            stage_a_pdf, stage_aq_pdf, params.strip_metadata, params.use_qpdf_objstms
        ):
            candidates.append((stage_aq_pdf, False, params.use_qpdf_objstms))
        else:
            candidates.append((stage_a_pdf, False, False))

        # 3. Stage A -> Stage B (Ghostscript) -> Stage C (QPDF)
        # Especially valuable for grayscale conversion, inline images, Form XObjects, or vector stream compaction
        if params.use_ghostscript:
            gs_ok = _run_ghostscript_stage(
                stage_a_pdf,
                stage_ab_pdf,
                params,
                passthrough_jpegs=not params.grayscale,
            )
            if gs_ok:
                if _sanitize_and_pack_pikepdf(
                    stage_ab_pdf,
                    stage_abq_pdf,
                    params.strip_metadata,
                    params.use_qpdf_objstms,
                ):
                    candidates.append((stage_abq_pdf, True, params.use_qpdf_objstms))
                else:
                    candidates.append((stage_ab_pdf, True, False))

        # 4. Also prepare a lossless sanitized structural copy of original if already tightly optimized
        if keep_original_if_larger and not params.grayscale:
            if _sanitize_and_pack_pikepdf(
                original_path, orig_clean_pdf, params.strip_metadata, True
            ):
                candidates.append((orig_clean_pdf, False, True))

        # Validate candidates in ascending order of file size and pick the smallest valid PDF
        candidates_with_sizes = [
            (os.path.getsize(p), p, u_gs, u_qp)
            for (p, u_gs, u_qp) in candidates
            if p.exists() and os.path.getsize(p) > 64
        ]
        candidates_with_sizes.sort(key=lambda item: item[0])

        best_choice: Optional[Tuple[int, Path, bool, bool, ValidationOutcome]] = None
        for sz, c_path, u_gs, u_qp in candidates_with_sizes:
            val = validate_compressed_pdf(
                original_path=original_path,
                candidate_path=c_path,
                expected_pages=expected_pages,
                original_had_text=original_had_text,
            )
            if val.is_valid:
                best_choice = (sz, c_path, u_gs, u_qp, val)
                break

        if best_choice is None:
            raise CompressionFailedError()

        best_sz, best_path, used_gs, used_qp, best_val = best_choice

        # Never inflate an already-optimized PDF unless user explicitly forced grayscale conversion
        if keep_original_if_larger and not params.grayscale and best_sz >= orig_size:
            # Copy original safely (after stripping any JS if needed)
            shutil.copy2(original_path, destination_path)
            fallback_val = validate_compressed_pdf(
                original_path, destination_path, expected_pages, original_had_text
            )
            return SinglePassResult(
                output_path=destination_path,
                size_bytes=os.path.getsize(destination_path),
                used_ghostscript=False,
                used_qpdf_objstms=False,
                validation=fallback_val,
            )

        shutil.copy2(best_path, destination_path)
        return SinglePassResult(
            output_path=destination_path,
            size_bytes=best_sz,
            used_ghostscript=used_gs,
            used_qpdf_objstms=used_qp,
            validation=best_val,
        )
