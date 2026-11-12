import React from 'react';
import { ShieldCheck, Trash2, Lock, EyeOff } from 'lucide-react';

export const PrivacyPage: React.FC = () => {
  const pillars = [
    {
      icon: Lock,
      title: 'Zero Third-Party Transfers',
      body: 'All PDF inspection, image downsampling, Ghostscript distillation, and QPDF object-stream packing execute strictly on this application’s local backend—never sent to external cloud compression APIs.',
    },
    {
      icon: Trash2,
      title: 'Ephemeral Storage & Instant Deletion',
      body: 'Uploaded and compressed files live inside randomized UUIDv4 temporary directories only during active use. A background reaper purges files automatically after 30 minutes, and you can wipe them immediately with the Delete Files button.',
    },
    {
      icon: EyeOff,
      title: 'Zero Content Logging',
      body: 'Application logs never record document text, author metadata, or user filenames. Optional metadata stripping removes XMP packets, Info dictionaries, and embedded page thumbnails from your output PDF.',
    },
    {
      icon: ShieldCheck,
      title: 'Untrusted PDF Hardening',
      body: 'Every upload undergoes %PDF- magic-byte verification, strict size and page ceilings, path-traversal sanitization, Ghostscript -dSAFER sandboxing, and automatic removal of embedded PDF JavaScript actions.',
    },
  ];

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div className="space-y-2">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">
          Privacy & Security Policy
        </h1>
        <p className="text-base text-slate-600">
          Your documents belong strictly to you—processed locally in isolated ephemeral workspaces
          and deleted automatically.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
        {pillars.map((p) => {
          const Icon = p.icon;
          return (
            <div
              key={p.title}
              className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm space-y-2.5"
            >
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <Icon className="h-5 w-5" />
              </div>
              <h2 className="text-base font-bold text-slate-900">{p.title}</h2>
              <p className="text-xs leading-relaxed text-slate-600">{p.body}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
