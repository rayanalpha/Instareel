"use client";
import { useState } from "react";
import { Card, CardTitle, EmptyState, Field, Spinner } from "@/components/ui";
import { useAccounts, useApiMutation, useBios } from "@/hooks/use-api";
import { timeAgo } from "@/lib/utils";
import type { Account, Bio } from "@/types/models";

export default function BiosPage() {
  const { data, isLoading } = useBios();
  const { data: accounts } = useAccounts();
  const create = useApiMutation("post", [["bios"]]);
  const remove = useApiMutation("delete", [["bios"]]);
  const apply = useApiMutation("post", [["bios"]]);
  const [form, setForm] = useState({ account_id: "", text: "", link_url: "", rotation_interval_days: 14 });
  const bios = (data ?? []) as Bio[];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Bio rotation</h1>
      <Card>
        <CardTitle>New bio config</CardTitle>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Account">
            <select className="input" value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Select…</option>
              {((accounts ?? []) as Account[]).map((a) => <option key={a.id} value={a.id}>@{a.username}</option>)}
            </select>
          </Field>
          <Field label="Link URL"><input className="input" value={form.link_url} onChange={(e) => setForm({ ...form, link_url: e.target.value })} placeholder="https://t.me/…" /></Field>
          <Field label="Rotate every (days)"><input className="input" type="number" min={1} max={365} value={form.rotation_interval_days} onChange={(e) => setForm({ ...form, rotation_interval_days: Number(e.target.value) })} /></Field>
          <div className="flex items-end"><button className="btn-primary w-full" disabled={!form.account_id || !form.text} onClick={() => { create.mutate({ url: "/bios", body: { ...form, account_id: Number(form.account_id) } }); setForm({ account_id: "", text: "", link_url: "", rotation_interval_days: 14 }); }}>Add</button></div>
        </div>
        <div className="mt-3"><Field label="Bio text"><textarea className="input" rows={2} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></Field></div>
      </Card>
      {isLoading ? <Spinner /> : bios.length === 0 ? <EmptyState title="No bio configs" /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {bios.map((b) => (
            <Card key={b.id}>
              <p className="text-sm font-semibold">Account #{b.account_id} · every {b.rotation_interval_days}d · last applied {timeAgo(b.last_applied)}</p>
              <p className="mt-2 whitespace-pre-wrap text-sm">{b.text}</p>
              {b.link_url && <a href={b.link_url} target="_blank" className="text-sm text-sky-500 hover:underline">{b.link_url}</a>}
              <div className="mt-2 flex gap-2">
                <button className="btn-primary !py-1.5 text-xs" onClick={() => apply.mutate({ url: `/bios/${b.id}/apply` })}>Apply now</button>
                <button className="btn-ghost !py-1.5 text-xs text-red-500" onClick={() => { if (confirm("Delete this bio?")) remove.mutate({ url: `/bios/${b.id}` }); }}>Delete</button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
