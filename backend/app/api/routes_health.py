import PIL
import pikepdf
import pymupdf as fitz
from fastapi import APIRouter

from app.core.config import settings
from app.models.schemas import HealthResponse
from app.services.cleanup import count_stored_items
from app.services.compression import check_ghostscript_available, check_qpdf_available
from app.workers.job_manager import job_manager

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    gs_ver = check_ghostscript_available()
    qpdf_ver = check_qpdf_available()
    engines = {
        "pymupdf": getattr(fitz, "__version__", "available"),
        "ghostscript": gs_ver or "unavailable",
        "qpdf": qpdf_ver or "unavailable",
        "pikepdf": pikepdf.__version__,
        "pillow": PIL.__version__,
    }
    status = "healthy" if gs_ver and qpdf_ver else "degraded"
    return HealthResponse(
        status=status,
        version=settings.APP_VERSION,
        engines=engines,
        active_jobs=job_manager.active_job_count(),
        stored_items=count_stored_items(),
        retention_minutes=settings.FILE_RETENTION_MINUTES,
    )
