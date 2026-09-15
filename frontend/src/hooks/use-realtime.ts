"use client";
import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { apiBase } from "@/lib/api";

const EVENTS = [
  "video_processing_progress",
  "video_processing_complete",
  "post_status_update",
  "account_status_change",
  "new_log",
];

/** Opens an authenticated WS feed; invalidates related queries on events (polling fallback lives in hooks). */
export function useRealtimeFeed(enabled: boolean) {
  const qc = useQueryClient();
  const tries = useRef(0);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    let ws: WebSocket | null = null;
    let closed = false;

    const connect = () => {
      const token = localStorage.getItem("access_token");
      if (!token) return;
      try {
        ws = new WebSocket(`${apiBase().replace(/^http/, "ws")}/ws?token=${encodeURIComponent(token)}`);
      } catch {
        return;
      }
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (!EVENTS.includes(msg.event) && msg.event !== "connected") return;
          tries.current = 0;
          if (msg.event.startsWith("video")) {
            qc.invalidateQueries({ queryKey: ["videos"] });
            qc.invalidateQueries({ queryKey: ["overview"] });
          } else if (msg.event.startsWith("post")) {
            qc.invalidateQueries({ queryKey: ["posts"] });
            qc.invalidateQueries({ queryKey: ["queue"] });
            qc.invalidateQueries({ queryKey: ["overview"] });
          } else if (msg.event.startsWith("account")) {
            qc.invalidateQueries({ queryKey: ["accounts"] });
          } else if (msg.event === "new_log") {
            qc.invalidateQueries({ queryKey: ["logs"] });
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        if (closed) return;
        tries.current += 1;
        setTimeout(connect, Math.min(15000, 1000 * 2 ** tries.current));
      };
    };

    connect();
    return () => {
      closed = true;
      ws?.close();
    };
  }, [enabled, qc]);
}
