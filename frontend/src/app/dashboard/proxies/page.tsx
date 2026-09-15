"use client";
import { useState } from "react";
import { Card, CardTitle, EmptyState, Field, Spinner, StatusBadge } from "@/components/ui";
import { useApiMutation, useProxies } from "@/hooks/use-api";
import type { Proxy } from "@/types/models";

export default function ProxiesPage() {
  const { data, isLoading } = useProxies();
  const create = useApiMutation("post", [["proxies"]]);
  const remove = useApiMutation("delete", [["proxies"]]);
  const test = useApiMutation("post", [["proxies"]]);
  const checkAll = useApiMutation("post", [["proxies"]]);
  const [form, setForm] = useState({ url: "", protocol: "http", username: "", password: "", country: "" });
  const proxies = (data ?? []) as Proxy[];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Proxy pool</h1>
        <button className="btn-ghost ml-auto !py-1.5 text-xs" onClick={() => checkAll.mutate({ url: "/proxies/check-all" })}>Health-check all</button>
      </div>
      <Card>
        <CardTitle>Add proxy</CardTitle>
        <div className="grid gap-3 md:grid-cols-5">
          <Field label="URL"><input className="input" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} placeholder="http://1.2.3.4:8080" /></Field>
          <Field label="Protocol">
            <select className="input" value={form.protocol} onChange={(e) => setForm({ ...form, protocol: e.target.value })}>
              <option value="http">http</option><option value="socks5">socks5</option><option value="socks4">socks4</option>
            </select>
          </Field>
          <Field label="Username"><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
          <Field label="Password"><input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <div className="flex items-end"><button className="btn-primary w-full" disabled={!form.url} onClick={() => { create.mutate({ url: "/proxies", body: { ...form, username: form.username || null, password: form.password || null, country: form.country || null } }); setForm({ url: "", protocol: "http", username: "", password: "", country: "" }); }}>Add</button></div>
        </div>
      </Card>
      {isLoading ? <Spinner /> : proxies.length === 0 ? <EmptyState title="No proxies" hint="Assign one proxy per IG account for best deliverability." /> : (
        <Card>
          {proxies.map((p) => (
            <div key={p.id} className="flex flex-wrap items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <span className={`h-2 w-2 rounded-full ${p.is_healthy ? "bg-emerald-500" : "bg-red-500"}`} />
              <code className="text-xs">{p.protocol}://{p.url.replace(/^https?:\/\//, "")}</code>
              <span className="text-zinc-500">{p.country ?? ""} · {p.latency_ms != null ? `${p.latency_ms}ms` : "—"} · fails {p.fail_count}</span>
              <span className="ml-auto flex gap-2">
                <button className="btn-ghost !px-3 !py-1 text-xs" onClick={() => test.mutate({ url: `/proxies/${p.id}/test` })}>Test</button>
                <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm("Delete proxy?")) remove.mutate({ url: `/proxies/${p.id}` }); }}>Delete</button>
              </span>
            </div>
          ))}
          {test.data && <p className="mt-2 text-xs text-zinc-500">Last test: {JSON.stringify(test.data)}</p>}
        </Card>
      )}
      <p className="text-xs text-zinc-500">Assign a proxy to an account from the Accounts page (proxy_id). Health checks run every 30 minutes via Celery Beat.</p>
    </div>
  );
}
