import io
import json
import os
import shutil
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Literal, Optional

import pymupdf as fitz
from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.core.config import settings
from app.core.exceptions import (
    AppPDFError,
    InvalidPDFError,
    JobNotFoundError,
    RenderingFailedError,
    ZipCreationError,
)
from app.core.security import (
    create_isolated_job_dir,
    sanitize_filename,
    stream_upload_to_disk,
    validate_token_id,
)
from app.models.schemas import (
    BatchItemSetting,
    BatchJobItemResponse,
    BatchSubmitResponse,
    CompressCustomRequest,
    CompressionPreset,
    CompressPresetRequest,
    JobState,
    JobStatusResponse,
    PDFAnalysisResponse,
    SizeUnit,
    ZipDownloadRequest,
)
from app.services.pdf_analyzer import analyze_pdf_file
from app.workers.job_manager import job_manager

router = APIRouter(prefix="/pdf", tags=["PDF Compression"])


@router.post("/upload", response_model=PDFAnalysisResponse, status_code=201)
async def upload_pdf(file: UploadFile = File(...)) -> PDFAnalysisResponse:
    """Stream, validate, and deeply analyze an uploaded PDF document."""
    safe_name = sanitize_filename(file.filename)
    file_id, storage_dir = create_isolated_job_dir()
    orig_path = storage_dir / "original.pdf"

    try:
        await stream_upload_to_disk(file, orig_path)
        analysis = analyze_pdf_file(
            pdf_path=orig_path,
            file_id=file_id,
            original_filename=safe_name,
            include_thumbnail=True,
        )
        job_manager.register_uploaded_file(
            file_id=file_id,
            filename=safe_name,
            original_path=orig_path,
            analysis=analysis,
        )
        return analysis
    except Exception:
        shutil.rmtree(storage_dir, ignore_errors=True)
        raise


@router.post("/sample", response_model=PDFAnalysisResponse, status_code=201)
async def load_sample_pdf() -> PDFAnalysisResponse:
    """Load the built-in multi-page sample PDF into a fresh ephemeral upload session."""
    sample_dir = Path(settings.SAMPLE_PDF_DIR)
    candidates = sorted(sample_dir.glob("*.pdf")) if sample_dir.exists() else []
    if not candidates:
        raise JobNotFoundError("No built-in sample PDF is currently available on the server.")

    sample_src = candidates[0]
    safe_name = sanitize_filename(sample_src.name)
    file_id, storage_dir = create_isolated_job_dir()
    orig_path = storage_dir / "original.pdf"
    shutil.copy2(sample_src, orig_path)

    analysis = analyze_pdf_file(
        pdf_path=orig_path,
        file_id=file_id,
        original_filename=safe_name,
        include_thumbnail=True,
    )
    job_manager.register_uploaded_file(
        file_id=file_id,
        filename=safe_name,
        original_path=orig_path,
        analysis=analysis,
    )
    return analysis


@router.post("/compress", response_model=JobStatusResponse, status_code=202)
async def compress_pdf_preset(payload: CompressPresetRequest) -> JobStatusResponse:
    """Start a background PDF compression job using a predefined compression preset."""
    fid = validate_token_id(payload.file_id)
    return job_manager.submit_preset_job(
        file_id=fid,
        preset=payload.preset,
        grayscale=payload.grayscale,
        strip_metadata=payload.strip_metadata,
        subset_fonts=payload.subset_fonts,
    )


@router.post("/compress/custom", response_model=JobStatusResponse, status_code=202)
async def compress_pdf_custom_target(payload: CompressCustomRequest) -> JobStatusResponse:
    """Start an iterative custom target-size PDF compression job."""
    fid = validate_token_id(payload.file_id)
    return job_manager.submit_custom_target_job(
        file_id=fid,
        target_value=payload.target_value,
        target_unit=payload.target_unit,
        intensity=payload.intensity,
        grayscale=payload.grayscale,
        strip_metadata=payload.strip_metadata,
        subset_fonts=payload.subset_fonts,
        force_max_dpi=payload.force_max_dpi,
    )


@router.post("/compress/batch", response_model=BatchSubmitResponse, status_code=202)
async def compress_pdf_batch(
    files: List[UploadFile] = File(...),
    settings_json: Optional[str] = Form(default=None),
) -> BatchSubmitResponse:
    """
    Upload and process multiple PDF files concurrently.
    Each file is validated and queued independently so a single failed file never stops the batch.
    """
    if not files:
        raise InvalidPDFError("Please select at least one PDF file for batch compression.")
    if len(files) > settings.MAX_BATCH_FILES:
        raise InvalidPDFError(
            f"A maximum of {settings.MAX_BATCH_FILES} PDF files can be processed in a single batch."
        )

    per_index_settings: Dict[int, BatchItemSetting] = {}
    if settings_json:
        try:
            raw_list = json.loads(settings_json)
            if isinstance(raw_list, list):
                for raw_item in raw_list:
                    parsed = BatchItemSetting.model_validate(raw_item)
                    per_index_settings[parsed.index] = parsed
        except Exception as exc:
            raise InvalidPDFError("Invalid batch settings JSON payload.") from exc

    batch_id = uuid.uuid4().hex
    results: List[BatchJobItemResponse] = []
    queued_count = 0
    failed_count = 0

    for idx, upload in enumerate(files):
        safe_name = sanitize_filename(upload.filename)
        file_id, storage_dir = create_isolated_job_dir()
        orig_path = storage_dir / "original.pdf"

        try:
            await stream_upload_to_disk(upload, orig_path)
            analysis = analyze_pdf_file(
                pdf_path=orig_path,
                file_id=file_id,
                original_filename=safe_name,
                include_thumbnail=False,
            )
            job_manager.register_uploaded_file(
                file_id=file_id,
                filename=safe_name,
                original_path=orig_path,
                analysis=analysis,
            )

            cfg = per_index_settings.get(idx)
            if cfg and cfg.mode == "custom" and cfg.target_value and cfg.target_value > 0:
                job_resp = job_manager.submit_custom_target_job(
                    file_id=file_id,
                    target_value=cfg.target_value,
                    target_unit=cfg.target_unit,
                    grayscale=cfg.grayscale,
                )
            else:
                preset = cfg.preset if cfg else CompressionPreset.RECOMMENDED
                gray = cfg.grayscale if cfg else False
                job_resp = job_manager.submit_preset_job(
                    file_id=file_id,
                    preset=preset,
                    grayscale=gray,
                )

            queued_count += 1
            results.append(
                BatchJobItemResponse(
                    index=idx,
                    filename=safe_name,
                    job_id=job_resp.job_id,
                    file_id=file_id,
                    status="queued",
                )
            )
        except AppPDFError as exc:
            shutil.rmtree(storage_dir, ignore_errors=True)
            failed_count += 1
            results.append(
                BatchJobItemResponse(
                    index=idx,
                    filename=safe_name,
                    status="failed",
                    error_code=exc.code,
                    error_message=exc.message,
                )
            )
        except Exception:
            shutil.rmtree(storage_dir, ignore_errors=True)
            failed_count += 1
            results.append(
                BatchJobItemResponse(
                    index=idx,
                    filename=safe_name,
                    status="failed",
                    error_code="UPLOAD_FAILED",
                    error_message="Failed to validate or queue this file.",
                )
            )

    return BatchSubmitResponse(
        batch_id=batch_id,
        total_files=len(files),
        queued_count=queued_count,
        failed_count=failed_count,
        items=results,
    )


@router.get("/status/{job_id}", response_model=JobStatusResponse)
async def get_compression_status(job_id: str) -> JobStatusResponse:
    """Retrieve real-time status, progress percentage, and metrics for a compression job."""
    jid = validate_token_id(job_id)
    return job_manager.get_job_status(jid)


@router.post("/cancel/{job_id}", response_model=JobStatusResponse)
async def cancel_compression_job(job_id: str) -> JobStatusResponse:
    """Cancel an active or queued compression job."""
    jid = validate_token_id(job_id)
    return job_manager.cancel_job(jid)


@router.get("/download/{job_id}")
async def download_compressed_pdf(job_id: str) -> FileResponse:
    """Download the validated compressed PDF for a completed job."""
    jid = validate_token_id(job_id)
    job = job_manager.get_job(jid)
    if job.state != JobState.COMPLETED or not job.output_path.exists():
        raise JobNotFoundError("Compressed PDF is not ready or has been deleted.")

    stem = job.filename[:-4] if job.filename.lower().endswith(".pdf") else job.filename
    download_name = sanitize_filename(f"{stem}-compressed.pdf")
    return FileResponse(
        path=str(job.output_path),
        media_type="application/pdf",
        filename=download_name,
    )


@router.post("/download/zip")
async def download_batch_zip(payload: ZipDownloadRequest) -> StreamingResponse:
    """Bundle multiple completed compression jobs into a single downloadable ZIP archive."""
    valid_entries: List[tuple[str, Path]] = []
    used_names: Dict[str, int] = {}

    for raw_id in payload.job_ids:
        jid = validate_token_id(raw_id)
        try:
            job = job_manager.get_job(jid)
        except JobNotFoundError:
            continue
        if job.state == JobState.COMPLETED and job.output_path.exists():
            stem = job.filename[:-4] if job.filename.lower().endswith(".pdf") else job.filename
            base_name = sanitize_filename(f"{stem}-compressed.pdf")
            count = used_names.get(base_name, 0)
            used_names[base_name] = count + 1
            if count > 0:
                arcname = f"{base_name[:-4]}-{count + 1}.pdf"
            else:
                arcname = base_name
            valid_entries.append((arcname, job.output_path))

    if not valid_entries:
        raise ZipCreationError("None of the requested batch jobs have completed PDF outputs available.")

    try:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for arcname, file_path in valid_entries:
                zf.write(file_path, arcname=arcname)
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": 'attachment; filename="optipdf-compressed-batch.zip"'
            },
        )
    except Exception as exc:
        raise ZipCreationError() from exc


@router.api_route("/preview/{identifier}", methods=["GET", "HEAD"])
async def preview_pdf(
    identifier: str,
    variant: Literal["original", "compressed"] = Query(default="compressed"),
    output_format: Literal["pdf", "png"] = Query(default="pdf", alias="format"),
    page: int = Query(default=1, ge=1, le=2000),
) -> Response:
    """
    Serve either the PDF binary stream (for interactive PDF.js rendering in browser)
    or a rendered PNG page preview. Accepts either a job_id or an uploaded file_id.
    """
    ident = validate_token_id(identifier)
    target_pdf: Optional[Path] = None

    # Resolve either job_id or file_id
    try:
        job = job_manager.get_job(ident)
        if variant == "original":
            target_pdf = job.original_path
        else:
            target_pdf = job.output_path if job.output_path.exists() else job.original_path
    except JobNotFoundError:
        uploaded = job_manager.get_uploaded_file(ident)
        target_pdf = uploaded.original_path

    if not target_pdf or not target_pdf.exists():
        raise JobNotFoundError("Preview source file is no longer available.")

    if output_format == "pdf":
        return FileResponse(
            path=str(target_pdf),
            media_type="application/pdf",
            headers={"Cache-Control": "no-store"},
        )

    # Render requested 1-based page as PNG
    doc = None
    try:
        doc = fitz.open(target_pdf)
        if page > doc.page_count:
            raise RenderingFailedError(f"Requested page {page}, but document has {doc.page_count} pages.")
        p = doc[page - 1]
        scale = min(2.0, 900.0 / max(1.0, p.rect.width))
        pix = p.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        png_bytes = pix.tobytes("png")
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )
    except AppPDFError:
        raise
    except Exception as exc:
        raise RenderingFailedError() from exc
    finally:
        if doc is not None:
            doc.close()


@router.delete("/{identifier}")
async def delete_pdf_data(identifier: str) -> Dict[str, object]:
    """Immediately delete original and compressed files for user privacy."""
    ident = validate_token_id(identifier)
    removed = job_manager.delete_file_or_job(ident)
    return {
        "deleted": removed,
        "message": "Temporary PDF files have been permanently removed from the server.",
    }
