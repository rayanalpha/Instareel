"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, apiBase } from "@/lib/api";
import { Card, CardTitle, Field, Spinner, StatusBadge } from "@/components/ui";
import { LivePreview } from "@/components/live-preview";
import { useApiMutation, useEffects } from "@/hooks/use-api";

interface Detail {
  id: number; original_filename: string; duration: number | null; status: string;
  effect_preset: string | null; add_watermark: boolean; trim_start: number | null;
  trim_end: number | null; failed_reason: string | null;
}

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [video, setVideo] = useState<Detail | null>(null);
  const [progress, setProgress] = useState<{ percentage: number; stage: string } | null>(null);
  const [form, setForm] = useState({ effect_preset: "", trim_start: "", trim_end: "", add_watermark: true });
  const { data: effects } = useEffects();
  const save = useApiMutation("put", [["videos"]]);
  const process = useApiMutation("post", [["videos"]]);

  async function load() {
    const { data } = await api.get(`/videos/${id}`);
    setVideo(data);
    setForm({
      effect_preset: data.effect_preset ?? "",
      trim_start: data.trim_start?.toString() ?? "",
      trim_end: data.trim_end?.toString() ?? "",
      add_watermark: data.add_watermark,
    });
    try {
      const s = await api.get(`/videos/${id}/status`);
      setProgress(s.data.progress);
    } catch { /* ignore */ }
  }

  useEffect(() => { load(); const t = setInterval(load, 4000); return () => clearInterval(t); /* eslint-disable-next-line */ }, [id]);

  if (!video) return <Spinner />;

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
        <div className="mb-2 flex items-center gap-2">
          <CardTitle>#{video.id} · {video.original_filename}</CardTitle>
          <StatusBadge status={video.status} />
        </div>
        <LivePreview
          key={`${video.status}-${form.effect_preset}-${form.add_watermark}`}
          src={`${apiBase()}/api/v1/videos/${id}/preview`}
          effectName={form.effect_preset}
          watermark={form.add_watermark}
        />
        <p className="mt-2 text-xs text-zinc-500">Preview shows the selected effect (CSS approximation) and watermark overlay live.</p>
        {video.status === "processing" && (
          <div className="mt-3">
            <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
              <div className="h-full bg-emerald-500 transition-all" style={{ width: `${progress?.percentage ?? 5}%` }} />
            </div>
            <p className="mt-1 text-xs text-zinc-500">{progress?.stage ?? "processing"} · {(progress?.percentage ?? 0).toFixed(0)}%</p>
          </div>
        )}
        {video.failed_reason && <p className="mt-2 text-sm text-red-500">{video.failed_reason}</p>}
      </Card>

      <Card>
        <CardTitle>Processing settings</CardTitle>
        <div className="space-y-3">
          <Field label="Effect preset">
            <select className="input" value={form.effect_preset} onChange={(e) => setForm({ ...form, effect_preset: e.target.value })}>
              <option value="">Auto (random active preset)</option>
              {((effects ?? []) as { name: string; description: string }[]).map((e) => (
                <option key={e.name} value={e.name}>{e.name} — {e.description.slice(0, 60)}</option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Trim start (s)">
              <input className="input" type="number" min={0} step={0.5} value={form.trim_start} onChange={(e) => setForm({ ...form, trim_start: e.target.value })} />
            </Field>
            <Field label="Trim end (s)">
              <input className="input" type="number" min={0} step={0.5} value={form.trim_end} onChange={(e) => setForm({ ...form, trim_end: e.target.value })} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={form.add_watermark} onChange={(e) => setForm({ ...form, add_watermark: e.target.checked })} />
            Add watermark overlay
          </label>
          <div className="flex gap-2">
            <button
              className="btn-primary flex-1"
              disabled={save.isPending}
              onClick={async () => {
                await save.mutateAsync({
                  url: `/videos/${id}/settings`,
                  body: {
                    effect_preset: form.effect_preset || null,
                    trim_start: form.trim_start ? Number(form.trim_start) : null,
                    trim_end: form.trim_end ? Number(form.trim_end) : null,
                    add_watermark: form.add_watermark,
                  },
                });
                load();
              }}
            >
              Save settings
            </button>
            <button
              className="btn-ghost flex-1"
              disabled={process.isPending}
              onClick={async () => { await process.mutateAsync({ url: `/videos/${id}/reprocess` }); load(); }}
            >
              Re-process
            </button>
          </div>
          <p className="text-xs text-zinc-500">Output: 720×1280 H.264 + loudnorm audio, thumbnail at 25% duration.</p>
        </div>
      </Card>
    </div>
  );
}
