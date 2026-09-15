"use client";
import Link from "next/link";
import { useState } from "react";
import { Plus } from "lucide-react";
import { Card, EmptyState, Spinner, StatusBadge } from "@/components/ui";
import { useApiMutation, useVideos } from "@/hooks/use-api";
import { timeAgo } from "@/lib/utils";
import type { Video } from "@/types/models";

export default function VideosPage() {
  const [status, setStatus] = useState("");
  const { data, isLoading } = useVideos(status);
  const del = useApiMutation("delete", [[ "videos" ]]);
  const process = useApiMutation("post", [["videos"]]);
  const videos = (data ?? []) as Video[];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Videos</h1>
        <div className="ml-auto flex gap-2">
          <select className="input !w-auto" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            {["uploaded", "processing", "processed", "posting", "posted", "failed", "archived"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <Link href="/dashboard/videos/upload" className="btn-primary"><Plus className="h-4 w-4" /> Upload</Link>
        </div>
      </div>
      {isLoading ? <Spinner /> : videos.length === 0 ? (
        <EmptyState title="No videos" hint="Upload your first video to start the funnel." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {videos.map((v) => (
            <Card key={v.id}>
              <div className="mb-2 flex items-center justify-between gap-2">
                <Link href={`/dashboard/videos/${v.id}`} className="truncate font-semibold hover:text-emerald-500">
                  #{v.id} · {v.original_filename}
                </Link>
                <StatusBadge status={v.status} />
              </div>
              <p className="text-xs text-zinc-500">
                {v.duration ? `${v.duration.toFixed(1)}s` : "—"} · {timeAgo(v.created_at)}
                {v.failed_reason ? ` · ${v.failed_reason.slice(0, 80)}` : ""}
              </p>
              <div className="mt-3 flex gap-2">
                <Link href={`/dashboard/videos/${v.id}`} className="btn-ghost flex-1 !py-1.5 text-xs">Detail</Link>
                {(v.status === "uploaded" || v.status === "failed") && (
                  <button
                    className="btn-primary flex-1 !py-1.5 text-xs"
                    disabled={process.isPending}
                    onClick={() => process.mutate({ url: `/videos/${v.id}/process` })}
                  >
                    Process
                  </button>
                )}
                <button
                  className="btn-ghost !py-1.5 text-xs text-red-500"
                  disabled={del.isPending}
                  onClick={() => { if (confirm(`Delete video #${v.id}?`)) del.mutate({ url: `/videos/${v.id}` }); }}
                >
                  Delete
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
