"use client";
import { useEffect, useMemo, useRef } from "react";
import { EFFECT_CSS, drawWatermark, useWatermarkImage } from "@/components/video-preview";

/**
 * Live preview: HTML5 video + canvas watermark overlay + CSS effect approximation.
 * Canvas sits exactly on top of the video and redraws on play/seek/resize so
 * the watermark stays static over the moving frame. The rAF loop only runs
 * while it can actually draw (playing, or paused with a pending redraw).
 */
export function LivePreview({
  src,
  effectName,
  watermark,
  className,
}: {
  src: string;
  effectName: string;
  watermark: boolean;
  className?: string;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const wm = useWatermarkImage();
  const css = useMemo(() => EFFECT_CSS[effectName] ?? "", [effectName]);

  useEffect(() => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;
    let raf = 0;
    let running = false;

    const draw = () => {
      const w = video.clientWidth;
      const h = video.clientHeight;
      if (w > 0 && h > 0 && (canvas.width !== w || canvas.height !== h)) {
        canvas.width = w;
        canvas.height = h;
      }
      if (watermark && wm) {
        drawWatermark(canvas, wm);
      }
      // Keep looping only while the frame is actually moving; idle → stop.
      if (!video.paused && !video.ended) {
        raf = requestAnimationFrame(draw);
      } else {
        running = false;
      }
    };

    const start = () => {
      if (!running) {
        running = true;
        raf = requestAnimationFrame(draw);
      }
    };
    const force = () => {
      // One immediate redraw (watermark state, resize, seek) without looping.
      if (watermark && wm) {
        const w = video.clientWidth;
        const h = video.clientHeight;
        if (w > 0 && h > 0) {
          if (canvas.width !== w || canvas.height !== h) {
            canvas.width = w;
            canvas.height = h;
          }
          drawWatermark(canvas, wm);
        }
      } else {
        canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
      }
    };

    // Stable handler refs so removeEventListener matches addEventListener.
    const onPlay = () => {
      force();
      start();
    };
    const onLoadedData = () => {
      force();
      if (!video.paused) start();
    };
    const onPauseOrEnded = () => {
      force();
    };

    video.addEventListener("play", onPlay);
    video.addEventListener("seeked", force);
    video.addEventListener("loadeddata", onLoadedData);
    video.addEventListener("pause", onPauseOrEnded);
    video.addEventListener("ended", onPauseOrEnded);
    window.addEventListener("resize", force);
    force();

    return () => {
      cancelAnimationFrame(raf);
      running = false;
      video.removeEventListener("play", onPlay);
      video.removeEventListener("seeked", force);
      video.removeEventListener("loadeddata", onLoadedData);
      video.removeEventListener("pause", onPauseOrEnded);
      video.removeEventListener("ended", onPauseOrEnded);
      window.removeEventListener("resize", force);
    };
  }, [src, watermark, wm]);

  return (
    <div className={`relative w-full max-w-full overflow-hidden rounded-lg bg-black ${className ?? ""}`}>
      <video ref={videoRef} controls src={src} className="aspect-[9/16] max-h-[560px] w-full" style={{ filter: css }} />
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden
      />
    </div>
  );
}
