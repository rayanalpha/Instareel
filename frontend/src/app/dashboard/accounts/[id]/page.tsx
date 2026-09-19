"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardTitle, EmptyState, Field, Spinner, StatusBadge } from "@/components/ui";
import { toast } from "@/components/toast";
import { useApiMutation } from "@/hooks/use-api";
import { fmt, timeAgo } from "@/lib/utils";
import type { Account, Proxy } from "@/types/models";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [acc, setAcc] = useState<Account | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const action = useApiMutation("post", [["accounts"]]);
  const update = useApiMutation("put", [["accounts"]]);

  async function load() {
    try {
      const [{ data: a }, { data: s }, { data: p }] = await Promise.all([
        api.get(`/accounts/${id}`),
        api.get(`/accounts/${id}/analytics`),
        api.get("/proxies"),
      ]);
      setLoadError("");
      setAcc(a);
      setStats(s);
      setProxies(p ?? []);
    } catch {
      setLoadError("Failed to load account.");
    }
  }

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [id]);

  async function uploadSession(file: File) {
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(`/accounts/${id}/session`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });
      toast("success", String(data.detail ?? "Session uploaded"));
      load();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Session upload failed";
      toast("error", String(msg));
    } finally {
      setUploading(false);
    }
  }

  if (loadError) return <EmptyState title="Load failed" hint={loadError} />;
  if (!acc) return <Spinner />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">@{acc.username}</h1>
        <StatusBadge status={acc.status} />
      </div>
      <div className="grid gap-4 md:grid-cols-4">
        {[["Posts", stats?.posts], ["Views", fmt(stats?.views)], ["Likes", fmt(stats?.likes)], ["Engagement", `${stats?.avg_engagement ?? 0}%`]].map(([k, v]) => (
          <Card key={k as string}><p className="text-2xl font-extrabold">{v as string}</p><p className="text-xs text-zinc-500">{k}</p></Card>
        ))}
      </div>
      <Card>
        <CardTitle>Connection</CardTitle>
        <div className="grid gap-3 md:grid-cols-3">
          <Field label="Proxy">
            <select
              className="input"
              value={acc.proxy_id ? String(acc.proxy_id) : ""}
              disabled={update.isPending}
              onChange={(e) => {
                const v = e.target.value;
                update.mutate(
                  { url: `/accounts/${id}`, body: { proxy_id: v === "" ? "none" : Number(v) } },
                  { onSuccess: load }
                );
              }}
            >
              <option value="">No proxy</option>
              {proxies.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.protocol}://{p.url.replace(/^https?:\/\//, "")}{p.country ? ` (${p.country})` : ""}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Session file">
            <div className="flex items-center gap-2">
              <span className={`text-sm font-semibold ${acc.has_session ? "text-emerald-500" : "text-amber-500"}`}>
                {acc.has_session ? "saved ✓" : "missing"}
              </span>
              <label className="btn-ghost cursor-pointer !py-1.5 text-xs">
                {uploading ? "Uploading…" : "Upload session JSON"}
                <input
                  type="file"
                  accept=".json,application/json"
                  className="hidden"
                  disabled={uploading}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) uploadSession(f);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
          </Field>
          <div className="flex items-end gap-2">
            <button
              className="btn-ghost flex-1"
              disabled={action.isPending}
              onClick={() => action.mutate({ url: `/accounts/${id}/test-session` })}
            >
              {action.isPending ? "Working…" : "Test session"}
            </button>
          </div>
        </div>
        <p className="mt-2 text-xs text-zinc-500">
          Upload a session JSON created by manual_login.py or session_from_browser.py — no server restart needed.
        </p>
      </Card>
      <Card>
        <CardTitle>Recent posts</CardTitle>
        {(stats?.recent ?? []).length === 0
          ? <p className="text-sm text-zinc-500">No posts yet.</p>
          : (stats.recent as any[]).map((p: any) => (
            <div key={p.id} className="flex items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <span>Post #{p.id}</span>
              <StatusBadge status={p.status} />
              <span className="ml-auto text-zinc-500">{fmt(p.views_7d)} views · {timeAgo(p.posted_at)}</span>
            </div>
          ))}
      </Card>
    </div>
  );
}
