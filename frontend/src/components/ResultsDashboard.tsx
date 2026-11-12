import React from 'react';
import {
  Download,
  Eye,
  RotateCcw,
  Zap,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Sliders,
  ImageOff,
  Minimize2,
  Trash2,
  ShieldCheck,
} from 'lucide-react';
import { JobStatusResponse } from '../types/pdf';
import { formatBytes, formatDurationMs } from '../utils/format';
import { getDownloadUrl } from '../services/api';

interface ResultsDashboardProps {
  job: JobStatusResponse;
  onCompressAnother: () => void;
  onTryStronger: () => void;
  onReduceResolution: () => void;
  onConvertGrayscale: () => void;
  onPreviewScroll: () => void;
  onDeleteFiles: () => void;
}

export const ResultsDashboard: React.FC<ResultsDashboardProps> = ({
  job,
  onCompressAnother,
  onTryStronger,
  onReduceResolution,
  onConvertGrayscale,
  onPreviewScroll,
  onDeleteFiles,
}) => {
  const res = job.result;
  if (!res) return null;

  const isFloorReached = res.target_status === 'floor_reached';
  const isAlreadyBelow = res.target_status === 'already_below_target';
  const compressedWidthPct = Math.max(
    4,
    Math.min(100, Math.round((res.compressed_size_bytes / Math.max(1, res.original_size_bytes)) * 100))
  );

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-md">
      {/* Status Banner */}
      <div
        className={`border-b px-6 py-4 ${
          isFloorReached
            ? 'border-amber-200 bg-amber-50/90'
            : 'border-emerald-200 bg-gradient-to-r from-emerald-50/90 to-teal-50/70'
        }`}
      >
        <div className="flex items-start gap-3">
          {isFloorReached ? (
            <AlertTriangle className="mt-0.5 h-6 w-6 shrink-0 text-amber-600" />
          ) : (
            <CheckCircle2 className="mt-0.5 h-6 w-6 shrink-0 text-emerald-600" />
          )}
          <div className="flex-1">
            <h3
              className={`text-base font-bold ${
                isFloorReached ? 'text-amber-950' : 'text-emerald-950'
              }`}
            >
              {isFloorReached
                ? 'Closest Safe Output Achieved'
                : isAlreadyBelow
                ? 'Lossless Structural Optimization Complete'
                : 'PDF Compression Successful'}
            </h3>
            <p
              className={`mt-0.5 text-sm ${
                isFloorReached ? 'text-amber-900' : 'text-emerald-800'
              }`}
            >
              {res.status_message}
            </p>
          </div>
        </div>
      </div>

      <div className="p-6 space-y-6">
        {/* Top 4 KPI Metrics */}
        <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/70 p-4">
            <p className="text-xs font-medium text-slate-500">Original Size</p>
            <p className="mt-1 text-xl font-bold tabular-nums text-slate-800">
              {formatBytes(res.original_size_bytes)}
            </p>
          </div>

          <div className="rounded-xl border border-indigo-200 bg-indigo-50/60 p-4">
            <p className="text-xs font-semibold text-indigo-700">Compressed Size</p>
            <p className="mt-1 text-xl font-extrabold tabular-nums text-indigo-950">
              {formatBytes(res.compressed_size_bytes)}
            </p>
            {res.target_size_bytes && (
              <p className="mt-0.5 text-[11px] text-indigo-700">
                Requested target: {formatBytes(res.target_size_bytes)}
              </p>
            )}
          </div>

          <div className="rounded-xl border border-emerald-200/80 bg-emerald-50/50 p-4">
            <p className="text-xs font-medium text-emerald-700">Space Saved</p>
            <p className="mt-1 text-xl font-bold tabular-nums text-emerald-900">
              {formatBytes(res.space_saved_bytes)}
            </p>
          </div>

          <div className="rounded-xl border border-violet-200/80 bg-violet-50/50 p-4">
            <p className="text-xs font-medium text-violet-700">Compression Ratio</p>
            <p className="mt-1 text-xl font-extrabold tabular-nums text-violet-950">
              {res.compression_ratio_percent.toFixed(2)}%
            </p>
          </div>
        </div>

        {/* Visual Size Comparison Chart */}
        <div className="rounded-xl border border-slate-200/90 bg-slate-50/60 p-4 space-y-3">
          <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-600">
            <span>Visual File Size Comparison</span>
            <span>{res.page_count} Pages Preserved</span>
          </div>

          <div className="space-y-2.5">
            <div>
              <div className="mb-1 flex justify-between text-xs font-medium text-slate-600">
                <span>Original PDF</span>
                <span className="tabular-nums font-semibold">
                  {formatBytes(res.original_size_bytes)} (100%)
                </span>
              </div>
              <div className="h-3.5 w-full overflow-hidden rounded-full bg-slate-300">
                <div className="h-full w-full rounded-full bg-slate-500" />
              </div>
            </div>

            <div>
              <div className="mb-1 flex justify-between text-xs font-medium text-indigo-800">
                <span>Compressed Output</span>
                <span className="tabular-nums font-bold">
                  {formatBytes(res.compressed_size_bytes)} ({compressedWidthPct}%)
                </span>
              </div>
              <div className="h-3.5 w-full overflow-hidden rounded-full bg-indigo-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-emerald-500 transition-all duration-500"
                  style={{ width: `${compressedWidthPct}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Floor Reached Actionable Recovery Panel (Section 4 Requirement) */}
        {isFloorReached && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4 space-y-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-900">
              Available Options to Reduce Size Further without Corrupting PDF
            </p>
            <div className="flex flex-wrap gap-2.5">
              <a
                href={getDownloadUrl(job.job_id)}
                download
                className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-amber-700"
              >
                <Download className="h-3.5 w-3.5" />
                <span>Download Best Available Result ({formatBytes(res.compressed_size_bytes)})</span>
              </a>

              {res.can_try_stronger && (
                <button
                  type="button"
                  onClick={onTryStronger}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
                >
                  <Zap className="h-3.5 w-3.5 text-amber-600" />
                  <span>Try Stronger Compression</span>
                </button>
              )}

              <button
                type="button"
                onClick={onReduceResolution}
                className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
              >
                <Minimize2 className="h-3.5 w-3.5 text-amber-600" />
                <span>Reduce Image Resolution (48 DPI)</span>
              </button>

              {res.can_try_grayscale && (
                <button
                  type="button"
                  onClick={onConvertGrayscale}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-white px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"
                >
                  <ImageOff className="h-3.5 w-3.5 text-amber-600" />
                  <span>Convert Color Images to Grayscale</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* Technical Telemetry & Settings Used */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 text-xs">
          <div className="flex items-center gap-2.5 rounded-xl border border-slate-200/80 p-3">
            <Sliders className="h-4 w-4 shrink-0 text-indigo-600" />
            <div>
              <p className="text-slate-500">Applied Settings</p>
              <p className="font-semibold text-slate-900">
                {res.applied_settings.image_dpi} DPI · JPEG Q{res.applied_settings.jpeg_quality}
                {res.applied_settings.grayscale ? ' · Grayscale' : ''}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 rounded-xl border border-slate-200/80 p-3">
            <Clock className="h-4 w-4 shrink-0 text-indigo-600" />
            <div>
              <p className="text-slate-500">Processing Time</p>
              <p className="font-semibold tabular-nums text-slate-900">
                {formatDurationMs(res.processing_time_ms)} ({res.applied_settings.iterations_run}{' '}
                {res.applied_settings.iterations_run === 1 ? 'pass' : 'passes'})
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2.5 rounded-xl border border-slate-200/80 p-3">
            <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-600" />
            <div>
              <p className="text-slate-500">Integrity & Text</p>
              <p className="font-semibold text-slate-900">
                Validated · {res.searchable_text_preserved ? 'Text Searchable' : 'Raster Verified'}
              </p>
            </div>
          </div>
        </div>

        {/* Iterative Convergence Log (shown when multi-pass custom target ran) */}
        {res.iterations.length > 1 && (
          <div className="overflow-hidden rounded-xl border border-slate-200">
            <div className="bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700">
              Bounded Iterative Target Search Log ({res.iterations.length} Passes)
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-t border-b border-slate-200 bg-slate-50/50 text-slate-500">
                  <tr>
                    <th className="px-4 py-2 font-medium">Pass</th>
                    <th className="px-4 py-2 font-medium">Parameters</th>
                    <th className="px-4 py-2 font-medium">Result Size</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {res.iterations.map((it) => (
                    <tr key={it.iteration} className="hover:bg-slate-50/80">
                      <td className="px-4 py-2 font-semibold tabular-nums text-slate-700">
                        #{it.iteration}
                      </td>
                      <td className="px-4 py-2 text-slate-600">
                        {it.image_dpi} DPI · Q{it.jpeg_quality}
                        {it.grayscale ? ' · Gray' : ''}
                      </td>
                      <td className="px-4 py-2 font-semibold tabular-nums text-slate-900">
                        {formatBytes(it.output_size_bytes)}
                      </td>
                      <td className="px-4 py-2">
                        {it.met_target ? (
                          <span className="inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">
                            ≤ Target
                          </span>
                        ) : (
                          <span className="inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                            Above target
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 tabular-nums text-slate-500">
                        {formatDurationMs(it.duration_ms)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Warnings if any */}
        {res.warnings.length > 0 && !isFloorReached && (
          <div className="space-y-1.5 rounded-xl border border-amber-200 bg-amber-50/70 p-3.5 text-xs text-amber-900">
            {res.warnings.map((w, idx) => (
              <p key={idx} className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-600" />
                <span>{w}</span>
              </p>
            ))}
          </div>
        )}

        {/* Primary Action Bar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <a
              href={getDownloadUrl(job.job_id)}
              download
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-3 text-sm font-bold text-white shadow-md shadow-indigo-600/20 transition hover:from-indigo-700 hover:to-violet-700"
            >
              <Download className="h-4 w-4" />
              <span>Download Compressed PDF</span>
            </a>

            <button
              type="button"
              onClick={onPreviewScroll}
              className="inline-flex items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50/70 px-4 py-3 text-sm font-semibold text-indigo-700 transition hover:bg-indigo-100"
            >
              <Eye className="h-4 w-4" />
              <span>Preview & Compare</span>
            </button>

            {res.can_try_stronger && (
              <button
                type="button"
                onClick={onTryStronger}
                className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
              >
                <Zap className="h-4 w-4 text-amber-500" />
                <span>Try Stronger Compression</span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onCompressAnother}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Compress Another PDF</span>
            </button>

            <button
              type="button"
              onClick={onDeleteFiles}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50/70 px-3.5 py-2.5 text-xs font-semibold text-rose-700 transition hover:bg-rose-100"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span>Delete Files</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
