export type CompressionPreset = 'low' | 'recommended' | 'high' | 'extreme';
export type SizeUnit = 'KB' | 'MB';

export type JobState =
  | 'uploaded'
  | 'queued'
  | 'analyzing'
  | 'compressing'
  | 'validating'
  | 'completed'
  | 'failed'
  | 'cancelled';

export type TargetOutcomeStatus =
  | 'met_target'
  | 'floor_reached'
  | 'already_below_target'
  | 'preset_applied';

export interface ImageAnalysisSummary {
  unique_images: number;
  image_bytes_estimate: number;
  image_share_percent: number;
  max_effective_dpi: number;
  median_effective_dpi: number;
  has_color_images: boolean;
  has_alpha_images: boolean;
}

export interface FontAnalysisSummary {
  total_fonts: number;
  embedded_fonts: number;
  subset_fonts: number;
}

export interface PDFAnalysisResponse {
  file_id: string;
  filename: string;
  original_size_bytes: number;
  original_size_formatted: string;
  page_count: number;
  pdf_version: string;
  page_dimensions: string;
  width_pt: number;
  height_pt: number;
  content_profile: 'text_heavy' | 'scanned' | 'image_heavy' | 'vector_rich' | 'mixed';
  has_searchable_text: boolean;
  has_vector_graphics: boolean;
  had_javascript_stripped: boolean;
  images: ImageAnalysisSummary;
  fonts: FontAnalysisSummary;
  estimated_min_size_bytes: number;
  recommended_min_size_bytes: number;
  estimated_reduction_percent_low: number;
  estimated_reduction_percent_high: number;
  thumbnail_data_url?: string | null;
  expires_in_minutes: number;
}

export interface IterationLogItem {
  iteration: number;
  image_dpi: number;
  jpeg_quality: number;
  grayscale: boolean;
  output_size_bytes: number;
  met_target: boolean;
  duration_ms: number;
  note: string;
}

export interface AppliedSettingsSummary {
  mode: 'preset' | 'custom';
  preset_name?: string | null;
  image_dpi: number;
  jpeg_quality: number;
  grayscale: boolean;
  strip_metadata: boolean;
  subset_fonts: boolean;
  used_ghostscript: boolean;
  used_qpdf_objstms: boolean;
  iterations_run: number;
}

export interface CompressionResultPayload {
  original_size_bytes: number;
  compressed_size_bytes: number;
  space_saved_bytes: number;
  compression_ratio_percent: number;
  page_count: number;
  processing_time_ms: number;
  target_size_bytes?: number | null;
  target_status: TargetOutcomeStatus;
  status_message: string;
  warnings: string[];
  suggestions: string[];
  can_try_stronger: boolean;
  can_try_grayscale: boolean;
  applied_settings: AppliedSettingsSummary;
  iterations: IterationLogItem[];
  validation_passed: boolean;
  searchable_text_preserved: boolean;
}

export interface JobStatusResponse {
  job_id: string;
  file_id: string;
  filename: string;
  state: JobState;
  progress_percent: number;
  stage_message: string;
  created_at: number;
  updated_at: number;
  error_code?: string | null;
  error_message?: string | null;
  analysis?: PDFAnalysisResponse | null;
  result?: CompressionResultPayload | null;
}

export interface BatchItemConfig {
  id: string;
  file: File;
  mode: 'preset' | 'custom';
  preset: CompressionPreset;
  targetValue: number;
  targetUnit: SizeUnit;
  grayscale: boolean;
  jobId?: string;
  fileId?: string;
  jobStatus?: JobStatusResponse;
  localError?: string;
}

export interface BatchJobItemResponse {
  index: number;
  filename: string;
  job_id?: string | null;
  file_id?: string | null;
  status: 'queued' | 'failed';
  error_code?: string | null;
  error_message?: string | null;
}

export interface BatchSubmitResponse {
  batch_id: string;
  total_files: number;
  queued_count: number;
  failed_count: number;
  items: BatchJobItemResponse[];
}

export interface HealthResponse {
  status: 'healthy' | 'degraded';
  version: string;
  engines: Record<string, string>;
  active_jobs: number;
  stored_items: number;
  retention_minutes: number;
}
