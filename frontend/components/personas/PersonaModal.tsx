"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";
import { getAgentColor, getAgentBgColor, getAgentInitials } from "@/lib/palette";
import type { Persona } from "@/types";

interface PersonaModalProps {
  persona: Persona;
  open: boolean;
  onClose: () => void;
}

export function PersonaModal({ persona, open, onClose }: PersonaModalProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open) {
      dialog.showModal();
    } else {
      dialog.close();
    }
  }, [open]);

  if (!open) return null;

  const color = getAgentColor(persona.id);
  const bgColor = getAgentBgColor(persona.id);
  const initials = getAgentInitials(persona.name);

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={`modal-title-${persona.id}`}
      aria-modal="true"
      data-testid={`persona-modal-${persona.id}`}
      className="m-auto max-w-2xl w-full rounded-xl shadow-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-0 backdrop:bg-black/50"
      onClose={onClose}
    >
      {/* Header */}
      <div
        className="flex items-start justify-between gap-4 px-6 py-5 border-b border-slate-200 dark:border-slate-700"
        style={{ borderLeftWidth: 4, borderLeftColor: color }}
      >
        <div className="flex items-center gap-4">
          <div
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full text-lg font-bold"
            style={{ backgroundColor: bgColor, color }}
            aria-hidden="true"
          >
            {initials}
          </div>
          <div>
            <h2
              id={`modal-title-${persona.id}`}
              className="text-lg font-bold text-slate-900 dark:text-slate-100"
            >
              {persona.name}
            </h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">{persona.role}</p>
            <span
              className="mt-1 inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
              style={{ backgroundColor: bgColor, color }}
            >
              {persona.stance}
            </span>
          </div>
        </div>
        <button
          onClick={onClose}
          aria-label="Close persona profile"
          className="rounded-md p-1 text-slate-400 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition-colors"
        >
          <X className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>

      {/* Body */}
      <div className="px-6 py-5 space-y-4 overflow-y-auto max-h-[60vh] text-sm">
        <Field label="Background" value={persona.background} />
        <Field label="Style" value={persona.style} />
        <Field label="Priorities" value={persona.priorities} />
        <Field label="Retrieval Focus" value={persona.retrieval_focus} />

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1.5">
            Expertise
          </p>
          <div className="flex flex-wrap gap-1.5">
            {persona.expertise.map((tag) => (
              <span
                key={tag}
                className="rounded-full px-2.5 py-0.5 text-xs font-medium"
                style={{ backgroundColor: bgColor, color }}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-1.5">
            Personality Traits
          </p>
          <div className="flex flex-wrap gap-1.5">
            {persona.personality_traits.map((trait) => (
              <span
                key={trait}
                className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-700 dark:text-slate-200"
              >
                {trait}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="border-t border-slate-200 dark:border-slate-700 px-6 py-4">
        <p className="text-xs font-mono text-slate-400">ID: {persona.id}</p>
      </div>
    </dialog>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-0.5">
        {label}
      </p>
      <p className="text-slate-700 dark:text-slate-300">{value}</p>
    </div>
  );
}
