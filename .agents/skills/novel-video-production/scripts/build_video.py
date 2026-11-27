#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ghép các ảnh scene sạch (art/p01.png..pNN.png) thành video MP4 1080p 30fps không âm thanh, kèm nhãn tên truyện góc trên bên phải."""

import argparse
import json
import os
import re
import shutil
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FPS = 30
W, H = 1920, 1080


def slugify_title(title: str) -> str:
    norm = unicodedata.normalize("NFKD", title)
    ascii_s = "".join(c for c in norm if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D")
    words = re.findall(r"[A-Za-z0-9]+", ascii_s)
    return "_".join(w.capitalize() for w in words) or "Novel"


def find_badge_font() -> str:
    for candidate in (
        r"C:\Windows\Fonts\NotoSans-Bold.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
    ):
        if os.path.exists(candidate):
            return candidate
    raise FileNotFoundError("No bold system font found for title badge")


def create_title_badge_overlay(title: str, out_png: Path) -> Path:
    """Tạo ảnh PNG 1920x1080 trong suốt chứa pill tên truyện ở góc trên bên phải (giống mẫu ĐẠI NIẾT BÀN)."""
    scale = 2
    cw, ch = W * scale, H * scale
    text = title.strip().upper()
    font = ImageFont.truetype(find_badge_font(), 24 * scale)
    tracking = 2.5 * scale

    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    char_widths = [dummy.textlength(ch_i, font=font) for ch_i in text]
    total_tw = sum(char_widths) + tracking * max(0, len(text) - 1)
    tb = dummy.textbbox((0, 0), text, font=font)
    th = tb[3] - tb[1]

    pad_x = 32 * scale
    pill_h = 54 * scale
    pill_w = int(round(total_tw + 2 * pad_x))
    rad = pill_h // 2

    margin_r = 34 * scale
    margin_t = 28 * scale
    x1 = cw - margin_r
    x0 = x1 - pill_w
    y0 = margin_t
    y1 = y0 + pill_h

    layer = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    # Drop shadow
    sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([x0, y0 + 3 * scale, x1, y1 + 3 * scale], radius=rad, fill=(0, 0, 0, 150))
    layer = Image.alpha_composite(layer, sh.filter(ImageFilter.GaussianBlur(radius=5 * scale)))

    # Translucent dark navy-slate pill + crisp thin border
    pill = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pill)
    pd.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=rad,
        fill=(10, 15, 28, 200),
        outline=(205, 220, 245, 78),
        width=2 * scale,
    )
    layer = Image.alpha_composite(layer, pill)

    # Letter-spaced text vertically centered inside pill
    td = ImageDraw.Draw(layer)
    cur_x = x0 + (pill_w - total_tw) / 2.0
    text_y = y0 + (pill_h - th) / 2.0 - tb[1] - 1 * scale
    for ch_i, cw_i in zip(text, char_widths):
        td.text((cur_x, text_y), ch_i, font=font, fill=(246, 249, 255, 245))
        cur_x += cw_i + tracking

    final_overlay = layer.resize((W, H), resample=Image.Resampling.LANCZOS)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    final_overlay.save(out_png, format="PNG")
    return out_png


def zoompan_expr(motion: str, frames: int) -> str:
    n = max(1, frames - 1)
    p = f"(on/{n})"
    if motion == "pushIn":
        z, x, y = f"1.0+0.08*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == "zoomOut":
        z, x, y = f"1.08-0.08*{p}", "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    elif motion == "panLeft":
        z, x, y = "1.08", f"(iw-iw/zoom)*(1.0-{p})", "ih/2-(ih/zoom/2)"
    elif motion == "panRight":
        z, x, y = "1.08", f"(iw-iw/zoom)*{p}", "ih/2-(ih/zoom/2)"
    elif motion == "driftUp":
        z, x, y = "1.08", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*(1.0-{p})"
    else:
        z, x, y = "1.08", "iw/2-(iw/zoom/2)", f"(ih-ih/zoom)*{p}"
    return f"scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s=1920x1080:fps={FPS},format=yuv420p"


def render_clip(art_dir: Path, temp_dir: Path, part: dict, clip_dur: float) -> Path:
    n = part["part"]
    art_path = art_dir / f"p{n:02d}.png"
    assert art_path.exists(), f"Missing clean art: {art_path}"
    assert "thumbnails" not in str(art_path).lower(), f"Refusing thumbnail input: {art_path}"

    frames = int(round(clip_dur * FPS))
    out_clip = temp_dir / f"c{n:02d}.mp4"
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-loop", "1", "-i", str(art_path),
        "-vf", zoompan_expr(part.get("camera_motion", "pushIn"), frames),
        "-t", f"{clip_dur:.2f}",
        "-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p",
        "-an", str(out_clip),
    ]
    subprocess.run(cmd, check=True)
    return out_clip


def xfade_merge(clips: list[Path], clip_duration: float, xfade_dur: float, out_path: Path, badge_png: Path | None = None, final_pass: bool = False):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    for c in clips:
        cmd.extend(["-i", str(c)])
    if badge_png is not None:
        cmd.extend(["-i", str(badge_png)])

    filters = []
    if len(clips) == 1:
        prev = "[0:v]"
    else:
        prev = "[0:v]"
        step = clip_duration - xfade_dur
        for i in range(1, len(clips)):
            offset = round(i * step, 3)
            nxt = f"[v{i}]" if i < len(clips) - 1 else "[vmerged]"
            filters.append(f"{prev}[{i}:v]xfade=transition=fade:duration={xfade_dur}:offset={offset}{nxt}")
            prev = nxt

    if badge_png is not None:
        badge_idx = len(clips)
        filters.append(f"{prev}[{badge_idx}:v]overlay=0:0:format=auto,format=yuv420p[vout]")
        out_label = "[vout]"
    else:
        out_label = prev

    if filters:
        cmd.extend(["-filter_complex", ";".join(filters), "-map", out_label])
    else:
        cmd.extend(["-map", "0:v"])

    if final_pass:
        cmd.extend(["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an"])
    else:
        cmd.extend(["-c:v", "libx264", "-crf", "14", "-preset", "fast", "-pix_fmt", "yuv420p", "-an"])
    cmd.append(str(out_path))
    subprocess.run(cmd, check=True)


def overlay_existing_video(src_mp4: Path, badge_png: Path, out_mp4: Path):
    """Đóng dấu badge góc trên bên phải lên video MP4 sẵn có không cần render lại từng cảnh."""
    tmp_out = out_mp4.with_name(out_mp4.stem + ".tmp.mp4")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(src_mp4),
        "-i", str(badge_png),
        "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto,format=yuv420p[vout]",
        "-map", "[vout]",
        "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", "-an",
        str(tmp_out),
    ]
    subprocess.run(cmd, check=True)
    os.replace(tmp_out, out_mp4)


def extract_qa(video_path: Path, prod_dir: Path, temp_dir: Path, total_dur: float):
    temp_dir.mkdir(parents=True, exist_ok=True)
    picks = [max(0.5, min(total_dur - 1.0, total_dur * frac)) for frac in (0.01, 0.17, 0.34, 0.50, 0.68, 0.96)]
    frames = []
    for idx, t in enumerate(picks):
        fp = temp_dir / f"frame_{idx}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", str(video_path), "-frames:v", "1", str(fp)],
            check=True,
        )
        frames.append((t, fp))

    sheet = Image.new("RGB", (1920, 780), "#141922")
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22)
    for i, (t, fp) in enumerate(frames):
        x, y = (i % 3) * 640, (i // 3) * 390
        with Image.open(fp) as im:
            sheet.paste(ImageOps.fit(im.convert("RGB"), (640, 360)), (x, y))
            if i == 0:
                crop = im.crop((int(im.width * 0.68), 0, im.width, int(im.height * 0.16)))
                crop.save(prod_dir / "qa_badge_crop.png")
        d.text((x + 10, y + 362), f"t = {t:.1f}s", font=font, fill="white")
    sheet.save(prod_dir / "qa_video_frames.jpg", quality=92)


def main():
    parser = argparse.ArgumentParser(description="Dựng video MP4 1080p không âm thanh từ art/p01..pNN.png kèm nhãn tên truyện")
    parser.add_argument("--work-dir", required=True, help="Thư mục dự án video")
    parser.add_argument("--title", required=True, help="Tên bộ truyện hiển thị góc trên bên phải (để trống '' để tắt)")
    parser.add_argument("--output", default=None, help="Đường dẫn file MP4 đầu ra")
    parser.add_argument("--clip-duration", type=float, default=3.5, help="Thời lượng mỗi clip trước khi xfade (giây)")
    parser.add_argument("--xfade", type=float, default=0.5, help="Thời lượng chuyển cảnh fade (giây)")
    parser.add_argument("--overlay-only", default=None, help="Chỉ gắn nhãn tên truyện lên video MP4 đã có")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    prod_dir = work_dir / "production"
    art_dir = work_dir / "art"
    temp_dir = prod_dir / "temp_clips"

    manifest = json.loads((prod_dir / "parts_manifest.json").read_text(encoding="utf-8"))
    total_parts = len(manifest)
    default_name = f"{slugify_title(args.title or work_dir.name)}_{total_parts}_Scenes.mp4"
    out_video = Path(args.output).resolve() if args.output else (work_dir / default_name)

    badge_png = None
    if args.title and args.title.strip():
        badge_png = create_title_badge_overlay(args.title.strip(), prod_dir / "title_badge.png")

    if args.overlay_only:
        src_mp4 = Path(args.overlay_only).resolve()
        assert src_mp4.exists(), f"Missing source video: {src_mp4}"
        assert badge_png is not None, "--overlay-only requires non-empty --title"
        overlay_existing_video(src_mp4, badge_png, out_video)
    else:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir(parents=True, exist_ok=True)

        print(f"Stage A: Rendering {total_parts} Ken Burns clips...")
        clips_by_part = {}
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = {ex.submit(render_clip, art_dir, temp_dir, p, args.clip_duration): p["part"] for p in manifest}
            for fut in as_completed(futs):
                part_no = futs[fut]
                clips_by_part[part_no] = fut.result()

        ordered = [clips_by_part[n] for n in range(1, total_parts + 1)]
        if len(ordered) <= 12:
            print("Stage B: Merging all clips into final MP4...")
            xfade_merge(ordered, args.clip_duration, args.xfade, out_video, badge_png=badge_png, final_pass=True)
        else:
            print("Stage B1: Merging batches of 10 clips...")
            batches = []
            batch_step = 10
            for b_idx, start in enumerate(range(0, len(ordered), batch_step), 1):
                group = ordered[start : start + batch_step]
                batch_out = temp_dir / f"batch_{b_idx:02d}.mp4"
                xfade_merge(group, args.clip_duration, args.xfade, batch_out, badge_png=None, final_pass=False)
                batches.append((batch_out, len(group)))
            # Note: all full batches have identical duration; if last batch is shorter, build step offsets accurately
            print("Stage B2: Merging batches + top-right title badge into final MP4...")
            cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
            for b_path, _ in batches:
                cmd.extend(["-i", str(b_path)])
            if badge_png is not None:
                cmd.extend(["-i", str(badge_png)])
            filters = []
            prev = "[0:v]"
            cursor = batches[0][1] * args.clip_duration - (batches[0][1] - 1) * args.xfade
            for i in range(1, len(batches)):
                offset = round(cursor - args.xfade, 3)
                nxt = f"[v{i}]" if i < len(batches) - 1 else "[vmerged]"
                filters.append(f"{prev}[{i}:v]xfade=transition=fade:duration={args.xfade}:offset={offset}{nxt}")
                prev = nxt
                b_dur = batches[i][1] * args.clip_duration - (batches[i][1] - 1) * args.xfade
                cursor = offset + b_dur
            if badge_png is not None:
                filters.append(f"{prev}[{len(batches)}:v]overlay=0:0:format=auto,format=yuv420p[vout]")
                out_label = "[vout]"
            else:
                out_label = prev
            cmd.extend(["-filter_complex", ";".join(filters), "-map", out_label, "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(out_video)])
            subprocess.run(cmd, check=True)

    probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_format", "-show_streams", str(out_video)], text=True)
    dur_m = re.search(r"duration=([\d.]+)", probe)
    total_dur = float(dur_m.group(1)) if dur_m else (total_parts * args.clip_duration - (total_parts - 1) * args.xfade)
    extract_qa(out_video, prod_dir, temp_dir, total_dur)
    shutil.rmtree(temp_dir, ignore_errors=True)
    print(probe)
    print(f"Done: {out_video}")


if __name__ == "__main__":
    main()
