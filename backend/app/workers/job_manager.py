import asyncio
import os
import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.exceptions import (
    AppPDFError,
    JobNotFoundError,
    ProcessingTimeoutError,
)
from app.core.security import create_isolated_job_dir
from app.models.schemas import (
    AppliedSettingsSummary,
    CompressionPreset,
    CompressionResultPayload,
    IterationLogItem,
    JobState,
    JobStatusResponse,
    PDFAnalysisResponse,
    SizeUnit,
    TargetOutcomeStatus,
)
from app.services.cleanup import delete_storage_item, purge_expired_files
from app.services.compression import (
    PRESET_PARAM_MAP,
    CompressionParams,
    run_compression_pipeline,
)
from app.services.pdf_analyzer import format_bytes
from app.services.target_optimizer import optimize_to_target_size


@dataclass
class UploadedFileEntry:
    file_id: str
    filename: str
    original_path: Path
    analysis: PDFAnalysisResponse
    created_at: float = field(default_factory=time.time)


@dataclass
class JobEntry:
    job_id: str
    file_id: str
    filename: str
    original_path: Path
    output_path: Path
    analysis: PDFAnalysisResponse
    state: JobState = JobState.QUEUED
    progress_percent: int = 0
    stage_message: str = "Queued for compression..."
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    result: Optional[CompressionResultPayload] = None
    cancel_requested: bool = False
    future: Optional[Future] = None


class JobManager:
    """Thread-safe background worker pool for PDF analysis, preset compression, and custom target optimization."""

    def __init__(self, max_workers: int = settings.MAX_CONCURRENT_JOBS):
        self._lock = threading.RLock()
        self._files: Dict[str, UploadedFileEntry] = {}
        self._jobs: Dict[str, JobEntry] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="optipdf-worker",
        )
        self._cleanup_task: Optional[asyncio.Task] = None

    def start_background_reaper(self) -> None:
        if self._cleanup_task is None:
            loop = asyncio.get_running_loop()
            self._cleanup_task = loop.create_task(self._reaper_loop())

    async def _reaper_loop(self) -> None:
        while True:
            await asyncio.sleep(settings.CLEANUP_INTERVAL_SECONDS)
            try:
                self.cleanup_expired()
            except Exception:
                pass

    def cleanup_expired(self) -> int:
        ttl = settings.FILE_RETENTION_MINUTES * 60
        now = time.time()
        expired_files: List[str] = []
        expired_jobs: List[str] = []

        with self._lock:
            for fid, entry in self._files.items():
                if (now - entry.created_at) > ttl:
                    expired_files.append(fid)
            for jid, jentry in self._jobs.items():
                if jentry.state in (JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED):
                    if (now - jentry.updated_at) > ttl:
                        expired_jobs.append(jid)

            for fid in expired_files:
                self._files.pop(fid, None)
            for jid in expired_jobs:
                self._jobs.pop(jid, None)

        for fid in expired_files:
            delete_storage_item(fid)
        for jid in expired_jobs:
            delete_storage_item(jid)
        removed_dirs = purge_expired_files()
        return len(expired_files) + len(expired_jobs) + removed_dirs

    def register_uploaded_file(
        self,
        file_id: str,
        filename: str,
        original_path: Path,
        analysis: PDFAnalysisResponse,
    ) -> UploadedFileEntry:
        entry = UploadedFileEntry(
            file_id=file_id,
            filename=filename,
            original_path=original_path,
            analysis=analysis,
        )
        with self._lock:
            self._files[file_id] = entry
        return entry

    def get_uploaded_file(self, file_id: str) -> UploadedFileEntry:
        with self._lock:
            entry = self._files.get(file_id)
        if not entry or not entry.original_path.exists():
            raise JobNotFoundError("Uploaded PDF session was not found or has expired.")
        return entry

    def get_job(self, job_id: str) -> JobEntry:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            raise JobNotFoundError()
        return job

    def get_job_status(self, job_id: str) -> JobStatusResponse:
        job = self.get_job(job_id)
        with self._lock:
            return JobStatusResponse(
                job_id=job.job_id,
                file_id=job.file_id,
                filename=job.filename,
                state=job.state,
                progress_percent=job.progress_percent,
                stage_message=job.stage_message,
                created_at=job.created_at,
                updated_at=job.updated_at,
                error_code=job.error_code,
                error_message=job.error_message,
                analysis=job.analysis,
                result=job.result,
            )

    def active_job_count(self) -> int:
        with self._lock:
            return sum(
                1
                for j in self._jobs.values()
                if j.state in (JobState.QUEUED, JobState.ANALYZING, JobState.COMPRESSING, JobState.VALIDATING)
            )

    def cancel_job(self, job_id: str) -> JobStatusResponse:
        job = self.get_job(job_id)
        with self._lock:
            job.cancel_requested = True
            if job.future and not job.future.done():
                job.future.cancel()
            if job.state not in (JobState.COMPLETED, JobState.FAILED):
                job.state = JobState.CANCELLED
                job.stage_message = "Compression cancelled by user."
                job.updated_at = time.time()
        return self.get_job_status(job_id)

    def delete_file_or_job(self, identifier: str) -> bool:
        deleted = False
        related_file_id: Optional[str] = None
        related_job_ids: List[str] = []

        with self._lock:
            if identifier in self._jobs:
                job = self._jobs.pop(identifier)
                job.cancel_requested = True
                related_file_id = job.file_id
                deleted = True
            if identifier in self._files:
                self._files.pop(identifier)
                deleted = True
                for jid, j in list(self._jobs.items()):
                    if j.file_id == identifier:
                        j.cancel_requested = True
                        related_job_ids.append(jid)
                        self._jobs.pop(jid, None)

        if delete_storage_item(identifier):
            deleted = True
        for jid in related_job_ids:
            delete_storage_item(jid)
        # Note: if user deleted a job, also delete its parent upload if no other jobs use it
        if related_file_id:
            with self._lock:
                still_used = any(j.file_id == related_file_id for j in self._jobs.values())
                if not still_used:
                    self._files.pop(related_file_id, None)
            if not still_used:
                delete_storage_item(related_file_id)

        return deleted

    def _update_job(
        self,
        job_id: str,
        *,
        state: Optional[JobState] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.state == JobState.CANCELLED:
                return
            if state is not None:
                job.state = state
            if progress is not None:
                job.progress_percent = max(0, min(100, progress))
            if message is not None:
                job.stage_message = message
            job.updated_at = time.time()

    def submit_preset_job(
        self,
        file_id: str,
        preset: CompressionPreset,
        grayscale: bool = False,
        strip_metadata: bool = True,
        subset_fonts: bool = True,
    ) -> JobStatusResponse:
        file_entry = self.get_uploaded_file(file_id)
        job_id, job_dir = create_isolated_job_dir()
        output_path = job_dir / "compressed.pdf"

        job = JobEntry(
            job_id=job_id,
            file_id=file_entry.file_id,
            filename=file_entry.filename,
            original_path=file_entry.original_path,
            output_path=output_path,
            analysis=file_entry.analysis,
            state=JobState.QUEUED,
            progress_percent=5,
            stage_message=f"Queued for {preset.value.capitalize()} compression...",
        )
        with self._lock:
            self._jobs[job_id] = job
            job.future = self._executor.submit(
                self._execute_preset_worker,
                job_id,
                preset,
                grayscale,
                strip_metadata,
                subset_fonts,
            )
        return self.get_job_status(job_id)

    def submit_custom_target_job(
        self,
        file_id: str,
        target_value: float,
        target_unit: SizeUnit,
        intensity: int = 60,
        grayscale: bool = False,
        strip_metadata: bool = True,
        subset_fonts: bool = True,
        force_max_dpi: Optional[int] = None,
    ) -> JobStatusResponse:
        file_entry = self.get_uploaded_file(file_id)
        job_id, job_dir = create_isolated_job_dir()
        output_path = job_dir / "compressed.pdf"

        multiplier = 1024 if target_unit == SizeUnit.KB else 1024 * 1024
        target_bytes = max(1024, int(round(target_value * multiplier)))

        job = JobEntry(
            job_id=job_id,
            file_id=file_entry.file_id,
            filename=file_entry.filename,
            original_path=file_entry.original_path,
            output_path=output_path,
            analysis=file_entry.analysis,
            state=JobState.QUEUED,
            progress_percent=5,
            stage_message=f"Queued for custom target ({format_bytes(target_bytes)}) optimization...",
        )
        with self._lock:
            self._jobs[job_id] = job
            job.future = self._executor.submit(
                self._execute_custom_worker,
                job_id,
                target_bytes,
                intensity,
                grayscale,
                strip_metadata,
                subset_fonts,
                force_max_dpi,
            )
        return self.get_job_status(job_id)

    def _execute_preset_worker(
        self,
        job_id: str,
        preset: CompressionPreset,
        grayscale: bool,
        strip_metadata: bool,
        subset_fonts: bool,
    ) -> None:
        t0 = time.perf_counter()
        try:
            job = self.get_job(job_id)
            if job.cancel_requested:
                return

            self._update_job(
                job_id,
                state=JobState.ANALYZING,
                progress=18,
                message="Inspecting embedded images, fonts, and PDF object streams...",
            )

            base_p = PRESET_PARAM_MAP[preset]
            params = CompressionParams(
                image_dpi=base_p.image_dpi,
                jpeg_quality=base_p.jpeg_quality,
                mono_dpi=base_p.mono_dpi,
                grayscale=grayscale or base_p.grayscale,
                strip_metadata=strip_metadata,
                subset_fonts=subset_fonts,
                use_ghostscript=base_p.use_ghostscript,
                use_qpdf_objstms=base_p.use_qpdf_objstms,
                allow_alpha_flatten=base_p.allow_alpha_flatten or grayscale,
            )

            self._update_job(
                job_id,
                state=JobState.COMPRESSING,
                progress=48,
                message=(
                    f"Applying {preset.value.capitalize()} compression "
                    f"({params.image_dpi} DPI, JPEG Q{params.jpeg_quality})..."
                ),
            )

            pass_res = run_compression_pipeline(
                original_path=job.original_path,
                destination_path=job.output_path,
                params=params,
                expected_pages=job.analysis.page_count,
                original_had_text=job.analysis.has_searchable_text,
                keep_original_if_larger=True,
            )

            if (time.perf_counter() - t0) > settings.COMPRESSION_TIMEOUT_SECONDS:
                raise ProcessingTimeoutError()

            self._update_job(
                job_id,
                state=JobState.VALIDATING,
                progress=88,
                message="Validating output PDF integrity, page geometry, and text streams...",
            )

            total_ms = max(1, int((time.perf_counter() - t0) * 1000))
            orig_sz = job.analysis.original_size_bytes
            comp_sz = pass_res.size_bytes
            saved = max(0, orig_sz - comp_sz)
            ratio = round((saved / max(1, orig_sz)) * 100.0, 2)

            warnings: List[str] = []
            if preset == CompressionPreset.EXTREME:
                warnings.append(
                    "Extreme compression prioritized maximum file size reduction; embedded photos were downsampled to 72 DPI."
                )
            if saved == 0:
                status_msg = (
                    "This PDF was already tightly optimized. Original visual quality and structure were preserved without size inflation."
                )
            else:
                status_msg = (
                    f"Compressed from {format_bytes(orig_sz)} to {format_bytes(comp_sz)} "
                    f"({ratio:.1f}% reduction) using {preset.value.capitalize()} mode."
                )

            payload = CompressionResultPayload(
                original_size_bytes=orig_sz,
                compressed_size_bytes=comp_sz,
                space_saved_bytes=saved,
                compression_ratio_percent=ratio,
                page_count=job.analysis.page_count,
                processing_time_ms=total_ms,
                target_size_bytes=None,
                target_status=TargetOutcomeStatus.PRESET_APPLIED,
                status_message=status_msg,
                warnings=warnings,
                suggestions=[],
                can_try_stronger=(preset != CompressionPreset.EXTREME),
                can_try_grayscale=(job.analysis.images.has_color_images and not params.grayscale),
                applied_settings=AppliedSettingsSummary(
                    mode="preset",
                    preset_name=f"{preset.value.capitalize()} Compression",
                    image_dpi=params.image_dpi,
                    jpeg_quality=params.jpeg_quality,
                    grayscale=params.grayscale,
                    strip_metadata=params.strip_metadata,
                    subset_fonts=params.subset_fonts,
                    used_ghostscript=pass_res.used_ghostscript,
                    used_qpdf_objstms=pass_res.used_qpdf_objstms,
                    iterations_run=1,
                ),
                iterations=[
                    IterationLogItem(
                        iteration=1,
                        image_dpi=params.image_dpi,
                        jpeg_quality=params.jpeg_quality,
                        grayscale=params.grayscale,
                        output_size_bytes=comp_sz,
                        met_target=True,
                        duration_ms=total_ms,
                        note=f"{preset.value.capitalize()} preset hybrid pipeline",
                    )
                ],
                validation_passed=pass_res.validation.is_valid,
                searchable_text_preserved=pass_res.validation.searchable_text_preserved,
            )

            with self._lock:
                j = self._jobs.get(job_id)
                if j and j.state != JobState.CANCELLED:
                    j.result = payload
                    j.state = JobState.COMPLETED
                    j.progress_percent = 100
                    j.stage_message = "Compression complete."
                    j.updated_at = time.time()

        except AppPDFError as exc:
            self._fail_job(job_id, exc.code, exc.message)
        except Exception:
            self._fail_job(
                job_id,
                "COMPRESSION_FAILED",
                "An unexpected PDF processing error occurred. Your original document remains untouched.",
            )

    def _execute_custom_worker(
        self,
        job_id: str,
        target_bytes: int,
        intensity: int,
        grayscale: bool,
        strip_metadata: bool,
        subset_fonts: bool,
        force_max_dpi: Optional[int],
    ) -> None:
        try:
            job = self.get_job(job_id)
            if job.cancel_requested:
                return

            self._update_job(
                job_id,
                state=JobState.COMPRESSING,
                progress=12,
                message=f"Starting iterative search for target ≤ {format_bytes(target_bytes)}...",
            )

            def on_progress(pct: int, msg: str) -> None:
                st = JobState.VALIDATING if pct >= 92 else JobState.COMPRESSING
                self._update_job(job_id, state=st, progress=pct, message=msg)

            def is_cancelled() -> bool:
                with self._lock:
                    j = self._jobs.get(job_id)
                    return bool(not j or j.cancel_requested)

            payload = optimize_to_target_size(
                original_path=job.original_path,
                destination_path=job.output_path,
                analysis=job.analysis,
                target_bytes=target_bytes,
                intensity=intensity,
                grayscale=grayscale,
                strip_metadata=strip_metadata,
                subset_fonts=subset_fonts,
                force_max_dpi=force_max_dpi,
                on_progress=on_progress,
                is_cancelled=is_cancelled,
            )

            with self._lock:
                j = self._jobs.get(job_id)
                if j and j.state != JobState.CANCELLED:
                    j.result = payload
                    j.state = JobState.COMPLETED
                    j.progress_percent = 100
                    j.stage_message = "Compression complete."
                    j.updated_at = time.time()

        except AppPDFError as exc:
            self._fail_job(job_id, exc.code, exc.message)
        except Exception:
            self._fail_job(
                job_id,
                "COMPRESSION_FAILED",
                "Iterative compression encountered an unexpected error while optimizing this PDF.",
            )

    def _fail_job(self, job_id: str, code: str, message: str) -> None:
        with self._lock:
            j = self._jobs.get(job_id)
            if j and j.state != JobState.CANCELLED:
                j.state = JobState.FAILED
                j.error_code = code
                j.error_message = message
                j.stage_message = message
                j.updated_at = time.time()


job_manager = JobManager()
