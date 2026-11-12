import React, { useMemo, useRef, useState } from 'react';
import { FileText, Layers, Shield, AlertCircle, CheckCircle2 } from 'lucide-react';
import { UploadZone } from '../components/UploadZone';
import { FileInfoCard } from '../components/FileInfoCard';
import { CompressionControls, StartCompressionArgs } from '../components/CompressionControls';
import { ProcessingProgress } from '../components/ProcessingProgress';
import { ResultsDashboard } from '../components/ResultsDashboard';
import { PdfComparisonViewer } from '../components/PdfComparisonViewer';
import { BatchWorkspace } from '../components/BatchWorkspace';
import { useJobPoller } from '../hooks/useJobPoller';
import {
  cancelJob,
  deletePdfFiles,
  getPdfPreviewStreamUrl,
  loadBuiltInSamplePdf,
  startCustomTargetCompression,
  startPresetCompression,
  uploadPdfFile,
} from '../services/api';
import { JobStatusResponse, PDFAnalysisResponse } from '../types/pdf';
import { extractApiError } from '../utils/format';

export const HomePage: React.FC = () => {
  const [workspaceMode, setWorkspaceMode] = useState<'single' | 'batch'>('single');

  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [analysis, setAnalysis] = useState<PDFAnalysisResponse | null>(null);
  const [lastArgs, setLastArgs] = useState<StartCompressionArgs | null>(null);
  const [job, setJob] = useState<JobStatusResponse | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);

  const previewSectionRef = useRef<HTMLDivElement | null>(null);

  const isJobRunning = Boolean(
    job && !['completed', 'failed', 'cancelled'].includes(job.state)
  );

  useJobPoller(
    job?.job_id ?? null,
    isJobRunning,
    (updated) => {
      setJob(updated);
    },
    (err) => {
      setUploadError(extractApiError(err));
    }
  );

  const handleSelectFile = async (file: File) => {
    setIsUploading(true);
    setUploadProgress(5);
    setUploadError(null);
    setActionNotice(null);
    setJob(null);

    try {
      const result = await uploadPdfFile(file, setUploadProgress);
      setAnalysis(result);
    } catch (err) {
      setUploadError(extractApiError(err));
    } finally {
      setIsUploading(false);
    }
  };

  const handleLoadSample = async () => {
    setIsUploading(true);
    setUploadProgress(40);
    setUploadError(null);
    setActionNotice(null);
    setJob(null);

    try {
      const result = await loadBuiltInSamplePdf();
      setUploadProgress(100);
      setAnalysis(result);
    } catch (err) {
      setUploadError(extractApiError(err));
    } finally {
      setIsUploading(false);
    }
  };

  const handleStartCompression = async (args: StartCompressionArgs) => {
    if (!analysis) return;
    setUploadError(null);
    setActionNotice(null);
    setLastArgs(args);

    try {
      const createdJob =
        args.mode === 'custom'
          ? await startCustomTargetCompression({
              file_id: analysis.file_id,
              target_value: args.targetValue,
              target_unit: args.targetUnit,
              intensity: args.intensity,
              grayscale: args.grayscale,
              strip_metadata: args.stripMetadata,
              subset_fonts: args.subsetFonts,
              force_max_dpi: args.forceMaxDpi ?? null,
            })
          : await startPresetCompression({
              file_id: analysis.file_id,
              preset: args.preset,
              grayscale: args.grayscale,
              strip_metadata: args.stripMetadata,
              subset_fonts: args.subsetFonts,
            });
      setJob(createdJob);
    } catch (err) {
      setUploadError(extractApiError(err));
    }
  };

  const handleCancelJob = async () => {
    if (!job) return;
    try {
      const cancelled = await cancelJob(job.job_id);
      setJob(cancelled);
    } catch (err) {
      setUploadError(extractApiError(err));
    }
  };

  const handleDeleteCurrentFiles = async () => {
    const idToDelete = job?.job_id ?? analysis?.file_id;
    if (!idToDelete) return;
    try {
      await deletePdfFiles(idToDelete);
      if (job?.job_id && analysis?.file_id && job.job_id !== analysis.file_id) {
        await deletePdfFiles(analysis.file_id).catch(() => {});
      }
      setJob(null);
      setAnalysis(null);
      setLastArgs(null);
      setActionNotice(
        'Your uploaded and compressed PDF files have been permanently deleted from temporary storage.'
      );
    } catch (err) {
      setUploadError(extractApiError(err));
    }
  };

  const handleResetForNewFile = () => {
    setJob(null);
    setAnalysis(null);
    setLastArgs(null);
    setUploadError(null);
  };

  const handleTryStronger = () => {
    if (!analysis) return;
    if (lastArgs?.mode === 'custom') {
      handleStartCompression({
        ...lastArgs,
        intensity: 100,
        forceMaxDpi: 48,
      });
    } else {
      const nextPreset =
        lastArgs?.preset === 'low'
          ? 'recommended'
          : lastArgs?.preset === 'recommended'
          ? 'high'
          : 'extreme';
      handleStartCompression({
        mode: 'preset',
        preset: nextPreset,
        targetValue: 500,
        targetUnit: 'KB',
        intensity: 85,
        grayscale: lastArgs?.grayscale ?? false,
        stripMetadata: true,
        subsetFonts: true,
      });
    }
  };

  const handleReduceResolution = () => {
    if (!analysis) return;
    handleStartCompression({
      mode: 'custom',
      preset: 'extreme',
      targetValue: lastArgs?.targetValue ?? 500,
      targetUnit: lastArgs?.targetUnit ?? 'KB',
      intensity: 100,
      grayscale: lastArgs?.grayscale ?? false,
      stripMetadata: true,
      subsetFonts: true,
      forceMaxDpi: 48,
    });
  };

  const handleConvertGrayscale = () => {
    if (!analysis) return;
    handleStartCompression({
      mode: lastArgs?.mode ?? 'custom',
      preset: lastArgs?.preset ?? 'extreme',
      targetValue: lastArgs?.targetValue ?? 500,
      targetUnit: lastArgs?.targetUnit ?? 'KB',
      intensity: 95,
      grayscale: true,
      stripMetadata: true,
      subsetFonts: true,
      forceMaxDpi: lastArgs?.forceMaxDpi ?? 60,
    });
  };

  const previewUrls = useMemo(() => {
    if (!analysis) return null;
    const orig = getPdfPreviewStreamUrl(analysis.file_id, 'original', 1);
    const comp =
      job?.state === 'completed'
        ? getPdfPreviewStreamUrl(job.job_id, 'compressed', job.updated_at)
        : null;
    return { orig, comp };
  }, [analysis, job?.job_id, job?.state, job?.updated_at]);

  return (
    <div className="space-y-8">
      {/* Hero Section */}
      <div className="text-center max-w-3xl mx-auto space-y-3">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50/80 px-3.5 py-1 text-xs font-semibold text-indigo-700">
          <span>Hybrid PyMuPDF · Ghostscript 10 · QPDF 12 · Pillow Pipeline</span>
        </div>
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
          Compress PDFs to Your{' '}
          <span className="bg-gradient-to-r from-indigo-600 to-violet-600 bg-clip-text text-transparent">
            Exact Target Size
          </span>
        </h1>
        <p className="text-sm text-slate-600 sm:text-base">
          Specify an exact KB or MB ceiling or pick a balanced preset. Searchable text, links, and
          vector graphics stay crisp while embedded images and object streams are intelligently
          optimized.
        </p>

        {/* Single vs Batch Mode Switcher */}
        <div className="pt-2 flex justify-center">
          <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
            <button
              type="button"
              onClick={() => setWorkspaceMode('single')}
              className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition sm:text-sm ${
                workspaceMode === 'single'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <FileText className="h-4 w-4" />
              <span>Single PDF Target Studio</span>
            </button>
            <button
              type="button"
              onClick={() => setWorkspaceMode('batch')}
              className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-bold transition sm:text-sm ${
                workspaceMode === 'batch'
                  ? 'bg-indigo-600 text-white shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Layers className="h-4 w-4" />
              <span>Batch PDF Compressor</span>
            </button>
          </div>
        </div>
      </div>

      {actionNotice && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-900">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
            <span>{actionNotice}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionNotice(null)}
            className="text-xs font-semibold text-emerald-700 hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      {workspaceMode === 'batch' ? (
        <BatchWorkspace />
      ) : (
        <div className="space-y-6">
          {!analysis ? (
            <UploadZone
              onSelectFile={handleSelectFile}
              onLoadSample={handleLoadSample}
              isUploading={isUploading}
              uploadProgress={uploadProgress}
              error={uploadError}
            />
          ) : (
            <div className="space-y-6">
              {/* File Information Panel */}
              <FileInfoCard
                analysis={analysis}
                onReplaceFile={handleResetForNewFile}
                onDeleteFile={handleDeleteCurrentFiles}
                disabled={isJobRunning}
              />

              {/* Error Banner if job failed */}
              {(uploadError || job?.state === 'failed') && (
                <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
                  <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
                  <div>
                    <p className="font-semibold">Compression Error</p>
                    <p className="mt-0.5 text-rose-700">
                      {uploadError || job?.error_message || 'Compression failed.'}
                    </p>
                  </div>
                </div>
              )}

              {/* Active Progress OR Results OR Controls */}
              {isJobRunning && job ? (
                <ProcessingProgress job={job} onCancel={handleCancelJob} />
              ) : job?.state === 'completed' ? (
                <ResultsDashboard
                  job={job}
                  onCompressAnother={handleResetForNewFile}
                  onTryStronger={handleTryStronger}
                  onReduceResolution={handleReduceResolution}
                  onConvertGrayscale={handleConvertGrayscale}
                  onPreviewScroll={() =>
                    previewSectionRef.current?.scrollIntoView({ behavior: 'smooth' })
                  }
                  onDeleteFiles={handleDeleteCurrentFiles}
                />
              ) : null}

              {/* Keep Compression Controls accessible when not actively running so user can tweak target anytime */}
              {!isJobRunning && (
                <CompressionControls
                  analysis={analysis}
                  onStart={handleStartCompression}
                  disabled={isJobRunning}
                />
              )}

              {/* Interactive PDF.js Preview & Side-by-Side Comparison */}
              {previewUrls && (
                <div ref={previewSectionRef}>
                  <PdfComparisonViewer
                    originalUrl={previewUrls.orig}
                    compressedUrl={previewUrls.comp}
                    originalSizeBytes={analysis.original_size_bytes}
                    compressedSizeBytes={
                      job?.state === 'completed' ? job.result?.compressed_size_bytes : null
                    }
                  />
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Privacy Guarantee Footer Banner */}
      <div className="flex flex-col items-start justify-between gap-4 rounded-2xl border border-slate-200/90 bg-white p-5 sm:flex-row sm:items-center">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
            <Shield className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-900">
              100% Local Server Processing & Automatic Privacy Cleanup
            </h3>
            <p className="mt-0.5 text-xs text-slate-600">
              Uploaded PDFs are never sent to external third-party APIs, never logged, and
              embedded PDF JavaScript is stripped. Temporary files are automatically purged after 30
              minutes—or immediately when you click <strong>Delete Files</strong>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
