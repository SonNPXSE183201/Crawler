#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CÀO TRUYỆN ĐA NGUỒN - dán link là tải, không cần copy/paste tay.

Ví dụ:
  python cao_truyen.py                                   # chế độ hỏi đáp
  python cao_truyen.py https://truyenfull.live/dau-pha-thuong-khung/
  python cao_truyen.py <link truyện> --start 1 --end 200 --merge
  python cao_truyen.py <link CHƯƠNG 1> --start 1         # web không có danh sách -> đi theo nút "Chương sau"
  python cao_truyen.py --batch ds_link.txt               # nhiều truyện, mỗi dòng 1 link
  python cao_truyen.py <link> --info                     # chỉ xem tên truyện + số chương
  python cao_truyen.py <link> --browser --show-browser   # web khó (captcha) -> mở Chrome thật
"""

import os
import sys
import argparse
import warnings

warnings.filterwarnings("ignore")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from novel_tool.engine import crawl
from novel_tool.fetcher import Fetcher
from novel_tool.sites import BUILTIN_RULES


def ask(msg, default=None):
    v = input(msg).strip()
    return v if v else default


def interactive():
    print("=" * 64)
    print("📚 TOOL CÀO TRUYỆN ĐA NGUỒN")
    print("   Hỗ trợ sẵn:", ", ".join(sorted({r.get('name', k) for k, r in BUILTIN_RULES.items() if 'name' in r})))
    print("   + Web khác: tự nhận diện nội dung & nút 'Chương sau'")
    print("=" * 64)
    print("👉 Dán link TRANG TRUYỆN (có danh sách chương) hoặc link 1 CHƯƠNG để bắt đầu.")
    print("   Muốn cào nhiều truyện: dán nhiều link, mỗi link 1 dòng, dòng trống để kết thúc.")
    urls = []
    while True:
        u = input(f"Link {len(urls) + 1}: ").strip()
        if not u:
            if urls:
                break
            continue
        urls.append(u)

    start = int(ask("\nChương BẮT ĐẦU (Enter = 1): ", "1"))
    end_s = ask("Chương KẾT THÚC (Enter = đến hết): ", "")
    end = int(end_s) if end_s and end_s.isdigit() else None

    print("\nTốc độ:")
    print("  1. Tự động theo từng web (khuyên dùng)")
    print("  2. An toàn (1 luồng, nghỉ 1.5s) - web hay chặn IP")
    print("  3. Nhanh (8 luồng, nghỉ 0.1s)")
    sp = ask("Chọn (Enter = 1): ", "1")
    workers, delay = {"2": (1, 1.5), "3": (8, 0.1)}.get(sp, (None, None))

    merge = ask("\nGộp tất cả chương thành 1 file FULL để biên tập? (y/N): ", "n").lower() == "y"
    overwrite = ask("Tải lại & ghi đè chương đã có? (y/N): ", "n").lower() == "y"
    proxy = ask("Proxy (Enter nếu không dùng): ", None)

    fx = Fetcher(mode="auto", proxy=proxy)
    try:
        for u in urls:
            crawl(u, start=start, end=end, workers=workers, delay=delay, overwrite=overwrite, merge=merge, fetcher=fx)
    finally:
        fx.close()


def main():
    p = argparse.ArgumentParser(description="Cào truyện từ nhiều web, lưu Chuong_xxxx.txt")
    p.add_argument("url", nargs="?", help="Link truyện hoặc link chương")
    p.add_argument("--batch", help="File .txt chứa nhiều link (mỗi dòng 1 link)")
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--end", type=int, default=None)
    p.add_argument("--workers", type=int, default=None, help="Số luồng (mặc định theo từng web)")
    p.add_argument("--delay", type=float, default=None, help="Giây nghỉ giữa các request (mặc định theo từng web)")
    p.add_argument("--output", help="Thư mục lưu (mặc định output/<Tên truyện>)")
    p.add_argument("--proxy", help="vd http://127.0.0.1:8080 hoặc socks5://127.0.0.1:1080")
    p.add_argument("--browser", action="store_true", help="Luôn dùng Chrome thật (web chặn bot nặng / dùng JavaScript)")
    p.add_argument("--http", action="store_true", help="Chỉ dùng HTTP, không bao giờ mở trình duyệt")
    p.add_argument("--show-browser", action="store_true", help="Hiện cửa sổ Chrome (để tự bấm captcha/đăng nhập)")
    p.add_argument("--chapter", action="store_true", help="Coi link là 1 chương, đi theo nút 'Chương sau'")
    p.add_argument("--merge", action="store_true", help="Gộp các chương thành 1 file FULL")
    p.add_argument("--overwrite", action="store_true", help="Tải lại cả chương đã có")
    p.add_argument("--info", action="store_true", help="Chỉ xem thông tin truyện, không tải")
    a = p.parse_args()

    if not a.url and not a.batch:
        interactive()
        return

    urls = []
    if a.batch:
        with open(a.batch, "r", encoding="utf-8") as f:
            urls = [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    if a.url:
        urls.insert(0, a.url)

    mode = "browser" if a.browser else ("http" if a.http else "auto")
    fx = Fetcher(mode=mode, proxy=a.proxy, show_browser=a.show_browser)
    try:
        for u in urls:
            crawl(u, start=a.start, end=a.end, workers=a.workers, delay=a.delay,
                  output=a.output if len(urls) == 1 else None, overwrite=a.overwrite, merge=a.merge,
                  chapter_mode=True if a.chapter else None, info_only=a.info, fetcher=fx)
    finally:
        fx.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Đã dừng.")
