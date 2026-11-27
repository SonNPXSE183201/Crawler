#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render bộ thumbnails (1920x1080) từ art/p01.png..pNN.png theo phong cách thumbnails_v3."""

import argparse
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

SKILL_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_FONT = SKILL_ROOT / "resources" / "Anton-Regular.ttf"

W, H = 1920, 1080
SHEAR = -0.11


def shear_layer(img: Image.Image, shear: float = SHEAR) -> Image.Image:
    cy = img.height / 2.0
    xshift = -shear * cy
    return img.transform(
        img.size,
        Image.Transform.AFFINE,
        (1.0, -shear, -xshift, 0.0, 1.0, 0.0),
        resample=Image.Resampling.BICUBIC,
    )


def add_left_vignette(base: Image.Image) -> Image.Image:
    arr = np.array(base.convert("RGBA"), dtype=np.float32)
    x = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :]
    t = np.clip(1.0 - (x / 0.58), 0.0, 1.0)
    alpha = ((t ** 1.45) * 0.84)[:, :, None]
    dark = np.array([6.0, 9.0, 15.0], dtype=np.float32)[None, None, :]
    arr[:, :, :3] = arr[:, :, :3] * (1.0 - alpha) + dark * alpha
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), mode="RGBA")


def balanced_split(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if len(words) <= 2:
        return [text]
    best = None
    best_diff = 10**9
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for split_at in range(1, len(words)):
        left = " ".join(words[:split_at])
        right = " ".join(words[split_at:])
        lw = dummy.textbbox((0, 0), left, font=font, stroke_width=14)[2]
        rw = dummy.textbbox((0, 0), right, font=font, stroke_width=14)[2]
        if lw <= max_width and rw <= max_width:
            diff = abs(lw - rw)
            if diff < best_diff:
                best_diff = diff
                best = [left, right]
    if best:
        return best
    out, cur = [], []
    for w in words:
        cand = " ".join(cur + [w])
        cw = dummy.textbbox((0, 0), cand, font=font, stroke_width=14)[2]
        if cur and cw > max_width:
            out.append(" ".join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        out.append(" ".join(cur))
    return out


def wrap_hook_lines(lines: list[str], font: ImageFont.FreeTypeFont, max_width: int, allow_wrap: bool = True) -> list[tuple[str, bool]]:
    result = []
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    for idx, raw in enumerate(lines):
        is_white = (idx == 0)
        text = raw.strip().upper()
        bbox = dummy.textbbox((0, 0), text, font=font, stroke_width=14)
        if bbox[2] - bbox[0] <= max_width or not allow_wrap:
            result.append((text, is_white))
        else:
            for part_line in balanced_split(text, font, max_width):
                result.append((part_line, is_white))
    return result


def measure_block(wrapped: list[tuple[str, bool]], font: ImageFont.FreeTypeFont, line_gap: int):
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    widths, heights = [], []
    for txt, _ in wrapped:
        bb = dummy.textbbox((0, 0), txt, font=font, stroke_width=14)
        widths.append(bb[2] - bb[0])
        heights.append(bb[3] - bb[1])
    total_h = sum(heights) + max(0, len(wrapped) - 1) * line_gap
    return max(widths, default=0), total_h, heights


def fit_typography(font_path: Path, lines: list[str], max_width: int = 850, max_height: int = 670):
    for size in range(144, 84, -4):
        font = ImageFont.truetype(str(font_path), size)
        wrapped = wrap_hook_lines(lines, font, max_width, allow_wrap=False)
        line_gap = int(size * 0.24)
        mw, th, heights = measure_block(wrapped, font, line_gap)
        if mw <= max_width and th <= max_height:
            return font, wrapped, line_gap, mw, th, heights
    for size in range(136, 76, -4):
        font = ImageFont.truetype(str(font_path), size)
        wrapped = wrap_hook_lines(lines, font, max_width, allow_wrap=True)
        if len(wrapped) > 5:
            continue
        line_gap = int(size * 0.22)
        mw, th, heights = measure_block(wrapped, font, line_gap)
        if mw <= max_width and th <= max_height:
            return font, wrapped, line_gap, mw, th, heights
    font = ImageFont.truetype(str(font_path), 78)
    wrapped = wrap_hook_lines(lines, font, max_width, allow_wrap=True)
    line_gap = 18
    mw, th, heights = measure_block(wrapped, font, line_gap)
    return font, wrapped, line_gap, mw, th, heights


def draw_gold_gradient_text(layer_size: tuple[int, int], xy: tuple[int, int], text: str, font: ImageFont.FreeTypeFont, is_white: bool, stroke_w: int = 13) -> Image.Image:
    w, h = layer_size
    sh_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(sh_layer).text((xy[0] + 6, xy[1] + 10), text, font=font, fill=(0, 0, 0, 230), stroke_width=stroke_w + 2, stroke_fill=(0, 0, 0, 230))
    sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(radius=8))

    st_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(st_layer).text(xy, text, font=font, fill=(0, 0, 0, 255), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 255))

    mask = Image.new("L", (w, h), 0)
    m_draw = ImageDraw.Draw(mask)
    m_draw.text(xy, text, font=font, fill=255)
    bb = m_draw.textbbox(xy, text, font=font)
    y0, y1 = max(0, bb[1]), min(h, bb[3])

    fill_grad = Image.new("RGBA", (w, h), (255, 255, 255, 255) if is_white else (255, 214, 0, 255))
    if not is_white and y1 > y0:
        arr = np.zeros((h, w, 4), dtype=np.uint8)
        t = np.linspace(0.0, 1.0, y1 - y0, dtype=np.float32)[:, None]
        arr[y0:y1, :, 0] = 255
        arr[y0:y1, :, 1] = np.clip(242 - t * 52, 0, 255).astype(np.uint8)
        arr[y0:y1, :, 2] = np.clip(76 - t * 76, 0, 255).astype(np.uint8)
        arr[y0:y1, :, 3] = 255
        fill_grad = Image.fromarray(arr, mode="RGBA")

    fill_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fill_layer.paste(fill_grad, (0, 0), mask)
    return Image.alpha_composite(Image.alpha_composite(sh_layer, st_layer), fill_layer)


def draw_red_badge(font_path: Path, part_num: int, center_x: int, top_y: int) -> Image.Image:
    badge_text = f"PHẦN {part_num:02d}"
    b_font = ImageFont.truetype(str(font_path), 62)
    dummy = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    tb = dummy.textbbox((0, 0), badge_text, font=b_font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    bw, bh = tw + 116, th + 44
    rad = bh // 2

    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bx0 = max(60, center_x - bw // 2)
    by0 = top_y
    bx1, by1 = bx0 + bw, by0 + bh

    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([bx0 + 4, by0 + 8, bx1 + 4, by1 + 8], radius=rad, fill=(0, 0, 0, 210))
    layer = Image.alpha_composite(layer, sh.filter(ImageFilter.GaussianBlur(radius=9)))

    pill = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    p_arr = np.zeros((bh, bw, 4), dtype=np.uint8)
    t = np.linspace(0.0, 1.0, bh, dtype=np.float32)[:, None]
    p_arr[:, :, 0] = np.clip(236 - t * 70, 0, 255).astype(np.uint8)
    p_arr[:, :, 1] = np.clip(24 - t * 20, 0, 255).astype(np.uint8)
    p_arr[:, :, 2] = np.clip(24 - t * 20, 0, 255).astype(np.uint8)
    p_arr[:, :, 3] = 255
    pill_mask = Image.new("L", (bw, bh), 0)
    ImageDraw.Draw(pill_mask).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=rad, fill=255)
    pill.paste(Image.fromarray(p_arr, mode="RGBA"), (0, 0), pill_mask)
    ImageDraw.Draw(pill).rounded_rectangle([2, 2, bw - 3, bh - 3], radius=rad - 2, outline=(255, 110, 110, 140), width=2)
    layer.paste(pill, (bx0, by0), pill)

    t_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    tx = bx0 + (bw - tw) // 2 - tb[0]
    ty = by0 + (bh - th) // 2 - tb[1] - 2
    ImageDraw.Draw(t_layer).text((tx, ty), badge_text, font=b_font, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(90, 0, 0, 220))
    return Image.alpha_composite(layer, shear_layer(t_layer, SHEAR))


def render_one(art_dir: Path, font_path: Path, part: dict, out_path: Path):
    n = part["part"]
    with Image.open(art_dir / f"p{n:02d}.png") as src:
        base = ImageOps.fit(src.convert("RGB"), (W, H), method=Image.Resampling.LANCZOS)

    canvas = add_left_vignette(base)
    font, wrapped, line_gap, max_line_w, total_text_h, heights = fit_typography(font_path, part["thumbnail_lines"])
    badge_h, badge_gap = 96, 42
    block_h = total_text_h + badge_gap + badge_h
    start_y = max(65, (H - block_h) // 2)
    left_margin = 76

    text_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dummy = ImageDraw.Draw(text_layer)
    cur_y = start_y
    for idx, (txt, is_white) in enumerate(wrapped):
        bb = dummy.textbbox((0, 0), txt, font=font, stroke_width=14)
        line_img = draw_gold_gradient_text((W, H), (left_margin - bb[0], cur_y - bb[1]), txt, font, is_white=is_white)
        text_layer = Image.alpha_composite(text_layer, line_img)
        cur_y += heights[idx] + line_gap

    canvas = Image.alpha_composite(canvas, shear_layer(text_layer, SHEAR))
    badge_cx = left_margin + max(240, max_line_w // 2)
    canvas = Image.alpha_composite(canvas, draw_red_badge(font_path, n, center_x=badge_cx, top_y=cur_y - line_gap + badge_gap))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, format="PNG", optimize=True)


def make_contact_sheets(thumb_dir: Path, prod_dir: Path):
    import re
    files = sorted(
        thumb_dir.glob("Chuong_*_Tap*.png"),
        key=lambda p: int(re.search(r"_Tap(\d+)$", p.stem).group(1)) if re.search(r"_Tap(\d+)$", p.stem) else 0,
    )
    if not files:
        files = sorted(thumb_dir.glob("p[0-9][0-9].png"))
    font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 14)
    for b_idx, start in enumerate(range(0, len(files), 16), 1):
        group = files[start : start + 16]
        rows = (len(group) + 3) // 4
        sheet = Image.new("RGB", (1280, rows * 204), "#141922")
        d = ImageDraw.Draw(sheet)
        for i, fp in enumerate(group):
            x, y = (i % 4) * 320, (i // 4) * 204
            with Image.open(fp) as im:
                sheet.paste(ImageOps.fit(im.convert("RGB"), (320, 180)), (x, y))
            d.text((x + 8, y + 184), fp.stem, font=font, fill="white")
        sheet.save(prod_dir / f"qa_thumbnails_{b_idx:02d}.jpg", quality=92)


def main():
    parser = argparse.ArgumentParser(description="Render bộ thumbnail tiếng Việt từ ảnh scene sạch")
    parser.add_argument("--work-dir", required=True, help="Thư mục dự án video")
    parser.add_argument("--parts", nargs="*", type=int, help="Render các phần cụ thể (mặc định: tất cả)")
    parser.add_argument("--font", default=str(DEFAULT_FONT), help="Đường dẫn file font .ttf")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    prod_dir = work_dir / "production"
    art_dir = work_dir / "art"
    thumb_dir = work_dir / "thumbnails"
    font_path = Path(args.font).resolve()
    assert font_path.exists(), f"Missing font: {font_path}"

    manifest = json.loads((prod_dir / "parts_manifest.json").read_text(encoding="utf-8"))
    target_set = set(args.parts) if args.parts else None
    rendered = 0
    for p in manifest:
        n = p["part"]
        if target_set and n not in target_set:
            continue
        out_name = f"Chuong_{p['chapter_start']:04d}-{p['chapter_end']:04d}_Tap{n:03d}.png"
        render_one(art_dir, font_path, p, thumb_dir / out_name)
        rendered += 1

    if not target_set or len(target_set) == len(manifest):
        make_contact_sheets(thumb_dir, prod_dir)
    print(f"Rendered {rendered} thumbnails into {thumb_dir}")


if __name__ == "__main__":
    main()
