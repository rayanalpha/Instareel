"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardTitle, EmptyState, Field, Spinner } from "@/components/ui";
import { useAccounts, useApiMutation, useBios } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { timeAgo } from "@/lib/utils";
import type { Account, Bio, IgProfile } from "@/types/models";

type Privacy = "" | "private" | "public";

export default function BiosPage() {
  const qc = useQueryClient();
  const { data, isLoading } = useBios();
  const { data: accounts } = useAccounts();
  const create = useApiMutation("post", [["bios"]]);
  const remove = useApiMutation("delete", [["bios"]]);
  const apply = useApiMutation("post", [["bios"]]);
  const [form, setForm] = useState({ account_id: "", text: "", link_url: "", full_name: "", privacy: "" as Privacy, rotation_interval_days: 14 });
  const [current, setCurrent] = useState<Record<number, IgProfile | null>>({});
  const [loadingCurrent, setLoadingCurrent] = useState<number | null>(null);
  const bios = (data ?? []) as Bio[];

  function privacyBody(p: Privacy) {
    return p === "" ? null : p === "private";
  }

  async function loadCurrent(id: number) {
    setLoadingCurrent(id);
    try {
      const { data } = await api.get(`/bios/${id}/current`);
      setCurrent((c) => ({ ...c, [id]: data as IgProfile }));
    } catch {
      setCurrent((c) => ({ ...c, [id]: null }));
    } finally {
      setLoadingCurrent(null);
    }
  }

  async function uploadPicture(id: number, file: File | null) {
    if (!file) return;
    const formData = new FormData();
    formData.append("file", file);
    await api.post(`/bios/${id}/picture`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000,
    });
    qc.invalidateQueries({ queryKey: ["bios"] });
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Profile rotation</h1>
      <p className="text-sm text-zinc-500">
        Bio text + link + full name + profile picture + privacy, applied together on rotation or Apply now.
        Empty fields are left untouched on Instagram.
      </p>
      <Card>
        <CardTitle>New profile config</CardTitle>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Account">
            <select className="input" value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}>
              <option value="">Select…</option>
              {((accounts ?? []) as Account[]).map((a) => <option key={a.id} value={a.id}>@{a.username}</option>)}
            </select>
          </Field>
          <Field label="Full name (optional)"><input className="input" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} placeholder="Brand Name" /></Field>
          <Field label="Link URL"><input className="input" value={form.link_url} onChange={(e) => setForm({ ...form, link_url: e.target.value })} placeholder="https://t.me/…" /></Field>
          <Field label="Privacy">
            <select className="input" value={form.privacy} onChange={(e) => setForm({ ...form, privacy: e.target.value as Privacy })}>
              <option value="">Leave as-is</option>
              <option value="private">Force private</option>
              <option value="public">Force public</option>
            </select>
          </Field>
        </div>
        <div className="mt-3 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <Field label="Bio text"><textarea className="input" rows={2} value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></Field>
          <div className="flex items-end gap-3">
            <Field label="Rotate every (days)"><input className="input" type="number" min={1} max={365} value={form.rotation_interval_days} onChange={(e) => setForm({ ...form, rotation_interval_days: Number(e.target.value) })} /></Field>
            <button className="btn-primary" disabled={!form.account_id || !form.text} onClick={() => { create.mutate({ url: "/bios", body: { account_id: Number(form.account_id), text: form.text, link_url: form.link_url, full_name: form.full_name, make_private: privacyBody(form.privacy), rotation_interval_days: form.rotation_interval_days } }); setForm({ account_id: "", text: "", link_url: "", full_name: "", privacy: "", rotation_interval_days: 14 }); }}>Add</button>
          </div>
        </div>
      </Card>
      {isLoading ? <Spinner /> : bios.length === 0 ? <EmptyState title="No profile configs" /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {bios.map((b) => (
            <Card key={b.id}>
              <p className="text-sm font-semibold">
                Account #{b.account_id} · every {b.rotation_interval_days}d · last applied {timeAgo(b.last_applied)}
              </p>
              {b.full_name && <p className="mt-1 text-sm font-medium">{b.full_name}</p>}
              <p className="mt-1 whitespace-pre-wrap text-sm">{b.text}</p>
              {b.link_url && <a href={b.link_url} target="_blank" className="text-sm text-sky-500 hover:underline">{b.link_url}</a>}
              <p className="mt-1 text-xs text-zinc-500">
                Privacy: {b.make_private === null || b.make_private === undefined ? "leave as-is" : b.make_private ? "private" : "public"}
                {" · "}Picture: {b.has_picture ? "set" : "none"}
              </p>
              {current[b.id] ? (
                <div className="mt-2 rounded bg-zinc-100 p-2 text-xs dark:bg-zinc-800">
                  <p className="font-semibold">Live on Instagram @{current[b.id]?.username} ({current[b.id]?.follower_count ?? "—"} followers):</p>
                  <p>{current[b.id]?.full_name} {current[b.id]?.is_private ? "🔒" : ""}</p>
                  <p className="whitespace-pre-wrap">{current[b.id]?.biography}</p>
                  {current[b.id]?.external_url && <p>{current[b.id]?.external_url}</p>}
                </div>
              ) : current[b.id] === null ? (
                <p className="mt-2 text-xs text-red-500">Could not read live profile (session/proxy issue).</p>
              ) : null}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <button className="btn-primary !py-1.5 text-xs" onClick={() => apply.mutate({ url: `/bios/${b.id}/apply` })}>Apply now</button>
                <button className="btn-ghost !py-1.5 text-xs" disabled={loadingCurrent === b.id} onClick={() => loadCurrent(b.id)}>
                  {loadingCurrent === b.id ? "Reading…" : "Compare live"}
                </button>
                <label className="btn-ghost cursor-pointer !py-1.5 text-xs">
                  {b.has_picture ? "Replace pic" : "Upload pic"}
                  <input type="file" className="hidden" accept="image/*" onChange={(e) => uploadPicture(b.id, e.target.files?.[0] ?? null)} />
                </label>
                <button className="btn-ghost !py-1.5 text-xs text-red-500" onClick={() => { if (confirm("Delete this profile config?")) remove.mutate({ url: `/bios/${b.id}` }); }}>Delete</button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
