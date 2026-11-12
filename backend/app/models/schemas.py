from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class CompressionPreset(str, Enum):
    LOW = "low"
    RECOMMENDED = "recommended"
    HIGH = "high"
    EXTREME = "extreme"


class SizeUnit(str, Enum):
    KB = "KB"
    MB = "MB"


class JobState(str, Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    ANALYZING = "analyzing"
    COMPRESSING = "compressing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TargetOutcomeStatus(str, Enum):
    MET_TARGET = "met_target"
    FLOOR_REACHED = "floor_reached"
    ALREADY_BELOW_TARGET = "already_below_target"
    PRESET_APPLIED = "preset_applied"


class ImageAnalysisSummary(BaseModel):
    unique_images: int
    image_bytes_estimate: int
    image_share_percent: float
    max_effective_dpi: int
    median_effective_dpi: int
    has_color_images: bool
    has_alpha_images: bool


class FontAnalysisSummary(BaseModel):
    total_fonts: int
    embedded_fonts: int
    subset_fonts: int


class PDFAnalysisResponse(BaseModel):
    file_id: str
    filename: str
    original_size_bytes: int
    original_size_formatted: str
    page_count: int
    pdf_version: str
    page_dimensions: str
    width_pt: float
    height_pt: float
    content_profile: Literal["text_heavy", "scanned", "image_heavy", "vector_rich", "mixed"]
    has_searchable_text: bool
    has_vector_graphics: bool
    had_javascript_stripped: bool = False
    images: ImageAnalysisSummary
    fonts: FontAnalysisSummary
    estimated_min_size_bytes: int
    recommended_min_size_bytes: int
    estimated_reduction_percent_low: float
    estimated_reduction_percent_high: float
    thumbnail_data_url: Optional[str] = None
    expires_in_minutes: int


class CompressPresetRequest(BaseModel):
    file_id: str = Field(..., min_length=16, max_length=64)
    preset: CompressionPreset = CompressionPreset.RECOMMENDED
    grayscale: bool = False
    strip_metadata: bool = True
    subset_fonts: bool = True


class CompressCustomRequest(BaseModel):
    file_id: str = Field(..., min_length=16, max_length=64)
    target_value: float = Field(..., gt=0, le=500000)
    target_unit: SizeUnit = SizeUnit.KB
    intensity: int = Field(default=60, ge=10, le=100, description="Compression intensity preference 10-100")
    grayscale: bool = False
    strip_metadata: bool = True
    subset_fonts: bool = True
    force_max_dpi: Optional[int] = Field(default=None, ge=36, le=300)

    @field_validator("target_value")
    @classmethod
    def validate_reasonable_target(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Target size must be greater than zero.")
        return v


class IterationLogItem(BaseModel):
    iteration: int
    image_dpi: int
    jpeg_quality: int
    grayscale: bool
    output_size_bytes: int
    met_target: bool
    duration_ms: int
    note: str = ""


class AppliedSettingsSummary(BaseModel):
    mode: Literal["preset", "custom"]
    preset_name: Optional[str] = None
    image_dpi: int
    jpeg_quality: int
    grayscale: bool
    strip_metadata: bool
    subset_fonts: bool
    used_ghostscript: bool
    used_qpdf_objstms: bool
    iterations_run: int = 1


class CompressionResultPayload(BaseModel):
    original_size_bytes: int
    compressed_size_bytes: int
    space_saved_bytes: int
    compression_ratio_percent: float
    page_count: int
    processing_time_ms: int
    target_size_bytes: Optional[int] = None
    target_status: TargetOutcomeStatus
    status_message: str
    warnings: List[str] = []
    suggestions: List[str] = []
    can_try_stronger: bool = False
    can_try_grayscale: bool = False
    applied_settings: AppliedSettingsSummary
    iterations: List[IterationLogItem] = []
    validation_passed: bool = True
    searchable_text_preserved: bool = True


class JobStatusResponse(BaseModel):
    job_id: str
    file_id: str
    filename: str
    state: JobState
    progress_percent: int = Field(ge=0, le=100)
    stage_message: str
    created_at: float
    updated_at: float
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    analysis: Optional[PDFAnalysisResponse] = None
    result: Optional[CompressionResultPayload] = None


class BatchItemSetting(BaseModel):
    index: int
    mode: Literal["preset", "custom"] = "preset"
    preset: CompressionPreset = CompressionPreset.RECOMMENDED
    target_value: Optional[float] = None
    target_unit: SizeUnit = SizeUnit.KB
    grayscale: bool = False


class BatchJobItemResponse(BaseModel):
    index: int
    filename: str
    job_id: Optional[str] = None
    file_id: Optional[str] = None
    status: Literal["queued", "failed"]
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class BatchSubmitResponse(BaseModel):
    batch_id: str
    total_files: int
    queued_count: int
    failed_count: int
    items: List[BatchJobItemResponse]


class ZipDownloadRequest(BaseModel):
    job_ids: List[str] = Field(..., min_length=1, max_length=50)


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    version: str
    engines: Dict[str, Any]
    active_jobs: int
    stored_items: int
    retention_minutes: int
