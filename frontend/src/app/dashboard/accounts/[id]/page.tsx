"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardTitle, Spinner, StatusBadge } from "@/components/ui";
import { fmt, timeAgo } from "@/lib/utils";

export default function AccountDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [acc, setAcc] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    (async () => {
      const [{ data: a }, { data: s }] = await Promise.all([
        api.get(`/accounts/${id}`),
        api.get(`/accounts/${id}/analytics`),
      ]);
      setAcc(a);
      setStats(s);
    })();
  }, [id]);

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
