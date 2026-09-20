"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardTitle, EmptyState, Field, QueryFailed, Spinner, StatusBadge } from "@/components/ui";
import { useApiMutation, useProxies, useProxySources } from "@/hooks/use-api";
import { api } from "@/lib/api";
import type { Proxy, ProxyImportResult, ProxySource } from "@/types/models";

export default function ProxiesPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useProxies();
  const { data: sourceRows } = useProxySources();
  const create = useApiMutation("post", [["proxies"]]);
  const remove = useApiMutation("delete", [["proxies"]]);
  const test = useApiMutation("post", [["proxies"]]);
  const checkAll = useApiMutation("post", [["proxies"]]);
  const refreshPool = useApiMutation("post", [["proxies"], ["proxy-sources"]]);
  const purgePool = useApiMutation("post", [["proxies"]]);
  const createSource = useApiMutation("post", [["proxy-sources"]]);
  const toggleSource = useApiMutation("put", [["proxy-sources"]]);
  const removeSource = useApiMutation("delete", [["proxy-sources"]]);
  const [srcForm, setSrcForm] = useState({ name: "", url: "", default_protocol: "http", default_country: "" });
  const [form, setForm] = useState({ url: "", protocol: "http", username: "", password: "", country: "" });
  const [impFile, setImpFile] = useState<File | null>(null);
  const [impProto, setImpProto] = useState("http");
  const [impCountry, setImpCountry] = useState("");
  const [impBusy, setImpBusy] = useState(false);
  const [impResult, setImpResult] = useState<ProxyImportResult | null>(null);
  const [impError, setImpError] = useState("");
  const proxies = (data ?? []) as Proxy[];

  async function bulkImport() {
    if (!impFile) return;
    setImpBusy(true);
    setImpError("");
    setImpResult(null);
    try {
      const fd = new FormData();
      fd.append("file", impFile);
      fd.append("default_protocol", impProto);
      fd.append("default_country", impCountry);
      const { data } = await api.post("/proxies/import", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      setImpResult(data as ProxyImportResult);
      setImpFile(null);
      qc.invalidateQueries({ queryKey: ["proxies"] });
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Import failed";
      setImpError(String(msg));
    } finally {
      setImpBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Proxy pool</h1>
        <button className="btn-ghost ml-auto !py-1.5 text-xs" onClick={() => checkAll.mutate({ url: "/proxies/check-all" })}>Health-check all</button>
        <button className="btn-ghost !py-1.5 text-xs" onClick={() => refreshPool.mutate({ url: "/proxies/pool/refresh" })}>Refresh auto-pool</button>
        <button className="btn-ghost !py-1.5 text-xs" onClick={() => { if (confirm("Delete long-dead auto-fetched proxies? Manual ones are never touched.")) purgePool.mutate({ url: "/proxies/pool/purge" }); }}>Purge stale</button>
      </div>
      {(() => {
        const auto = proxies.filter((p) => p.source && p.source !== "manual");
        const healthy = proxies.filter((p) => p.is_healthy && p.is_active);
        const byCountry = new Map<string, number>();
        proxies.forEach((p) => { if (p.country) byCountry.set(p.country, (byCountry.get(p.country) ?? 0) + 1); });
        return (
          <p className="text-xs text-zinc-500">
            {proxies.length} total · {healthy.length} healthy · {auto.length} auto-fetched
            {byCountry.size > 0 && <> · {[...byCountry.entries()].map(([c, n]) => `${c}:${n}`).join(" ")}</>}
          </p>
        );
      })()}
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
      <Card>
        <CardTitle>Bulk import (.txt, one per line)</CardTitle>
        <p className="mb-2 text-xs text-zinc-500">
          host:port · scheme://host:port · user:pass@host:port · scheme://user:pass@host:port · host:port:user:pass —
          no-auth (IP-whitelisted) lines work as-is. Optional country tag per line: <code>|DE</code> or <code>#DE</code>.
          Duplicates are skipped, every bad line is reported.
        </p>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="List file">
            <input type="file" className="input" accept=".txt,text/plain" onChange={(e) => setImpFile(e.target.files?.[0] ?? null)} />
          </Field>
          <Field label="Default protocol">
            <select className="input" value={impProto} onChange={(e) => setImpProto(e.target.value)}>
              <option value="http">http</option><option value="socks5">socks5</option><option value="socks4">socks4</option>
            </select>
          </Field>
          <Field label="Default country (optional)"><input className="input" value={impCountry} onChange={(e) => setImpCountry(e.target.value)} placeholder="DE" maxLength={2} /></Field>
          <div className="flex items-end"><button className="btn-primary w-full" disabled={!impFile || impBusy} onClick={bulkImport}>{impBusy ? "Importing…" : "Import"}</button></div>
        </div>
        {impError && <p className="mt-2 text-sm text-red-500">{impError}</p>}
        {impResult && (
          <div className="mt-2 text-xs">
            <p className="text-emerald-600">Added {impResult.added} · {impResult.duplicates_skipped} duplicates skipped · {impResult.errors.filter((e) => e.reason !== "duplicate").length} bad lines</p>
            {impResult.errors.slice(0, 10).map((e, i) => (
              <p key={i} className="text-zinc-500">line {e.line}: {e.reason} — <code>{e.text}</code></p>
            ))}
          </div>
        )}
      </Card>
      <Card>
        <CardTitle>Auto-pool sources (refreshed every 3h by beat)</CardTitle>
        <p className="mb-2 text-xs text-zinc-500">
          Public lists are low-trust by nature — fetched rows are health-checked like the rest, single-location
          policy applies at insert, and only long-dead auto rows are ever purged. Manual proxies are immortal.
          Pool location is enforced via Settings keys <code>pool_country</code> + <code>pool_require_country</code>.
        </p>
        <div className="grid gap-3 md:grid-cols-5">
          <Field label="Name"><input className="input" value={srcForm.name} onChange={(e) => setSrcForm({ ...srcForm, name: e.target.value })} placeholder="free-list-1" /></Field>
          <Field label="List URL (https txt)"><input className="input" value={srcForm.url} onChange={(e) => setSrcForm({ ...srcForm, url: e.target.value })} placeholder="https://…" /></Field>
          <Field label="Default protocol">
            <select className="input" value={srcForm.default_protocol} onChange={(e) => setSrcForm({ ...srcForm, default_protocol: e.target.value })}>
              <option value="http">http</option><option value="socks5">socks5</option><option value="socks4">socks4</option>
            </select>
          </Field>
          <Field label="Default country"><input className="input" value={srcForm.default_country} onChange={(e) => setSrcForm({ ...srcForm, default_country: e.target.value })} placeholder="DE" maxLength={2} /></Field>
          <div className="flex items-end"><button className="btn-primary w-full" disabled={!srcForm.name || !srcForm.url} onClick={() => { createSource.mutate({ url: "/proxies/sources", body: srcForm }); setSrcForm({ name: "", url: "", default_protocol: "http", default_country: "" }); }}>Add source</button></div>
        </div>
        <div className="mt-2 space-y-1">
          {((sourceRows ?? []) as ProxySource[]).map((s) => (
            <div key={s.id} className="flex flex-wrap items-center gap-2 border-t border-zinc-100 py-1.5 text-sm first:border-0 dark:border-zinc-800">
              <span className={`h-2 w-2 rounded-full ${s.is_active ? "bg-emerald-500" : "bg-zinc-400"}`} />
              <strong>{s.name}</strong>
              <span className="truncate text-xs text-zinc-500">{s.url} · {s.default_protocol}{s.default_country ? ` · ${s.default_country}` : ""}</span>
              <span className="text-xs text-zinc-500">last fetch: +{s.last_added}/{s.last_total}</span>
              <span className="ml-auto flex gap-2">
                <button className="btn-ghost !px-3 !py-1 text-xs" onClick={() => toggleSource.mutate({ url: `/proxies/sources/${s.id}`, body: { name: s.name, url: s.url, default_protocol: s.default_protocol, default_country: s.default_country, is_active: !s.is_active } })}>
                  {s.is_active ? "Disable" : "Enable"}
                </button>
                <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete source "${s.name}"? (Its proxies stay.)`)) removeSource.mutate({ url: `/proxies/sources/${s.id}` }); }}>Delete</button>
              </span>
            </div>
          ))}
        </div>
      </Card>
      {isLoading ? <Spinner /> : isError ? <QueryFailed onRetry={() => refetch()} /> : proxies.length === 0 ? <EmptyState title="No proxies" hint="Assign one proxy per IG account for best deliverability." /> : (
        <Card>
          {proxies.map((p) => (
            <div key={p.id} className="flex flex-wrap items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <span className={`h-2 w-2 rounded-full ${p.is_healthy ? "bg-emerald-500" : "bg-red-500"}`} />
              <code className="text-xs">{p.protocol}://{p.url.replace(/^https?:\/\//, "")}</code>
              <span className="text-zinc-500">{p.country ?? ""} · {p.latency_ms != null ? `${p.latency_ms}ms` : "—"} · fails {p.fail_count} · {p.source ?? "manual"}</span>
              {!p.is_active && <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-600 dark:bg-red-900/40">disabled</span>}
              {p.last_error && <span className="max-w-full truncate text-xs text-red-400" title={p.last_error}>· ⚠ {p.last_error.slice(0, 80)}</span>}
              <span className="ml-auto flex gap-2">
                <button className="btn-ghost !px-3 !py-1 text-xs" onClick={() => test.mutate({ url: `/proxies/${p.id}/test` })}>Test</button>
                <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm("Delete proxy?")) remove.mutate({ url: `/proxies/${p.id}` }); }}>Delete</button>
              </span>
            </div>
          ))}
          {test.data && <p className="mt-2 text-xs text-zinc-500">Last test: {JSON.stringify(test.data)}</p>}
        </Card>
      )}
      <p className="text-xs text-zinc-500">Assign a proxy to an account from the Accounts page (proxy_id). Health checks run every 30 minutes in oldest-first batches (fast TCP sweep, full verify for survivors) so posting never stalls. Results land live via realtime — no page switching needed. Unhealthy auto-fetched proxies are deleted automatically after the retention set in Settings → proxy → pool_purge_after_days (manual ones are never touched).</p>
    </div>
  );
}
