"use client";
import { Fragment, useState } from "react";
import { Card, CardTitle, EmptyState, Field, QueryFailed, Spinner } from "@/components/ui";
import { useAccounts, useApiMutation, useCaptions, useEffects, useRules } from "@/hooks/use-api";
import { dayLabel } from "@/lib/utils";
import type { Account, Caption, Effect, ScheduleRule } from "@/types/models";

const HOURS = Array.from({ length: 24 }, (_, h) => h);

export default function SchedulePage() {
  const { data: rules, isLoading, isError, refetch } = useRules();
  const { data: accounts } = useAccounts();
  const { data: captions } = useCaptions();
  const { data: effects } = useEffects();
  const create = useApiMutation("post", [["rules"]]);
  const remove = useApiMutation("delete", [["rules"]]);
  const toggle = useApiMutation("post", [["rules"]]);
  const [form, setForm] = useState({ name: "", day_of_week: -1, hour: 12, minute: 0, account_id: "", preferred_effect: "", caption_template_id: "" });
  const list = (rules ?? []) as ScheduleRule[];

  function submit() {
    create.mutate({
      url: "/schedule",
      body: {
        name: form.name || `${dayLabel(form.day_of_week)} ${form.hour}:${String(form.minute).padStart(2, "0")}`,
        day_of_week: form.day_of_week, hour: form.hour, minute: form.minute,
        account_id: form.account_id ? Number(form.account_id) : null,
        preferred_effect: form.preferred_effect || null,
        caption_template_id: form.caption_template_id ? Number(form.caption_template_id) : null,
      },
    });
    setForm({ name: "", day_of_week: -1, hour: 12, minute: 0, account_id: "", preferred_effect: "", caption_template_id: "" });
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Posting schedule</h1>

      <Card>
        <CardTitle>Weekly calendar</CardTitle>
        <div className="grid grid-cols-8 gap-1 text-center text-xs">
          <div />
          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d} className="font-semibold text-zinc-500">{d}</div>)}
          {HOURS.filter((h) => list.some((r) => r.hour === h)).map((h) => (
            <Fragment key={`row-${h}`}>
              <div className="pr-1 text-right text-zinc-400">{h}:00</div>
              {[0, 1, 2, 3, 4, 5, 6].map((d) => {
                const hits = list.filter((r) => r.hour === h && (r.day_of_week === -1 || r.day_of_week === d));
                return (
                  <div key={`${h}-${d}`} className="min-h-6 rounded bg-zinc-100 px-1 dark:bg-zinc-800">
                    {hits.map((r) => (
                      <span key={r.id} className={`mr-0.5 inline-block h-2 w-2 rounded-full ${r.is_active ? "bg-emerald-500" : "bg-zinc-400"}`} title={r.name} />
                    ))}
                  </div>
                );
              })}
            </Fragment>
          ))}
        </div>
        {list.length === 0 && !isLoading && <p className="mt-2 text-sm text-zinc-500">No rules yet — every active hour shows here once added.</p>}
      </Card>

      <Card>
        <CardTitle>New rule</CardTitle>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Name"><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="auto" /></Field>
          <Field label="Day">
            <select className="input" value={form.day_of_week} onChange={(e) => setForm({ ...form, day_of_week: Number(e.target.value) })}>
              <option value={-1}>Every day</option>
              {[0, 1, 2, 3, 4, 5, 6].map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}
            </select>
          </Field>
          <Field label="Hour"><input className="input" type="number" min={0} max={23} value={form.hour} onChange={(e) => setForm({ ...form, hour: Number(e.target.value) })} /></Field>
          <Field label="Minute"><input className="input" type="number" min={0} max={59} value={form.minute} onChange={(e) => setForm({ ...form, minute: Number(e.target.value) })} /></Field>
          <Field label="Account">
            <select className="input" value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Auto-select</option>
              {((accounts ?? []) as Account[]).map((a) => <option key={a.id} value={a.id}>@{a.username}</option>)}
            </select>
          </Field>
          <Field label="Effect">
            <select className="input" value={form.preferred_effect} onChange={(e) => setForm({ ...form, preferred_effect: e.target.value })}>
              <option value="">Any</option>
              {((effects ?? []) as Effect[]).map((e) => <option key={e.name} value={e.name}>{e.name}</option>)}
            </select>
          </Field>
          <Field label="Caption template">
            <select className="input" value={form.caption_template_id} onChange={(e) => setForm({ ...form, caption_template_id: e.target.value })}>
              <option value="">Random</option>
              {((captions ?? []) as Caption[]).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </Field>
          <div className="flex items-end"><button className="btn-primary w-full" onClick={submit} disabled={create.isPending}>Add rule</button></div>
        </div>
      </Card>

      {isLoading ? <Spinner /> : isError ? <QueryFailed onRetry={() => refetch()} /> : list.length === 0 ? <EmptyState title="No schedule rules" /> : (
        <Card>
          {list.map((r) => (
            <div key={r.id} className="flex flex-wrap items-center gap-2 border-t border-zinc-100 py-2 text-sm first:border-0 dark:border-zinc-800">
              <strong>{r.name}</strong>
              <span className="text-zinc-500">{dayLabel(r.day_of_week)} · {r.hour}:{String(r.minute).padStart(2, "0")}</span>
              <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${r.is_active ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300" : "bg-zinc-200 text-zinc-500"}`}>
                {r.is_active ? "active" : "paused"}
              </span>
              <span className="ml-auto flex gap-2">
                <button className="btn-ghost !px-3 !py-1 text-xs" onClick={() => toggle.mutate({ url: `/schedule/${r.id}/toggle` })}>Toggle</button>
                <button className="btn-ghost !px-3 !py-1 text-xs text-red-500" onClick={() => { if (confirm(`Delete rule "${r.name}"?`)) remove.mutate({ url: `/schedule/${r.id}` }); }}>Delete</button>
              </span>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}
