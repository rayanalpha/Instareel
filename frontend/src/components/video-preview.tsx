"use client";
import { useEffect, useState } from "react";

/**
 * CSS approximations of the FFmpeg effect presets (visual preview only —
 * the real filter runs server-side during processing).
 */
export const EFFECT_CSS: Record<string, string> = {
  // quality
  clean_natural: "saturate(1.08) contrast(1.02)",
  vivid_pop: "saturate(1.6) contrast(1.15) brightness(1.02)",
  sharp_pro: "contrast(1.06) saturate(1.12)",
  soft_denoise: "saturate(1.05) contrast(1.01)",
  ultra_detail: "contrast(1.08) saturate(1.15)",
  hdr_punch: "saturate(1.45) contrast(1.22) brightness(1.03)",
  gentle_clarity: "contrast(1.05) saturate(1.1)",
  // grade
  warm_sunset: "saturate(1.25) contrast(1.05) sepia(0.18) brightness(1.02)",
  golden_hour: "saturate(1.35) contrast(1.06) sepia(0.28) brightness(1.04)",
  cool_morning: "saturate(1.1) hue-rotate(-12deg) brightness(1.02)",
  teal_orange: "saturate(1.3) contrast(1.08) hue-rotate(-8deg)",
  cinematic: "saturate(0.85) contrast(1.12) brightness(0.98)",
  moody_dark: "saturate(0.75) contrast(1.15) brightness(0.95)",
  vintage_film: "saturate(0.7) contrast(1.05) sepia(0.4)",
  noir: "grayscale(1) contrast(1.2)",
  pastel_soft: "saturate(0.8) contrast(0.92) brightness(1.05) blur(0.3px)",
  sepia_classic: "sepia(0.9) contrast(1.02)",
  cyberpunk_neon: "saturate(1.7) contrast(1.15) hue-rotate(15deg)",
  matrix_code: "saturate(0.6) contrast(1.1) hue-rotate(60deg)",
  arctic_frost: "saturate(0.9) contrast(1.05) brightness(1.08) hue-rotate(-15deg)",
  desert_heat: "saturate(1.4) contrast(1.08) sepia(0.3) brightness(1.05)",
  rose_blush: "saturate(1.2) brightness(1.05) hue-rotate(10deg)",
  midnight_ocean: "saturate(1.1) contrast(1.12) brightness(0.96) hue-rotate(-25deg)",
  forest_mist: "saturate(0.95) brightness(1.05) hue-rotate(20deg) blur(0.2px)",
  candy_pop: "saturate(1.8) contrast(1.1) brightness(1.05)",
  matte_fade: "saturate(0.85) contrast(0.95) brightness(1.03)",
  tungsten_night: "saturate(1.15) sepia(0.35) brightness(0.98)",
  aqua_dream: "saturate(1.25) brightness(1.06) hue-rotate(-18deg)",
  ember_red: "saturate(1.3) contrast(1.1) hue-rotate(-20deg)",
  ultraviolet: "saturate(1.4) contrast(1.08) hue-rotate(90deg)",
  // stylize
  grain_35mm: "saturate(1.05) contrast(1.02)",
  old_film: "saturate(0.65) contrast(1.05) sepia(0.45)",
  heavy_vignette: "contrast(1.05) brightness(0.97)",
  letterbox_cinema: "contrast(1.03) saturate(1.05)",
  white_frame: "brightness(1.01)",
  scanlines_crt: "saturate(1.15) contrast(1.08)",
  rgb_glitch: "saturate(1.3) contrast(1.1)",
  digital_glitch: "saturate(1.4) contrast(1.2)",
  sketch_ink: "grayscale(1) contrast(2)",
  sobel_edges: "grayscale(1) contrast(1.8) invert(1)",
  negative_invert: "invert(1)",
  pixel_censor: "saturate(1.1)",
  pixel_mosaic: "saturate(1.1)",
  dream_blur: "brightness(1.05) saturate(1.2) blur(1.5px)",
  soft_beauty: "saturate(1.1) brightness(1.02) blur(0.2px)",
  // obfuscate
  mirror_flip: "saturate(1.02)",
  flip_vertical: "saturate(1.02)",
  punch_in_zoom: "saturate(1.05) contrast(1.02)",
  reframe_top: "saturate(1.02)",
  rotate_micro: "saturate(1.02)",
  downscale_soft: "saturate(1.02)",
  reverse_play: "saturate(1.02)",
  hue_shift: "hue-rotate(60deg) saturate(1.1)",
};

const PLACEHOLDER_SVG =
  "data:image/svg+xml," +
  encodeURIComponent(
    `<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80"><rect width="240" height="80" rx="12" fill="rgba(0,0,0,0.55)"/><text x="120" y="50" font-family="Arial" font-size="28" font-weight="bold" fill="white" text-anchor="middle">@yourbrand</text></svg>`
  );

export const WATERMARK_SRC = "/watermark.png";

/** Loads /watermark.png, falling back to a built-in placeholder badge. */
export function useWatermarkImage(): HTMLImageElement | null {
  const [img, setImg] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    let cancelled = false;
    const primary = new Image();
    primary.onload = () => {
      if (!cancelled) setImg(primary);
    };
    primary.onerror = () => {
      const fallback = new Image();
      fallback.onload = () => {
        if (!cancelled) setImg(fallback);
      };
      fallback.src = PLACEHOLDER_SVG;
    };
    primary.src = WATERMARK_SRC;
    return () => {
      cancelled = true;
    };
  }, []);
  return img;
}

/**
 * Draws the watermark bottom-right, mirroring the backend FFmpeg filter:
 *   [1:v]scale=120:-1[wm]; [v][wm]overlay=W-w-20:20
 * i.e. 120px wide at 720p output, 20px padding from right/bottom edges.
 * Scaled proportionally to the canvas size (output is 720 wide).
 */
export function drawWatermark(canvas: HTMLCanvasElement, wm: HTMLImageElement) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const scale = canvas.width / 720;
  const w = 120 * scale;
  const h = (wm.naturalHeight / wm.naturalWidth) * w || 40 * scale;
  const pad = 20 * scale;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.globalAlpha = 0.85;
  ctx.drawImage(wm, canvas.width - w - pad, canvas.height - h - pad, w, h);
  ctx.globalAlpha = 1;
}
