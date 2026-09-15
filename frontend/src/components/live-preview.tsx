"use client";
import { useEffect, useMemo, useRef, useState } from "react";
import { EFFECT_CSS, drawWatermark, useWatermarkImage } from "@/components/video-preview";

/**
 * Live preview: HTML5 video + canvas watermark overlay + CSS effect approximation.
 * Canvas sits exactly on top of the video and redraws on play/seek/resize so
 * the watermark stays static over the moving frame.
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
    let lastDrawn = -1;

    const draw = () => {
      const w = video.clientWidth;
      const h = video.clientHeight;
      if (w > 0 && h > 0 && (canvas.width !== w || canvas.height !== h)) {
        canvas.width = w;
        canvas.height = h;
      }
      // Redraw when playing (time changes) or after a state change.
      if (watermark && wm && (!video.paused || video.currentTime !== lastDrawn)) {
        drawWatermark(canvas, wm);
        lastDrawn = video.currentTime;
      } else if (!watermark) {
        const ctx = canvas.getContext("2d");
        ctx?.clearRect(0, 0, canvas.width, canvas.height);
        lastDrawn = video.currentTime;
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);

    const force = () => {
      lastDrawn = -1;
    };
    video.addEventListener("play", force);
    video.addEventListener("seeked", force);
    video.addEventListener("loadeddata", force);
    window.addEventListener("resize", force);
    return () => {
      cancelAnimationFrame(raf);
      video.removeEventListener("play", force);
      video.removeEventListener("seeked", force);
      video.removeEventListener("loadeddata", force);
      window.removeEventListener("resize", force);
    };
  }, [src, watermark, wm]);

  return (
    <div className={`relative overflow-hidden rounded-lg bg-black ${className ?? ""}`}>
      <video ref={videoRef} controls src={src} className="aspect-[9/16] max-h-[560px] w-full" style={{ filter: css }} />
      <canvas
        ref={canvasRef}
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden
      />
    </div>
  );
}
