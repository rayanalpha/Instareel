"use client";
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiBase } from "@/lib/api";

const EVENTS = [
  "video_processing_progress",
  "video_processing_complete",
  "video_source_update",
  "post_status_update",
  "account_status_change",
  "new_log",
  "proxy_pool_update",
];

/** Resolve the WebSocket URL: same-origin in the browser when no API host
 * is configured (avoids cross-origin WS issues entirely). */
function wsBase(): string {
  if (typeof window !== "undefined") {
    const host = apiBase();
    if (host) return host.replace(/^http/, "ws");
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}`;
  }
  return "";
}

/** Opens an authenticated WS feed; invalidates related queries on events (polling fallback lives in hooks). */
export function useRealtimeFeed(enabled: boolean) {
  const qc = useQueryClient();
  const tries = useRef(0);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    let ws: WebSocket | null = null;
    let closed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      const token = localStorage.getItem("access_token");
      if (!token) return;
      try {
        // Token travels as the first WS message, never in the URL (URLs land
        // in server/proxy access logs; message frames don't).
        ws = new WebSocket(`${wsBase()}/ws`);
      } catch {
        return;
      }
      ws.onopen = () => {
        ws?.send(JSON.stringify({ token }));
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (!EVENTS.includes(msg.event) && msg.event !== "connected") return;
          tries.current = 0;
          if (msg.event.startsWith("video")) {
            qc.invalidateQueries({ queryKey: ["videos"] });
            qc.invalidateQueries({ queryKey: ["video-sources"] });
            qc.invalidateQueries({ queryKey: ["overview"] });
          } else if (msg.event.startsWith("post")) {
            qc.invalidateQueries({ queryKey: ["posts"] });
            qc.invalidateQueries({ queryKey: ["queue"] });
            qc.invalidateQueries({ queryKey: ["overview"] });
          } else if (msg.event.startsWith("account")) {
            qc.invalidateQueries({ queryKey: ["accounts"] });
          } else if (msg.event === "new_log") {
            qc.invalidateQueries({ queryKey: ["logs"] });
          } else if (msg.event === "proxy_pool_update") {
            qc.invalidateQueries({ queryKey: ["proxies"] });
            qc.invalidateQueries({ queryKey: ["proxy-pipeline"] });
            qc.invalidateQueries({ queryKey: ["proxy-sources"] });
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        if (closed) return;
        tries.current += 1;
        retryTimer = setTimeout(connect, Math.min(15000, 1000 * 2 ** tries.current));
      };
    };

    connect();
    return () => {
      closed = true;
      if (retryTimer) clearTimeout(retryTimer);
      ws?.close();
    };
  }, [enabled, qc]);
}
