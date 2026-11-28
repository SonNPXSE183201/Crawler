#!/usr/bin/env python3
"""Đếm số ký tự, từ và đoạn văn cho một bộ truyện hoặc tất cả các bộ truyện."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from count_chapter_chars import (  # noqa: E402
    configure_utf8_streams,
    count_chapter_file,
    find_chapter_files,
)

SKIP_DIR_NAMES = {"__pycache__"}


def _collect_novel_subdirs(parent_dir: Path) -> list[Path]:
    """Lấy tất cả thư mục con cấp 1 có chứa file chương truyện."""
    novels: list[Path] = []
    children = sorted(
        (
            p
            for p in parent_dir.iterdir()
            if p.is_dir()
            and not p.name.startswith(".")
            and p.name not in SKIP_DIR_NAMES
        ),
        key=lambda p: p.name.lower(),
    )
    for sub in children:
        if find_chapter_files(sub):
            novels.append(sub)
    return novels


def discover_novels(targets: list[str], scan_all: bool) -> tuple[list[Path], bool]:
    """Khám phá danh sách thư mục truyện từ targets hoặc mặc định output/.

    Trả về (danh sách thư mục truyện, is_parent_scan).
    """
    default_output = SCRIPT_DIR.parent / "output"
    raw_targets = [Path(t) for t in targets] if targets else [default_output]

    found: list[Path] = []
    seen: set[Path] = set()
    used_parent_scan = scan_all or not targets

    for target in raw_targets:
        if not target.exists() or not target.is_dir():
            raise FileNotFoundError(f"Không tìm thấy thư mục: {target}")

        direct_chapters = find_chapter_files(target)
        if not scan_all and direct_chapters:
            resolved = target.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(target)
            continue

        subdirs = _collect_novel_subdirs(target)
        if subdirs:
            used_parent_scan = True
            for sub in subdirs:
                resolved = sub.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    found.append(sub)
        elif direct_chapters:
            resolved = target.resolve()
            if resolved not in seen:
                seen.add(resolved)
                found.append(target)

    if not found:
        searched = ", ".join(str(p) for p in raw_targets)
        raise FileNotFoundError(
            f"Không tìm thấy bộ truyện nào có file chương (.txt) trong: {searched}"
        )

    return found, used_parent_scan


def count_novel_dir(
    novel_dir: Path,
    start: int | None = None,
    end: int | None = None,
) -> dict:
    """Tổng hợp số liệu tất cả các chương của một bộ truyện."""
    discovered = find_chapter_files(novel_dir)
    selected: list[tuple[int, Path]] = []

    for idx, (num, path) in enumerate(discovered, start=1):
        effective_num = num if num is not None else idx
        if start is not None and effective_num < start:
            continue
        if end is not None and effective_num > end:
            continue
        selected.append((effective_num, path))

    chapters: list[dict] = []
    total_chars_with_spaces = 0
    total_chars_no_newlines = 0
    total_chars_no_spaces = 0
    total_body_chars_with_spaces = 0
    total_body_chars_no_spaces = 0
    total_words = 0
    total_paragraphs = 0

    for effective_num, path in selected:
        stats = count_chapter_file(path)
        stats["chapter_num"] = effective_num
        chapters.append(stats)
        total_chars_with_spaces += stats["chars_with_spaces"]
        total_chars_no_newlines += stats["chars_no_newlines"]
        total_chars_no_spaces += stats["chars_no_spaces"]
        total_body_chars_with_spaces += stats["body_chars_with_spaces"]
        total_body_chars_no_spaces += stats["body_chars_no_spaces"]
        total_words += stats["words"]
        total_paragraphs += stats["paragraphs"]

    count = len(chapters)
    avg_chars_with_spaces = round(total_chars_with_spaces / count, 1) if count else 0.0
    avg_chars_no_spaces = round(total_chars_no_spaces / count, 1) if count else 0.0
    avg_words = round(total_words / count, 1) if count else 0.0

    def _chapter_brief(item: dict) -> dict:
        return {
            "chapter_num": item["chapter_num"],
            "file": item["file"],
            "title": item["title"],
            "chars_with_spaces": item["chars_with_spaces"],
            "chars_no_spaces": item["chars_no_spaces"],
            "words": item["words"],
        }

    shortest = (
        _chapter_brief(min(chapters, key=lambda c: c["chars_with_spaces"]))
        if chapters
        else None
    )
    longest = (
        _chapter_brief(max(chapters, key=lambda c: c["chars_with_spaces"]))
        if chapters
        else None
    )

    return {
        "novel": novel_dir.name,
        "path": str(novel_dir.resolve()),
        "chapter_count": count,
        "total_chars_with_spaces": total_chars_with_spaces,
        "total_chars_no_newlines": total_chars_no_newlines,
        "total_chars_no_spaces": total_chars_no_spaces,
        "total_body_chars_with_spaces": total_body_chars_with_spaces,
        "total_body_chars_no_spaces": total_body_chars_no_spaces,
        "total_words": total_words,
        "total_paragraphs": total_paragraphs,
        "avg_chars_with_spaces": avg_chars_with_spaces,
        "avg_chars_no_spaces": avg_chars_no_spaces,
        "avg_words": avg_words,
        "shortest_chapter": shortest,
        "longest_chapter": longest,
        "chapters": chapters,
    }


def export_csv(
    results: list[dict],
    csv_path: Path,
    multi_mode: bool,
) -> None:
    """Xuất thống kê ra file CSV UTF-8-SIG."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        if multi_mode:
            writer.writerow(
                [
                    "novel",
                    "path",
                    "chapter_count",
                    "total_chars_with_spaces",
                    "total_chars_no_newlines",
                    "total_chars_no_spaces",
                    "total_body_chars_with_spaces",
                    "total_body_chars_no_spaces",
                    "total_words",
                    "total_paragraphs",
                    "avg_chars_with_spaces",
                    "avg_chars_no_spaces",
                    "avg_words",
                ]
            )
            for item in results:
                writer.writerow(
                    [
                        item["novel"],
                        item["path"],
                        item["chapter_count"],
                        item["total_chars_with_spaces"],
                        item["total_chars_no_newlines"],
                        item["total_chars_no_spaces"],
                        item["total_body_chars_with_spaces"],
                        item["total_body_chars_no_spaces"],
                        item["total_words"],
                        item["total_paragraphs"],
                        item["avg_chars_with_spaces"],
                        item["avg_chars_no_spaces"],
                        item["avg_words"],
                    ]
                )
        else:
            writer.writerow(
                [
                    "chapter_num",
                    "file",
                    "title",
                    "chars_with_spaces",
                    "chars_no_newlines",
                    "chars_no_spaces",
                    "body_chars_with_spaces",
                    "body_chars_no_spaces",
                    "words",
                    "lines",
                    "paragraphs",
                ]
            )
            for ch in results[0]["chapters"]:
                writer.writerow(
                    [
                        ch["chapter_num"],
                        ch["file"],
                        ch["title"],
                        ch["chars_with_spaces"],
                        ch["chars_no_newlines"],
                        ch["chars_no_spaces"],
                        ch["body_chars_with_spaces"],
                        ch["body_chars_no_spaces"],
                        ch["words"],
                        ch["lines"],
                        ch["paragraphs"],
                    ]
                )


def format_single_novel_report(
    stats: dict,
    start: int | None,
    end: int | None,
    top_k: int,
) -> str:
    """Định dạng báo cáo chi tiết cho một bộ truyện."""
    range_note = ""
    if start is not None or end is not None:
        left = str(start) if start is not None else "đầu"
        right = str(end) if end is not None else "cuối"
        range_note = f" (lọc chương {left} -> {right})"

    lines = [
        f"Bộ truyện: {stats['novel']}",
        f"Đường dẫn: {stats['path']}",
        f"Tổng số chương: {stats['chapter_count']:,}{range_note}",
        "-" * 64,
        f"Tổng ký tự (gồm khoảng trắng & xuống dòng): {stats['total_chars_with_spaces']:,}",
        f"Tổng ký tự (không tính xuống dòng):         {stats['total_chars_no_newlines']:,}",
        f"Tổng ký tự (không tính khoảng trắng):       {stats['total_chars_no_spaces']:,}",
        f"Nội dung - bỏ tiêu đề (gồm khoảng trắng):   {stats['total_body_chars_with_spaces']:,}",
        f"Nội dung - bỏ tiêu đề (không khoảng trắng): {stats['total_body_chars_no_spaces']:,}",
        f"Tổng số từ:                                 {stats['total_words']:,}",
        f"Tổng số đoạn văn:                           {stats['total_paragraphs']:,}",
        "-" * 64,
        f"Trung bình / chương (có khoảng trắng):      {stats['avg_chars_with_spaces']:,.1f}",
        f"Trung bình / chương (không khoảng trắng):   {stats['avg_chars_no_spaces']:,.1f}",
        f"Trung bình số từ / chương:                  {stats['avg_words']:,.1f}",
    ]

    if stats["shortest_chapter"]:
        s = stats["shortest_chapter"]
        lines.append(
            f"Chương ngắn nhất: {s['file']} ({s['chars_with_spaces']:,} ký tự) - {s['title']}"
        )
    if stats["longest_chapter"]:
        l = stats["longest_chapter"]
        lines.append(
            f"Chương dài nhất:  {l['file']} ({l['chars_with_spaces']:,} ký tự) - {l['title']}"
        )

    if top_k > 0 and stats["chapters"]:
        by_len = sorted(stats["chapters"], key=lambda c: c["chars_with_spaces"])
        shortest_list = by_len[:top_k]
        longest_list = list(reversed(by_len[-top_k:]))

        lines.append("")
        lines.append(f"Top {len(longest_list)} chương dài nhất:")
        for ch in longest_list:
            lines.append(
                f"  - {ch['file']}: {ch['chars_with_spaces']:,} ký tự "
                f"({ch['chars_no_spaces']:,} không KT, {ch['words']:,} từ) | {ch['title']}"
            )

        lines.append("")
        lines.append(f"Top {len(shortest_list)} chương ngắn nhất:")
        for ch in shortest_list:
            lines.append(
                f"  - {ch['file']}: {ch['chars_with_spaces']:,} ký tự "
                f"({ch['chars_no_spaces']:,} không KT, {ch['words']:,} từ) | {ch['title']}"
            )

    return "\n".join(lines)


def format_multi_novel_table(results: list[dict]) -> str:
    """Định dạng bảng so sánh nhiều bộ truyện cùng dòng TỔNG CỘNG."""
    headers = (
        "Bộ truyện",
        "Số chương",
        "Ký tự (có KT)",
        "Ký tự (không KT)",
        "TB/chương",
        "Tổng từ",
    )

    rows: list[tuple[str, str, str, str, str, str]] = []
    grand_chapters = 0
    grand_chars_ws = 0
    grand_chars_ns = 0
    grand_words = 0

    for item in results:
        grand_chapters += item["chapter_count"]
        grand_chars_ws += item["total_chars_with_spaces"]
        grand_chars_ns += item["total_chars_no_spaces"]
        grand_words += item["total_words"]
        rows.append(
            (
                item["novel"],
                f"{item['chapter_count']:,}",
                f"{item['total_chars_with_spaces']:,}",
                f"{item['total_chars_no_spaces']:,}",
                f"{item['avg_chars_with_spaces']:,.1f}",
                f"{item['total_words']:,}",
            )
        )

    grand_avg = round(grand_chars_ws / grand_chapters, 1) if grand_chapters else 0.0
    total_row = (
        f"TỔNG CỘNG ({len(results)} bộ)",
        f"{grand_chapters:,}",
        f"{grand_chars_ws:,}",
        f"{grand_chars_ns:,}",
        f"{grand_avg:,.1f}",
        f"{grand_words:,}",
    )

    all_rows = [headers, *rows, total_row]
    widths = [max(len(r[i]) for r in all_rows) for i in range(len(headers))]

    def _fmt(row: tuple[str, ...]) -> str:
        cells = [row[0].ljust(widths[0])]
        for idx in range(1, len(row)):
            cells.append(row[idx].rjust(widths[idx]))
        return " | ".join(cells)

    sep = "-+-".join("-" * w for w in widths)
    lines = [_fmt(headers), sep]
    for row in rows:
        lines.append(_fmt(row))
    lines.append(sep)
    lines.append(_fmt(total_row))
    return "\n".join(lines)


def build_json_payload(
    results: list[dict],
    multi_mode: bool,
    include_details: bool,
) -> dict | list:
    """Chuẩn bị payload JSON (ẩn danh sách từng chương nếu không bật --details)."""
    cleaned: list[dict] = []
    for item in results:
        entry = dict(item)
        if not include_details:
            entry.pop("chapters", None)
        cleaned.append(entry)

    if not multi_mode and len(cleaned) == 1:
        return cleaned[0]

    grand_chapters = sum(r["chapter_count"] for r in results)
    grand_chars_ws = sum(r["total_chars_with_spaces"] for r in results)
    grand_chars_nl = sum(r["total_chars_no_newlines"] for r in results)
    grand_chars_ns = sum(r["total_chars_no_spaces"] for r in results)
    grand_words = sum(r["total_words"] for r in results)
    return {
        "novel_count": len(cleaned),
        "grand_totals": {
            "chapter_count": grand_chapters,
            "total_chars_with_spaces": grand_chars_ws,
            "total_chars_no_newlines": grand_chars_nl,
            "total_chars_no_spaces": grand_chars_ns,
            "total_words": grand_words,
            "avg_chars_with_spaces": (
                round(grand_chars_ws / grand_chapters, 1) if grand_chapters else 0.0
            ),
        },
        "novels": cleaned,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Đếm ký tự, từ, đoạn văn cho 1 bộ truyện hoặc tất cả các bộ truyện."
    )
    parser.add_argument(
        "targets",
        nargs="*",
        help="Thư mục bộ truyện (VD: output/Ten_Truyen) hoặc thư mục cha (VD: output/). Mặc định quét output/.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Quét tất cả các bộ truyện trong thư mục chỉ định (hoặc output/ nếu bỏ trống).",
    )
    parser.add_argument(
        "--start",
        type=int,
        help="Chỉ tính từ chương số >= START.",
    )
    parser.add_argument(
        "--end",
        type=int,
        help="Chỉ tính đến chương số <= END.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Hiển thị top K chương dài nhất và ngắn nhất (chế độ 1 bộ truyện).",
    )
    parser.add_argument(
        "--csv",
        help="Xuất kết quả ra file CSV (UTF-8-SIG).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Xuất kết quả dưới dạng JSON.",
    )
    parser.add_argument(
        "--details",
        action="store_true",
        help="Kèm danh sách chi tiết từng chương khi xuất --json.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_streams()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        novel_dirs, is_parent_scan = discover_novels(args.targets, args.all)
    except FileNotFoundError as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 1

    results = [count_novel_dir(ndir, args.start, args.end) for ndir in novel_dirs]
    multi_mode = args.all or len(results) > 1 or is_parent_scan

    if args.csv:
        csv_path = Path(args.csv)
        export_csv(results, csv_path, multi_mode=multi_mode)
        print(f"Đã xuất CSV: {csv_path.resolve()}", file=sys.stderr)

    if args.json:
        payload = build_json_payload(
            results, multi_mode=multi_mode, include_details=args.details
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    elif multi_mode:
        print(format_multi_novel_table(results))
    else:
        print(format_single_novel_report(results[0], args.start, args.end, args.top))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
