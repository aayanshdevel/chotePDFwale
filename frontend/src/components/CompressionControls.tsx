import React, { useEffect, useMemo, useState } from 'react';
import {
  Target,
  Sliders,
  Play,
  AlertTriangle,
  Info,
  Sparkles,
  Check,
  Gauge,
} from 'lucide-react';
import { CompressionPreset, PDFAnalysisResponse, SizeUnit } from '../types/pdf';
import { buildSmartTargetPills, formatBytes, toBytes } from '../utils/format';

export interface StartCompressionArgs {
  mode: 'custom' | 'preset';
  preset: CompressionPreset;
  targetValue: number;
  targetUnit: SizeUnit;
  intensity: number;
  grayscale: boolean;
  stripMetadata: boolean;
  subsetFonts: boolean;
  forceMaxDpi?: number | null;
}

interface CompressionControlsProps {
  analysis: PDFAnalysisResponse;
  onStart: (args: StartCompressionArgs) => void;
  disabled?: boolean;
}

const PRESET_CARDS: {
  id: CompressionPreset;
  title: string;
  badge: string;
  dpi: number;
  quality: number;
  description: string;
}[] = [
  {
    id: 'low',
    title: 'Low Compression',
    badge: 'Max Quality',
    dpi: 200,
    quality: 85,
    description: 'Maximum visual quality preservation, minimal image downsampling, structural & metadata cleanup.',
  },
  {
    id: 'recommended',
    title: 'Recommended',
    badge: 'Best Balance',
    dpi: 150,
    quality: 75,
    description: 'Balanced image clarity and substantial file size savings with smart JPEG & object-stream optimization.',
  },
  {
    id: 'high',
    title: 'High Compression',
    badge: 'Strong Reduction',
    dpi: 100,
    quality: 52,
    description: 'Aggressive image resolution reduction and chroma subsampling for strict portal upload limits.',
  },
  {
    id: 'extreme',
    title: 'Extreme Compression',
    badge: 'Minimum Size',
    dpi: 72,
    quality: 35,
    description: 'Maximum practical size reduction (72 DPI, aggressive recompression, optional grayscale conversion).',
  },
];

export const CompressionControls: React.FC<CompressionControlsProps> = ({
  analysis,
  onStart,
  disabled = false,
}) => {
  const [mode, setMode] = useState<'custom' | 'preset'>('custom');
  const [preset, setPreset] = useState<CompressionPreset>('recommended');

  const smartPills = useMemo(
    () => buildSmartTargetPills(analysis.original_size_bytes, analysis.estimated_min_size_bytes),
    [analysis.original_size_bytes, analysis.estimated_min_size_bytes]
  );

  const [targetValue, setTargetValue] = useState<string>('500');
  const [targetUnit, setTargetUnit] = useState<SizeUnit>('KB');
  const [intensity, setIntensity] = useState<number>(65);
  const [grayscale, setGrayscale] = useState<boolean>(false);
  const [stripMetadata, setStripMetadata] = useState<boolean>(true);
  const [subsetFonts, setSubsetFonts] = useState<boolean>(true);

  // Initialize sensible default custom target whenever a new PDF is uploaded
  useEffect(() => {
    const idealBytes = Math.max(
      analysis.recommended_min_size_bytes,
      Math.round(analysis.original_size_bytes * 0.35)
    );
    const clampedBytes = Math.min(Math.round(analysis.original_size_bytes * 0.7), idealBytes);
    if (clampedBytes >= 1024 * 1024) {
      setTargetUnit('MB');
      setTargetValue((clampedBytes / (1024 * 1024)).toFixed(1));
    } else {
      setTargetUnit('KB');
      setTargetValue(String(Math.max(25, Math.round(clampedBytes / 1024 / 10) * 10)));
    }
  }, [analysis.file_id, analysis.original_size_bytes, analysis.recommended_min_size_bytes]);

  const numericTarget = parseFloat(targetValue) || 0;
  const targetBytes = toBytes(numericTarget, targetUnit);

  const handleUnitChange = (nextUnit: SizeUnit) => {
    if (nextUnit === targetUnit) return;
    const val = parseFloat(targetValue);
    if (Number.isFinite(val) && val > 0) {
      if (nextUnit === 'MB') {
        setTargetValue(Math.max(0.05, Number((val / 1024).toFixed(2))).toString());
      } else {
        setTargetValue(Math.max(10, Math.round(val * 1024)).toString());
      }
    }
    setTargetUnit(nextUnit);
  };

  // Compute live estimated output size for custom mode
  const effectiveFloor = grayscale
    ? Math.round(analysis.estimated_min_size_bytes * 0.78)
    : analysis.estimated_min_size_bytes;

  const estimatedCustomOutputBytes = useMemo(() => {
    if (targetBytes <= 0) return analysis.recommended_min_size_bytes;
    if (targetBytes >= analysis.original_size_bytes) {
      return Math.round(analysis.original_size_bytes * 0.96);
    }
    if (targetBytes < effectiveFloor) {
      return effectiveFloor;
    }
    return Math.round(targetBytes * 0.94);
  }, [targetBytes, analysis.original_size_bytes, analysis.recommended_min_size_bytes, effectiveFloor]);

  const isTargetAboveOriginal = targetBytes >= analysis.original_size_bytes;
  const isTargetBelowFloor = targetBytes > 0 && targetBytes < effectiveFloor;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'custom' && numericTarget <= 0) return;
    onStart({
      mode,
      preset,
      targetValue: numericTarget,
      targetUnit,
      intensity,
      grayscale,
      stripMetadata,
      subsetFonts,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm"
    >
      {/* Mode Segmented Header */}
      <div className="border-b border-slate-200 bg-slate-50/80 p-2 sm:p-3">
        <div className="grid grid-cols-2 gap-2 rounded-xl bg-slate-200/70 p-1">
          <button
            type="button"
            onClick={() => setMode('custom')}
            className={`flex items-center justify-center gap-2 rounded-lg py-2.5 px-3 text-sm font-semibold transition-all ${
              mode === 'custom'
                ? 'bg-white text-indigo-700 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Target className="h-4 w-4" />
            <span>Custom Target Size</span>
            <span className="hidden rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-indigo-700 sm:inline">
              Primary
            </span>
          </button>

          <button
            type="button"
            onClick={() => setMode('preset')}
            className={`flex items-center justify-center gap-2 rounded-lg py-2.5 px-3 text-sm font-semibold transition-all ${
              mode === 'preset'
                ? 'bg-white text-indigo-700 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sliders className="h-4 w-4" />
            <span>Predefined Presets</span>
          </button>
        </div>
      </div>

      <div className="p-5 sm:p-6 space-y-6">
        {mode === 'custom' ? (
          /* ===================== CUSTOM TARGET SIZE MODE ===================== */
          <div className="space-y-5">
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label
                  htmlFor="target-size-input"
                  className="text-sm font-bold text-slate-900"
                >
                  Desired Maximum Output Size
                </label>
                <span className="text-xs text-slate-500">
                  Original: <strong className="text-slate-800">{formatBytes(analysis.original_size_bytes)}</strong>
                </span>
              </div>

              {/* Quick Target Suggestion Pills */}
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-slate-500 mr-1">Quick targets:</span>
                {smartPills.map((pill) => {
                  const active =
                    Math.abs(targetBytes - pill.bytes) < 2048;
                  return (
                    <button
                      key={pill.label}
                      type="button"
                      onClick={() => {
                        setTargetUnit(pill.unit);
                        setTargetValue(String(pill.value));
                      }}
                      className={`rounded-lg border px-3 py-1.5 text-xs font-semibold tabular-nums transition ${
                        active
                          ? 'border-indigo-600 bg-indigo-600 text-white shadow-sm'
                          : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-indigo-300 hover:bg-indigo-50'
                      }`}
                    >
                      {pill.label}
                    </button>
                  );
                })}
              </div>

              {/* Numeric Input + KB/MB Switcher */}
              <div className="mt-3 flex items-stretch gap-2">
                <div className="relative flex-1">
                  <input
                    id="target-size-input"
                    type="number"
                    step={targetUnit === 'MB' ? '0.05' : '10'}
                    min="1"
                    max="500000"
                    required
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    className="w-full rounded-xl border border-slate-300 bg-white px-4 py-3 text-lg font-bold tabular-nums text-slate-900 shadow-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    placeholder={targetUnit === 'KB' ? '500' : '1.5'}
                  />
                </div>

                <div className="inline-flex rounded-xl border border-slate-300 bg-slate-100 p-1">
                  {(['KB', 'MB'] as SizeUnit[]).map((u) => (
                    <button
                      key={u}
                      type="button"
                      onClick={() => handleUnitChange(u)}
                      className={`rounded-lg px-4 py-2 text-sm font-bold transition ${
                        targetUnit === u
                          ? 'bg-indigo-600 text-white shadow-sm'
                          : 'text-slate-600 hover:text-slate-900'
                      }`}
                    >
                      {u}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Minimum Recommended Size & Estimated Output Readout */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-slate-500">
                    Minimum Recommended Size
                  </span>
                  <Sparkles className="h-3.5 w-3.5 text-indigo-500" />
                </div>
                <p className="mt-1 text-base font-bold tabular-nums text-slate-900">
                  {formatBytes(analysis.recommended_min_size_bytes)}
                </p>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  Extreme safe floor: ~{formatBytes(effectiveFloor)}
                </p>
              </div>

              <div className="rounded-xl border border-indigo-200/80 bg-indigo-50/40 p-3.5">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-indigo-700">
                    Estimated Output Size
                  </span>
                  <Gauge className="h-3.5 w-3.5 text-indigo-600" />
                </div>
                <p className="mt-1 text-base font-bold tabular-nums text-indigo-950">
                  ~{formatBytes(estimatedCustomOutputBytes)}
                </p>
                <p className="mt-0.5 text-[11px] text-indigo-700/80">
                  Bounded iterative search (up to 6 passes)
                </p>
              </div>
            </div>

            {/* Compression Intensity Slider */}
            <div className="rounded-xl border border-slate-200/80 bg-white p-4">
              <div className="flex items-center justify-between">
                <label
                  htmlFor="intensity-slider"
                  className="text-xs font-semibold uppercase tracking-wide text-slate-700"
                >
                  Compression Intensity Preference
                </label>
                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-bold tabular-nums text-slate-800">
                  {intensity}%
                </span>
              </div>
              <input
                id="intensity-slider"
                type="range"
                min={15}
                max={100}
                step={5}
                value={intensity}
                onChange={(e) => setIntensity(Number(e.target.value))}
                className="mt-2.5 h-2 w-full cursor-pointer appearance-none rounded-lg bg-slate-200 accent-indigo-600"
              />
              <div className="mt-1 flex justify-between text-[11px] text-slate-500">
                <span>Prioritize Image Sharpness</span>
                <span>Balanced Search</span>
                <span>Aggressive Floor Probe</span>
              </div>
            </div>

            {/* Real-time Advisory Warnings */}
            {isTargetAboveOriginal && (
              <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                <div>
                  <span className="font-semibold">Target exceeds or equals original size: </span>
                  Your target ({formatBytes(targetBytes)}) is at least as large as the uploaded PDF (
                  {formatBytes(analysis.original_size_bytes)}). Compression beyond lossless metadata
                  cleanup may not provide additional benefit.
                </div>
              </div>
            )}

            {isTargetBelowFloor && (
              <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                <div>
                  <span className="font-semibold">Aggressive target detected: </span>
                  {formatBytes(targetBytes)} is below the estimated structural floor (~
                  {formatBytes(effectiveFloor)}). The optimizer will get as close as safely possible
                  without corrupting fonts or text legibility.
                </div>
              </div>
            )}
          </div>
        ) : (
          /* ===================== PREDEFINED PRESETS MODE ===================== */
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {PRESET_CARDS.map((card) => {
                const selected = preset === card.id;
                return (
                  <button
                    key={card.id}
                    type="button"
                    onClick={() => setPreset(card.id)}
                    className={`relative flex flex-col justify-between rounded-xl border p-4 text-left transition-all ${
                      selected
                        ? 'border-indigo-600 bg-indigo-50/50 ring-2 ring-indigo-600/20'
                        : 'border-slate-200 bg-white hover:border-indigo-300 hover:bg-slate-50/60'
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-bold text-slate-900">{card.title}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                            selected
                              ? 'bg-indigo-600 text-white'
                              : 'bg-slate-100 text-slate-600'
                          }`}
                        >
                          {card.badge}
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed text-slate-600">
                        {card.description}
                      </p>
                    </div>

                    <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-2.5 text-[11px] font-medium text-slate-500">
                      <span>
                        Max {card.dpi} DPI · JPEG Q{card.quality}
                      </span>
                      {selected && <Check className="h-4 w-4 text-indigo-600" />}
                    </div>
                  </button>
                );
              })}
            </div>

            {preset === 'extreme' && (
              <div className="flex items-start gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3.5 text-xs text-amber-900">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                <div>
                  <span className="font-semibold">Extreme Compression Quality Warning: </span>
                  Embedded photographs and scanned pages will be downsampled to 72 DPI with strong
                  JPEG quantization. Text and vector graphics remain sharp, but raster images may
                  show visible softness.
                </div>
              </div>
            )}
          </div>
        )}

        {/* Advanced Optimization Toggles */}
        <div className="border-t border-slate-100 pt-4">
          <p className="mb-2.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
            Optimization Controls
          </p>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-200/80 bg-slate-50/60 px-3 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-100/70">
              <input
                type="checkbox"
                checked={grayscale}
                onChange={(e) => setGrayscale(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span>Convert images to grayscale</span>
            </label>

            <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-200/80 bg-slate-50/60 px-3 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-100/70">
              <input
                type="checkbox"
                checked={stripMetadata}
                onChange={(e) => setStripMetadata(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span>Strip metadata & thumbnails</span>
            </label>

            <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-200/80 bg-slate-50/60 px-3 py-2.5 text-xs font-medium text-slate-700 hover:bg-slate-100/70">
              <input
                type="checkbox"
                checked={subsetFonts}
                onChange={(e) => setSubsetFonts(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span>Subset embedded fonts</span>
            </label>
          </div>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={disabled || (mode === 'custom' && numericTarget <= 0)}
          className="flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-6 py-4 text-base font-bold text-white shadow-lg shadow-indigo-600/25 transition hover:from-indigo-700 hover:to-violet-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50"
        >
          <Play className="h-5 w-5 fill-current" />
          <span>
            {mode === 'custom'
              ? `Start Target Compression (${numericTarget > 0 ? `${numericTarget} ${targetUnit}` : ''})`
              : `Start ${preset.charAt(0).toUpperCase() + preset.slice(1)} Compression`}
          </span>
        </button>
      </div>
    </form>
  );
};
