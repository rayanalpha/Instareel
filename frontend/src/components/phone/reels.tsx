"use client";
import type { Account, Post, Video } from "@/types/models";
import { useBlobUrl } from "./blob";
import { fmt } from "@/lib/utils";

function Reel({
  post,
  video,
  username,
  onPick,
}: {
  post: Post;
  video: Video | undefined;
  username: string;
  onPick: () => void;
}) {
  const { url, failed } = useBlobUrl("preview", video?.id ?? null);
  return (
    <div className="relative h-full w-full shrink-0 snap-start snap-always bg-black">
      {url ? (
        <video src={url} className="h-full w-full object-contain" controls playsInline preload="metadata" />
      ) : (
        <div className="flex h-full items-center justify-center text-sm text-zinc-500">
          {!video ? "No file yet" : failed ? "Unavailable — reprocess the video" : "Loading…"}
        </div>
      )}
      <button onClick={onPick} className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/70 to-transparent p-3 pt-8 text-left text-white">
        <p className="text-sm font-bold">@{username}</p>
        {(post.caption || post.hashtags) && (
          <p className="line-clamp-2 text-xs opacity-90">
            {[post.caption, post.hashtags].filter(Boolean).join(" ")}
          </p>
        )}
        <p className="mt-1 flex gap-3 text-xs opacity-90">
          <span>▶ {fmt(post.views_7d ?? post.views_24h)}</span>
          {post.audio_track && <span>♪ {post.audio_track}</span>}
          {post.is_trial && <span>trial</span>}
        </p>
      </button>
    </div>
  );
}

export function PhoneReels({
  account,
  posts,
  videos,
  onPickPost,
}: {
  account: Account;
  posts: Post[];
  videos: Video[];
  onPickPost: (post: Post) => void;
}) {
  const byVideo = new Map(videos.map((v) => [v.id, v]));
  const mine = posts
    .filter((p) => p.account_id === account.id && p.status === "posted")
    .sort((a, b) => (b.posted_at ?? b.created_at).localeCompare(a.posted_at ?? a.created_at));

  if (mine.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-8 text-center text-sm text-zinc-500">
        No posted reels yet — publish from the composer or wait for the schedule.
      </div>
    );
  }
  return (
    <div className="h-full snap-y snap-mandatory overflow-y-auto">
      {mine.map((p) => (
        <Reel key={p.id} post={p} video={byVideo.get(p.video_id)} username={account.username} onPick={() => onPickPost(p)} />
      ))}
    </div>
  );
}
