from typing import Any, Dict, Optional


class AppPDFError(Exception):
    """Base domain exception for safe client-facing error reporting."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class EmptyPDFError(AppPDFError):
    def __init__(self, message: str = "The uploaded file is empty (0 bytes) or contains no pages."):
        super().__init__("EMPTY_PDF", message, 400)


class InvalidPDFError(AppPDFError):
    def __init__(
        self,
        message: str = "Invalid file format. Please upload a genuine PDF document with a valid PDF header.",
    ):
        super().__init__("INVALID_PDF", message, 400)


class PasswordProtectedPDFError(AppPDFError):
    def __init__(
        self,
        message: str = "This PDF is password-protected or encrypted. Please unlock the document before compressing.",
    ):
        super().__init__("PASSWORD_PROTECTED_PDF", message, 422)


class UnsupportedEncryptionError(AppPDFError):
    def __init__(
        self,
        message: str = "This PDF uses an unsupported security handler or DRM encryption that prevents safe optimization.",
    ):
        super().__init__("UNSUPPORTED_ENCRYPTION", message, 422)


class CorruptedPDFError(AppPDFError):
    def __init__(
        self,
        message: str = "The uploaded PDF appears to be corrupted or structurally damaged and cannot be safely processed.",
    ):
        super().__init__("CORRUPTED_PDF", message, 422)


class FileTooLargeError(AppPDFError):
    def __init__(self, max_mb: int):
        super().__init__(
            "FILE_TOO_LARGE",
            f"The uploaded file exceeds the maximum allowed size of {max_mb} MB.",
            413,
            {"max_upload_mb": max_mb},
        )


class PageLimitExceededError(AppPDFError):
    def __init__(self, page_count: int, max_pages: int):
        super().__init__(
            "PAGE_LIMIT_EXCEEDED",
            f"This PDF contains {page_count} pages, exceeding the server limit of {max_pages} pages.",
            422,
            {"page_count": page_count, "max_page_count": max_pages},
        )


class CompressionFailedError(AppPDFError):
    def __init__(
        self,
        message: str = "Compression could not produce a valid PDF output. Your original document was not modified.",
    ):
        super().__init__("COMPRESSION_FAILED", message, 500)


class ProcessingTimeoutError(AppPDFError):
    def __init__(
        self,
        message: str = "PDF compression timed out due to document complexity. Try a faster preset or split large documents.",
    ):
        super().__init__("PROCESSING_TIMEOUT", message, 504)


class InsufficientMemoryError(AppPDFError):
    def __init__(
        self,
        message: str = "Server memory limit was reached while processing high-resolution pages. Please try a smaller document.",
    ):
        super().__init__("INSUFFICIENT_MEMORY", message, 507)


class RenderingFailedError(AppPDFError):
    def __init__(
        self,
        message: str = "Unable to render the requested PDF preview page.",
    ):
        super().__init__("PREVIEW_RENDER_FAILED", message, 422)


class ZipCreationError(AppPDFError):
    def __init__(
        self,
        message: str = "Failed to generate the batch ZIP archive for the selected jobs.",
    ):
        super().__init__("ZIP_CREATION_FAILED", message, 500)


class JobNotFoundError(AppPDFError):
    def __init__(
        self,
        message: str = "The requested file or compression job was not found or has expired and been deleted for privacy.",
    ):
        super().__init__("JOB_NOT_FOUND", message, 404)
