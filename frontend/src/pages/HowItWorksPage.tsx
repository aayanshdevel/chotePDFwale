import React from 'react';
import { Search, Sliders, Cpu, CheckCircle2, ArrowRight } from 'lucide-react';

export const HowItWorksPage: React.FC<{ onGoHome: () => void }> = ({ onGoHome }) => {
  const steps = [
    {
      icon: Search,
      title: '1. Deep PDF Structure & DPI Inspection',
      description:
        'Upon upload, PyMuPDF and pikepdf verify the %PDF- magic header, detect encryption, measure the exact rendered DPI of every unique image xref on each page, count embedded fonts and vector paths, and calculate a realistic physics-based minimum file size.',
    },
    {
      icon: Sliders,
      title: '2. Bounded Iterative Target-Size Search',
      description:
        'When you enter a custom target (such as 500 KB or 1.5 MB), our target optimizer maps DPI, JPEG quantization, chroma subsampling, and optional grayscale conversion onto a continuous quality curve. Using log-linear + binary bracketing, it converges in up to 6 passes to find the highest-quality valid PDF below your target.',
    },
    {
      icon: Cpu,
      title: '3. Hybrid 3-Stage Compression Pipeline',
      description:
        'Stage A surgically downsamples oversized raster images via Pillow Lanczos filtering while leaving crisp 1-bit scans and tiny icons untouched. Stage B runs sandboxed Ghostscript (-dSAFER) for inline images, Form XObjects, and duplicate resource folding. Stage C packs QPDF compressed object streams and strips metadata/JavaScript bloat.',
    },
    {
      icon: CheckCircle2,
      title: '4. Strict Validation & Interactive PDF.js Comparison',
      description:
        'Every candidate PDF is verified for cross-reference integrity, exact page count, aspect geometry, sample page raster decoding, and searchable text preservation before you compare Original vs Compressed side by side in PDF.js.',
    },
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
          How Precision PDF Compression Works
        </h1>
        <p className="text-base text-slate-600">
          Genuine multi-engine PDF optimization—never simulated metadata edits or destructive page
          rasterization.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
        {steps.map((s) => {
          const Icon = s.icon;
          return (
            <div
              key={s.title}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-3"
            >
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
                <Icon className="h-5 w-5" />
              </div>
              <h2 className="text-base font-bold text-slate-900">{s.title}</h2>
              <p className="text-sm leading-relaxed text-slate-600">{s.description}</p>
            </div>
          );
        })}
      </div>

      <div className="rounded-2xl border border-indigo-200 bg-indigo-50/60 p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h3 className="text-base font-bold text-indigo-950">
            Why can’t every PDF reach an arbitrarily small KB target?
          </h3>
          <p className="mt-1 text-xs leading-relaxed text-indigo-900/80 max-w-2xl">
            Embedded font glyph tables, vector drawings, and searchable text streams have a lossless
            structural floor. Rather than corrupting your PDF or turning sharp text into unreadable
            blur, OptiPDF Studio stops at the smallest valid output and offers optional grayscale or
            lower-DPI controls.
          </p>
        </div>
        <button
          type="button"
          onClick={onGoHome}
          className="inline-flex shrink-0 items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white hover:bg-indigo-700"
        >
          <span>Try It Now</span>
          <ArrowRight className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};
