import axios from 'axios';
import { SizeUnit } from '../types/pdf';

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${Math.round(bytes)} B`;
  const kb = bytes / 1024;
  if (kb < 1024) {
    return kb >= 100 ? `${Math.round(kb)} KB` : `${kb.toFixed(1)} KB`;
  }
  const mb = kb / 1024;
  return `${mb.toFixed(2)} MB`;
}

export function toBytes(value: number, unit: SizeUnit): number {
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Math.round(value * (unit === 'MB' ? 1024 * 1024 : 1024));
}

export function formatDurationMs(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function profileLabel(profile: string): string {
  switch (profile) {
    case 'scanned':
      return 'Scanned Document';
    case 'image_heavy':
      return 'Image-Heavy PDF';
    case 'mixed':
      return 'Mixed Text & Images';
    case 'vector_rich':
      return 'Vector Graphics';
    case 'text_heavy':
    default:
      return 'Text & Typography';
  }
}

export interface QuickTargetSuggestion {
  label: string;
  value: number;
  unit: SizeUnit;
  bytes: number;
}

export function buildSmartTargetPills(originalBytes: number, minBytes: number): QuickTargetSuggestion[] {
  const candidates: QuickTargetSuggestion[] = [
    { label: '5 MB', value: 5, unit: 'MB', bytes: 5 * 1024 * 1024 },
    { label: '2 MB', value: 2, unit: 'MB', bytes: 2 * 1024 * 1024 },
    { label: '1 MB', value: 1, unit: 'MB', bytes: 1024 * 1024 },
    { label: '500 KB', value: 500, unit: 'KB', bytes: 500 * 1024 },
    { label: '250 KB', value: 250, unit: 'KB', bytes: 250 * 1024 },
    { label: '100 KB', value: 100, unit: 'KB', bytes: 100 * 1024 },
  ];

  const filtered = candidates.filter(
    (c) => c.bytes < originalBytes * 0.92 && c.bytes >= Math.max(40 * 1024, minBytes * 0.65)
  );

  if (filtered.length >= 3) {
    return filtered.slice(0, 5);
  }

  // Generate proportional fallback pills for small or huge PDFs
  const ratios = [0.7, 0.5, 0.35, 0.2];
  return ratios.map((r) => {
    const targetB = Math.max(25 * 1024, Math.round(originalBytes * r));
    if (targetB >= 1024 * 1024) {
      const mbVal = Number((targetB / (1024 * 1024)).toFixed(1));
      return { label: `${mbVal} MB`, value: mbVal, unit: 'MB' as SizeUnit, bytes: mbVal * 1024 * 1024 };
    }
    const kbVal = Math.max(20, Math.round(targetB / 1024 / 10) * 10);
    return { label: `${kbVal} KB`, value: kbVal, unit: 'KB' as SizeUnit, bytes: kbVal * 1024 };
  });
}

export function extractApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const apiMsg = err.response?.data?.error?.message;
    if (typeof apiMsg === 'string' && apiMsg.trim()) {
      return apiMsg;
    }
    if (typeof err.response?.data?.detail === 'string') {
      return err.response.data.detail;
    }
    if (err.code === 'ECONNABORTED') {
      return 'Request timed out while communicating with the PDF compression engine.';
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return 'An unexpected error occurred while processing the PDF.';
}
