#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tạo các file tóm lược nguồn (digests/p01.txt..pNN.txt) từ thư mục chương Chuong_*.txt của một bộ truyện."""

import argparse
import math
import re
from pathlib import Path


def extract_chapter_info(fp: Path) -> tuple[str, str]:
    """Đọc tiêu đề và một số đoạn tiêu biểu ngắn gọn của chương."""
    text = fp.read_text(encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0] if lines else fp.stem
    body = [ln for ln in lines[1:] if len(ln) > 25]
    picks = []
    if body:
        picks.append(body[0][:260])
        if len(body) > 2:
            picks.append(body[min(3, len(body) - 1)][:240])
        if len(body) > 6:
            picks.append(body[len(body) // 2][:240])
        if len(body) > 4:
            picks.append(body[-1][:240])
    return title, " [...] ".join(picks)


def chapter_num(fp: Path) -> int:
    m = re.search(r"(\d+)", fp.stem)
    return int(m.group(1)) if m else 0


def main():
    parser = argparse.ArgumentParser(description="Tạo digest nguồn theo từng phần từ thư mục chương truyện")
    parser.add_argument("--novel-dir", required=True, help="Thư mục chứa các file Chuong_*.txt")
    parser.add_argument("--work-dir", required=True, help="Thư mục dự án video output (vd video_<ten_truyen>)")
    parser.add_argument("--chapters-per-part", type=int, required=True, help="Số chương mỗi phần/scene do người dùng chọn (vd: 20, 40, 50)")
    args = parser.parse_args()

    novel_dir = Path(args.novel_dir).resolve()
    work_dir = Path(args.work_dir).resolve()
    out_dir = work_dir / "production" / "digests"
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(novel_dir.glob("Chuong_*.txt"), key=chapter_num)
    if not files:
        raise FileNotFoundError(f"Không tìm thấy Chuong_*.txt trong {novel_dir}")

    by_num = {chapter_num(f): f for f in files}
    total_chapters = max(by_num)
    total_parts = math.ceil(total_chapters / args.chapters_per_part)

    incomplete = []
    for part in range(1, total_parts + 1):
        c_start = (part - 1) * args.chapters_per_part + 1
        c_end = min(part * args.chapters_per_part, total_chapters)
        lines = [
            f"=== PHẦN {part:02d} (Chương {c_start} - {c_end}) ===",
            "",
            "DANH SÁCH TIÊU ĐỀ CHƯƠNG:",
        ]
        span = c_end - c_start + 1
        rep_chapters = {
            c_start + max(0, min(span - 1, off))
            for off in (0, span // 5, (2 * span) // 5, (3 * span) // 5, (4 * span) // 5, span - 1)
        }
        excerpts = []
        missing_in_part = []
        for ch in range(c_start, c_end + 1):
            fp = by_num.get(ch)
            if not fp:
                missing_in_part.append(ch)
                continue
            title, snippet = extract_chapter_info(fp)
            lines.append(f"- {title}")
            if ch in rep_chapters:
                excerpts.append(f"[{title}]\n{snippet}")

        if missing_in_part:
            incomplete.append((part, len(missing_in_part)))

        lines.extend(["", "TRÍCH ĐOẠN TIÊU BIỂU:", *excerpts])
        (out_dir / f"p{part:02d}.txt").write_text("\n".join(lines), encoding="utf-8")

    print(f"Novel: {novel_dir.name} | Chapters: {len(files)} (max={total_chapters}) | Parts: {total_parts} ({args.chapters_per_part}/part)")
    print(f"Digests saved in: {out_dir}")
    if incomplete:
        print(f"Warning - incomplete parts: {incomplete}")


if __name__ == "__main__":
    main()
