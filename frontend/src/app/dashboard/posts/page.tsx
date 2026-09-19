"use client";
import { useState } from "react";
import { Card, EmptyState, QueryFailed, Spinner, StatusBadge } from "@/components/ui";
import { useApiMutation, usePosts, useQueue } from "@/hooks/use-api";
import { fmt, timeAgo } from "@/lib/utils";
import type { Post } from "@/types/models";

export default function PostsPage() {
  const [status, setStatus] = useState("");
  const { data, isLoading, isError, refetch } = usePosts(status);
  const { data: queue } = useQueue();
  const retry = useApiMutation("post", [["posts"]]);
  const remove = useApiMutation("delete", [["posts"]]);
  const posts = (data ?? []) as Post[];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Posts</h1>
        <select className="input ml-auto !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {["scheduled", "posting", "posted", "failed"].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <Card>
        <p className="mb-2 text-sm font-semibold">Up next ({((queue ?? []) as Post[]).length})</p>
        {((queue ?? []) as Post[]).slice(0, 5).map((p) => (
          <div key={p.id} className="flex items-center gap-2 border-t border-zinc-100 py-1.5 text-sm first:border-0 dark:border-zinc-800">
            <span>Post #{p.id}</span>
            <span className="text-zinc-500">account #{p.account_id} · video #{p.video_id}</span>
            <span className="ml-auto text-zinc-500">{p.scheduled_for ? timeAgo(p.scheduled_for) : "asap"}</span>
          </div>
        ))}
        {(queue ?? []).length === 0 && <p className="text-sm text-zinc-500">Nothing scheduled.</p>}
      </Card>

      {isLoading ? <Spinner /> : isError ? <QueryFailed onRetry={() => refetch()} /> : posts.length === 0 ? (
        <EmptyState title="No posts" hint="Schedule rules create posts automatically every minute." />
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                  <tr className="text-left text-xs uppercase text-zinc-400">
                    <th className="py-2 pr-4">Post</th><th className="py-2 pr-4">Status</th>
                    <th className="py-2 pr-4">Audio</th>
                    <th className="py-2 pr-4 text-right">Views</th><th className="py-2 pr-4 text-right">Eng.</th>
                    <th className="py-2 pr-4">Link</th><th className="py-2 text-right">Actions</th>
                  </tr>
              </thead>
              <tbody>
                {posts.map((p) => (
                  <tr key={p.id} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="py-2 pr-4">#{p.id} · acc #{p.account_id} · vid #{p.video_id}</td>
                    <td className="py-2 pr-4"><StatusBadge status={p.status} /></td>
                    <td className="py-2 pr-4 text-zinc-500">{p.audio_track ?? "—"}</td>
                    <td className="py-2 pr-4 text-right">{fmt(p.views_7d ?? p.views_24h)}</td>
                    <td className="py-2 pr-4 text-right">{p.engagement_rate != null ? `${p.engagement_rate}%` : "—"}</td>
                    <td className="py-2 pr-4">{p.ig_permalink ? <a className="text-emerald-500 hover:underline" href={p.ig_permalink} target="_blank">Reel ↗</a> : "—"}</td>
                    <td className="py-2 text-right">
                      {p.status === "failed" && <button className="btn-ghost mr-2 !px-3 !py-1 text-xs" onClick={() => retry.mutate({ url: `/posts/${p.id}/retry` })}>Retry</button>}
                      <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete post #${p.id}?`)) remove.mutate({ url: `/posts/${p.id}` }); }}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
