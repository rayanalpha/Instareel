"""Built-in professional effect presets (seeded on first use, no manual entry needed).

Each entry is a single-input video filter chain applied AFTER the 9:16
crop/scale in ``build_filter`` — so only use plain video filters here.
Never include ``;``/``[``/``]`` (filtergraph separators/labels); chains are
joined with commas inside ``[0:v]...[outv]``.

Categories:
- quality .... cleanups and detail/clarity enhancers
- grade ...... cinematic and social-media color grades
- stylize .... textures, frames, glitch and artistic looks
- obfuscate .. geometry/pixel transforms that change the file's fingerprint
  (mirror, reframe, pixelize, micro-rotate, downscale pass, reverse, hue
  shift) — handy for privacy masking and re-use edits.
"""

def missing_presets(existing_names) -> list[dict[str, str]]:
    """Built-ins absent from the DB (pure — unit tested)."""
    have = set(existing_names)
    return [p for p in DEFAULT_EFFECT_PRESETS if p["name"] not in have]


DEFAULT_EFFECT_PRESETS: list[dict[str, str]] = [
    # ---------------- quality ----------------
    {
        "name": "clean_natural",
        "description": "Neutral everyday look — light saturation lift and gentle sharpen.",
        "ffmpeg_filter": "eq=saturation=1.08:contrast=1.02,unsharp=5:5:0.3",
    },
    {
        "name": "vivid_pop",
        "description": "High-energy reels look — punchy saturation, contrast and crisp detail.",
        "ffmpeg_filter": "eq=saturation=1.6:contrast=1.15:brightness=0.02,unsharp=5:5:0.6",
    },
    {
        "name": "sharp_pro",
        "description": "Maximum clarity for product/detail shots — crisp without oversaturation.",
        "ffmpeg_filter": "unsharp=7:7:0.8,eq=contrast=1.06:saturation=1.12",
    },
    {
        "name": "soft_denoise",
        "description": "Cleans sensor noise and grain while keeping detail — night clips.",
        "ffmpeg_filter": "hqdn3d=1.5:1.5:6:6,eq=saturation=1.05",
    },
    {
        "name": "ultra_detail",
        "description": "Aggressive micro-contrast and sharpening — textures jump out.",
        "ffmpeg_filter": "unsharp=9:9:1.0,eq=contrast=1.08:saturation=1.15",
    },
    {
        "name": "hdr_punch",
        "description": "HDR-style pop — deep contrast, rich color, crisp edges.",
        "ffmpeg_filter": "eq=saturation=1.45:contrast=1.22:brightness=0.03,unsharp=5:5:0.5",
    },
    {
        "name": "gentle_clarity",
        "description": "Subtle everyday polish — barely-there lift for talking heads.",
        "ffmpeg_filter": "eq=contrast=1.05:saturation=1.1,unsharp=5:5:0.4",
    },
    # ---------------- grade ----------------
    {
        "name": "warm_sunset",
        "description": "Golden warm grade — cozy reds and ambers, soft highlight lift.",
        "ffmpeg_filter": "eq=saturation=1.25:contrast=1.05:brightness=0.02,colorbalance=rs=0.15:gs=0.05:bs=-0.15:rm=0.1:gm=0.0:bm=-0.1",
    },
    {
        "name": "golden_hour",
        "description": "Strong golden-hour glow — deep warm highlights, rich skin tones.",
        "ffmpeg_filter": "eq=saturation=1.35:contrast=1.06:brightness=0.04,colorbalance=rs=0.25:gs=0.1:bs=-0.2",
    },
    {
        "name": "cool_morning",
        "description": "Fresh cool grade — airy blues, clean whites, calm mood.",
        "ffmpeg_filter": "eq=saturation=1.1:contrast=1.03,colorbalance=rs=-0.12:gs=0.0:bs=0.15",
    },
    {
        "name": "teal_orange",
        "description": "Blockbuster teal-and-orange — cinematic color contrast.",
        "ffmpeg_filter": "colorbalance=rs=0.2:gs=0.05:bs=-0.1:rm=-0.15:gm=0.05:bm=0.2,eq=saturation=1.3:contrast=1.08",
    },
    {
        "name": "cinematic",
        "description": "Movie-frame feel — muted saturation, lifted contrast, soft vignette.",
        "ffmpeg_filter": "eq=saturation=0.85:contrast=1.12:brightness=-0.02,vignette=PI/4.5",
    },
    {
        "name": "moody_dark",
        "description": "Dark moody aesthetic — crushed blacks, desaturated, heavy vignette.",
        "ffmpeg_filter": "eq=saturation=0.75:contrast=1.15:brightness=-0.05,vignette=PI/3.5",
    },
    {
        "name": "vintage_film",
        "description": "Analog film nostalgia — faded blacks, warm cast, grain, vignette.",
        "ffmpeg_filter": "curves=all='0/0 0.5/0.45 1/0.9',eq=saturation=0.7:contrast=1.05,vignette=PI/5,noise=alls=6:allf=t",
    },
    {
        "name": "noir",
        "description": "Classic black & white — deep contrast monochrome with vignette.",
        "ffmpeg_filter": "hue=s=0,eq=contrast=1.2:brightness=0.01,vignette=PI/4",
    },
    {
        "name": "pastel_soft",
        "description": "Soft pastel feed look — lifted, low-contrast, dreamy glow.",
        "ffmpeg_filter": "eq=saturation=0.8:contrast=0.92:brightness=0.04,gblur=sigma=0.4",
    },
    {
        "name": "sepia_classic",
        "description": "Old-photo sepia — warm brown monochrome tone.",
        "ffmpeg_filter": "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    },
    {
        "name": "cyberpunk_neon",
        "description": "Neon night-city grade — electric magentas and cyans.",
        "ffmpeg_filter": "eq=saturation=1.7:contrast=1.15,colorbalance=rs=-0.2:gs=0.1:bs=0.3",
    },
    {
        "name": "matrix_code",
        "description": "Green-terminal tint — sickly digital green cast.",
        "ffmpeg_filter": "eq=saturation=0.6:contrast=1.1,colorbalance=rs=-0.3:gs=0.35:bs=-0.2",
    },
    {
        "name": "arctic_frost",
        "description": "Icy pale grade — desaturated blues, lifted frosty whites.",
        "ffmpeg_filter": "eq=saturation=0.9:contrast=1.05:brightness=0.08,colorbalance=rs=-0.2:gs=0.05:bs=0.25",
    },
    {
        "name": "desert_heat",
        "description": "Scorched warm grade — blazing highlights, amber shadows.",
        "ffmpeg_filter": "eq=saturation=1.4:contrast=1.08:brightness=0.05,colorbalance=rs=0.3:gs=0.1:bs=-0.25",
    },
    {
        "name": "rose_blush",
        "description": "Soft pink romantic tint — glowing rosy highlights.",
        "ffmpeg_filter": "eq=saturation=1.2:brightness=0.05,colorbalance=rs=0.2:gs=-0.05:bs=0.1",
    },
    {
        "name": "midnight_ocean",
        "description": "Deep-sea grade — dark navy blues, glowing aqua mids.",
        "ffmpeg_filter": "eq=saturation=1.1:contrast=1.12:brightness=-0.04,colorbalance=rs=-0.25:gs=-0.05:bs=0.3",
    },
    {
        "name": "forest_mist",
        "description": "Misty green grade — soft woodland haze, gentle glow.",
        "ffmpeg_filter": "eq=saturation=0.95:brightness=0.05,colorbalance=rs=-0.1:gs=0.2:bs=-0.05,gblur=sigma=0.3",
    },
    {
        "name": "candy_pop",
        "description": "Hyper-saturated playful pop — candy colors, bright finish.",
        "ffmpeg_filter": "eq=saturation=1.8:contrast=1.1:brightness=0.05",
    },
    {
        "name": "matte_fade",
        "description": "Faded matte blacks — soft filmic low-contrast finish.",
        "ffmpeg_filter": "curves=all='0/0.08 1/0.92',eq=saturation=0.85:contrast=0.95",
    },
    {
        "name": "tungsten_night",
        "description": "Warm indoor-night cast — amber tungsten glow, deep shadows.",
        "ffmpeg_filter": "colorbalance=rs=0.3:gs=0.12:bs=-0.3,eq=brightness=-0.02",
    },
    {
        "name": "aqua_dream",
        "description": "Bright tropical aqua — turquoise water, sunlit glow.",
        "ffmpeg_filter": "eq=saturation=1.25:brightness=0.06,colorbalance=rs=-0.15:gs=0.15:bs=0.2",
    },
    {
        "name": "ember_red",
        "description": "Fiery red intensity — smoldering warm shadows.",
        "ffmpeg_filter": "eq=saturation=1.3:contrast=1.1,colorbalance=rs=0.35:gs=-0.1:bs=-0.15",
    },
    {
        "name": "ultraviolet",
        "description": "Psychedelic UV shift — unreal violet-magenta spectrum.",
        "ffmpeg_filter": "hue=h=90:s=1.4,eq=contrast=1.08",
    },
    # ---------------- stylize ----------------
    {
        "name": "grain_35mm",
        "description": "Subtle 35mm film grain over a clean grade.",
        "ffmpeg_filter": "noise=alls=10:allf=t,eq=saturation=1.05",
    },
    {
        "name": "old_film",
        "description": "Aged cinema reel — vintage curves, grain, vignette.",
        "ffmpeg_filter": "curves=vintage,eq=saturation=0.65:contrast=1.05,vignette=PI/5,noise=alls=12:allf=t",
    },
    {
        "name": "heavy_vignette",
        "description": "Dramatic spotlight vignette — dark falls off hard at the edges.",
        "ffmpeg_filter": "vignette=PI/3,eq=contrast=1.05",
    },
    {
        "name": "letterbox_cinema",
        "description": "Widescreen cinema bars top and bottom.",
        "ffmpeg_filter": "pad=iw:ih+160:0:80:black",
    },
    {
        "name": "white_frame",
        "description": "Clean white gallery border around the frame.",
        "ffmpeg_filter": "pad=iw+24:ih+24:12:12:white",
    },
    {
        "name": "scanlines_crt",
        "description": "Retro CRT monitor — scanlines, boosted color and contrast.",
        "ffmpeg_filter": "drawgrid=w=iw:h=3:t=1:c=black@0.25,eq=saturation=1.15:contrast=1.08",
    },
    {
        "name": "rgb_glitch",
        "description": "Mild RGB split glitch with fine digital noise.",
        "ffmpeg_filter": "rgbashift=rh=8:bh=-8,noise=alls=8:allf=t",
    },
    {
        "name": "digital_glitch",
        "description": "Hard glitch art — heavy channel split, crushed contrast.",
        "ffmpeg_filter": "rgbashift=rh=12:rv=3:gh=-8,eq=saturation=1.4:contrast=1.2",
    },
    {
        "name": "sketch_ink",
        "description": "Ink-sketch line art — edges on paper white.",
        "ffmpeg_filter": "edgedetect=low=0.1:high=0.4,negate",
    },
    {
        "name": "sobel_edges",
        "description": "Glowing edge map — dark neon-outline tracing.",
        "ffmpeg_filter": "sobel,negate,eq=contrast=1.3",
    },
    {
        "name": "negative_invert",
        "description": "Full color negative — inverted film look.",
        "ffmpeg_filter": "negate",
    },
    {
        "name": "pixel_censor",
        "description": "Privacy pixelation — coarse mosaic over the whole frame.",
        "ffmpeg_filter": "scale=90:160:flags=neighbor,scale=720:1280:flags=neighbor",
    },
    {
        "name": "pixel_mosaic",
        "description": "Extreme mosaic abstraction — heavy block pixels.",
        "ffmpeg_filter": "scale=45:80:flags=neighbor,scale=720:1280:flags=neighbor",
    },
    {
        "name": "dream_blur",
        "description": "Hazy dream sequence — soft blur with lifted glow.",
        "ffmpeg_filter": "gblur=sigma=1.5,eq=brightness=0.05:saturation=1.2",
    },
    {
        "name": "soft_beauty",
        "description": "Skin-smoothing beauty filter — softens texture, keeps edges.",
        "ffmpeg_filter": "bilateral=sigmaS=3:sigmaR=0.15,eq=saturation=1.1:brightness=0.02",
    },
    # ---------------- obfuscate ----------------
    {
        "name": "mirror_flip",
        "description": "Horizontal mirror — new composition and new file fingerprint.",
        "ffmpeg_filter": "hflip",
    },
    {
        "name": "flip_vertical",
        "description": "Vertical flip — disorienting upside-down variant.",
        "ffmpeg_filter": "vflip",
    },
    {
        "name": "punch_in_zoom",
        "description": "12% punch-in reframe — tighter crop, reframed subject.",
        "ffmpeg_filter": "crop=iw*0.88:ih*0.88:(iw-iw*0.88)/2:(ih-ih*0.88)/2,scale=720:1280",
    },
    {
        "name": "reframe_top",
        "description": "Reframe toward the top — drops the bottom 10% of frame.",
        "ffmpeg_filter": "crop=iw:ih*0.9:0:0,scale=720:1280",
    },
    {
        "name": "rotate_micro",
        "description": "Barely-visible tilt — shifts every pixel, keeps composition.",
        "ffmpeg_filter": "rotate=0.025:fillcolor=black",
    },
    {
        "name": "downscale_soft",
        "description": "Softening downscale-upscale pass — new encode fingerprint.",
        "ffmpeg_filter": "scale=360:640:flags=bilinear,scale=720:1280:flags=bilinear",
    },
    {
        "name": "reverse_play",
        "description": "Plays the clip backwards — same length, reversed motion.",
        "ffmpeg_filter": "reverse",
    },
    {
        "name": "hue_shift",
        "description": "Spectrum rotation — same luma, shifted hues throughout.",
        "ffmpeg_filter": "hue=h=60",
    },
]
