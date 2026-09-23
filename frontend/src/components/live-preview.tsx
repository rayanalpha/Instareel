"use client";
import { useMemo } from "react";
import { EFFECT_CSS } from "@/components/video-preview";

/**
 * Live preview: HTML5 video + CSS effect approximation.
 */
export function LivePreview({
  src,
  effectName,
  className,
}: {
  src: string;
  effectName: string;
  className?: string;
}) {
  const css = useMemo(() => EFFECT_CSS[effectName] ?? "", [effectName]);

  return (
    <div className={`relative w-full max-w-full overflow-hidden rounded-lg bg-black ${className ?? ""}`}>
      <video controls src={src} className="aspect-[9/16] max-h-[560px] w-full" style={{ filter: css }} />
    </div>
  );
}
