"""Built-in professional effect presets (seeded on first use, no manual entry needed).

Each entry is a single-input video filter chain applied AFTER the 9:16
crop/scale in ``build_filter`` — so only use plain video filters here.
Never include ``;``/``[``/``]`` (filtergraph separators/labels); chains are
joined with commas inside ``[0:v]...[outv]``.
"""

DEFAULT_EFFECT_PRESETS: list[dict[str, str]] = [
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
        "name": "sharp_pro",
        "description": "Maximum clarity for product/detail shots — crisp without oversaturation.",
        "ffmpeg_filter": "unsharp=7:7:0.8,eq=contrast=1.06:saturation=1.12",
    },
]
