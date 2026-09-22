"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { UploadCloud } from "lucide-react";
import { Card, Field } from "@/components/ui";
import { LivePreview } from "@/components/live-preview";
import { useAudios, useEffects } from "@/hooks/use-api";

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [effect, setEffect] = useState("");
  const [audio, setAudio] = useState("");
  const [isTrial, setIsTrial] = useState(false);
  const [watermark, setWatermark] = useState(true);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [thumb, setThumb] = useState<File | null>(null);
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [drag, setDrag] = useState(false);
  const router = useRouter();
  const { data: effects } = useEffects();
  const { data: audios } = useAudios();

  useEffect(() => {
    if (!file) {
      setObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  useEffect(() => {
    if (!thumb) {
      setThumbUrl(null);
      return;
    }
    const url = URL.createObjectURL(thumb);
    setThumbUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [thumb]);

  async function upload() {
    if (!file) return;
    setBusy(true);
    setProgress(0);
    setError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const { data } = await api.post(`/videos/upload`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 600000,
        onUploadProgress: (e) => {
          if (e.total) setProgress(Math.round((e.loaded * 100) / e.total));
        },
      });
      // Persist the preview choices as the video's processing settings.
      try {
        await api.put(
          `/videos/${data.id}/settings`,
          {
            effect_preset: effect || null,
            audio_track: audio || null,
            is_trial: isTrial,
            add_watermark: watermark,
          },
        );
      } catch {
        /* settings save is best-effort; processing still proceeds */
      }
      // Custom cover is best-effort too — the auto frame still works.
      if (thumb) {
        try {
          const tf = new FormData();
          tf.append("file", thumb);
          await api.post(`/videos/${data.id}/thumbnail`, tf, {
            headers: { "Content-Type": "multipart/form-data" },
            timeout: 120000,
          });
        } catch {
          /* ignore */
        }
      }
      router.push(`/dashboard/videos/${data.id}`);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Upload failed";
      setError(String(msg));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <h1 className="text-xl font-extrabold tracking-tight">Upload video</h1>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <div
            role="button"
            tabIndex={0}
            aria-label="Choose a video file"
            onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => { e.preventDefault(); setDrag(false); setFile(e.dataTransfer.files?.[0] ?? null); }}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") document.getElementById("video-file-input")?.click(); }}
            className={`flex min-w-0 flex-col items-center gap-3 rounded-xl border-2 border-dashed p-6 text-center transition sm:p-10 ${drag ? "border-emerald-500 bg-emerald-500/5" : "border-zinc-300 dark:border-zinc-700"}`}
          >
            <UploadCloud className="h-10 w-10 text-zinc-400" />
            <p className="text-sm text-zinc-500">Drag & drop a video here, or</p>
            <label className="btn-ghost cursor-pointer">
              Choose file
              <input
                id="video-file-input" type="file" className="hidden" accept="video/*"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
            </label>
            {file && <p title={file.name} className="max-w-full break-all text-sm font-medium">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</p>}
          </div>
          <div className="mt-4 space-y-3">
            <Field label="Effect preset (live preview)">
              <select className="input" value={effect} onChange={(e) => setEffect(e.target.value)}>
                <option value="">Auto (random active preset)</option>
                {((effects ?? []) as { name: string; description: string }[]).map((e) => (
                  <option key={e.name} value={e.name}>{e.name}</option>
                ))}
              </select>
            </Field>
            <Field label="Trending audio (mixed in at processing)">
              <select className="input" value={audio} onChange={(e) => setAudio(e.target.value)}>
                <option value="">Auto (best least-used track)</option>
                {((audios ?? []) as { name: string; description: string }[]).map((a) => (
                  <option key={a.name} value={a.name}>{a.name}</option>
                ))}
              </select>
            </Field>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={watermark} onChange={(e) => setWatermark(e.target.checked)} />
              Watermark overlay (bottom-right, as in output)
            </label>
            <label className="flex items-center gap-2 text-sm" title="Show to non-followers first (explore engine). Falls back to a regular reel if Instagram rejects trial.">
              <input type="checkbox" checked={isTrial} onChange={(e) => setIsTrial(e.target.checked)} />
              Trial reel (non-followers first)
            </label>
            <Field label="Custom cover (optional — else auto frame at 25%)">
              <div className="flex min-w-0 flex-wrap items-center gap-2">
                {thumbUrl && <img src={thumbUrl} alt="cover" className="h-16 w-9 shrink-0 rounded object-cover" />}
                <label className="btn-ghost cursor-pointer !py-1.5 text-xs">
                  {thumb ? "Change" : "Choose image"}
                  <input
                    type="file" className="hidden" accept="image/jpeg,image/png,image/webp"
                    onChange={(e) => setThumb(e.target.files?.[0] ?? null)}
                  />
                </label>
                {thumb && <button className="btn-ghost !py-1.5 text-xs text-red-500" onClick={() => setThumb(null)}>Clear</button>}
              </div>
            </Field>
          </div>
          {error && <p className="mt-3 break-words text-sm text-red-500">{error}</p>}
          <button className="btn-primary mt-4 w-full" disabled={!file || busy} onClick={upload}>
            {busy ? `Uploading… ${progress}%` : "Upload & process"}
          </button>
          <p className="mt-2 text-xs text-zinc-500">MP4/MOV/MKV/WebM/AVI up to the MAX_UPLOAD_MB limit. Duplicate files are rejected by content hash.</p>
        </Card>

        <Card>
          <p className="mb-2 text-sm font-semibold">Live preview</p>
          {objectUrl ? (
            <>
              <LivePreview src={objectUrl} effectName={effect} watermark={watermark} />
              <p className="mt-2 text-xs text-zinc-500">
                Effect is a CSS approximation; the real FFmpeg filter runs during processing. Watermark matches the backend 120px / 20px overlay.
              </p>
            </>
          ) : (
            <div className="flex aspect-[9/16] max-h-[560px] items-center justify-center rounded-lg bg-zinc-100 text-sm text-zinc-500 dark:bg-zinc-800">
              Select a file to preview it here
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
