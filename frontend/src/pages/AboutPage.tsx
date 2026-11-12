import React from 'react';
import { Layers, Terminal, FileCheck2, Zap } from 'lucide-react';

export const AboutPage: React.FC = () => {
  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
          About OptiPDF Studio
        </h1>
        <p className="text-base text-slate-600">
          Engineered for full transparency, deterministic quality control, and strict document
          safety.
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
        <h2 className="text-lg font-bold text-slate-900">Technology Stack</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 text-sm">
          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
            <div className="flex items-center gap-2 font-bold text-slate-900">
              <Zap className="h-4 w-4 text-indigo-600" />
              <span>Frontend Experience</span>
            </div>
            <ul className="mt-2 space-y-1 text-xs text-slate-600 list-disc list-inside">
              <li>React 18 + TypeScript + Vite</li>
              <li>Tailwind CSS responsive design system</li>
              <li>PDF.js (pdfjs-dist) canvas rendering & before/after diffing</li>
              <li>Real-time job status polling & batch queue management</li>
            </ul>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4">
            <div className="flex items-center gap-2 font-bold text-slate-900">
              <Terminal className="h-4 w-4 text-indigo-600" />
              <span>Backend PDF Engine</span>
            </div>
            <ul className="mt-2 space-y-1 text-xs text-slate-600 list-disc list-inside">
              <li>Python FastAPI + background worker pool</li>
              <li>PyMuPDF (MuPDF) for xref analysis, font subsetting & stream updates</li>
              <li>Ghostscript 10 (-dSAFER) for PDF distiller & color conversion</li>
              <li>pikepdf + QPDF 12 for object streams & JS sanitization</li>
              <li>Pillow + NumPy for Lanczos scaling & progressive JPEG optimization</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
            <FileCheck2 className="h-4 w-4 text-emerald-600" />
            <span>Preserves Document Usability</span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-600">
            Selectable text, table of contents bookmarks, internal/external hyperlinks, and page
            rotations remain intact so compressed documents stay accessible and searchable.
          </p>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 font-bold text-slate-900 text-sm">
            <Layers className="h-4 w-4 text-violet-600" />
            <span>Never Inflates Optimized PDFs</span>
          </div>
          <p className="mt-2 text-xs leading-relaxed text-slate-600">
            Every recompressed image stream and output candidate is byte-checked against the
            original stream—preventing already compact PDFs from accidentally growing larger.
          </p>
        </div>
      </div>
    </div>
  );
};
