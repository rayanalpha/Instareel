"use client";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Account } from "@/types/models";

export function PhoneComposer({ account, effects, audios }: { account: Account; effects: string[]; audios: string[] }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [caption, setCaption] = useState("");
  const [hashtags, setHashtags] = useState("");
  const [effect, setEffect] = useState("");
  const [audio, setAudio] = useState("");
  const [isTrial, setIsTrial] = useState(false);
  const [busy, setBusy] = useState(false);
  const [step, setStep] = useState("");
  const [done, setDone] = useState("");
  const [error, setError] = useState("");

  async function publish() {
    if (!file || busy) return;
    setBusy(true);
    setStep("Uploading video…");
    setError("");
    setDone("");
    try {
      const form = new FormData();
      form.append("file", file);
      const { data: video } = await api.post("/videos/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 600000,
      });
      setStep("Saving settings…");
      await api.put(`/videos/${video.id}/settings`, {
        effect_preset: effect || null,
        audio_track: audio || null,
        is_trial: isTrial,
      });
      setStep("Scheduling post…");
      await api.post("/posts/schedule", {
        video_id: video.id,
        account_id: account.id,
        caption,
        hashtags,
        is_trial: isTrial,
      });
      setDone(`Queued as ${isTrial ? "trial reel" : "reel"} for @${account.username}`);
      setFile(null);
      setCaption("");
      setHashtags("");
      qc.invalidateQueries({ queryKey: ["videos"] });
      qc.invalidateQueries({ queryKey: ["posts"] });
      qc.invalidateQueries({ queryKey: ["queue"] });
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "Publish failed";
      setError(String(msg));
    } finally {
      setBusy(false);
      setStep("");
    }
  }

  return (
    <div className="flex h-full flex-col gap-2 overflow-y-auto p-3 text-sm">
      <p className="text-center font-bold">New reel · @{account.username}</p>
      <label className="rounded-xl border-2 border-dashed border-zinc-300 p-4 text-center text-zinc-500 dark:border-zinc-700">
        {file ? file.name : "Choose video"}
        <input type="file" className="hidden" accept="video/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      </label>
      <textarea className="input" rows={2} placeholder="Caption…" value={caption} onChange={(e) => setCaption(e.target.value)} />
      <input className="input" placeholder="#hashtags…" value={hashtags} onChange={(e) => setHashtags(e.target.value)} />
      <div className="grid grid-cols-2 gap-2">
        <select className="input" value={effect} onChange={(e) => setEffect(e.target.value)}>
          <option value="">Effect: auto</option>
          {effects.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        <select className="input" value={audio} onChange={(e) => setAudio(e.target.value)}>
          <option value="">Audio: auto</option>
          {audios.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
      </div>
      <label className="flex items-center gap-2 text-xs">
        <input type="checkbox" checked={isTrial} onChange={(e) => setIsTrial(e.target.checked)} />
        Trial reel (non-followers first)
      </label>
      {error && <p className="text-xs text-red-500">{error}</p>}
      {done && <p className="text-xs text-emerald-600">{done}</p>}
      <button className="btn-primary w-full" disabled={!file || busy} onClick={publish}>
        {busy ? step || "Publishing…" : "Share"}
      </button>
      <p className="text-[11px] text-zinc-500">Uploads, processes, and queues the post — the scheduler fires it at the next due slot.</p>
    </div>
  );
}
