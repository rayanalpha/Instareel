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
    let tokenTimer: ReturnType<typeof setInterval> | null = null;
    // Generation counter: ignores onclose from a superseded socket so an
    // old socket's reconnect timer can't resurrect itself after connect()
    // already opened a fresh one.
    let generation = 0;
    // Token this connection authenticated with. The API client refreshes the
    // access token on 401s; the server also closes the socket with 4401 when
    // the token expires — either way we must reconnect with the fresh token.
    let connectedToken: string | null = null;

    const clearRetry = () => {
      if (retryTimer) {
        clearTimeout(retryTimer);
        retryTimer = null;
      }
    };

    const connect = () => {
      const gen = ++generation;
      clearRetry();
      if (ws) {
        try {
          ws.close();
        } catch {
          /* ignore */
        }
        ws = null;
      }
      const token = localStorage.getItem("access_token");
      if (!token) {
        // Not logged in (yet) — retry; login will also trigger a token check.
        retryTimer = setTimeout(() => {
          if (!closed && gen === generation) connect();
        }, 5000);
        return;
      }
      connectedToken = token;
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
          if (msg.event === "ping") {
            // Server heartbeat — any frame back counts as alive.
            try {
              ws?.send(JSON.stringify({ event: "pong" }));
            } catch {
              /* ignore */
            }
            return;
          }
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
      ws.onclose = (ev: CloseEvent) => {
        if (closed || gen !== generation) return;
        connectedToken = null;
        tries.current += 1;
        // 4401 = auth failed/expired. The API client may have just refreshed
        // the token, so retry quickly once, then fall back to backoff.
        const cap = ev.code === 4401 ? 3000 : 15000;
        retryTimer = setTimeout(connect, Math.min(cap, 1000 * 2 ** tries.current));
      };
    };

    connect();
    // If the API client refreshed the access token (401 → refresh → retry),
    // this socket is authenticating with a stale token — reconnect now with
    // the fresh one instead of waiting for the server's 4401.
    tokenTimer = setInterval(() => {
      if (closed) return;
      const current = localStorage.getItem("access_token");
      if (current && current !== connectedToken) connect();
    }, 30000);

    return () => {
      closed = true;
      generation += 1;
      clearRetry();
      if (tokenTimer) clearInterval(tokenTimer);
      try {
        ws?.close();
      } catch {
        /* ignore */
      }
    };
  }, [enabled, qc]);
}
