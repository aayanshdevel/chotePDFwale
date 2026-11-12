import React, { useEffect, useRef, useState } from 'react';
import {
  UploadCloud,
  Play,
  Download,
  Archive,
  Trash2,
  CheckCircle2,
  AlertCircle,
  Loader2,
  FileText,
} from 'lucide-react';
import {
  BatchItemConfig,
  CompressionPreset,
  SizeUnit,
} from '../types/pdf';
import {
  downloadBatchZip,
  getDownloadUrl,
  getJobStatus,
  submitBatchCompression,
} from '../services/api';
import { extractApiError, formatBytes } from '../utils/format';

export const BatchWorkspace: React.FC = () => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [items, setItems] = useState<BatchItemConfig[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [zipLoading, setZipLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  const addFiles = (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    setGlobalError(null);
    const additions: BatchItemConfig[] = Array.from(fileList).map((f) => ({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
      file: f,
      mode: 'preset',
      preset: 'recommended',
      targetValue: Math.max(100, Math.round((f.size / 1024) * 0.4)),
      targetUnit: 'KB',
      grayscale: false,
    }));
    setItems((prev) => [...prev, ...additions].slice(0, 20));
  };

  // Poll active batch jobs concurrently
  useEffect(() => {
    const activeItems = items.filter(
      (it) =>
        it.jobId &&
        (!it.jobStatus ||
          !['completed', 'failed', 'cancelled'].includes(it.jobStatus.state))
    );
    if (activeItems.length === 0) return;

    let cancelled = false;
    const timer = window.setTimeout(async () => {
      await Promise.all(
        activeItems.map(async (it) => {
          if (!it.jobId) return;
          try {
            const st = await getJobStatus(it.jobId);
            if (cancelled) return;
            setItems((prev) =>
              prev.map((row) => (row.id === it.id ? { ...row, jobStatus: st } : row))
            );
          } catch {
            // Keep polling next tick
          }
        })
      );
    }, 400);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [items]);

  const handleStartBatch = async () => {
    if (items.length === 0) return;
    setIsSubmitting(true);
    setUploadProgress(0);
    setGlobalError(null);

    try {
      const response = await submitBatchCompression(items, setUploadProgress);
      setItems((prev) =>
        prev.map((row, idx) => {
          const match = response.items.find((r) => r.index === idx);
          if (!match) return row;
          if (match.status === 'failed') {
            return {
              ...row,
              localError: match.error_message || 'Failed to validate PDF.',
            };
          }
          return {
            ...row,
            jobId: match.job_id || undefined,
            fileId: match.file_id || undefined,
            localError: undefined,
          };
        })
      );
    } catch (err) {
      setGlobalError(extractApiError(err));
    } finally {
      setIsSubmitting(false);
    }
  };

  const completedJobs = items.filter(
    (it) => it.jobId && it.jobStatus?.state === 'completed'
  );

  const overallProgress = (() => {
    const tracked = items.filter((it) => it.jobId || it.localError);
    if (tracked.length === 0) return 0;
    const sum = tracked.reduce((acc, it) => {
      if (it.localError) return acc + 100;
      return acc + (it.jobStatus?.progress_percent ?? 5);
    }, 0);
    return Math.round(sum / tracked.length);
  })();

  const applyPresetToAll = (preset: CompressionPreset) => {
    setItems((prev) =>
      prev.map((it) => (it.jobId ? it : { ...it, mode: 'preset', preset }))
    );
  };

  const handleDownloadZip = async () => {
    const ids = completedJobs.map((it) => it.jobId!).filter(Boolean);
    if (ids.length === 0) return;
    setZipLoading(true);
    try {
      await downloadBatchZip(ids);
    } catch (err) {
      setGlobalError(extractApiError(err));
    } finally {
      setZipLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Multi-file Dropzone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={(e) => {
          e.preventDefault();
          setIsDragging(false);
        }}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          addFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`cursor-pointer rounded-2xl border-2 border-dashed p-8 text-center transition ${
          isDragging
            ? 'border-indigo-500 bg-indigo-50/70'
            : 'border-slate-300 bg-white hover:border-indigo-400'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = '';
          }}
        />
        <div className="mx-auto flex max-w-lg flex-col items-center">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <UploadCloud className="h-6 w-6" />
          </div>
          <h3 className="text-lg font-bold text-slate-900">
            Drop multiple PDFs for Batch Compression
          </h3>
          <p className="mt-1 text-xs text-slate-600">
            Configure individual presets or custom KB/MB targets per file (up to 20 PDFs per batch).
            Failed files are isolated so valid PDFs always finish cleanly.
          </p>
        </div>
      </div>

      {globalError && (
        <div className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <AlertCircle className="h-5 w-5 shrink-0 text-rose-600" />
          <span>{globalError}</span>
        </div>
      )}

      {items.length > 0 && (
        <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          {/* Batch Toolbar */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-5 py-3.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-bold text-slate-900">
                Batch Queue ({items.length} {items.length === 1 ? 'PDF' : 'PDFs'})
              </span>
              <span className="text-xs text-slate-400">|</span>
              <span className="text-xs text-slate-500">Quick apply preset:</span>
              {(['low', 'recommended', 'high', 'extreme'] as CompressionPreset[]).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => applyPresetToAll(p)}
                  className="rounded-md border border-slate-200 bg-white px-2 py-1 text-[11px] font-semibold capitalize text-slate-700 hover:border-indigo-300 hover:text-indigo-700"
                >
                  {p}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2">
              {completedJobs.length > 0 && (
                <button
                  type="button"
                  disabled={zipLoading}
                  onClick={handleDownloadZip}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-3.5 py-2 text-xs font-bold text-white shadow-sm hover:bg-emerald-700 disabled:opacity-50"
                >
                  <Archive className="h-3.5 w-3.5" />
                  <span>
                    {zipLoading
                      ? 'Building ZIP...'
                      : `Download All as ZIP (${completedJobs.length})`}
                  </span>
                </button>
              )}

              <button
                type="button"
                onClick={() => setItems([])}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 hover:bg-slate-100"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Clear All</span>
              </button>
            </div>
          </div>

          {/* Overall Batch Progress */}
          {(isSubmitting || items.some((i) => i.jobId)) && (
            <div className="border-b border-slate-100 bg-indigo-50/40 px-5 py-3">
              <div className="mb-1 flex justify-between text-xs font-semibold text-indigo-900">
                <span>
                  {isSubmitting
                    ? `Uploading batch (${uploadProgress}%)...`
                    : `Overall Batch Progress (${completedJobs.length}/${items.length} completed)`}
                </span>
                <span className="tabular-nums">
                  {isSubmitting ? uploadProgress : overallProgress}%
                </span>
              </div>
              <div className="h-2 w-full overflow-hidden rounded-full bg-indigo-100">
                <div
                  className="h-full rounded-full bg-indigo-600 transition-all duration-300"
                  style={{ width: `${isSubmitting ? uploadProgress : overallProgress}%` }}
                />
              </div>
            </div>
          )}

          {/* Individual File Rows */}
          <div className="divide-y divide-slate-100">
            {items.map((item) => {
              const st = item.jobStatus;
              const locked = Boolean(item.jobId) || isSubmitting;
              const res = st?.result;

              return (
                <div
                  key={item.id}
                  className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <FileText className="h-4 w-4 shrink-0 text-indigo-600" />
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {item.file.name}
                      </p>
                      <span className="shrink-0 rounded bg-slate-100 px-2 py-0.5 text-xs font-medium tabular-nums text-slate-600">
                        {formatBytes(item.file.size)}
                      </span>
                    </div>

                    {/* Status / Error / Result line */}
                    {item.localError && (
                      <p className="mt-1 flex items-center gap-1 text-xs font-medium text-rose-600">
                        <AlertCircle className="h-3.5 w-3.5" />
                        <span>{item.localError}</span>
                      </p>
                    )}

                    {st && st.state === 'failed' && (
                      <p className="mt-1 flex items-center gap-1 text-xs font-medium text-rose-600">
                        <AlertCircle className="h-3.5 w-3.5" />
                        <span>{st.error_message || 'Compression failed for this PDF.'}</span>
                      </p>
                    )}

                    {st && !['completed', 'failed'].includes(st.state) && (
                      <div className="mt-2 max-w-md">
                        <div className="mb-1 flex justify-between text-[11px] text-indigo-700">
                          <span className="flex items-center gap-1">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            {st.stage_message}
                          </span>
                          <span className="tabular-nums">{st.progress_percent}%</span>
                        </div>
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full bg-indigo-600 transition-all"
                            style={{ width: `${st.progress_percent}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {res && st?.state === 'completed' && (
                      <p className="mt-1 flex items-center gap-1.5 text-xs font-medium text-emerald-700">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        <span>
                          Compressed to{' '}
                          <strong className="tabular-nums">
                            {formatBytes(res.compressed_size_bytes)}
                          </strong>{' '}
                          (-{res.compression_ratio_percent.toFixed(1)}%)
                        </span>
                      </p>
                    )}
                  </div>

                  {/* Per-File Settings or Download Action */}
                  <div className="flex flex-wrap items-center gap-2">
                    {!locked && !item.localError && (
                      <>
                        <select
                          value={item.mode}
                          onChange={(e) =>
                            setItems((prev) =>
                              prev.map((r) =>
                                r.id === item.id
                                  ? { ...r, mode: e.target.value as 'preset' | 'custom' }
                                  : r
                              )
                            )
                          }
                          className="rounded-lg border border-slate-200 bg-slate-50 px-2.5 py-1.5 text-xs font-medium text-slate-700"
                        >
                          <option value="preset">Preset Mode</option>
                          <option value="custom">Custom Target</option>
                        </select>

                        {item.mode === 'preset' ? (
                          <select
                            value={item.preset}
                            onChange={(e) =>
                              setItems((prev) =>
                                prev.map((r) =>
                                  r.id === item.id
                                    ? { ...r, preset: e.target.value as CompressionPreset }
                                    : r
                                )
                              )
                            }
                            className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-800"
                          >
                            <option value="low">Low (200 DPI)</option>
                            <option value="recommended">Recommended (150 DPI)</option>
                            <option value="high">High (100 DPI)</option>
                            <option value="extreme">Extreme (72 DPI)</option>
                          </select>
                        ) : (
                          <div className="flex items-center gap-1">
                            <input
                              type="number"
                              min={10}
                              value={item.targetValue}
                              onChange={(e) =>
                                setItems((prev) =>
                                  prev.map((r) =>
                                    r.id === item.id
                                      ? { ...r, targetValue: Number(e.target.value) || 100 }
                                      : r
                                  )
                                )
                              }
                              className="w-20 rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-bold tabular-nums text-slate-900"
                            />
                            <select
                              value={item.targetUnit}
                              onChange={(e) =>
                                setItems((prev) =>
                                  prev.map((r) =>
                                    r.id === item.id
                                      ? { ...r, targetUnit: e.target.value as SizeUnit }
                                      : r
                                  )
                                )
                              }
                              className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs font-semibold"
                            >
                              <option value="KB">KB</option>
                              <option value="MB">MB</option>
                            </select>
                          </div>
                        )}

                        <button
                          type="button"
                          onClick={() =>
                            setItems((prev) => prev.filter((r) => r.id !== item.id))
                          }
                          className="rounded-lg p-1.5 text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                          aria-label="Remove file"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </>
                    )}

                    {st?.state === 'completed' && item.jobId && (
                      <a
                        href={getDownloadUrl(item.jobId)}
                        download
                        className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
                      >
                        <Download className="h-3.5 w-3.5" />
                        <span>Download</span>
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Start Batch Footer */}
          {items.some((i) => !i.jobId && !i.localError) && (
            <div className="border-t border-slate-200 bg-slate-50 p-4">
              <button
                type="button"
                disabled={isSubmitting}
                onClick={handleStartBatch}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-3.5 text-sm font-bold text-white shadow-md hover:from-indigo-700 hover:to-violet-700 disabled:opacity-50"
              >
                <Play className="h-4 w-4 fill-current" />
                <span>
                  {isSubmitting ? 'Uploading & Queueing Batch...' : 'Start Batch Compression'}
                </span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
