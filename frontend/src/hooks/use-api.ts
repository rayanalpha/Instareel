"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

async function get<T = any>(url: string): Promise<T> {
  const { data } = await api.get(url);
  return data;
}

export function useOverview(days = 30) {
  return useQuery({ queryKey: ["overview", days], queryFn: () => get(`/analytics/overview?days=${days}`), refetchInterval: 15000 });
}
export function useAccounts() {
  return useQuery({ queryKey: ["accounts"], queryFn: () => get("/accounts"), refetchInterval: 15000 });
}
export function useVideos(status = "") {
  return useQuery({
    queryKey: ["videos", status],
    queryFn: () => get(status ? `/videos?status=${status}` : "/videos"),
    refetchInterval: 5000,
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
      const { data } = await api.request({ method, url, data: body });
      return data;
    },
    onSuccess: () => {
      for (const key of invalidate) qc.invalidateQueries({ queryKey: key });
      qc.invalidateQueries({ queryKey: ["overview"] });
    },
  });
}
