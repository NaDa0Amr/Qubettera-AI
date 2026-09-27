"use client";

import { useEffect, useState, useCallback } from "react";
import { clsx } from "clsx";
import { X, CheckCircle, AlertCircle, Info } from "lucide-react";

type ToastType = "info" | "success" | "error";

interface ToastData {
  id: string;
  type: ToastType;
  message: string;
}

// Global toast store — simple singleton for this app's scope.
let listeners: Array<(toasts: ToastData[]) => void> = [];
let toasts: ToastData[] = [];

function notify() {
  for (const cb of listeners) cb([...toasts]);
}

export function toast(type: ToastType, message: string) {
  const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  toasts = [...toasts, { id, type, message }];
  notify();
  setTimeout(() => dismissToast(id), 5000);
}

function dismissToast(id: string) {
  toasts = toasts.filter((t) => t.id !== id);
  notify();
}

const typeConfig: Record<ToastType, { icon: typeof Info; bg: string; border: string; text: string }> = {
  info: { icon: Info, bg: "bg-slate-900", border: "border-slate-700", text: "text-white" },
  success: { icon: CheckCircle, bg: "bg-emerald-800", border: "border-emerald-600", text: "text-white" },
  error: { icon: AlertCircle, bg: "bg-red-800", border: "border-red-600", text: "text-white" },
};

export function ToastContainer() {
  const [items, setItems] = useState<ToastData[]>([]);

  useEffect(() => {
    listeners.push(setItems);
    return () => {
      listeners = listeners.filter((l) => l !== setItems);
    };
  }, []);

  const dismiss = useCallback((id: string) => dismissToast(id), []);

  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
    >
      {items.map((item) => {
        const { icon: Icon, bg, border, text } = typeConfig[item.type];
        return (
          <div
            key={item.id}
            role="alert"
            className={clsx(
              "flex items-start gap-3 rounded-lg border px-4 py-3 shadow-lg text-sm",
              bg, border, text,
            )}
          >
            <Icon className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
            <span className="flex-1">{item.message}</span>
            <button
              onClick={() => dismiss(item.id)}
              aria-label="Dismiss notification"
              className="shrink-0 opacity-70 hover:opacity-100 transition-opacity"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
