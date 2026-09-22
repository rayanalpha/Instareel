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
    "border-emerald-500 bg-emerald-50/95 text-emerald-900 dark:border-emerald-400 dark:bg-emerald-950 dark:text-emerald-100",
  error:
    "border-red-500 bg-red-50/95 text-red-900 dark:border-red-400 dark:bg-red-950 dark:text-red-100",
  info:
    "border-sky-500 bg-sky-50/95 text-sky-900 dark:border-sky-400 dark:bg-sky-950 dark:text-sky-100",
};

export function Toaster() {
  const items = useToasts((s) => s.items);
  const remove = useToasts((s) => s.remove);
  if (items.length === 0) return null;
  return (
    <div className="fixed inset-x-4 top-4 z-[100] flex flex-col gap-2 sm:inset-x-auto sm:right-4 sm:w-80 sm:max-w-[90vw]">
      {items.map((t) => (
        <div
          key={t.id}
          role="status"
          className={`flex max-w-full items-start gap-2 overflow-hidden rounded-xl border-2 p-3 text-sm shadow-xl backdrop-blur-md ${STYLES[t.kind]}`}
        >
          <span className="min-w-0 flex-1 break-all">{t.message}</span>
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
