import React from 'react';
import {
  FileText,
  Layers,
  Maximize2,
  Image as ImageIcon,
  Type,
  Trash2,
  RefreshCw,
  TrendingDown,
} from 'lucide-react';
import { PDFAnalysisResponse } from '../types/pdf';
import { formatBytes, profileLabel } from '../utils/format';

interface FileInfoCardProps {
  analysis: PDFAnalysisResponse;
  onReplaceFile: () => void;
  onDeleteFile: () => void;
  disabled?: boolean;
}

export const FileInfoCard: React.FC<FileInfoCardProps> = ({
  analysis,
  onReplaceFile,
  onDeleteFile,
  disabled = false,
}) => {
  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm">
      <div className="border-b border-slate-100 bg-slate-50/70 px-5 py-3.5 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-600">
            Document Inspection Complete
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            disabled={disabled}
            onClick={onReplaceFile}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>Change PDF</span>
          </button>
          <button
            type="button"
            disabled={disabled}
            onClick={onDeleteFile}
            title="Immediately delete uploaded PDF from server"
            className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 bg-rose-50/70 px-2.5 py-1 text-xs font-medium text-rose-700 transition hover:bg-rose-100 disabled:opacity-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Delete File</span>
          </button>
        </div>
      </div>

      <div className="p-5 sm:p-6">
        <div className="flex flex-col gap-6 sm:flex-row">
          {/* Page 1 Preview Thumbnail */}
          <div className="mx-auto flex w-36 shrink-0 flex-col items-center sm:mx-0">
            <div className="relative aspect-[1/1.414] w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-100 shadow-inner">
              {analysis.thumbnail_data_url ? (
                <img
                  src={analysis.thumbnail_data_url}
                  alt={`Preview of ${analysis.filename}`}
                  className="h-full w-full object-contain bg-white"
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-slate-400">
                  <FileText className="h-10 w-10" />
                  <span className="mt-1 text-[11px]">PDF Preview</span>
                </div>
              )}
              <span className="absolute bottom-1.5 right-1.5 rounded bg-slate-900/75 px-1.5 py-0.5 text-[10px] font-medium text-white">
                {analysis.pdf_version}
              </span>
            </div>
          </div>

          {/* Metadata & Metrics */}
          <div className="min-w-0 flex-1 space-y-4">
            <div>
              <h3
                className="truncate text-lg font-bold text-slate-900"
                title={analysis.filename}
              >
                {analysis.filename}
              </h3>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center rounded-md bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold text-indigo-700 ring-1 ring-inset ring-indigo-600/20">
                  {profileLabel(analysis.content_profile)}
                </span>
                {analysis.has_searchable_text && (
                  <span className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                    <Type className="h-3 w-3" />
                    Searchable Text
                  </span>
                )}
                {analysis.has_vector_graphics && (
                  <span className="inline-flex items-center rounded-md bg-violet-50 px-2 py-0.5 text-xs font-medium text-violet-700 ring-1 ring-inset ring-violet-600/20">
                    Vector Graphics
                  </span>
                )}
              </div>
            </div>

            {/* Key Info Grid */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
                  Original Size
                </p>
                <p className="mt-0.5 text-base font-bold tabular-nums text-slate-900">
                  {formatBytes(analysis.original_size_bytes)}
                </p>
              </div>

              <div className="rounded-xl border border-slate-100 bg-slate-50/80 p-3">
                <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                  <Layers className="h-3 w-3" /> Pages
                </p>
                <p className="mt-0.5 text-base font-bold tabular-nums text-slate-900">
                  {analysis.page_count} {analysis.page_count === 1 ? 'page' : 'pages'}
                </p>
              </div>

              <div className="col-span-2 rounded-xl border border-slate-100 bg-slate-50/80 p-3 sm:col-span-1">
                <p className="flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                  <ImageIcon className="h-3 w-3" /> Embedded Images
                </p>
                <p className="mt-0.5 text-sm font-bold tabular-nums text-slate-900">
                  {analysis.images.unique_images} ({analysis.images.image_share_percent}% of size)
                </p>
              </div>
            </div>

            {/* Page Dimensions & Compression Potential */}
            <div className="flex flex-col justify-between gap-3 rounded-xl border border-indigo-100 bg-indigo-50/50 p-3.5 sm:flex-row sm:items-center">
              <div className="flex items-start gap-2.5">
                <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
                <div className="text-xs text-slate-700">
                  <span className="font-semibold text-slate-900">
                    Estimated Compression Potential:{' '}
                  </span>
                  {analysis.estimated_reduction_percent_high > 3 ? (
                    <>
                      Up to{' '}
                      <span className="font-bold text-indigo-700">
                        {analysis.estimated_reduction_percent_high}% smaller
                      </span>{' '}
                      (Recommended floor ~{formatBytes(analysis.recommended_min_size_bytes)} · Max
                      floor ~{formatBytes(analysis.estimated_min_size_bytes)})
                    </>
                  ) : (
                    <span>Already compact; structural cleanup available</span>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-1 text-[11px] text-slate-500 shrink-0">
                <Maximize2 className="h-3 w-3" />
                <span>{analysis.page_dimensions}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
