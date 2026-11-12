import axios from 'axios';
import {
  BatchItemConfig,
  BatchSubmitResponse,
  CompressionPreset,
  HealthResponse,
  JobStatusResponse,
  PDFAnalysisResponse,
  SizeUnit,
} from '../types/pdf';

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
});

export async function fetchBackendHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/health');
  return data;
}

export async function uploadPdfFile(
  file: File,
  onProgress?: (percent: number) => void
): Promise<PDFAnalysisResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await api.post<PDFAnalysisResponse>('/pdf/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        const pct = Math.min(100, Math.round((evt.loaded * 100) / evt.total));
        onProgress(pct);
      }
    },
  });
  return data;
}

export async function loadBuiltInSamplePdf(): Promise<PDFAnalysisResponse> {
  const { data } = await api.post<PDFAnalysisResponse>('/pdf/sample');
  return data;
}

export async function startPresetCompression(params: {
  file_id: string;
  preset: CompressionPreset;
  grayscale: boolean;
  strip_metadata: boolean;
  subset_fonts: boolean;
}): Promise<JobStatusResponse> {
  const { data } = await api.post<JobStatusResponse>('/pdf/compress', params);
  return data;
}

export async function startCustomTargetCompression(params: {
  file_id: string;
  target_value: number;
  target_unit: SizeUnit;
  intensity: number;
  grayscale: boolean;
  strip_metadata: boolean;
  subset_fonts: boolean;
  force_max_dpi?: number | null;
}): Promise<JobStatusResponse> {
  const { data } = await api.post<JobStatusResponse>('/pdf/compress/custom', params);
  return data;
}

export async function submitBatchCompression(
  items: BatchItemConfig[],
  onUploadProgress?: (pct: number) => void
): Promise<BatchSubmitResponse> {
  const formData = new FormData();
  const settingsPayload = items.map((item, idx) => {
    formData.append('files', item.file);
    return {
      index: idx,
      mode: item.mode,
      preset: item.preset,
      target_value: item.mode === 'custom' ? item.targetValue : null,
      target_unit: item.targetUnit,
      grayscale: item.grayscale,
    };
  });
  formData.append('settings_json', JSON.stringify(settingsPayload));

  const { data } = await api.post<BatchSubmitResponse>('/pdf/compress/batch', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (onUploadProgress && evt.total) {
        onUploadProgress(Math.min(100, Math.round((evt.loaded * 100) / evt.total)));
      }
    },
  });
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const { data } = await api.get<JobStatusResponse>(`/pdf/status/${jobId}`);
  return data;
}

export async function cancelJob(jobId: string): Promise<JobStatusResponse> {
  const { data } = await api.post<JobStatusResponse>(`/pdf/cancel/${jobId}`);
  return data;
}

export async function deletePdfFiles(identifier: string): Promise<void> {
  await api.delete(`/pdf/${identifier}`);
}

export function getDownloadUrl(jobId: string): string {
  return `/api/v1/pdf/download/${encodeURIComponent(jobId)}`;
}

export function getPdfPreviewStreamUrl(
  identifier: string,
  variant: 'original' | 'compressed',
  cacheBuster?: number
): string {
  const ts = cacheBuster ?? Date.now();
  return `/api/v1/pdf/preview/${encodeURIComponent(identifier)}?variant=${variant}&format=pdf&t=${ts}`;
}

export async function downloadBatchZip(jobIds: string[]): Promise<void> {
  const response = await api.post(
    '/pdf/download/zip',
    { job_ids: jobIds },
    { responseType: 'blob' }
  );
  const blobUrl = window.URL.createObjectURL(new Blob([response.data], { type: 'application/zip' }));
  const link = document.createElement('a');
  link.href = blobUrl;
  link.setAttribute('download', 'optipdf-compressed-batch.zip');
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(blobUrl);
}
