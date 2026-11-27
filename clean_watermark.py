#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Clean Watermark Tool for Web Novels
Loại bỏ các watermark quảng cáo web truyện (Truyện FULL, TruyenFull.vn, tunghoanh, ...)
nằm xen kẽ trong câu hoặc đứng riêng thành dòng khỏi các file Chuong_*.txt.
"""

import argparse
import glob
import os
import re
from typing import Tuple

# Thứ tự ưu tiên: cụm từ dài/cụ thể trước, mẫu ngắn/dự phòng sau
_TF_DOMAIN = r"(?:https?://)?(?:www\.)?(?:TruyenFull\.vn|TruyệnFULL\.vn|Truy[ệe]n\s*FULL|TruyenFull)"
WATERMARK_PATTERNS = [
    # "Bạn đang xem truyện được sao chép tại: TruyenFull.vn chấm c.o.m"
    rf"Bạn đang xem truyện được sao chép tại\s*:?\s*{_TF_DOMAIN}(?:\s*chấm\s*c\.o\.m)?",
    # "Bạn đang xem tại Truyện FULL - www.Truyện FULL"
    rf"Bạn đang xem tại\s*{_TF_DOMAIN}(?:\s*-\s*{_TF_DOMAIN})?",
    # "Bạn đang đọc chuyện/truyện tại Truyện FULL / TruyệnFULL.vn"
    rf"Bạn đang đọc (?:truyện|chuyện) tại\s*:?\s*{_TF_DOMAIN}(?:\s*-\s*{_TF_DOMAIN})?",
    # "Đọc Truyện Online mới nhất ở TruyenFull.vn"
    rf"Đọc Truy[ệe]n Online mới nhất ở\s*{_TF_DOMAIN}",
    # "Truyện/Text được copy/lấy/sao chép tại Truyện FULL / TruyenFull.vn"
    rf"(?:Truy[ệe]n|Text)\s+được\s+(?:copy|lấy|sao chép)\s+tại\s*:?\s*{_TF_DOMAIN}(?:\s*chấm\s*c\.o\.m)?",
    # "Nguồn tại http://Truyện FULL" / "nguồn TruyenFull.vn"
    rf"Nguồn(?:\s+(?:tại|truyện))?\s*:?\s*{_TF_DOMAIN}",
    # "xem tại TruyenFull.vn"
    rf"xem\s+tại\s*:?\s*{_TF_DOMAIN}",
    # "nguồn truyện t u n g h o a n h. c o m" / "nguồn t.u.n.g h.o.a.n.h (.) c.o.m"
    r"nguồn\s+(?:truyện\s+)?t[\s.]*u[\s.]*n[\s.]*g[\s.]*h[\s.]*o[\s.]*a[\s.]*n[\s.]*h(?:\s*\(\.\)|\s*\.)?\s*c[\s.]*o[\s.]*m",
    # Mảnh sót ".vn chấm c.o.m" hoặc "chấm c.o.m" từ TruyenFull
    r"\.vn\s*chấm\s*c\.o\.m",
    # Mẫu dự phòng còn sót
    rf"{_TF_DOMAIN}(?:\s*chấm\s*c\.o\.m)?",
]

INLINE_WATERMARK_RE = re.compile(
    "|".join(f"(?:{p})" for p in WATERMARK_PATTERNS),
    re.IGNORECASE,
)


def clean_watermark_text(text: str) -> Tuple[str, int]:
    """Loại bỏ watermark khỏi chuỗi văn bản và chuẩn hóa khoảng trắng từng dòng.

    Trả về (văn bản đã làm sạch, số lượng watermark đã xóa).
    """
    removed_count = 0
    out_lines = []
    # Giữ nguyên kiểu xuống dòng gốc nếu có, chuẩn hóa qua splitlines
    for line in text.splitlines():
        if not line.strip():
            out_lines.append("")
            continue

        matches = INLINE_WATERMARK_RE.findall(line)
        if matches:
            removed_count += len(matches)
            new_line = INLINE_WATERMARK_RE.sub("", line)
            # Thu gọn khoảng trắng thừa do cắt bỏ watermark
            new_line = re.sub(r"[ \t]{2,}", " ", new_line)
            new_line = re.sub(r"\s+([.,!?;:])", r"\1", new_line)
            new_line = new_line.strip()
            # Nếu cả dòng chỉ chứa watermark (nay đã rỗng), bỏ qua dòng này
            if not new_line:
                continue
            out_lines.append(new_line)
        else:
            out_lines.append(line.rstrip())

    # Thu gọn > 2 dòng trống liên tiếp phát sinh do xóa dòng chỉ chứa watermark
    cleaned = "\n".join(out_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if text.endswith("\n") and not cleaned.endswith("\n"):
        cleaned += "\n"
    return cleaned, removed_count


def clean_file(filepath: str, dry_run: bool = False) -> Tuple[bool, int]:
    """Làm sạch 1 file txt. Trả về (modified, removed_count)."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    cleaned, removed_count = clean_watermark_text(content)
    if removed_count > 0 and cleaned != content:
        if not dry_run:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(cleaned)
        return True, removed_count
    return False, 0


def clean_folder(folder_path: str, dry_run: bool = False) -> Tuple[int, int, int]:
    """Quét và làm sạch toàn bộ các file Chuong_*.txt trong thư mục."""
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Thư mục không tồn tại: {folder_path}")

    files = sorted(glob.glob(os.path.join(folder_path, "Chuong_*.txt")))
    modified_files = 0
    total_removed = 0
    for fp in files:
        mod, cnt = clean_file(fp, dry_run=dry_run)
        if mod:
            modified_files += 1
            total_removed += cnt

    mode = "[DRY-RUN] " if dry_run else ""
    print(f"{mode}Folder: {folder_path}")
    print(f"{mode}Scanned {len(files)} chapters | Modified: {modified_files} | Watermarks removed: {total_removed}")
    return len(files), modified_files, total_removed


def main():
    parser = argparse.ArgumentParser(description="Loại bỏ watermark TruyenFull / copy tại khỏi file chương truyện")
    parser.add_argument("--path", required=True, help="Đường dẫn file hoặc thư mục chứa Chuong_*.txt")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ kiểm tra, không ghi đè file")
    args = parser.parse_args()

    if os.path.isfile(args.path):
        mod, cnt = clean_file(args.path, dry_run=args.dry_run)
        print(f"File: {args.path} | Modified: {mod} | Watermarks removed: {cnt}")
    else:
        clean_folder(args.path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
