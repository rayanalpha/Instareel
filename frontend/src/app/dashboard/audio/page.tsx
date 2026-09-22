"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Card, CardTitle, EmptyState, Field, QueryFailed, Spinner } from "@/components/ui";
import { useApiMutation, useAudioStats, useAudios } from "@/hooks/use-api";
import { api } from "@/lib/api";
import { toast } from "@/components/toast";
import type { AudioStats, AudioTrack } from "@/types/models";

export default function AudioPage() {
  const qc = useQueryClient();
  const { data, isLoading, isError, refetch } = useAudios();
  const { data: stats } = useAudioStats();
  const remove = useApiMutation("delete", [["audio"], ["audio-stats"]], "Track deleted");
  const toggle = useApiMutation("put", [["audio"], ["audio-stats"]], "Track updated");
  const [form, setForm] = useState({ name: "", description: "", music_volume: "0.4", duck_original: false });
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const tracks = (data ?? []) as AudioTrack[];
  const byName = new Map(((stats ?? []) as AudioStats[]).map((s) => [s.name, s]));

  async function upload() {
    if (!file) return;
    setBusy(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("name", form.name || file.name.replace(/\.[^.]+$/, ""));
      formData.append("description", form.description);
      formData.append("music_volume", form.music_volume);
      formData.append("duck_original", String(form.duck_original));
      await api.post("/audio/upload", formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 180000,
      });
      toast("success", "Track uploaded");
      setFile(null);
      setForm({ name: "", description: "", music_volume: "0.4", duck_original: false });
      qc.invalidateQueries({ queryKey: ["audio"] });
      qc.invalidateQueries({ queryKey: ["audio-stats"] });
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Upload failed";
      setError(String(msg));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Trending audio</h1>
      <p className="text-sm text-zinc-500">
        Sounds mixed into processed videos (original audio kept at full volume plus the track at your level —
        or the track alone when ducking is on). Picked automatically, least-used and best-performing first.
      </p>
      <Card>
        <CardTitle>New track</CardTitle>
        <div className="grid gap-3 md:grid-cols-4">
          <Field label="Audio file (MP3/WAV/M4A…)">
            <input type="file" className="input" accept="audio/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
          </Field>
          <Field label="Name"><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="From filename" /></Field>
          <Field label="Music level (0–2)"><input className="input" value={form.music_volume} onChange={(e) => setForm({ ...form, music_volume: e.target.value })} placeholder="0.4" /></Field>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.duck_original} onChange={(e) => setForm({ ...form, duck_original: e.target.checked })} />
              Duck original
            </label>
            <button className="btn-primary min-w-0 flex-1" disabled={!file || busy} onClick={upload}>{busy ? "Uploading…" : "Add"}</button>
          </div>
        </div>
        <div className="mt-3"><Field label="Description"><input className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Viral hook — 15s chorus" /></Field></div>
        {error && <p className="mt-2 break-words text-sm text-red-500">{error}</p>}
      </Card>
      {isLoading ? <Spinner /> : isError ? <QueryFailed onRetry={() => refetch()} /> : tracks.length === 0 ? <EmptyState title="No tracks" hint="Upload trending sounds above — processing auto-picks from active tracks." /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {tracks.map((t) => {
            const s = byName.get(t.name);
            return (
              <Card key={t.id}>
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <strong title={t.name} className="min-w-0 flex-1 truncate">{t.name}</strong>
                  <span className="shrink-0 text-xs text-zinc-500">{t.duration ? `${t.duration.toFixed(0)}s` : ""} · lvl {t.music_volume}{t.duck_original ? " · ducked" : ""}</span>
                  <span className="shrink-0 text-xs text-zinc-500">
                    {s ? `${s.posts} posts · ${s.avg_engagement}% eng. · ${s.views} views` : `used ${t.use_count}×`}
                  </span>
                </div>
                {t.description && <p className="mt-1 break-words text-sm text-zinc-500">{t.description}</p>}
                <div className="mt-2 flex flex-wrap gap-2">
                  <button
                    className="btn-ghost !py-1 text-xs"
                    disabled={toggle.isPending}
                    onClick={() => toggle.mutate({ url: `/audio/${t.id}`, body: { name: t.name, description: t.description, music_volume: t.music_volume, duck_original: t.duck_original, is_active: !t.is_active } })}
                  >
                    {toggle.isPending ? "Saving…" : t.is_active ? "Disable" : "Enable"}
                  </button>
                  <button className="btn-ghost mt-0 !py-1 text-xs text-red-500" disabled={remove.isPending} onClick={() => { if (confirm(`Delete "${t.name}"?`)) remove.mutate({ url: `/audio/${t.id}` }); }}>{remove.isPending ? "Deleting…" : "Delete"}</button>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
