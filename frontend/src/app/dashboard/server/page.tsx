"use client";
import { useEffect, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardTitle, QueryFailed, Spinner } from "@/components/ui";
import { useServerStats } from "@/hooks/use-api";

interface Sample {
  t: string;
  cpu: number;
  mem: number;
}

function fmtBytes(n: number): string {
  if (!n) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v >= 100 ? 0 : 1)} ${u[i]}`;
}

function fmtRate(bps: number): string {
  return `${fmtBytes(bps)}/s`;
}

function fmtUptime(s: number): string {
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

/** Emerald → amber → red load tone. */
function tone(pct: number): string {
  if (pct >= 90) return "bg-red-500";
  if (pct >= 70) return "bg-amber-500";
  return "bg-emerald-500";
}

function Bar({ pct }: { pct: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
      <div className={`h-full rounded-full transition-all ${tone(pct)}`} style={{ width: `${Math.min(100, pct)}%` }} />
    </div>
  );
}

export default function ServerPage() {
  const { data, isLoading, isError, refetch } = useServerStats();
  const [history, setHistory] = useState<Sample[]>([]);
  const prevNet = useRef<{ ts: number; sent: number; recv: number } | null>(null);
  const [rates, setRates] = useState({ down: 0, up: 0 });

  // Rolling ~5min window + per-second network rates from cumulative counters.
  useEffect(() => {
    if (!data) return;
    const label = new Date((data.ts ?? Date.now() / 1000) * 1000).toLocaleTimeString();
    setHistory((h) => [...h.slice(-59), { t: label, cpu: data.cpu.total, mem: data.mem.percent }]);
    const p = prevNet.current;
    const dt = p ? (data.ts ?? 0) - p.ts : 0;
    if (p && dt > 0) {
      setRates({
        down: Math.max(0, (data.net.recv - p.recv) / dt),
        up: Math.max(0, (data.net.sent - p.sent) / dt),
      });
    }
    prevNet.current = { ts: data.ts ?? Date.now() / 1000, sent: data.net.sent, recv: data.net.recv };
  }, [data]);

  if (isLoading) return <Spinner />;
  if (isError || !data) return <QueryFailed onRetry={() => refetch()} />;

  const containers = (data.containers ?? []) as {
    name: string; state: string; cpu: number; mem_used: number; mem_limit: number; mem_percent: number;
  }[];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Server</h1>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
          <span className="relative flex h-2 w-2">
            <span className="absolute h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
            <span className="h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          live · 5s
        </span>
        <span className="ml-auto text-xs text-zinc-500">uptime {fmtUptime(data.uptime_s)} · {data.cpu.count} cores</span>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <p className="text-2xl font-extrabold">{data.cpu.total}<span className="text-sm font-medium text-zinc-500"> %</span></p>
          <p className="mb-2 text-xs text-zinc-500">CPU · load {data.cpu.load1} {data.cpu.load5} {data.cpu.load15}</p>
          <div className="space-y-1">
            {(data.cpu.per_core ?? []).map((c: number, i: number) => (
              <div key={i} className="flex items-center gap-2">
                <span className="w-8 shrink-0 text-[10px] text-zinc-500">c{i}</span>
                <Bar pct={c} />
                <span className="w-10 shrink-0 text-right text-[10px] text-zinc-500">{c}%</span>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <p className="text-2xl font-extrabold">{data.mem.percent}<span className="text-sm font-medium text-zinc-500"> %</span></p>
          <p className="mb-2 text-xs text-zinc-500">RAM · {fmtBytes(data.mem.used)} / {fmtBytes(data.mem.total)}</p>
          <Bar pct={data.mem.percent} />
          <p className="mt-2 text-xs text-zinc-500">
            Swap {fmtBytes(data.mem.swap_used)} / {fmtBytes(data.mem.swap_total)}
            {data.mem.swap_total > 0 && ` (${data.mem.swap_percent}%)`}
          </p>
        </Card>
        <Card>
          <p className="text-2xl font-extrabold">{fmtRate(rates.down)}<span className="text-sm font-medium text-zinc-500"> ↓</span></p>
          <p className="mb-2 text-xs text-zinc-500">Network · ↑ {fmtRate(rates.up)}</p>
          <p className="text-xs text-zinc-500">total ↓ {fmtBytes(data.net.recv)} · ↑ {fmtBytes(data.net.sent)}</p>
          {(data.net.errin + data.net.errout) > 0 && (
            <p className="mt-1 text-xs text-amber-600">errors in/out: {data.net.errin}/{data.net.errout}</p>
          )}
        </Card>
        <Card>
          <CardTitle>Disk</CardTitle>
          <div className="space-y-3">
            {(data.disk ?? []).map((d: { mount: string; total: number; used: number; percent: number }) => (
              <div key={d.mount}>
                <div className="mb-1 flex items-baseline justify-between gap-2">
                  <span className="min-w-0 truncate text-xs font-medium" title={d.mount}>{d.mount}</span>
                  <span className="shrink-0 text-[11px] text-zinc-500">{fmtBytes(d.used)} / {fmtBytes(d.total)}</span>
                </div>
                <Bar pct={d.percent} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      <Card>
        <CardTitle>Load history · last ~5 min</CardTitle>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={history}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="t" tick={{ fontSize: 11 }} minTickGap={40} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, 100]} tickFormatter={(v: number) => `${v}%`} />
              <Tooltip />
              <Line type="monotone" dataKey="cpu" name="CPU %" stroke="#10b981" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="mem" name="RAM %" stroke="#6366f1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card>
        <CardTitle>Containers</CardTitle>
        {!data.docker ? (
          <p className="text-sm text-zinc-500">
            Per-container stats need the Docker socket: mount{" "}
            <code className="rounded bg-zinc-100 px-1 text-xs dark:bg-zinc-800">/var/run/docker.sock:/var/run/docker.sock:ro</code>{" "}
            on the backend service and rebuild.
          </p>
        ) : containers.length === 0 ? (
          <p className="text-sm text-zinc-500">No containers visible to the backend.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="text-left text-xs text-zinc-500">
                  <th className="py-1 pr-2 font-medium">Name</th>
                  <th className="py-1 pr-2 font-medium">State</th>
                  <th className="py-1 pr-2 font-medium">CPU</th>
                  <th className="py-1 font-medium">RAM</th>
                </tr>
              </thead>
              <tbody>
                {containers.map((c) => (
                  <tr key={c.name} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="max-w-[220px] truncate py-2 pr-2 font-medium" title={c.name}>{c.name}</td>
                    <td className="py-2 pr-2 text-xs text-zinc-500">{c.state}</td>
                    <td className="whitespace-nowrap py-2 pr-2 tabular-nums">{c.cpu}%</td>
                    <td className="min-w-[180px] py-2">
                      <div className="flex items-center gap-2">
                        <div className="flex-1"><Bar pct={c.mem_percent} /></div>
                        <span className="shrink-0 text-xs text-zinc-500">{fmtBytes(c.mem_used)}{c.mem_limit > 0 && ` / ${fmtBytes(c.mem_limit)}`}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
