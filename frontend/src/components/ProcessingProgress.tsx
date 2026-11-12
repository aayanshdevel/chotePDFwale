import React, { useEffect, useState } from 'react';
import { Loader2, StopCircle, CheckCircle2, Sparkles } from 'lucide-react';
import { JobStatusResponse } from '../types/pdf';

interface ProcessingProgressProps {
  job: JobStatusResponse;
  onCancel: () => void;
}

export const ProcessingProgress: React.FC<ProcessingProgressProps> = ({ job, onCancel }) => {
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = window.setInterval(() => {
      setElapsedSec(((Date.now() - start) / 1000));
    }, 100);
    return () => window.clearInterval(id);
  }, [job.job_id]);

  const stages = [
    { key: 'analyzing', label: 'Inspect Structure', threshold: 10 },
    { key: 'compressing', label: 'Hybrid Optimization', threshold: 35 },
    { key: 'validating', label: 'Validate PDF Streams', threshold: 88 },
  ];

  return (
    <div className="rounded-2xl border border-indigo-200 bg-white p-6 shadow-md shadow-indigo-500/5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
            <Loader2 className="h-6 w-6 animate-spin" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-base font-bold text-slate-900">Optimizing PDF Document</h3>
              <span className="rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-semibold tabular-nums text-indigo-700">
                {job.progress_percent}%
              </span>
            </div>
            <p className="mt-0.5 text-sm text-slate-600">{job.stage_message}</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-medium tabular-nums text-slate-500">
            {elapsedSec.toFixed(1)}s elapsed
          </span>
          <button
            type="button"
            onClick={onCancel}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
          >
            <StopCircle className="h-3.5 w-3.5" />
            <span>Cancel</span>
          </button>
        </div>
      </div>

      {/* Main Progress Bar */}
      <div className="mt-5 h-3 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full bg-gradient-to-r from-indigo-600 via-violet-600 to-indigo-500 transition-all duration-300"
          style={{ width: `${Math.max(6, job.progress_percent)}%` }}
        />
      </div>

      {/* Step Milestones */}
      <div className="mt-4 grid grid-cols-3 gap-2 pt-1">
        {stages.map((st) => {
          const reached = job.progress_percent >= st.threshold;
          return (
            <div
              key={st.key}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${
                reached ? 'bg-indigo-50/70 text-indigo-800' : 'bg-slate-50 text-slate-400'
              }`}
            >
              {reached ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-indigo-600" />
              ) : (
                <Sparkles className="h-4 w-4 shrink-0 text-slate-300" />
              )}
              <span className="truncate">{st.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
