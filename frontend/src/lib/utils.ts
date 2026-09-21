import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

/** API datetimes come from SQLite: UTC wall time with no offset suffix.
 *  A naive ISO string parses as browser-local time, shifting every
 *  timestamp by the viewer's UTC offset (e.g. +3:30 Tehran turns a fresh
 *  row into "3h ago"). Assume UTC unless a zone is already present. */
export function parseApiDate(iso: string): Date {
  const zoned = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(iso.includes("T") && !zoned ? `${iso}Z` : iso);
}

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "never";
  const s = Math.floor((Date.now() - parseApiDate(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/** Host part of a stored proxy URL. Stored URLs already carry their own
 *  scheme (e.g. socks5://h:port) — callers must not prepend protocol again. */
export function proxyHost(url: string): string {
  return (url || "").replace(/^[a-z][a-z0-9+.-]*:\/\//i, "");
}

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function dayLabel(dow: number): string {
  return dow === -1 ? "Every day" : DAYS[dow] ?? `Day ${dow}`;
}
