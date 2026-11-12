import React, { useEffect, useRef, useState } from 'react';
import type { PDFDocumentProxy, RenderTask } from 'pdfjs-dist';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  Columns,
  Square,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { loadPdfDocument, renderPdfPageToCanvas } from '../utils/pdfRenderer';
import { formatBytes } from '../utils/format';

interface PdfComparisonViewerProps {
  originalUrl: string;
  compressedUrl?: string | null;
  originalSizeBytes: number;
  compressedSizeBytes?: number | null;
}

const ThumbnailItem: React.FC<{
  pdfDoc: PDFDocumentProxy;
  pageNumber: number;
  active: boolean;
  onSelect: () => void;
}> = ({ pdfDoc, pageNumber, active, onSelect }) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    const taskHolder: { current: RenderTask | null } = { current: null };
    if (canvasRef.current) {
      renderPdfPageToCanvas(pdfDoc, pageNumber, canvasRef.current, 0.2, taskHolder).catch(() => {
        if (!cancelled) {
          // Ignore thumbnail render cancellation
        }
      });
    }
    return () => {
      cancelled = true;
      taskHolder.current?.cancel();
    };
  }, [pdfDoc, pageNumber]);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`group flex flex-col items-center rounded-xl border p-1.5 transition ${
        active
          ? 'border-indigo-600 bg-indigo-50/70 ring-2 ring-indigo-600/20'
          : 'border-slate-200 bg-white hover:border-indigo-300'
      }`}
    >
      <canvas ref={canvasRef} className="rounded border border-slate-100 bg-white shadow-sm" />
      <span
        className={`mt-1 text-[11px] font-semibold tabular-nums ${
          active ? 'text-indigo-700' : 'text-slate-500 group-hover:text-slate-800'
        }`}
      >
        Page {pageNumber}
      </span>
    </button>
  );
};

export const PdfComparisonViewer: React.FC<PdfComparisonViewerProps> = ({
  originalUrl,
  compressedUrl,
  originalSizeBytes,
  compressedSizeBytes,
}) => {
  const [origDoc, setOrigDoc] = useState<PDFDocumentProxy | null>(null);
  const [compDoc, setCompDoc] = useState<PDFDocumentProxy | null>(null);
  const [pageCount, setPageCount] = useState<number>(1);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [zoom, setZoom] = useState<number>(0.85);
  const [viewMode, setViewMode] = useState<'split' | 'compressed' | 'original'>(
    compressedUrl ? 'split' : 'original'
  );
  const [loading, setLoading] = useState<boolean>(true);
  const [renderError, setRenderError] = useState<string | null>(null);

  const origCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const compCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const origTaskRef = useRef<RenderTask | null>(null);
  const compTaskRef = useRef<RenderTask | null>(null);

  useEffect(() => {
    setViewMode(compressedUrl ? 'split' : 'original');
  }, [compressedUrl]);

  // Load PDF documents with PDF.js
  useEffect(() => {
    let active = true;
    setLoading(true);
    setRenderError(null);

    const loadAll = async () => {
      try {
        const loadedOrig = await loadPdfDocument(originalUrl);
        let loadedComp: PDFDocumentProxy | null = null;
        if (compressedUrl) {
          loadedComp = await loadPdfDocument(compressedUrl);
        }
        if (!active) {
          await loadedOrig.destroy();
          if (loadedComp) await loadedComp.destroy();
          return;
        }
        setOrigDoc(loadedOrig);
        setCompDoc(loadedComp);
        setPageCount(loadedOrig.numPages);
        setCurrentPage(1);
      } catch {
        if (active) {
          setRenderError('Failed to load PDF preview in PDF.js.');
        }
      } finally {
        if (active) setLoading(false);
      }
    };

    loadAll();

    return () => {
      active = false;
    };
  }, [originalUrl, compressedUrl]);

  // Render active page onto Original and/or Compressed canvases
  useEffect(() => {
    if (!origDoc) return;

    if ((viewMode === 'split' || viewMode === 'original') && origCanvasRef.current) {
      renderPdfPageToCanvas(origDoc, currentPage, origCanvasRef.current, zoom, origTaskRef).catch(
        () => {}
      );
    }
    if (
      compDoc &&
      (viewMode === 'split' || viewMode === 'compressed') &&
      compCanvasRef.current
    ) {
      renderPdfPageToCanvas(compDoc, currentPage, compCanvasRef.current, zoom, compTaskRef).catch(
        () => {}
      );
    }
  }, [origDoc, compDoc, currentPage, zoom, viewMode]);

  // Cap thumbnail count to first 24 pages for instant responsiveness on 100+ page documents
  const thumbPages = Array.from({ length: Math.min(pageCount, 24) }, (_, idx) => idx + 1);

  const savedRatio =
    compressedSizeBytes && originalSizeBytes > 0
      ? Math.max(0, ((originalSizeBytes - compressedSizeBytes) / originalSizeBytes) * 100)
      : 0;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Viewer Top Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-bold text-slate-900">
            Interactive PDF.js Preview {compressedUrl ? '& Before/After Comparison' : ''}
          </h3>
          {compressedSizeBytes != null && (
            <span className="hidden rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800 sm:inline-block">
              -{savedRatio.toFixed(1)}% Saved
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* View Mode Selector when compressed version exists */}
          {compressedUrl && (
            <div className="inline-flex rounded-lg border border-slate-200 bg-white p-0.5 text-xs font-semibold">
              <button
                type="button"
                onClick={() => setViewMode('split')}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 transition ${
                  viewMode === 'split'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Columns className="h-3.5 w-3.5" />
                <span>Side-by-Side</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('original')}
                className={`rounded-md px-2.5 py-1.5 transition ${
                  viewMode === 'original'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                Original
              </button>
              <button
                type="button"
                onClick={() => setViewMode('compressed')}
                className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 transition ${
                  viewMode === 'compressed'
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                <Square className="h-3 w-3" />
                <span>Compressed</span>
              </button>
            </div>
          )}

          {/* Page Navigation */}
          <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs font-semibold text-slate-700">
            <button
              type="button"
              disabled={currentPage <= 1}
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              className="rounded p-1 hover:bg-slate-100 disabled:opacity-40"
              aria-label="Previous page"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <span className="px-2 tabular-nums">
              Page {currentPage} / {pageCount}
            </span>
            <button
              type="button"
              disabled={currentPage >= pageCount}
              onClick={() => setCurrentPage((p) => Math.min(pageCount, p + 1))}
              className="rounded p-1 hover:bg-slate-100 disabled:opacity-40"
              aria-label="Next page"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          {/* Zoom Controls */}
          <div className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-1.5 py-1 text-xs font-semibold text-slate-700">
            <button
              type="button"
              disabled={zoom <= 0.5}
              onClick={() => setZoom((z) => Math.max(0.5, Number((z - 0.15).toFixed(2))))}
              className="rounded p-1 hover:bg-slate-100 disabled:opacity-40"
              aria-label="Zoom out"
            >
              <ZoomOut className="h-4 w-4" />
            </button>
            <span className="px-2 tabular-nums">{Math.round(zoom * 100)}%</span>
            <button
              type="button"
              disabled={zoom >= 2.1}
              onClick={() => setZoom((z) => Math.min(2.15, Number((z + 0.15).toFixed(2))))}
              className="rounded p-1 hover:bg-slate-100 disabled:opacity-40"
              aria-label="Zoom in"
            >
              <ZoomIn className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="flex h-80 flex-col items-center justify-center gap-2 text-slate-500">
          <Loader2 className="h-7 w-7 animate-spin text-indigo-600" />
          <p className="text-sm font-medium">Rendering PDF pages with PDF.js...</p>
        </div>
      ) : renderError ? (
        <div className="flex h-60 items-center justify-center gap-2 p-6 text-sm text-rose-700">
          <AlertCircle className="h-5 w-5" />
          <span>{renderError}</span>
        </div>
      ) : (
        <div className="flex flex-col lg:flex-row">
          {/* Page Thumbnails Strip */}
          {origDoc && pageCount > 1 && (
            <div className="flex gap-2.5 overflow-x-auto border-b border-slate-200 bg-slate-50/70 p-3 lg:max-h-[640px] lg:w-40 lg:shrink-0 lg:flex-col lg:overflow-y-auto lg:border-b-0 lg:border-r">
              {thumbPages.map((pNum) => (
                <ThumbnailItem
                  key={pNum}
                  pdfDoc={compDoc ?? origDoc}
                  pageNumber={pNum}
                  active={pNum === currentPage}
                  onSelect={() => setCurrentPage(pNum)}
                />
              ))}
              {pageCount > 24 && (
                <p className="py-2 text-center text-[11px] text-slate-400">
                  + {pageCount - 24} more pages (use Prev/Next)
                </p>
              )}
            </div>
          )}

          {/* Canvas Viewport(s) */}
          <div
            className={`grid flex-1 gap-4 overflow-auto bg-slate-100/90 p-4 sm:p-6 max-h-[680px] ${
              viewMode === 'split' && compressedUrl ? 'grid-cols-1 xl:grid-cols-2' : 'grid-cols-1'
            }`}
          >
            {(viewMode === 'split' || viewMode === 'original') && (
              <div className="flex flex-col items-center">
                <div className="mb-2.5 inline-flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-1 text-xs font-semibold text-slate-700 shadow-sm">
                  <span>Original PDF</span>
                  <span className="text-slate-400">•</span>
                  <span className="tabular-nums font-bold text-slate-900">
                    {formatBytes(originalSizeBytes)}
                  </span>
                </div>
                <div className="overflow-auto rounded-lg border border-slate-300 bg-white shadow-md">
                  <canvas ref={origCanvasRef} />
                </div>
              </div>
            )}

            {compressedUrl && (viewMode === 'split' || viewMode === 'compressed') && (
              <div className="flex flex-col items-center">
                <div className="mb-2.5 inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-600 px-3 py-1 text-xs font-semibold text-white shadow-sm">
                  <span>Compressed PDF</span>
                  {compressedSizeBytes != null && (
                    <>
                      <span className="text-indigo-200">•</span>
                      <span className="tabular-nums font-bold">
                        {formatBytes(compressedSizeBytes)}
                      </span>
                    </>
                  )}
                </div>
                <div className="overflow-auto rounded-lg border border-indigo-300 bg-white shadow-md">
                  <canvas ref={compCanvasRef} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
