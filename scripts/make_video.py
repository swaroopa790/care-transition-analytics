"""Build the project feedback video (silent, captioned) as an MP4.

Renders a 1920x1080 storyboard - title cards, the eight publication figures,
the KPI scoreboard and the "what I learned" slides - and pipes the frames
straight into ffmpeg, so nothing large is written to disk.

Run::

    python scripts/make_video.py [output.mp4]

Requires ``pillow`` and ``imageio-ffmpeg`` (both are in requirements.txt's
analysis group; the ffmpeg binary ships inside imageio-ffmpeg).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FIGURES = ROOT / "outputs" / "figures"

W, H = 1920, 1080
FPS = 24
BAND_H = 210          # caption band height
TOP_H = 92            # header bar height

BG = (242, 245, 248)
CARD = (255, 255, 255)
INK = (27, 39, 51)
MUTED = (96, 112, 128)
ACCENT = (76, 120, 168)
GREEN = (84, 162, 75)
RED = (217, 83, 79)
BAND = (27, 39, 51)

FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


F_TITLE = font("segoeuib.ttf", 74)
F_SUB = font("segoeui.ttf", 38)
F_HEAD = font("segoeuib.ttf", 52)
F_BODY = font("segoeui.ttf", 36)
F_BODY_B = font("segoeuib.ttf", 38)
F_CAP = font("segoeuib.ttf", 44)
F_SMALL = font("segoeui.ttf", 26)
F_SMALL_B = font("segoeuib.ttf", 26)


# --------------------------------------------------------------------------- #
# Storyboard
# --------------------------------------------------------------------------- #
STORY: list[dict] = [
    dict(kind="title", dur=9,
         title="Care Transition Efficiency & Placement Outcome Analytics",
         sub="HHS Unaccompanied Alien Children programme, 2023-2025\n"
             "Project feedback, walkthrough and learnings",
         caption="A walkthrough of what I built, what the data shows, and what I learned."),
    dict(kind="text", dur=13, head="The problem I reframed",
         bullets=[
             "Counts tell you how many children are held - not how well they move.",
             "Modelled the programme as a pipeline:  CBP custody  >  HHS care  >  sponsor placement",
             "Two queues (border custody, HHS care) and three flows (entry, handoff, exit).",
             "So the question becomes: how fast does a child move through, and is that slowing?",
         ],
         caption="Reframing a headcount dataset as a process turned the analysis into a speed problem."),
    dict(kind="text", dur=12, head="The data I had to respect",
         bullets=[
             "720 populated reporting days out of 1,075 calendar days  (67% coverage)",
             "Reports run Mon-Thu + Sunday: no Saturday reports, two Fridays, 10-day longest blind spot",
             "450 trailing blank rows discarded; no duplicates, no negatives, no missing values",
             "2023 stock/flow identity does not close (~151 children/day unexplained) - flagged, not hidden",
         ],
         caption="Coverage and the mass-balance gap are results in their own right - they constrain every claim."),
    dict(kind="figure", fig="fig01_pipeline_overview.png", dur=14,
         caption="Figure 1 - the three-stage pipeline: entries, handoffs, exits and both queues."),
    dict(kind="figure", fig="fig02_transition_efficiency.png", dur=14,
         caption="Transfer efficiency fell 83% (2023) to 46% (2025); discharge effectiveness 3.34% to 0.90% per day."),
    dict(kind="figure", fig="fig03_backlog_identification.png", dur=13,
         caption="Backlog: 36 sustained accumulation runs - 27 of them inside 2024."),
    dict(kind="figure", fig="fig04_bottleneck_detection.png", dur=13,
         caption="Bottlenecks: threshold breaches, with every alert marker drawn on the timeline."),
    dict(kind="figure", fig="fig05_temporal_patterns.png", dur=13,
         caption="Temporal patterns: monthly volumes and a weekday/weekend discharge gap (+61/day on Sundays)."),
    dict(kind="figure", fig="fig06_outcome_stability.png", dur=13,
         caption="Outcome Stability collapsed 77.7 to 0.0 - placement outcomes stopped being predictable."),
    dict(kind="figure", fig="fig07_throughput_funnel.png", dur=12,
         caption="Throughput: entries vs exits over the window (1.85x overall)."),
    dict(kind="figure", fig="fig08_regime_comparison.png", dur=12,
         caption="Year-by-year regimes: 2023 fast but unclosed, 2024 backlog growth, 2025 slow and flat."),
    dict(kind="kpi", dur=15,
         caption="The five KPIs in one scoreboard - full period and by year."),
    dict(kind="text", dur=14, head="The dashboard I shipped (Streamlit Cloud)",
         bullets=[
             "5 modules: pipeline flow + Sankey, efficiency, bottlenecks, outcome trends, data & method",
             "Sidebar controls: date range, ratio/count/days-to-clear toggle, rolling window, 4 alert sliders",
             "Every control recomputes all panels for the selected window; CSVs downloadable per tab",
             "One library feeds the paper, the figures, insights.json and the app - numbers cannot drift apart",
         ],
         caption="Live at care-transition-analytics.streamlit.app - try dragging the date range."),
    dict(kind="text", dur=15, head="What I learned (1/2)",
         bullets=[
             "Ratios travel better than volumes: with a broken stock/flow identity in 2023, only ratio-based "
             "metrics compare fairly across years.",
             "Turning headcount into dwell time changed the story - implied placement cycle went 31 to 227 days.",
             "Measurement design matters: one constants block (ALERT_THRESHOLDS) drives paper, app and JSON.",
         ],
         caption="Lesson: define the metric contract once, then derive every deliverable from it."),
    dict(kind="text", dur=15, head="What I learned (2/2)",
         bullets=[
             "Publish the caveats: coverage gaps and the mass-balance residual are part of the findings.",
             "Build for reproducibility: a single smoke check verifies every analytics entry point before push.",
             "Deployment is part of the project - pinned, loosely-bounded deps and a re-runnable build.",
             "Visual alerts beat tables: thresholds as sliders make the analysis interrogable by non-analysts.",
         ],
         caption="Lesson: honest limitations plus a reproducible pipeline make results defensible."),
    dict(kind="text", dur=13, head="What I would do next",
         bullets=[
             "Gap-aware reporting: model the 10-day blind spots explicitly instead of treating them as silence",
             "Sponsor-level and placement-type breakdowns once those fields are available",
             "Alert history persisted over time so threshold tuning can be evaluated, not just observed",
         ],
         caption="Thank you - repo, paper and live app links are in the submission form."),
]


# --------------------------------------------------------------------------- #
# Layout helpers
# --------------------------------------------------------------------------- #
def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, max_w: int) -> list[str]:
    lines: list[str] = []
    for raw in text.split("\n"):
        words, line = raw.split(), ""
        for w in words:
            trial = f"{line} {w}".strip()
            if draw.textlength(trial, font=fnt) <= max_w:
                line = trial
            else:
                if line:
                    lines.append(line)
                line = w
        lines.append(line)
    return lines


def header(draw: ImageDraw.ImageDraw, label: str) -> None:
    draw.rectangle([0, 0, W, TOP_H], fill=BAND)
    draw.text((56, 24), "CARE TRANSITION ANALYTICS", font=F_SMALL_B, fill=(255, 255, 255))
    tw = draw.textlength(label, font=F_SMALL)
    draw.text((W - 56 - tw, 24), label, font=F_SMALL, fill=(168, 190, 214))


def caption_band(draw: ImageDraw.ImageDraw, text: str, index: int, total: int, progress: float = 0.0) -> None:
    y0 = H - BAND_H
    draw.rectangle([0, y0, W, H], fill=BAND)
    draw.rectangle([0, y0, W, y0 + 6], fill=ACCENT)
    lines = wrap(draw, text, F_CAP, W - 160)
    y = y0 + 42
    for ln in lines[:3]:
        draw.text((80, y), ln, font=F_CAP, fill=(255, 255, 255))
        y += 60
    page = f"{index} / {total}"
    pw = draw.textlength(page, font=F_SMALL)
    draw.text((W - 56 - pw, H - 44), page, font=F_SMALL, fill=(150, 168, 190))
    draw.rectangle([0, H - 6, int(W * progress), H], fill=GREEN)


def blank(label: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    header(d, label)
    return img, d


def fit(img: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """Fit `img` into box, letterboxed on the card."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    scale = min(bw / img.width, bh / img.height)
    nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
    resized = img.resize((nw, nh), Image.LANCZOS)
    out = Image.new("RGB", (bw, bh), CARD)
    out.paste(resized, ((bw - nw) // 2, (bh - nh) // 2))
    return out


def render(slide: dict, index: int, total: int) -> Image.Image:
    kind = slide["kind"]
    label = f"SLIDE {index}"

    if kind == "figure":
        img, d = blank(label)
        d.text((56, TOP_H + 24), slide["fig"].replace("_", " ").removesuffix(".png").title(),
               font=F_HEAD, fill=INK)
        card = (56, TOP_H + 100, W - 56, H - BAND_H - 40)
        d.rounded_rectangle(card, radius=18, fill=CARD, outline=(225, 231, 238), width=2)
        src = Image.open(FIGURES / slide["fig"]).convert("RGB")
        inner = (card[0] + 18, card[1] + 18, card[2] - 18, card[3] - 18)
        img.paste(fit(src, inner), (inner[0], inner[1]))
        caption_band(d, slide["caption"], index, total)
        return img

    if kind == "kpi":
        img, d = blank(label)
        d.text((56, TOP_H + 24), "KPI scoreboard", font=F_HEAD, fill=INK)
        rows = [
            ("Metric", "Full period", "2023", "2024", "2025"),
            ("Transfer Efficiency Ratio", "69.1%", "83.0%", "78.3%", "46.0%"),
            ("Discharge Effectiveness (/day)", "2.37%", "3.34%", "2.90%", "0.90%"),
            ("Implied HHS release time", "98 d", "31 d", "37 d", "227 d"),
            ("Pipeline Throughput", "1.85x", "2.45x", "1.39x", "2.22x"),
            ("Net HHS backlog (/day)", "-45", "-131", "+3.4", "-12"),
            ("Outcome Stability Score", "44", "77.7", "75.2", "0.0"),
            ("Sustained accumulation runs", "36", "-", "27", "-"),
            ("Threshold alerts", "445", "-", "-", "all DE alerts"),
        ]
        x0, y0 = 56, TOP_H + 110
        col_w = [560, 260, 240, 240, 340]
        rh = 76
        for r, row in enumerate(rows):
            y = y0 + r * rh
            fill = BAND if r == 0 else (CARD if r % 2 else (247, 249, 252))
            d.rectangle([x0, y, x0 + sum(col_w), y + rh], fill=fill)
            x = x0
            for c, cell in enumerate(row):
                fnt = F_SMALL_B if r == 0 else (F_BODY_B if c == 0 else F_BODY)
                colour = (255, 255, 255) if r == 0 else INK
                if r > 0 and c == 4 and cell in ("46.0%", "0.90%", "227 d", "0.0"):
                    colour = RED
                d.text((x + 24, y + 18), cell, font=fnt, fill=colour)
                x += col_w[c]
            d.line([x0, y + rh, x0 + sum(col_w), y + rh], fill=(228, 233, 239), width=1)
        caption_band(d, slide["caption"], index, total)
        return img

    # title / text slides
    if kind == "title":
        img, d = blank(label)
        y = 300
        for ln in wrap(d, slide["title"], F_TITLE, W - 220):
            d.text((110, y), ln, font=F_TITLE, fill=INK)
            y += 96
        y += 24
        for ln in wrap(d, slide["sub"], F_SUB, W - 260):
            d.text((114, y), ln, font=F_SUB, fill=MUTED)
            y += 56
        d.rectangle([110, y + 30, 470, y + 38], fill=ACCENT)
        caption_band(d, slide["caption"], index, total)
        return img

    img, d = blank(label)
    d.text((56, TOP_H + 24), slide["head"], font=F_HEAD, fill=INK)
    d.rectangle([56, TOP_H + 92, 176, TOP_H + 100], fill=ACCENT)
    y = TOP_H + 140
    for bullet in slide["bullets"]:
        d.ellipse([64, y + 16, 82, y + 34], fill=ACCENT)
        lines = wrap(d, bullet, F_BODY, W - 260)
        for i, ln in enumerate(lines):
            d.text((110, y), ln, font=F_BODY_B if i == 0 and len(lines) == 1 else F_BODY, fill=INK)
            y += 52
        y += 26
    caption_band(d, slide["caption"], index, total)
    return img


# --------------------------------------------------------------------------- #
# Encode
# --------------------------------------------------------------------------- #
def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # pragma: no cover
        import shutil

        exe = shutil.which("ffmpeg")
        if not exe:
            raise SystemExit("ffmpeg not found - pip install imageio-ffmpeg")
        return exe


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Downloads" / "project_feedback_video.mp4"
    total = len(STORY)
    cmd = [
        ffmpeg_exe(), "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    frames = 0
    for i, slide in enumerate(STORY, start=1):
        n = int(round(slide["dur"] * FPS))
        base = render(slide, i, total)          # painted once per slide
        for k in range(n):
            frame = base.copy()                 # per frame: cheap copy + progress bar
            ImageDraw.Draw(frame).rectangle([0, H - 6, int(W * (k + 1) / n), H], fill=GREEN)
            proc.stdin.write(frame.tobytes())
            frames += 1
    proc.stdin.close()
    stderr = proc.stderr.read().decode("utf-8", "replace")
    code = proc.wait()

    if code != 0:
        print(stderr[-2000:])
        return code

    size = out.stat().st_size / 1_048_576
    dur = frames / FPS
    print(f"wrote {out}")
    print(f"  {frames} frames @ {FPS} fps = {int(dur // 60)}:{int(dur % 60):02d} min, {size:.1f} MiB, {total} slides")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
