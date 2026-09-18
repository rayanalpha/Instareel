"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { toast } from "@/components/toast";

async function get<T = any>(url: string): Promise<T> {
  const { data } = await api.get(url);
  return data;
}

/** Show the API's own result payload as a toast so every action gives visible feedback. */
function announce(data: unknown) {
  if (!data || typeof data !== "object") return;
  const d = data as Record<string, unknown>;
  if (d.ok === false) {
    toast("error", String(d.detail ?? d.error ?? "Operation failed"));
  } else if (d.ok === true && "detail" in d) {
    toast("success", String(d.detail));
  } else if ("valid" in d) {
    toast(d.valid ? "success" : "error", d.valid ? "Session is valid" : "Session invalid or expired");
  } else if (d.queued === true) {
    toast("info", "Queued — watch the worker logs / status");
  } else if (typeof d.error === "string") {
    toast("error", d.error);
  }
}

function errorMessage(err: unknown): string {
  const e = err as { response?: { data?: { detail?: unknown; message?: unknown; error?: unknown } }; message?: string };
  const rd = e?.response?.data;
  const detail = rd?.detail ?? rd?.message ?? rd?.error ?? e?.message;
  return typeof detail === "string" ? detail : "Request failed";
}

export function useOverview(days = 30) {
  return useQuery({ queryKey: ["overview", days], queryFn: () => get(`/analytics/overview?days=${days}`), refetchInterval: 15000 });
}
export function useAccounts() {
  return useQuery({ queryKey: ["accounts"], queryFn: () => get("/accounts"), refetchInterval: 15000 });
}

/** Videos list: poll only while something is uploaded/processing —
 * once everything settles, refetching stops (and so does the log noise). */
export function useVideos(status = "") {
  return useQuery({
    queryKey: ["videos", status],
    queryFn: () => get(status ? `/videos?status=${status}` : "/videos"),
    refetchInterval: (query) => {
      const rows = (query.state.data ?? []) as { status?: string }[];
      const busy = rows.some((v) => v.status === "uploaded" || v.status === "processing");
      return busy ? 5000 : false;
    },
  });
}
export function usePosts(status = "") {
  return useQuery({
    queryKey: ["posts", status],
    queryFn: () => get(status ? `/posts?status=${status}` : "/posts"),
    refetchInterval: 10000,
  });
}
export function useQueue() {
  return useQuery({ queryKey: ["queue"], queryFn: () => get("/posts/queue"), refetchInterval: 10000 });
}
export function useRules() {
  return useQuery({ queryKey: ["rules"], queryFn: () => get("/schedule") });
}
export function useCaptions() {
  return useQuery({ queryKey: ["captions"], queryFn: () => get("/captions") });
}
export function useHashtags() {
  return useQuery({ queryKey: ["hashtags"], queryFn: () => get("/hashtags") });
}
export function useBios() {
  return useQuery({ queryKey: ["bios"], queryFn: () => get("/bios") });
}
export function useProxies() {
  return useQuery({ queryKey: ["proxies"], queryFn: () => get("/proxies") });
}
export function useEffects() {
  return useQuery({ queryKey: ["effects"], queryFn: () => get("/effects") });
}
export function useAudios() {
  return useQuery({ queryKey: ["audio"], queryFn: () => get("/audio") });
}
export function useAudioStats() {
  return useQuery({ queryKey: ["audio-stats"], queryFn: () => get("/analytics/audio") });
}
export function useLogs() {
  return useQuery({ queryKey: ["logs"], queryFn: () => get("/logs?limit=200"), refetchInterval: 8000 });
}
export function useSettings() {
  return useQuery({ queryKey: ["settings"], queryFn: () => get("/settings") });
}
export function useApiMutation(method: "post" | "put" | "delete", invalidate: string[][] = []) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ url, body }: { url: string; body?: unknown }) => {
      // Instagram-facing endpoints can take minutes; don't let axios kill the request at 30s.
      const { data } = await api.request({ method, url, data: body, timeout: 180000 });
      return data;
    },
    onSuccess: (data) => {
      announce(data);
      for (const key of invalidate) qc.invalidateQueries({ queryKey: key });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
    onError: (err) => {
      toast("error", errorMessage(err));
    },
  });
}
