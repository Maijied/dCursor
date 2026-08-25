#!/usr/bin/env python3
"""Generate animated dCursor splash WEBM videos (640x700, matches upstream Cursor)."""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError as exc:
    raise SystemExit("error: Pillow is required (python3-pil)") from exc


ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

WIDTH = 640
HEIGHT = 700
LOGO_W = 421
LOGO_H = 480
LOGO_X = (WIDTH - LOGO_W) // 2
LOGO_Y = int(HEIGHT * 0.22)
FRAMES = 60
FPS = 30


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def mix_color(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


def draw_segment(
    draw: ImageDraw.ImageDraw,
    shadow_draw: ImageDraw.ImageDraw,
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    phase: float,
    glow: float,
) -> None:
    shell_top = (122, 136, 156)
    shell_mid = (42, 49, 64)
    shell_bot = (10, 15, 24)
    core_a = (57, 255, 20)
    core_b = (0, 243, 255)
    core_c = (188, 19, 254)

    t = (math.sin(phase) + 1) / 2
    core = mix_color(mix_color(core_a, core_b, t), core_c, (math.sin(phase * 1.7) + 1) / 2)

    shadow_draw.ellipse(
        (cx - rx * 0.95, cy - ry * 0.55 + 10, cx + rx * 0.95, cy + ry * 1.05 + 10),
        fill=(0, 0, 0, int(55 + 25 * glow)),
    )

    for i in range(10, 0, -1):
        factor = i / 10
        shade = mix_color(mix_color(shell_top, shell_mid, factor * 0.7), shell_bot, factor)
        draw.ellipse(
            (cx - rx * factor, cy - ry * factor, cx + rx * factor, cy + ry * factor),
            fill=shade + (255,),
        )

    draw.ellipse(
        (cx - rx * 0.78, cy - ry * 0.82, cx + rx * 0.2, cy - ry * 0.2),
        fill=(255, 255, 255, int(28 + 18 * glow)),
    )
    draw.ellipse(
        (cx - rx * 0.72, cy - ry * 0.72, cx + rx * 0.72, cy + ry * 0.72),
        fill=core + (int(105 + 90 * glow),),
    )
    draw.ellipse(
        (cx - rx * 0.35, cy - ry * 0.58, cx - rx * 0.05, cy - ry * 0.18),
        fill=(255, 255, 255, int(65 + 45 * glow)),
    )
    draw.ellipse(
        (cx - rx * 0.9, cy - ry * 0.12, cx + rx * 0.9, cy + ry * 0.12),
        fill=(0, 0, 0, int(70 + 20 * glow)),
    )


def render_logo_tile(index: int, *, light: bool = False) -> Image.Image:
    """Render the animated larva tile at splash PNG dimensions (421x480)."""
    size = LOGO_W
    t = index / FRAMES
    phase = t * math.tau
    breath = 1.0 + 0.045 * math.sin(phase * 2)
    glow = (math.sin(phase * 3) + 1) / 2
    center = size / 2

    if light:
        bg = Image.new("RGBA", (size, LOGO_H), (248, 250, 252, 255))
        tile_top = (241, 245, 249)
        tile_bot = (226, 232, 240)
        ring = (8, 145, 178)
        ambient = (0, 243, 255, 18)
    else:
        bg = Image.new("RGBA", (size, LOGO_H), (3, 7, 18, 255))
        tile_top = (16, 28, 56)
        tile_bot = (3, 7, 18)
        ring = (0, 243, 255)
        ambient = (188, 19, 254, 22)

    draw = ImageDraw.Draw(bg)
    margin = int(size * 0.0625)
    for y in range(margin, LOGO_H - margin):
        row_t = (y - margin) / (LOGO_H - 2 * margin)
        shade = mix_color(tile_top, tile_bot, row_t)
        draw.line((margin, y, size - margin, y), fill=shade + (255,))

    glow_patch = Image.new("RGBA", (size, LOGO_H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow_patch)
    gdraw.ellipse((size * 0.14, LOGO_H * 0.12, size * 0.7, LOGO_H * 0.72), fill=ambient)
    gdraw.ellipse((size * 0.3, LOGO_H * 0.62, size * 0.82, LOGO_H * 0.9), fill=(57, 255, 20, 16 if light else 28))
    bg.alpha_composite(glow_patch.filter(ImageFilter.GaussianBlur(radius=14)))

    glass = Image.new("RGBA", (size, LOGO_H), (0, 0, 0, 0))
    ImageDraw.Draw(glass).rounded_rectangle(
        (margin + 6, margin + 6, size - margin - 6, LOGO_H - margin - 90),
        radius=70,
        fill=(255, 255, 255, 28 if light else 18),
    )
    bg.alpha_composite(glass)

    draw.rounded_rectangle(
        (margin, margin, size - margin, LOGO_H - margin),
        radius=int(size * 0.1875),
        outline=mix_color((0, 243, 255), (188, 19, 254), glow) + (int(150 + 70 * glow),),
        width=6,
    )

    ring_layer = Image.new("RGBA", (size, LOGO_H), (0, 0, 0, 0))
    ring_draw = ImageDraw.Draw(ring_layer)
    ring_r = size * 0.37 + 4 * math.sin(phase)
    ring_draw.ellipse(
        (center - ring_r, center - ring_r * 0.96, center + ring_r, center + ring_r * 0.96),
        outline=ring + (int(75 + 55 * glow),),
        width=2,
    )
    ring_layer = ring_layer.rotate(
        math.degrees(phase * 0.65),
        resample=Image.Resampling.BICUBIC,
        center=(center, LOGO_H * 0.45),
    )
    bg.alpha_composite(ring_layer)

    scale_x = size / 512
    scale_y = LOGO_H / 512
    larva = Image.new("RGBA", (size, LOGO_H), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, LOGO_H), (0, 0, 0, 0))
    ldraw = ImageDraw.Draw(larva)
    sdraw = ImageDraw.Draw(shadow)

    segments = [
        (360, 298, 46, 36, 0.0),
        (306, 282, 48, 38, 0.4),
        (252, 264, 50, 40, 0.8),
        (198, 244, 46, 36, 1.2),
        (144, 216, 56, 46, 1.6),
    ]

    offset_y = -5 * math.sin(phase * 2)

    def map_x(x: float) -> float:
        return (x - 256) * breath * scale_x + center

    def map_y(y: float) -> float:
        return (y - 256) * breath * scale_y + LOGO_H * 0.45 + offset_y * scale_y

    for sx, sy, rx, ry, seg_phase in segments:
        draw_segment(
            ldraw,
            sdraw,
            map_x(sx),
            map_y(sy),
            rx * breath * scale_x,
            ry * breath * scale_y,
            phase + seg_phase,
            glow,
        )

    eye_y = map_y(206)
    for ex in (124, 164):
        exs = map_x(ex)
        eye_r = (17 + 4 * glow) * scale_x
        ldraw.ellipse(
            (exs - eye_r, eye_y - eye_r, exs + eye_r, eye_y + eye_r),
            fill=(57, 255, 20, 235),
        )
        ldraw.ellipse(
            (exs - 8 * scale_x, eye_y - 8 * scale_y, exs + 8 * scale_x, eye_y + 8 * scale_y),
            fill=(6, 16, 24, 255),
        )
        ldraw.ellipse(
            (exs - 2 * scale_x, eye_y - 4 * scale_y, exs + scale_x, eye_y - scale_y),
            fill=(255, 255, 255, 240),
        )

    for ax, ay, color in ((94, 148, (0, 243, 255)), (194, 148, (57, 255, 20))):
        axs = map_x(ax)
        ays = map_y(ay - 20)
        r = 7 * scale_x
        ldraw.ellipse((axs - r, ays - r, axs + r, ays + r), fill=color + (int(180 + 60 * glow),))

    larva = Image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(radius=5)), larva)
    glow_layer = larva.copy().filter(ImageFilter.GaussianBlur(radius=10))
    bg.alpha_composite(glow_layer)
    bg.alpha_composite(larva)

    pointer = [
        (334, 330),
        (462, 398),
        (428, 403),
        (446, 435),
        (427, 446),
        (409, 415),
        (387, 440),
        (334, 330),
    ]
    mapped = [(map_x(x), map_y(y)) for x, y in pointer]
    draw.polygon(mapped, fill=(255, 255, 255, 255))
    draw.polygon(mapped, outline=(7, 17, 26, 255))

    return bg


def render_frame(index: int, *, light: bool = False) -> Image.Image:
    """Composite logo tile onto full splash canvas (640x700)."""
    t = index / FRAMES
    phase = t * math.tau
    glow = (math.sin(phase * 3) + 1) / 2

    if light:
        top = (248, 250, 252)
        bottom = (226, 232, 240)
        vignette = (0, 243, 255, 12)
    else:
        top = (3, 7, 18)
        bottom = (1, 3, 8)
        vignette = (188, 19, 254, 16)

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), top + (255,))
    draw = ImageDraw.Draw(canvas)
    for y in range(HEIGHT):
        shade = mix_color(top, bottom, y / HEIGHT)
        draw.line((0, y, WIDTH, y), fill=shade + (255,))

    halo = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(halo)
    hdraw.ellipse(
        (LOGO_X - 40, LOGO_Y - 30, LOGO_X + LOGO_W + 40, LOGO_Y + LOGO_H + 50),
        fill=vignette,
    )
    canvas.alpha_composite(halo.filter(ImageFilter.GaussianBlur(radius=28)))

    logo = render_logo_tile(index, light=light)
    float_y = int(3 * math.sin(phase * 2))
    canvas.alpha_composite(logo, (LOGO_X, LOGO_Y + float_y))

    return canvas.convert("RGB")


def encode_webm_ffmpeg(frames_dir: Path, output: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg not found")

    pattern = str(frames_dir / "frame_%04d.png")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            pattern,
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            "0",
            "-crf",
            "30",
            "-an",
            str(output),
        ],
        check=True,
    )


def encode_webm_gstreamer(frames_dir: Path, output: Path) -> None:
    gst = shutil.which("gst-launch-1.0")
    if not gst:
        raise RuntimeError("gst-launch-1.0 not found")

    pattern = str(frames_dir / "frame_%04d.png")
    subprocess.run(
        [
            gst,
            "-q",
            "multifilesrc",
            f"location={pattern}",
            "index=0",
            f"caps=image/png,framerate={FPS}/1",
            "!",
            "pngdec",
            "!",
            "videoconvert",
            "!",
            "vp9enc",
            "target-bitrate=700000",
            "!",
            "webmmux",
            "!",
            "filesink",
            f"location={output}",
        ],
        check=True,
    )


def encode_webm(frames_dir: Path, output: Path) -> None:
    if shutil.which("ffmpeg"):
        encode_webm_ffmpeg(frames_dir, output)
        return
    if shutil.which("gst-launch-1.0"):
        encode_webm_gstreamer(frames_dir, output)
        return
    raise RuntimeError("need ffmpeg or GStreamer (gst-launch-1.0) to encode WEBM")


def generate_video(name: str, *, light: bool) -> Path:
    out = ASSETS / name
    ASSETS.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dcursor-frames-") as tmp:
        frames_dir = Path(tmp)
        for i in range(FRAMES):
            frame = render_frame(i, light=light)
            frame.save(frames_dir / f"frame_{i:04d}.png")

        encode_webm(frames_dir, out)

    return out


def main() -> int:
    print("==> Generating dCursor splash WEBM videos (640x700 luminous larva)")
    dark = generate_video("dcursor-logo-for-dark-theme.webm", light=False)
    light = generate_video("dcursor-logo-for-light-theme.webm", light=True)
    print(f"    {dark} ({dark.stat().st_size} bytes)")
    print(f"    {light} ({light.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
