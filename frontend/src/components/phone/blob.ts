"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

// Process-scoped blob cache: one authenticated fetch per media, shared by
// grid cells and the player. Bounded by video count; never revoked mid-session.
const cache = new Map<string, string>();
const pending = new Map<string, Promise<string>>();

function loadBlob(key: string, url: string): Promise<string> {
  const hit = cache.get(key);
  if (hit) return Promise.resolve(hit);
  const inflight = pending.get(key);
  if (inflight) return inflight;
  const p = api
    .get(url, { responseType: "blob", timeout: 120000 })
    .then((res) => {
      const objectUrl = URL.createObjectURL(res.data);
      cache.set(key, objectUrl);
      pending.delete(key);
      return objectUrl;
    })
    .catch((e: unknown) => {
      pending.delete(key);
      throw e;
    });
  pending.set(key, p);
  return p;
}

/** Authenticated media for <img>/<video> tags (preview or thumbnail).
 * Tri-state: url set = ready, failed = gave up (show placeholder, no spin),
 * neither = still loading. */
export function useBlobUrl(kind: "preview" | "thumbnail", id: number | null): { url: string | null; failed: boolean } {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!id) {
      setUrl(null);
      return;
    }
    let cancelled = false;
    setUrl(null);
    setFailed(false);
    loadBlob(`${kind}:${id}`, `/videos/${id}/${kind}`).then(
      (u) => {
        if (!cancelled) setUrl(u);
      },
      () => {
        if (!cancelled) setFailed(true);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [kind, id]);
  return { url, failed };
}
