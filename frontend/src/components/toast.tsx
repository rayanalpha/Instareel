"use client";
import { create } from "zustand";

export type ToastKind = "success" | "error" | "info";

interface ToastItem {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastState {
  items: ToastItem[];
  push: (kind: ToastKind, message: string) => void;
  remove: (id: number) => void;
}

export const useToasts = create<ToastState>((set, get) => ({
  items: [],
  push: (kind, message) => {
    const id = Date.now() + Math.floor(Math.random() * 1000);
    set((s) => ({ items: [...s.items, { id, kind, message }] }));
    setTimeout(() => get().remove(id), 8000);
  },
  remove: (id) => set((s) => ({ items: s.items.filter((t) => t.id !== id) })),
}));

/** Imperative helper usable from anywhere (hooks, handlers). */
export function toast(kind: ToastKind, message: string) {
  useToasts.getState().push(kind, message);
}

const STYLES: Record<ToastKind, string> = {
  success:
    "border-emerald-500/40 bg-emerald-50 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-100",
  error:
    "border-red-500/40 bg-red-50 text-red-900 dark:bg-red-900/40 dark:text-red-100",
  info:
    "border-sky-500/40 bg-sky-50 text-sky-900 dark:bg-sky-900/40 dark:text-sky-100",
};

export function Toaster() {
  const items = useToasts((s) => s.items);
  const remove = useToasts((s) => s.remove);
  if (items.length === 0) return null;
  return (
    <div className="fixed right-4 top-4 z-50 flex w-80 max-w-[90vw] flex-col gap-2">
      {items.map((t) => (
        <div
          key={t.id}
          className={`flex items-start gap-2 rounded-xl border p-3 text-sm shadow-sm ${STYLES[t.kind]}`}
        >
          <span className="flex-1 break-words">{t.message}</span>
          <button
            onClick={() => remove(t.id)}
            className="shrink-0 opacity-60 transition hover:opacity-100"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
