"use client";

import { useState } from "react";
import { clsx } from "clsx";
import { getAgentColor, getAgentBgColor, getAgentInitials } from "@/lib/palette";
import { PersonaModal } from "./PersonaModal";
import type { Persona } from "@/types";

interface PersonaCardProps {
  persona: Persona;
  selectable?: boolean;
  selected?: boolean;
  onToggle?: (id: string) => void;
}

export function PersonaCard({
  persona,
  selectable = false,
  selected = false,
  onToggle,
}: PersonaCardProps) {
  const [modalOpen, setModalOpen] = useState(false);

  const color = getAgentColor(persona.id);
  const bgColor = getAgentBgColor(persona.id);
  const initials = getAgentInitials(persona.name);

  return (
    <>
      <div
        data-testid={`persona-card-${persona.id}`}
        className={clsx(
          "relative rounded-lg border p-4 transition-all duration-150",
          selectable
            ? "cursor-pointer select-none"
            : "cursor-default",
          selected && selectable
            ? "border-indigo-400 bg-indigo-50/50 ring-1 ring-indigo-400 dark:bg-indigo-950/30 dark:border-indigo-500"
            : "border-slate-200 bg-white dark:border-slate-700 dark:bg-slate-900",
          "hover:shadow-md",
        )}
        onClick={() => {
          if (selectable && onToggle) {
            onToggle(persona.id);
          } else {
            setModalOpen(true);
          }
        }}
        role={selectable ? "checkbox" : "button"}
        aria-checked={selectable ? selected : undefined}
        aria-label={selectable ? `${persona.name} — ${selected ? "selected" : "not selected"}` : `View ${persona.name} profile`}
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (selectable && onToggle) onToggle(persona.id);
            else setModalOpen(true);
          }
        }}
      >
        {/* Selection checkbox */}
        {selectable && (
          <div
            className={clsx(
              "absolute top-3 right-3 h-5 w-5 rounded border-2 flex items-center justify-center transition-colors",
              selected
                ? "border-indigo-600 bg-indigo-600"
                : "border-slate-300 dark:border-slate-600",
            )}
            aria-hidden="true"
          >
            {selected && (
              <svg className="h-3 w-3 text-white" viewBox="0 0 12 12" fill="none">
                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            )}
          </div>
        )}

        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-sm font-bold"
            style={{ backgroundColor: bgColor, color }}
            aria-hidden="true"
          >
            {initials}
          </div>

          <div className="min-w-0 flex-1">
            <p className="font-semibold text-slate-900 dark:text-slate-100 text-sm leading-tight">
              {persona.name}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              {persona.role}
            </p>

            {/* Stance pill */}
            <span
              className="mt-2 inline-block rounded-full px-2 py-0.5 text-xs font-medium"
              style={{ backgroundColor: bgColor, color }}
            >
              {persona.stance}
            </span>

            {/* Expertise tags */}
            <div className="mt-2 flex flex-wrap gap-1">
              {persona.expertise.slice(0, 3).map((tag) => (
                <span
                  key={tag}
                  className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-300"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Click to view detail hint for non-selectable mode */}
        {!selectable && (
          <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
            Click to view full profile
          </p>
        )}
      </div>

      {/* Detail modal — only rendered in non-selectable mode */}
      {!selectable && (
        <PersonaModal
          persona={persona}
          open={modalOpen}
          onClose={() => setModalOpen(false)}
        />
      )}
    </>
  );
}
