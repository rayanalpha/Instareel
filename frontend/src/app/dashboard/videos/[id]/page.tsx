"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { Card, CardTitle, EmptyState, Field, Spinner, StatusBadge } from "@/components/ui";
import { LivePreview } from "@/components/live-preview";
import { useApiMutation, useAudios, useEffects } from "@/hooks/use-api";

interface Detail {
  id: number; original_filename: string; duration: number | null; status: string;
  effect_preset: string | null; audio_track: string | null; is_trial: boolean;
  trial_strategy: string; add_watermark: boolean;
  trim_start: number | null; trim_end: number | null; failed_reason: string | null;
  custom_thumbnail_path: string | null;
}

// Terminal states: nothing left to wait for — stop polling.
const DONE_STATES = new Set(["processed", "posted", "failed", "archived"]);

export default function VideoDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [video, setVideo] = useState<Detail | null>(null);
  const [progress, setProgress] = useState<{ percentage: number; stage: string } | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState("");
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);
  const [thumbBusy, setThumbBusy] = useState(false);
  const [form, setForm] = useState({ effect_preset: "", audio_track: "", is_trial: false, trial_strategy: "manual", trim_start: "", trim_end: "", add_watermark: true });
  const { data: effects } = useEffects();
  const { data: audios } = useAudios();
  const save = useApiMutation("put", [["videos"]]);
  const process = useApiMutation("post", [["videos"]]);
  const postNow = useApiMutation("post", [["videos"], ["posts"], ["queue"]]);
  const [nowPostId, setNowPostId] = useState<number | null>(null);
  const [nowState, setNowState] = useState<{ status: string; url?: string; error?: string } | null>(null);

  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  async function load() {
    const { data } = await api.get(`/videos/${id}`);
    setLoadError("");
    setVideo(data);
    setForm({
      effect_preset: data.effect_preset ?? "",
      audio_track: data.audio_track ?? "",
      is_trial: data.is_trial ?? false,
      trial_strategy: data.trial_strategy ?? "manual",
      trim_start: data.trim_start?.toString() ?? "",
      trim_end: data.trim_end?.toString() ?? "",
      add_watermark: data.add_watermark,
    });
    try {
      const s = await api.get(`/videos/${id}/status`);
      setProgress(s.data.progress);
    } catch { /* ignore */ }
    return data as Detail;
  }

  // Poll only while the video is in a transitional state; stop on error.
  // Guarded against overlap: a slow load() never piles up concurrent polls.
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;
    let inflight = false;
    const stop = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };
    const tick = async () => {
      if (inflight || cancelled) return;
      inflight = true;
      try {
        const cur = await load();
        if (DONE_STATES.has(cur.status)) stop();
      } catch {
        if (!cancelled) {
          setLoadError("Failed to load video — retrying stopped.");
          stop();
        }
      } finally {
        inflight = false;
      }
    };
    (async () => {
      try {
        const v = await load();
        if (!cancelled && !DONE_STATES.has(v.status)) {
          timer = setInterval(tick, 4000);
        }
      } catch {
        if (!cancelled) setLoadError("Failed to load video.");
      }
    })();
    return () => {
      cancelled = true;
      stop();
    };
    /* eslint-disable-next-line */
  }, [id]);

  // Fetch the preview through the same-origin /api proxy as a blob —
  // <video> tags can't send the Authorization header, and cross-origin
  // media requests get blocked by Chrome's ORB.
  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setPreviewUrl(null);
    setPreviewError("");
    (async () => {
      try {
        const res = await api.get(`/videos/${id}/preview`, {
          responseType: "blob",
          timeout: 120000,
        });
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setPreviewUrl(objectUrl);
      } catch (e: unknown) {
        if (!cancelled) {
          const status = (e as { response?: { status?: number } })?.response?.status;
          setPreviewError(status === 404 ? "No preview file yet — process the video first." : "Preview failed to load.");
        }
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, video?.status]);

  // Cover thumbnail: same-origin blob fetch (auth header), like the preview.
  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    setThumbUrl(null);
    (async () => {
      try {
        const res = await api.get(`/videos/${id}/thumbnail`, { responseType: "blob", timeout: 60000 });
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setThumbUrl(objectUrl);
      } catch { /* no thumbnail yet — upload one below */ }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, video?.custom_thumbnail_path, video?.status]);

  async function uploadThumb(file: File | null) {
    if (!file) return;
    setThumbBusy(true);
    setActionError("");
    try {
      const form = new FormData();
      form.append("file", file);
      await api.post(`/videos/${id}/thumbnail`, form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 120000,
      });
      await load();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Cover upload failed";
      setActionError(String(msg));
    } finally {
      setThumbBusy(false);
    }
  }

  async function removeThumb() {
    setThumbBusy(true);
    setActionError("");
    try {
      await api.delete(`/videos/${id}/thumbnail`);
      await load();
    } catch {
      setActionError("Could not remove cover.");
    } finally {
      setThumbBusy(false);
    }
  }
  // Live status for a Post-now request: poll until a terminal post state.
  useEffect(() => {
    if (!nowPostId) return;
    let timer: ReturnType<typeof setInterval> | null = null;
    let cancelled = false;
    const stop = () => {
      if (timer) {
        clearInterval(timer);
        timer = null;
      }
    };
    const poll = async () => {
      try {
        const { data } = await api.get(`/posts/${nowPostId}`);
        if (cancelled) return;
        if (data.status === "posted" || data.status === "failed") {
          stop();
          setNowState({ status: data.status, url: data.ig_permalink ?? undefined, error: data.fail_reason ?? undefined });
          load();
        } else {
          setNowState({ status: data.status });
        }
      } catch {
        if (!cancelled) {
          stop();
          setNowState({ status: "failed", error: "status check failed" });
        }
      }
    };
    poll();
    timer = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      stop();
    };
    /* eslint-disable-next-line */
  }, [nowPostId]);

  if (loadError) return <EmptyState title="Load failed" hint={loadError} />;
  if (!video) return <Spinner />;

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card>
          <div className="mb-2 flex min-w-0 items-center gap-2">
            <div className="min-w-0 flex-1 truncate" title={video.original_filename}><CardTitle>#{video.id} · {video.original_filename}</CardTitle></div>
          <span className="shrink-0"><StatusBadge status={video.status} /></span>
        </div>
        {previewUrl ? (
          <LivePreview
            key={`${video.status}-${form.effect_preset}-${form.add_watermark}`}
            src={previewUrl}
            effectName={form.effect_preset}
            watermark={form.add_watermark}
          />
        ) : (
          <div className="flex aspect-[9/16] max-h-[560px] items-center justify-center rounded-lg bg-zinc-100 text-sm text-zinc-500 dark:bg-zinc-800">
            {previewError || "Loading preview…"}
          </div>
        )}
        <p className="mt-2 text-xs text-zinc-500">Preview shows the selected effect (CSS approximation) and watermark overlay live.</p>
        <div className="mt-3 rounded-lg border border-zinc-200 p-2 dark:border-zinc-800">
          <div className="flex items-center gap-2">
            {thumbUrl ? (
              <img src={thumbUrl} alt="cover" className="h-20 w-11 shrink-0 rounded object-cover" />
            ) : (
              <div className="flex h-20 w-11 shrink-0 items-center justify-center rounded bg-zinc-100 text-[10px] text-zinc-400 dark:bg-zinc-800">no cover</div>
            )}
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold">
                Cover {video.custom_thumbnail_path
                  ? <span className="text-emerald-500">· custom</span>
                  : <span className="text-zinc-400">· auto frame</span>}
              </p>
              <p className="text-[11px] text-zinc-500">Posted as the reel cover. Custom wins over the auto frame.</p>
            </div>
          </div>
            <div className="mt-2 flex flex-wrap gap-2">
            <label className="btn-ghost cursor-pointer !py-1.5 text-xs">
              {thumbBusy ? "Uploading…" : video.custom_thumbnail_path ? "Replace" : "Upload cover"}
              <input
                type="file" className="hidden" accept="image/jpeg,image/png,image/webp"
                disabled={thumbBusy}
                onChange={(e) => { uploadThumb(e.target.files?.[0] ?? null); e.target.value = ""; }}
              />
            </label>
            {video.custom_thumbnail_path && (
              <button className="btn-ghost !py-1.5 text-xs text-red-500" disabled={thumbBusy} onClick={removeThumb}>
                Revert to auto
              </button>
            )}
          </div>
        </div>
        {video.status === "processing" && (
          <div className="mt-3">
            <div className="h-2 overflow-hidden rounded-full bg-zinc-200 dark:bg-zinc-800">
              <div className="h-full bg-emerald-500 transition-all" style={{ width: `${progress?.percentage ?? 5}%` }} />
            </div>
            <p title={typeof progress?.stage === "string" ? progress.stage : undefined} className="mt-1 truncate text-xs text-zinc-500">{progress?.stage ?? "processing"} · {(progress?.percentage ?? 0).toFixed(0)}%</p>
          </div>
        )}
        {video.status === "uploaded" && (
          <button
            className="btn-primary mt-3 w-full"
            disabled={process.isPending}
            onClick={async () => {
              setActionError("");
              try {
                await process.mutateAsync({ url: `/videos/${id}/process` });
                load();
              } catch {
                setActionError("Could not queue processing.");
              }
            }}
          >
            {process.isPending ? "Queuing…" : "Start processing"}
          </button>
        )}
        {actionError && <p className="mt-2 break-words text-sm text-red-500">{actionError}</p>}
        {video.status === "failed" && video.failed_reason && (
          <div className="mt-2 rounded-lg border border-red-500 bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            <p className="font-semibold">Processing failed</p>
            <p className="mt-1 break-all">{video.failed_reason}</p>
          </div>
        )}
        {video.status === "processed" && (
          <div className="mt-2 rounded-lg border border-emerald-500 bg-emerald-50 p-3 text-sm text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
            <span className="font-semibold">Processed —</span> preview is ready and Post now is unlocked below.
          </div>
        )}
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
          <Field label="Trending audio">
            <select className="input" value={form.audio_track} onChange={(e) => setForm({ ...form, audio_track: e.target.value })}>
              <option value="">Auto (best least-used track)</option>
              {((audios ?? []) as { name: string; description: string }[]).map((a) => (
                <option key={a.name} value={a.name}>{a.name} — {a.description.slice(0, 60)}</option>
              ))}
            </select>
          </Field>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
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
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={form.is_trial} onChange={(e) => setForm({ ...form, is_trial: e.target.checked })} />
              Trial reel
            </label>
            {form.is_trial && (
              <select className="input !w-auto max-w-full !py-1 text-xs" value={form.trial_strategy} onChange={(e) => setForm({ ...form, trial_strategy: e.target.value })}>
                <option value="manual">graduate manually</option>
                <option value="auto">graduate automatically</option>
              </select>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              className="btn-primary min-w-0 flex-1"
              disabled={save.isPending}
              onClick={async () => {
                setActionError("");
                try {
                  await save.mutateAsync({
                    url: `/videos/${id}/settings`,
                    body: {
                      effect_preset: form.effect_preset || null,
                      audio_track: form.audio_track || null,
                      is_trial: form.is_trial,
                      trial_strategy: form.trial_strategy,
                      trim_start: form.trim_start ? Number(form.trim_start) : null,
                      trim_end: form.trim_end ? Number(form.trim_end) : null,
                      add_watermark: form.add_watermark,
                    },
                  });
                  load();
                } catch {
                  setActionError("Could not save settings.");
                }
              }}
            >
              Save settings
            </button>
            <button
              className="btn-ghost min-w-0 flex-1"
              disabled={process.isPending}
              onClick={async () => {
                setActionError("");
                try {
                  await process.mutateAsync({ url: `/videos/${id}/reprocess` });
                  load();
                } catch {
                  setActionError("Could not queue re-processing.");
                }
              }}
            >
              Re-process
            </button>
          </div>
          {video.status === "processed" && (
            <div className="mt-2">
              <button
                className="btn-primary w-full"
                disabled={postNow.isPending || nowState?.status === "scheduled" || nowState?.status === "posting"}
                onClick={async () => {
                  setNowState(null);
                  setActionError("");
                  try {
                    const res = await postNow.mutateAsync({
                      url: "/posts/schedule",
                      body: { video_id: Number(id), is_trial: form.is_trial },
                    });
                    setNowPostId((res as { id: number }).id);
                    setNowState({ status: "scheduled" });
                  } catch {
                    setActionError("Could not schedule post (already queued?).");
                  }
                }}
              >
                {postNow.isPending ? "Queuing…" : "Post now"}
              </button>
              {nowState && (
                <p className="mt-1 text-xs text-zinc-500">
                  {nowState.status === "posted" && nowState.url ? (
                    <a className="text-emerald-500 hover:underline" href={nowState.url} target="_blank">Posted — open reel ↗</a>
                  ) : nowState.status === "failed" ? (
                    <span className="break-words text-red-500">Failed: {nowState.error ?? "see Posts"}</span>
                  ) : (
                    <>Posting… ({nowState.status})</>
                  )}
                </p>
              )}
              <p className="mt-1 text-xs text-zinc-500">Schedules for now — the per-minute beat fires it, then live status shows here.</p>
            </div>
          )}
          <p className="text-xs text-zinc-500">Output: 720×1280 H.264 + loudnorm audio, thumbnail at 25% duration.</p>
        </div>
      </Card>
    </div>
  );
}
