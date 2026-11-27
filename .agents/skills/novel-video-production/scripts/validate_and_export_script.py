#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kiểm tra toàn bộ summaries/p01.json..pNN.json và xuất kịch bản, parts_manifest.json, scene_order.csv, thumbnails.json."""

import argparse
import csv
import json
import math
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Xác thực kịch bản từng phần và xuất manifest + markdown")
    parser.add_argument("--work-dir", required=True, help="Thư mục dự án video")
    parser.add_argument("--novel-title", required=True, help="Tên bộ truyện (vd: Bí Thư Trùng Sinh)")
    parser.add_argument("--source-chapters", type=int, required=True, help="Tổng số chương nguồn")
    parser.add_argument("--chapters-per-part", type=int, required=True, help="Số chương mỗi phần/scene do người dùng chọn")
    parser.add_argument("--forbidden-names", default="", help="Tên nhân vật/từ cấm trong thumbnail_lines, cách nhau bằng dấu phẩy")
    args = parser.parse_args()

    work_dir = Path(args.work_dir).resolve()
    prod_dir = work_dir / "production"
    summaries_dir = prod_dir / "summaries"
    total_parts = math.ceil(args.source_chapters / args.chapters_per_part)

    forbidden = [t.strip().lower() for t in args.forbidden_names.split(",") if t.strip()]
    forbidden.extend(["chương ", args.novel_title.strip().lower()])

    parts = []
    for n in range(1, total_parts + 1):
        fp = summaries_dir / f"p{n:02d}.json"
        if not fp.exists():
            raise FileNotFoundError(f"Missing summary file: {fp}")
        data = json.loads(fp.read_text(encoding="utf-8-sig"))
        assert data["part"] == n, f"Part mismatch in {fp}: {data['part']} != {n}"
        exp_start = (n - 1) * args.chapters_per_part + 1
        exp_end = min(n * args.chapters_per_part, args.source_chapters)
        assert data["chapter_start"] == exp_start, f"p{n:02d} chapter_start {data['chapter_start']} != {exp_start}"
        assert data["chapter_end"] == exp_end, f"p{n:02d} chapter_end {data['chapter_end']} != {exp_end}"
        for k in ("arc_stage", "summary", "scene_title", "visual_scene", "camera_motion", "image_prompt"):
            assert isinstance(data.get(k), str) and data[k].strip(), f"p{n:02d} empty {k}"
        lines = data.get("thumbnail_lines")
        assert isinstance(lines, list) and 2 <= len(lines) <= 3, f"p{n:02d} invalid thumbnail_lines: {lines}"
        for ln in lines:
            low = ln.lower()
            for tok in forbidden:
                if tok and tok in low:
                    raise AssertionError(f"p{n:02d} forbidden token {tok!r} in thumbnail_lines: {ln!r}")
            assert not re.search(r"chương\s*\d+", low), f"p{n:02d} chapter number in thumbnail_lines: {ln!r}"
        assert "STRICTLY NO text" in data["image_prompt"], f"p{n:02d} missing STRICTLY NO text clause"
        parts.append(data)

    md = [
        f"# {args.novel_title} — Kịch Bản {total_parts} Scene ({args.source_chapters} Chương)",
        "",
        f"- **Quy cách chia phần:** {args.chapters_per_part} chương/phần (Tổng {total_parts} phần, {args.source_chapters} chương).",
        f"- **Sản phẩm:** {total_parts} ảnh scene không chữ (`art/p01.png`–`p{total_parts:02d}.png`), {total_parts} thumbnail (`thumbnails/Chuong_XXXX-YYYY_TapZZZ.png`), và 1 video MP4 1080p 30fps không âm thanh kèm nhãn tên truyện góc trên bên phải.",
        "",
    ]

    manifest = []
    thumbs_index = []
    cursor = 0.0
    clip_dur = 3.5
    xfade_dur = 0.5

    for idx, p in enumerate(parts):
        n = p["part"]
        thumb_rel = f"thumbnails/Chuong_{p['chapter_start']:04d}-{p['chapter_end']:04d}_Tap{n:03d}.png"
        eff_start = round(cursor, 2)
        eff_end = round(cursor + (clip_dur if idx == 0 else (clip_dur - xfade_dur)), 2)
        cursor += clip_dur if idx == len(parts) - 1 else (clip_dur - xfade_dur)

        md.extend([
            f"## Scene {n:02d} — Chương {p['chapter_start']}–{p['chapter_end']} ({p['arc_stage']})",
            "",
            f"- **Tên cảnh:** {p['scene_title']}",
            f"- **Chuyển động camera:** `{p['camera_motion']}` (~{clip_dur}s clip, crossfade {xfade_dur}s)",
            f"- **Hook thumbnail:** {' / '.join(p['thumbnail_lines'])}",
            f"- **Tóm tắt diễn biến:** {p['summary']}",
            f"- **Kịch bản hình ảnh (không chữ):** {p['visual_scene']}",
            "",
        ])

        manifest.append({
            **p,
            "art": f"art/p{n:02d}.png",
            "thumbnail": thumb_rel,
            "timeline_approx_start": eff_start,
            "timeline_approx_end": eff_end,
        })
        thumbs_index.append({
            "part": n,
            "chapter_start": p["chapter_start"],
            "chapter_end": p["chapter_end"],
            "arc_stage": p["arc_stage"],
            "art": f"art/p{n:02d}.png",
            "thumbnail": thumb_rel,
            "hook": p["thumbnail_lines"],
        })

    (prod_dir / "kich_ban_scenes.md").write_text("\n".join(md), encoding="utf-8")
    (prod_dir / "parts_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (work_dir / "thumbnails.json").write_text(
        json.dumps(
            {
                "novel_title": args.novel_title,
                "chapters_per_part": args.chapters_per_part,
                "source_chapters": args.source_chapters,
                "total_parts": total_parts,
                "parts": thumbs_index,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    with (prod_dir / "scene_order.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["part", "chapter_start", "chapter_end", "arc_stage", "camera_motion", "scene_title", "art", "thumbnail", "hook"])
        for p in manifest:
            w.writerow([p["part"], p["chapter_start"], p["chapter_end"], p["arc_stage"], p["camera_motion"], p["scene_title"], p["art"], p["thumbnail"], " | ".join(p["thumbnail_lines"])])

    print(f"Validated {total_parts} parts covering chapters 1..{args.source_chapters}. Exported script, manifest, csv, and thumbnails.json.")


if __name__ == "__main__":
    main()
