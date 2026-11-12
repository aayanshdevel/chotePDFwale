import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Sparkles, Lock, AlertCircle, CheckCircle2 } from 'lucide-react';

interface UploadZoneProps {
  onSelectFile: (file: File) => void;
  onLoadSample: () => void;
  isUploading: boolean;
  uploadProgress: number;
  error: string | null;
  maxUploadMb?: number;
}

export const UploadZone: React.FC<UploadZoneProps> = ({
  onSelectFile,
  onLoadSample,
  isUploading,
  uploadProgress,
  error,
  maxUploadMb = 100,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    onSelectFile(files[0]);
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isUploading) setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (isUploading) return;
    handleFiles(e.dataTransfer.files);
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isUploading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !isUploading) {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={`group relative cursor-pointer overflow-hidden rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-200 sm:p-12 ${
          isDragging
            ? 'border-indigo-500 bg-indigo-50/70 shadow-lg shadow-indigo-500/10'
            : 'border-slate-300 bg-white hover:border-indigo-400 hover:bg-slate-50/60 shadow-sm'
        } ${isUploading ? 'pointer-events-none opacity-90' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files);
            e.target.value = '';
          }}
        />

        <div className="mx-auto flex max-w-lg flex-col items-center">
          <div
            className={`mb-5 flex h-16 w-16 items-center justify-center rounded-2xl transition-transform duration-200 ${
              isDragging
                ? 'scale-110 bg-indigo-600 text-white'
                : 'bg-indigo-50 text-indigo-600 group-hover:scale-105 group-hover:bg-indigo-100'
            }`}
          >
            <UploadCloud className="h-8 w-8" />
          </div>

          <h2 className="text-xl font-bold tracking-tight text-slate-900 sm:text-2xl">
            {isDragging ? 'Drop your PDF here to inspect' : 'Drag & drop your PDF file here'}
          </h2>
          <p className="mt-2 text-sm text-slate-600">
            Compress to an exact custom KB/MB target or choose an intelligent quality preset.
          </p>

          {/* Action Buttons */}
          <div
            className="mt-6 flex flex-wrap items-center justify-center gap-3"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              disabled={isUploading}
              onClick={() => inputRef.current?.click()}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-3 text-sm font-semibold text-white shadow-md shadow-indigo-600/20 transition hover:from-indigo-700 hover:to-violet-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-60"
            >
              <FileText className="h-4 w-4" />
              <span>Upload PDF</span>
            </button>

            <button
              type="button"
              disabled={isUploading}
              onClick={onLoadSample}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-medium text-slate-700 transition hover:border-indigo-300 hover:bg-indigo-50/60 hover:text-indigo-700 disabled:opacity-60"
            >
              <Sparkles className="h-4 w-4 text-indigo-600" />
              <span>Try 10.2 MB Sample PDF</span>
            </button>
          </div>

          {/* Supported format & limit indicators */}
          <div className="mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs text-slate-500">
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              Format: PDF 1.0 – 2.0 (.pdf)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
              Max file size: {maxUploadMb} MB (up to 1,000 pages)
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Lock className="h-3.5 w-3.5 text-indigo-600" />
              Auto-deleted after 30 min
            </span>
          </div>

          {/* Upload Progress Bar */}
          {isUploading && (
            <div className="mt-6 w-full max-w-md">
              <div className="mb-1.5 flex items-center justify-between text-xs font-medium text-indigo-700">
                <span>Uploading & analyzing PDF structure...</span>
                <span className="tabular-nums">{uploadProgress}%</span>
              </div>
              <div className="h-2.5 w-full overflow-hidden rounded-full bg-indigo-100">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 transition-all duration-200"
                  style={{ width: `${Math.max(8, uploadProgress)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
          <div>
            <p className="font-semibold">Unable to load PDF</p>
            <p className="mt-0.5 text-rose-700">{error}</p>
          </div>
        </div>
      )}
    </div>
  );
};
