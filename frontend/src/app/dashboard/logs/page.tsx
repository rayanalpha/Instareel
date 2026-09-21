"use client";
import { useState } from "react";
import { Card, EmptyState, QueryFailed, Spinner } from "@/components/ui";
import { useApiMutation, useLogs } from "@/hooks/use-api";
import type { LogEntry } from "@/types/models";

const COLORS: Record<string, string> = {
  DEBUG: "text-zinc-400", INFO: "text-sky-500", WARNING: "text-amber-500",
  ERROR: "text-red-500", CRITICAL: "text-red-700 font-bold",
};

export default function LogsPage() {
  const { data, isLoading, isError, refetch } = useLogs();
  const clear = useApiMutation("delete", [["logs"]]);
  const [level, setLevel] = useState("");
  const [category, setCategory] = useState("");
  const logs = ((data ?? []) as LogEntry[]).filter(
    (l) => (!level || l.level === level) && (!category || l.category === category)
  );

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">System logs</h1>
        <select className="input ml-auto !w-auto" value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="">All levels</option>
          {["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].map((l) => <option key={l} value={l}>{l}</option>)}
        </select>
        <select className="input !w-auto" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">All categories</option>
          {["auth", "video", "post", "account", "scheduler", "system"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="btn-ghost !py-2 text-xs" onClick={() => { if (confirm("Delete logs older than 30 days?")) clear.mutate({ url: "/logs?older_than_days=30" }); }}>Prune 30d+</button>
      </div>
      {isLoading ? <Spinner /> : isError ? <QueryFailed onRetry={() => refetch()} /> : logs.length === 0 ? <EmptyState title="No logs" /> : (
        <Card className="!p-2 font-mono text-xs">
          {logs.map((l) => (
            <div key={l.id} className="flex flex-wrap gap-x-2 gap-y-1 border-b border-zinc-100 px-2 py-1.5 last:border-0 dark:border-zinc-800">
              <span className="shrink-0 text-zinc-400">{new Date(l.timestamp).toLocaleString()}</span>
              <span className={`shrink-0 font-semibold ${COLORS[l.level] ?? ""}`}>{l.level}</span>
              <span className="shrink-0 rounded bg-zinc-100 px-1 dark:bg-zinc-800">{l.category}</span>
              <span className="w-full break-all sm:w-auto sm:flex-1">{l.message}</span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
