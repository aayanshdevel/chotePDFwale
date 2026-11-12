import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

mimetypes.add_type("text/javascript", ".mjs")

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes_health import router as health_router
from app.api.routes_pdf import router as pdf_router
from app.core.config import settings
from app.core.exceptions import AppPDFError
from app.core.rate_limit import RateLimitMiddleware
from app.workers.job_manager import job_manager


@asynccontextmanager
async def lifespan(_app: FastAPI):
    job_manager.start_background_reaper()
    yield
    job_manager.cleanup_expired()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production PDF Size Reducer API with hybrid PyMuPDF, Ghostscript, Pillow, and QPDF target-size optimization.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)


@app.exception_handler(AppPDFError)
async def handle_app_pdf_error(_request: Request, exc: AppPDFError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    first_msg = "Invalid request parameters."
    if exc.errors():
        err = exc.errors()[0]
        loc = " -> ".join(str(x) for x in err.get("loc", []) if x != "body")
        msg = err.get("msg", "Invalid input")
        first_msg = f"{loc}: {msg}" if loc else msg
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": first_msg,
            }
        },
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_request: Request, _exc: Exception) -> JSONResponse:
    # Never expose internal tracebacks or server file paths
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected server error occurred while processing your request.",
            }
        },
    )


app.include_router(health_router, prefix=settings.API_V1_PREFIX)
app.include_router(pdf_router, prefix=settings.API_V1_PREFIX)

# Serve compiled frontend SPA when present (for unified single-origin production / live preview)
_static_dir = Path(settings.STATIC_FRONTEND_DIR)
if _static_dir.exists() and (_static_dir / "index.html").exists():
    _assets_dir = _static_dir / "assets"
    if _assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(_assets_dir)), name="assets")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "NOT_FOUND", "message": "API endpoint not found."}},
            )
        candidate = (_static_dir / full_path).resolve()
        if _static_dir.resolve() in candidate.parents and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_static_dir / "index.html"))
