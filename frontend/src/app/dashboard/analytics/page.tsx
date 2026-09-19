"use client";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardTitle, QueryFailed, Spinner } from "@/components/ui";
import { toast } from "@/components/toast";
import { useAccounts, useOverview } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { fmt } from "@/lib/utils";

export default function AnalyticsPage() {
  const [days, setDays] = useState(30);
  const { data, isLoading, isError, refetch } = useOverview(days);
  const { data: accounts } = useAccounts();

  async function exportCsv() {
    let url = "";
    try {
      const { data: csv } = await api.get(`/analytics/export`);
      const blob = new Blob([csv], { type: "text/csv" });
      url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "analytics.csv";
      a.click();
    } catch {
      toast("error", "CSV export failed");
    } finally {
      if (url) URL.revokeObjectURL(url);
    }
  }

  if (isLoading) return <Spinner />;
  if (isError || !data) return <QueryFailed onRetry={() => refetch()} />;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Analytics</h1>
        <select className="input ml-auto !w-auto" value={days} onChange={(e) => setDays(Number(e.target.value))}>
          {[7, 14, 30, 90].map((d) => <option key={d} value={d}>Last {d} days</option>)}
        </select>
        <button className="btn-ghost" onClick={exportCsv}>Export CSV</button>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card><p className="text-2xl font-extrabold">{fmt(data.total_posts)}</p><p className="text-xs text-zinc-500">Posts</p></Card>
        <Card><p className="text-2xl font-extrabold">{fmt(data.total_views)}</p><p className="text-xs text-zinc-500">Views</p></Card>
        <Card><p className="text-2xl font-extrabold">{data.avg_engagement_rate}%</p><p className="text-xs text-zinc-500">Avg engagement</p></Card>
      </div>
      <Card>
        <CardTitle>Views trend</CardTitle>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data.series}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line type="monotone" dataKey="views" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <CardTitle>Posts per day</CardTitle>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.series}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} minTickGap={30} />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="posts" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
      <Card>
        <CardTitle>Account comparison</CardTitle>
        {(accounts ?? []).length === 0
          ? <p className="text-sm text-zinc-500">No accounts yet.</p>
          : (accounts as { username: string; posts_today?: number; total_posts: number; total_views: number }[]).map((a: any) => (
            <div key={a.username ?? a.id} className="flex items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <strong>@{a.username}</strong>
              <span className="ml-auto text-zinc-500">{a.total_posts ?? 0} posts · {fmt(a.total_views)} views</span>
            </div>
          ))}
      </Card>
    </div>
  );
}
