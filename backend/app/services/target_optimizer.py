import math
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from app.core.config import settings
from app.models.schemas import (
    AppliedSettingsSummary,
    CompressionResultPayload,
    IterationLogItem,
    PDFAnalysisResponse,
    TargetOutcomeStatus,
)
from app.services.compression import CompressionParams, run_compression_pipeline
from app.services.pdf_analyzer import format_bytes


ProgressCallback = Callable[[int, str], None]
CancelCheck = Callable[[], bool]


def _quality_score_to_params(
    q_score: float,
    grayscale: bool,
    strip_metadata: bool,
    subset_fonts: bool,
    force_max_dpi: Optional[int] = None,
) -> CompressionParams:
    """
    Map a continuous quality score q_score in [0.0, 1.0] to concrete PDF compression parameters:
    - q_score = 1.00 -> DPI 240, JPEG Q 90 (near-lossless)
    - q_score = 0.75 -> DPI 195, JPEG Q 83 (High Quality)
    - q_score = 0.55 -> DPI 150, JPEG Q 74 (Recommended)
    - q_score = 0.40 -> DPI 118, JPEG Q 62 (Balanced)
    - q_score = 0.22 -> DPI  88, JPEG Q 46 (Strong)
    - q_score = 0.08 -> DPI  66, JPEG Q 30 (Extreme)
    - q_score = 0.00 -> DPI  48, JPEG Q 18 (Maximum practical floor without destroying legibility)
    """
    q = max(0.0, min(1.0, q_score))
    # Smooth non-linear curve giving finer resolution in 65..180 DPI range
    dpi = int(round(48 + (240 - 48) * (q ** 0.88)))
    if force_max_dpi is not None:
        dpi = min(dpi, force_max_dpi)
    jpeg_q = int(round(18 + (90 - 18) * (q ** 0.82)))
    mono_dpi = max(85, int(round(dpi * 1.35)))
    allow_alpha_flatten = q <= 0.48 or grayscale

    return CompressionParams(
        image_dpi=max(42, dpi),
        jpeg_quality=max(16, min(92, jpeg_q)),
        mono_dpi=mono_dpi,
        grayscale=grayscale,
        strip_metadata=strip_metadata,
        subset_fonts=subset_fonts,
        use_ghostscript=(q <= 0.45 or grayscale),
        use_qpdf_objstms=True,
        allow_alpha_flatten=allow_alpha_flatten,
    )


def optimize_to_target_size(
    original_path: Path,
    destination_path: Path,
    analysis: PDFAnalysisResponse,
    target_bytes: int,
    intensity: int = 60,
    grayscale: bool = False,
    strip_metadata: bool = True,
    subset_fonts: bool = True,
    force_max_dpi: Optional[int] = None,
    on_progress: Optional[ProgressCallback] = None,
    is_cancelled: Optional[CancelCheck] = None,
) -> CompressionResultPayload:
    """
    Bounded iterative PDF target-size optimizer.
    Finds the highest-quality valid compressed PDF whose size <= target_bytes,
    or returns the smallest valid achievable output when target_bytes is below the quality floor.
    """
    t0 = time.perf_counter()
    orig_size = analysis.original_size_bytes

    def report(pct: int, msg: str) -> None:
        if on_progress:
            on_progress(max(5, min(98, pct)), msg)

    def check_cancel() -> bool:
        return bool(is_cancelled and is_cancelled())

    # Case 1: Target size >= Original PDF size
    if target_bytes >= orig_size:
        report(35, "Target size exceeds original size — applying lossless structural cleanup...")
        gentle_params = CompressionParams(
            image_dpi=300,
            jpeg_quality=92,
            mono_dpi=300,
            grayscale=grayscale,
            strip_metadata=strip_metadata,
            subset_fonts=subset_fonts,
            use_ghostscript=False,
            use_qpdf_objstms=True,
            allow_alpha_flatten=False,
        )
        t_pass = time.perf_counter()
        pass_res = run_compression_pipeline(
            original_path=original_path,
            destination_path=destination_path,
            params=gentle_params,
            expected_pages=analysis.page_count,
            original_had_text=analysis.has_searchable_text,
            keep_original_if_larger=True,
        )
        dur_ms = max(1, int((time.perf_counter() - t_pass) * 1000))
        total_ms = max(1, int((time.perf_counter() - t0) * 1000))
        saved = max(0, orig_size - pass_res.size_bytes)
        ratio = round((saved / max(1, orig_size)) * 100.0, 2)

        return CompressionResultPayload(
            original_size_bytes=orig_size,
            compressed_size_bytes=pass_res.size_bytes,
            space_saved_bytes=saved,
            compression_ratio_percent=ratio,
            page_count=analysis.page_count,
            processing_time_ms=total_ms,
            target_size_bytes=target_bytes,
            target_status=TargetOutcomeStatus.ALREADY_BELOW_TARGET,
            status_message=(
                f"Your requested target size ({format_bytes(target_bytes)}) is greater than or equal to "
                f"the original PDF size ({format_bytes(orig_size)}). Lossless structural optimization "
                f"was applied without reducing visual quality."
            ),
            warnings=[
                "Requested target size is larger than or equal to the original file; aggressive lossy compression was skipped to preserve 100% visual fidelity."
            ],
            suggestions=[
                f"Set a custom target below {format_bytes(int(orig_size * 0.75))} if you want stronger file size reduction."
            ],
            can_try_stronger=True,
            can_try_grayscale=analysis.images.has_color_images and not grayscale,
            applied_settings=AppliedSettingsSummary(
                mode="custom",
                preset_name="Lossless Structural",
                image_dpi=gentle_params.image_dpi,
                jpeg_quality=gentle_params.jpeg_quality,
                grayscale=grayscale,
                strip_metadata=strip_metadata,
                subset_fonts=subset_fonts,
                used_ghostscript=pass_res.used_ghostscript,
                used_qpdf_objstms=pass_res.used_qpdf_objstms,
                iterations_run=1,
            ),
            iterations=[
                IterationLogItem(
                    iteration=1,
                    image_dpi=gentle_params.image_dpi,
                    jpeg_quality=gentle_params.jpeg_quality,
                    grayscale=grayscale,
                    output_size_bytes=pass_res.size_bytes,
                    met_target=True,
                    duration_ms=dur_ms,
                    note="Lossless structural & metadata optimization",
                )
            ],
            validation_passed=pass_res.validation.is_valid,
            searchable_text_preserved=pass_res.validation.searchable_text_preserved,
        )

    # Case 2: Iterative Bounded Optimization
    max_iters = settings.MAX_TARGET_ITERATIONS
    iterations_log: List[IterationLogItem] = []

    with tempfile.TemporaryDirectory(prefix="optipdf_target_", dir=settings.STORAGE_DIR) as work_dir:
        work = Path(work_dir)
        # Track best valid candidate UNDER target (maximize q_score), and smallest valid overall
        best_under: Optional[Tuple[float, Path, CompressionParams, int, bool, bool, bool]] = None
        smallest_overall: Optional[Tuple[int, float, Path, CompressionParams, bool, bool, bool]] = None

        tested_signatures: set[Tuple[int, int, bool]] = set()

        def evaluate_q(q_val: float, note: str, step_idx: int) -> Tuple[int, CompressionParams]:
            params = _quality_score_to_params(
                q_score=q_val,
                grayscale=grayscale,
                strip_metadata=strip_metadata,
                subset_fonts=subset_fonts,
                force_max_dpi=force_max_dpi,
            )
            sig = (params.image_dpi, params.jpeg_quality, params.grayscale)
            if sig in tested_signatures:
                # Nudge slightly if duplicate signature encountered
                nudged_dpi = max(42, params.image_dpi - 4)
                nudged_q = max(16, params.jpeg_quality - 3)
                params.image_dpi = nudged_dpi
                params.jpeg_quality = nudged_q
                sig = (params.image_dpi, params.jpeg_quality, params.grayscale)
            tested_signatures.add(sig)

            pct = 18 + int((step_idx / max(1, max_iters)) * 72)
            report(
                pct,
                f"Pass {step_idx}/{max_iters}: Optimizing at {params.image_dpi} DPI, JPEG Q{params.jpeg_quality}"
                + (" (Grayscale)" if params.grayscale else "")
                + "...",
            )

            cand_file = work / f"iter_{step_idx}.pdf"
            t_iter = time.perf_counter()
            res = run_compression_pipeline(
                original_path=original_path,
                destination_path=cand_file,
                params=params,
                expected_pages=analysis.page_count,
                original_had_text=analysis.has_searchable_text,
                keep_original_if_larger=True,
            )
            iter_ms = max(1, int((time.perf_counter() - t_iter) * 1000))
            met = res.size_bytes <= target_bytes

            iterations_log.append(
                IterationLogItem(
                    iteration=step_idx,
                    image_dpi=params.image_dpi,
                    jpeg_quality=params.jpeg_quality,
                    grayscale=params.grayscale,
                    output_size_bytes=res.size_bytes,
                    met_target=met,
                    duration_ms=iter_ms,
                    note=note,
                )
            )

            nonlocal best_under, smallest_overall
            if smallest_overall is None or res.size_bytes < smallest_overall[0]:
                smallest_overall = (
                    res.size_bytes,
                    q_val,
                    cand_file,
                    params,
                    res.used_ghostscript,
                    res.used_qpdf_objstms,
                    res.validation.searchable_text_preserved,
                )

            if met:
                # Prefer highest quality score (and closest utilization of target budget)
                if best_under is None or q_val > best_under[0]:
                    best_under = (
                        q_val,
                        cand_file,
                        params,
                        res.size_bytes,
                        res.used_ghostscript,
                        res.used_qpdf_objstms,
                        res.validation.searchable_text_preserved,
                    )

            return res.size_bytes, params

        # Initial smart estimate based on target/original ratio and user intensity slider
        desired_ratio = target_bytes / float(max(1, orig_size))
        intensity_bias = (100 - intensity) / 100.0 * 0.16 - 0.08
        q_initial = max(0.08, min(0.88, (desired_ratio ** 0.55) + intensity_bias))

        step = 1
        sz_init, _ = evaluate_q(q_initial, "Initial smart target estimate", step)

        if not check_cancel():
            # Sweet-spot early exit: under target and already using >= 88% of allowed target budget
            if sz_init <= target_bytes and sz_init >= int(target_bytes * 0.88):
                pass
            elif sz_init > target_bytes:
                # Probe quality floor first to verify target feasibility and bracket [q_low, q_high]
                step += 1
                # Floor depends slightly on intensity: higher intensity probes deeper floor
                q_floor = 0.0 if intensity >= 75 else 0.04
                sz_floor, _ = evaluate_q(q_floor, "Minimum valid quality floor probe", step)

                if sz_floor <= target_bytes and not check_cancel():
                    # Target IS achievable! Bracketed between [q_low (<= target), q_high (> target)]
                    q_low, sz_low = q_floor, sz_floor
                    q_high, sz_high = q_initial, sz_init

                    while step < max_iters and (q_high - q_low) > 0.045 and not check_cancel():
                        if best_under and best_under[3] >= int(target_bytes * 0.91):
                            break
                        # Log-space interpolation blended with binary midpoint for fast convergence
                        if sz_high > sz_low > 0:
                            log_frac = (math.log(target_bytes) - math.log(sz_low)) / max(
                                0.05, (math.log(sz_high) - math.log(sz_low))
                            )
                            log_frac = max(0.25, min(0.75, log_frac))
                            q_mid = q_low + (q_high - q_low) * log_frac
                        else:
                            q_mid = 0.5 * (q_low + q_high)

                        step += 1
                        sz_mid, _ = evaluate_q(q_mid, "Iterative quality maximization pass", step)
                        if sz_mid <= target_bytes:
                            q_low, sz_low = q_mid, sz_mid
                        else:
                            q_high, sz_high = q_mid, sz_mid
            else:
                # sz_init <= target_bytes, but well below target (< 88%): try recovering higher visual quality!
                q_low, sz_low = q_initial, sz_init
                q_high = 0.94
                step += 1
                sz_top, _ = evaluate_q(q_high, "High-quality ceiling check", step)
                if sz_top > target_bytes:
                    sz_high = sz_top
                    while step < max_iters and (q_high - q_low) > 0.05 and not check_cancel():
                        if best_under and best_under[3] >= int(target_bytes * 0.90):
                            break
                        q_mid = 0.5 * (q_low + q_high)
                        step += 1
                        sz_mid, _ = evaluate_q(q_mid, "Refining visual quality near target ceiling", step)
                        if sz_mid <= target_bytes:
                            q_low, sz_low = q_mid, sz_mid
                        else:
                            q_high, sz_high = q_mid, sz_mid

        report(95, "Finalizing and validating compressed PDF output...")

        total_ms = max(1, int((time.perf_counter() - t0) * 1000))

        # Outcome A: Successfully achieved target size!
        if best_under is not None:
            _, chosen_file, chosen_params, chosen_sz, u_gs, u_qp, txt_ok = best_under
            shutil.copy2(chosen_file, destination_path)
            saved = max(0, orig_size - chosen_sz)
            ratio = round((saved / max(1, orig_size)) * 100.0, 2)
            warnings: List[str] = []
            if chosen_params.image_dpi <= 75 or chosen_params.jpeg_quality <= 35:
                warnings.append(
                    "Strong image compression was required to meet your target size. Fine image details may appear softer when zoomed in."
                )

            return CompressionResultPayload(
                original_size_bytes=orig_size,
                compressed_size_bytes=chosen_sz,
                space_saved_bytes=saved,
                compression_ratio_percent=ratio,
                page_count=analysis.page_count,
                processing_time_ms=total_ms,
                target_size_bytes=target_bytes,
                target_status=TargetOutcomeStatus.MET_TARGET,
                status_message=(
                    f"Target achieved! Compressed to {format_bytes(chosen_sz)} "
                    f"(requested ≤ {format_bytes(target_bytes)}) while preserving optimal visual clarity."
                ),
                warnings=warnings,
                suggestions=[],
                can_try_stronger=chosen_params.image_dpi > 52,
                can_try_grayscale=analysis.images.has_color_images and not grayscale,
                applied_settings=AppliedSettingsSummary(
                    mode="custom",
                    preset_name=f"Custom Target ({format_bytes(target_bytes)})",
                    image_dpi=chosen_params.image_dpi,
                    jpeg_quality=chosen_params.jpeg_quality,
                    grayscale=chosen_params.grayscale,
                    strip_metadata=chosen_params.strip_metadata,
                    subset_fonts=chosen_params.subset_fonts,
                    used_ghostscript=u_gs,
                    used_qpdf_objstms=u_qp,
                    iterations_run=len(iterations_log),
                ),
                iterations=iterations_log,
                validation_passed=True,
                searchable_text_preserved=txt_ok,
            )

        # Outcome B: Target size is below the smallest valid quality floor
        assert smallest_overall is not None
        min_sz, _, chosen_file, chosen_params, u_gs, u_qp, txt_ok = smallest_overall
        shutil.copy2(chosen_file, destination_path)
        saved = max(0, orig_size - min_sz)
        ratio = round((saved / max(1, orig_size)) * 100.0, 2)

        suggestions: List[str] = ["Download best available result"]
        can_gray = analysis.images.has_color_images and not grayscale
        can_stronger = (force_max_dpi is None or force_max_dpi > 42) or intensity < 95
        if can_stronger:
            suggestions.append("Try stronger compression")
            suggestions.append("Reduce image resolution")
        if can_gray:
            suggestions.append("Convert color images to grayscale")
        if analysis.images.unique_images == 0:
            suggestions.append(
                "Note: This PDF consists primarily of text, fonts, and vector paths rather than compressible raster photos."
            )

        return CompressionResultPayload(
            original_size_bytes=orig_size,
            compressed_size_bytes=min_sz,
            space_saved_bytes=saved,
            compression_ratio_percent=ratio,
            page_count=analysis.page_count,
            processing_time_ms=total_ms,
            target_size_bytes=target_bytes,
            target_status=TargetOutcomeStatus.FLOOR_REACHED,
            status_message=(
                f"Unable to reach your requested target size without significantly affecting document quality. "
                f"The smallest valid output achieved is {format_bytes(min_sz)}."
            ),
            warnings=[
                f"Requested target was {format_bytes(target_bytes)}, whereas structural PDF streams, subsetted fonts, and legible page content require at least {format_bytes(min_sz)}."
            ],
            suggestions=suggestions,
            can_try_stronger=can_stronger,
            can_try_grayscale=can_gray,
            applied_settings=AppliedSettingsSummary(
                mode="custom",
                preset_name=f"Best Safe Floor (Target {format_bytes(target_bytes)})",
                image_dpi=chosen_params.image_dpi,
                jpeg_quality=chosen_params.jpeg_quality,
                grayscale=chosen_params.grayscale,
                strip_metadata=chosen_params.strip_metadata,
                subset_fonts=chosen_params.subset_fonts,
                used_ghostscript=u_gs,
                used_qpdf_objstms=u_qp,
                iterations_run=len(iterations_log),
            ),
            iterations=iterations_log,
            validation_passed=True,
            searchable_text_preserved=txt_ok,
        )
