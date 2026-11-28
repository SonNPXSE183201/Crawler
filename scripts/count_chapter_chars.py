#!/usr/bin/env python3
"""Đếm số ký tự, từ, dòng và đoạn văn cho một chương truyện (.txt)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

CHAPTER_HEADING_RE = re.compile(
    r"^(chương|chuong|chapter|hồi|hoi|quyển|quyen)\b",
    re.IGNORECASE,
)
CHUONG_FILE_RE = re.compile(r"^Chuong_(\d+)\.txt$", re.IGNORECASE)


def configure_utf8_streams() -> None:
    """Đảm bảo stdout/stderr in tiếng Việt có dấu ổn định trên Windows."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def is_chapter_txt(path: Path) -> bool:
    """Loại bỏ các file phụ không phải chương truyện (_loi.txt, *_FULL.txt, v.v.)."""
    if not path.is_file() or path.suffix.lower() != ".txt":
        return False
    name = path.name
    if name.startswith("_") or name.lower().endswith("_full.txt"):
        return False
    return True


def find_chapter_files(novel_dir: Path) -> list[tuple[int | None, Path]]:
    """Tìm và sắp xếp tự nhiên các file chương trong một thư mục truyện."""
    if not novel_dir.is_dir():
        return []

    txt_files = [p for p in novel_dir.iterdir() if is_chapter_txt(p)]
    if not txt_files:
        return []

    chuong_matches: list[tuple[int, Path]] = []
    for path in txt_files:
        m = CHUONG_FILE_RE.match(path.name)
        if m:
            chuong_matches.append((int(m.group(1)), path))

    if chuong_matches:
        chuong_matches.sort(key=lambda item: (item[0], item[1].name.lower()))
        return [(num, p) for num, p in chuong_matches]

    numbered: list[tuple[int, int, str, int | None, Path]] = []
    for path in txt_files:
        m = re.search(r"(\d+)", path.stem)
        if m:
            num = int(m.group(1))
            numbered.append((0, num, path.name.lower(), num, path))
        else:
            numbered.append((1, 0, path.name.lower(), None, path))

    numbered.sort(key=lambda item: (item[0], item[1], item[2]))
    return [(item[3], item[4]) for item in numbered]


def count_chapter_file(path: Path) -> dict:
    """Đọc file chương UTF-8 và trả về thống kê ký tự, từ, dòng, đoạn."""
    raw = path.read_text(encoding="utf-8-sig", errors="replace")
    text = raw.replace("\r\n", "\n").replace("\r", "\n")

    raw_lines = text.splitlines()
    title = ""
    first_non_empty_idx: int | None = None
    for idx, line in enumerate(raw_lines):
        stripped = line.strip()
        if stripped:
            title = stripped
            first_non_empty_idx = idx
            break

    if first_non_empty_idx is not None and CHAPTER_HEADING_RE.match(title):
        body_lines = raw_lines[first_non_empty_idx + 1 :]
        while body_lines and not body_lines[0].strip():
            body_lines.pop(0)
        body_text = "\n".join(body_lines)
        if text.endswith("\n") and body_text:
            body_text += "\n"
    else:
        body_text = text

    chars_with_spaces = len(text)
    chars_no_newlines = len(text.replace("\n", ""))
    chars_no_spaces = len(re.sub(r"\s+", "", text))
    body_chars_with_spaces = len(body_text)
    body_chars_no_spaces = len(re.sub(r"\s+", "", body_text))
    words = len(text.split())
    lines = len(raw_lines)
    paragraphs = sum(1 for ln in raw_lines if ln.strip())

    return {
        "file": path.name,
        "path": str(path.resolve()),
        "title": title,
        "chars_with_spaces": chars_with_spaces,
        "chars_no_newlines": chars_no_newlines,
        "chars_no_spaces": chars_no_spaces,
        "body_chars_with_spaces": body_chars_with_spaces,
        "body_chars_no_spaces": body_chars_no_spaces,
        "words": words,
        "lines": lines,
        "paragraphs": paragraphs,
    }


def resolve_chapter_path(
    chapter_file: str | None,
    novel_dir: str | None,
    chapter_num: int | None,
) -> Path:
    """Xác định đường dẫn file chương từ tham số dòng lệnh."""
    if chapter_file:
        path = Path(chapter_file)
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy file chương: {path}")
        return path

    if novel_dir is not None and chapter_num is not None:
        ndir = Path(novel_dir)
        if not ndir.is_dir():
            raise FileNotFoundError(f"Không tìm thấy thư mục truyện: {ndir}")

        direct = ndir / f"Chuong_{chapter_num:04d}.txt"
        if direct.is_file():
            return direct

        for num, path in find_chapter_files(ndir):
            if num == chapter_num:
                return path
        raise FileNotFoundError(
            f"Không tìm thấy chương {chapter_num} trong thư mục: {ndir}"
        )

    raise ValueError(
        "Cần truyền đường dẫn <chapter_file> hoặc dùng cặp --novel <thư_mục> --chapter <số>."
    )


def format_report(stats: dict) -> str:
    """Định dạng báo cáo thống kê 1 chương bằng tiếng Việt."""
    lines = [
        f"File: {stats['file']}",
        f"Đường dẫn: {stats['path']}",
        f"Tiêu đề: {stats['title'] or '(Không có)'}",
        "-" * 50,
        f"Tổng ký tự (gồm khoảng trắng & xuống dòng): {stats['chars_with_spaces']:,}",
        f"Tổng ký tự (không tính xuống dòng):         {stats['chars_no_newlines']:,}",
        f"Tổng ký tự (không tính khoảng trắng):       {stats['chars_no_spaces']:,}",
        f"Nội dung - bỏ tiêu đề (gồm khoảng trắng):   {stats['body_chars_with_spaces']:,}",
        f"Nội dung - bỏ tiêu đề (không khoảng trắng): {stats['body_chars_no_spaces']:,}",
        f"Tổng số từ (tách theo khoảng trắng):        {stats['words']:,}",
        f"Tổng số dòng:                               {stats['lines']:,}",
        f"Số đoạn văn (dòng có nội dung):             {stats['paragraphs']:,}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Đếm số ký tự, từ và đoạn văn của một chương truyện (.txt)."
    )
    parser.add_argument(
        "chapter_file",
        nargs="?",
        help="Đường dẫn tới file chương (.txt).",
    )
    parser.add_argument(
        "--novel",
        help="Thư mục bộ truyện để tìm chương theo số (dùng kèm --chapter).",
    )
    parser.add_argument(
        "--chapter",
        type=int,
        help="Số chương cần đếm trong thư mục --novel.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới dạng JSON.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_streams()
    parser = build_parser()
    args = parser.parse_args(argv)

    if (args.novel is None) != (args.chapter is None) and not args.chapter_file:
        print(
            "Lỗi: Khi dùng --novel hoặc --chapter thì phải truyền đủ cả hai.",
            file=sys.stderr,
        )
        return 1

    try:
        target = resolve_chapter_path(args.chapter_file, args.novel, args.chapter)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1

    stats = count_chapter_file(target)
    if args.json:
        print(json.dumps(stats, ensure_ascii=False, indent=2))
    else:
        print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
