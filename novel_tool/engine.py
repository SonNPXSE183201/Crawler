# -*- coding: utf-8 -*-
"""Điều phối việc cào: chọn chương, tải đa luồng, bỏ qua chương đã có, thử lại chương lỗi, lưu file, gộp file."""

import os
import re
import sys
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from .fetcher import Fetcher, FetchError
from .sites import make_site, ROOT
from . import extract as X

STATE_FILE = "_nguon.json"
ERROR_FILE = "_loi.txt"


def clean_filename(s):
    s = re.sub(r'[\\/*?:"<>|\r\n\t]', "", s or "").strip().rstrip(".")
    return s[:120] or "Truyen"


def chapter_path(out_dir, n):
    return os.path.join(out_dir, f"Chuong_{n:04d}.txt")


def is_valid_file(path):
    try:
        if os.path.getsize(path) < 300:
            return False
        with open(path, "r", encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        return len(lines) >= 4 and "Sát Ma Trận" not in lines[0]
    except Exception:
        return False


def _uncensor(text):
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from clean_censor import uncensor_text
        return uncensor_text(text)
    except Exception:
        return text


def _clean_watermark(text):
    try:
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        from clean_watermark import clean_watermark_text
        cleaned, _ = clean_watermark_text(text)
        return cleaned
    except Exception:
        return text


def save_chapter(out_dir, n, raw_title, paragraphs):
    title = X.clean_chapter_title(raw_title)
    header = f"Chương {n}: {title}" if title else f"Chương {n}"
    content = _clean_watermark(_uncensor(header + "\n\n" + "\n\n".join(paragraphs) + "\n"))
    tmp = chapter_path(out_dir, n) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, chapter_path(out_dir, n))


def merge_files(out_dir, title, start, end):
    path = os.path.join(out_dir, f"{clean_filename(title)}_C{start}-{end}_FULL.txt")
    count = 0
    with open(path, "w", encoding="utf-8") as out:
        for n in range(start, end + 1):
            p = chapter_path(out_dir, n)
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    out.write(f.read().rstrip() + "\n\n\n")
                count += 1
    return path, count


class State:
    """Lưu link nguồn + link từng chương để chạy tiếp (resume) lần sau."""

    def __init__(self, out_dir):
        self.path = os.path.join(out_dir, STATE_FILE)
        self.lock = threading.Lock()
        self.data = {}
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {}
        self.data.setdefault("chapter_urls", {})

    def set_url(self, n, url):
        with self.lock:
            self.data["chapter_urls"][str(n)] = url

    def get_url(self, n):
        return self.data["chapter_urls"].get(str(n))

    def save(self):
        with self.lock:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)


def crawl(url, start=1, end=None, workers=None, delay=None, output=None, mode="auto", proxy=None,
          show_browser=False, overwrite=False, merge=False, chapter_mode=None, info_only=False,
          fetcher=None, log=print):
    own_fetcher = fetcher is None
    fx = fetcher or Fetcher(mode=mode, proxy=proxy, show_browser=show_browser, log=log)
    try:
        return _crawl(fx, url, start, end, workers, delay, output, overwrite, merge, chapter_mode, info_only, log)
    finally:
        if own_fetcher:
            fx.close()


def _crawl(fx, url, start, end, workers, delay, output, overwrite, merge, chapter_mode, info_only, log):
    site = make_site(url, fx, log)
    fx.delay = site.default_delay() if delay is None else delay
    workers = workers or site.default_workers()

    log("\n" + "=" * 64)
    log(f"🚀 CÀO TRUYỆN ĐA NGUỒN  |  Web: {site.name}")
    log("=" * 64)
    log(f"[*] Đang đọc thông tin: {url}")
    try:
        info = site.novel_info(url, chapter_mode)
    except FetchError as e:
        log(f"❌ Không mở được trang: {e}")
        log("   Gợi ý: web có thể bị nhà mạng chặn -> thử bật 1.1.1.1/WARP hoặc dùng --proxy; "
            "hoặc thêm --browser --show-browser để tự vượt captcha.")
        return {"ok": False}

    total = len(info["chapters"])
    log(f"📖 Tên truyện : {info['title']}")
    if info.get("author"):
        log(f"✍️  Tác giả    : {info['author']}")
    if info["mode"] == "list":
        log(f"📊 Số chương  : {total}")
    else:
        if not info.get("first_url"):
            log("❌ Không tìm thấy danh sách chương lẫn link chương đầu.")
            log("   Hãy dán trực tiếp link CHƯƠNG muốn bắt đầu (vd .../chuong-1) để tool tự đi theo nút 'Chương sau'.")
            return {"ok": False}
        log(f"📊 Chế độ     : đi theo nút 'Chương sau' bắt đầu từ {info['first_url']}")

    if info_only:
        if total:
            for i, c in enumerate(info["chapters"][:5], 1):
                log(f"   {i}. {c['title']}  ->  {c['url']}")
            if total > 5:
                log(f"   ... {total - 5} chương nữa ... | cuối: {info['chapters'][-1]['title']}")
        return {"ok": True, "info": info}

    out_dir = output or os.path.join(ROOT, "output", clean_filename(info["title"]))
    os.makedirs(out_dir, exist_ok=True)
    state = State(out_dir)
    state.data.update({"source": url, "site": site.name, "title": info["title"], "author": info.get("author", "")})
    # Chương nào trước đây được tải từ link khác (do thứ tự cũ sai / web đổi danh sách) -> tải lại
    changed = set()
    for i, c in enumerate(info["chapters"], 1):
        prev = state.get_url(i)
        if prev and prev != c["url"] and os.path.exists(chapter_path(out_dir, i)):
            changed.add(i)
        state.set_url(i, c["url"])
    state.save()
    if changed:
        log(f"♻️  {len(changed)} chương đã tải trước đây không khớp link nguồn hiện tại -> sẽ tải lại")

    log(f"📁 Lưu tại    : {out_dir}")
    log(f"⚡ Luồng: {workers}  |  ⏱️ Nghỉ giữa request: ~{fx.delay}s  |  Ghi đè: {'Có' if overwrite else 'Không (tự bỏ qua chương đã có)'}")

    if info["mode"] == "list":
        end = min(end or total, total)
        if start > end:
            log(f"❌ Chương bắt đầu ({start}) lớn hơn chương kết thúc ({end})")
            return {"ok": False}
        res = _crawl_list(site, info, out_dir, start, end, workers, overwrite, log, changed)
    else:
        res = _crawl_next(site, info, state, out_dir, start, end, overwrite, log)
        end = res.get("last", start)
    state.save()

    if res["failed"]:
        with open(os.path.join(out_dir, ERROR_FILE), "w", encoding="utf-8") as f:
            for n, u, err in sorted(res["failed"]):
                f.write(f"Chương {n}\t{err}\t{u}\n")

    log("\n" + "=" * 64)
    log(f"🎉 XONG: tải mới {res['ok']} | đã có sẵn {res['skipped']} | lỗi {len(res['failed'])}")
    if res["failed"]:
        log(f"⚠️  Danh sách chương lỗi: {os.path.join(out_dir, ERROR_FILE)} (chạy lại lệnh cũ để tải bù)")
    if merge and end:
        p, c = merge_files(out_dir, info["title"], start, end)
        log(f"📚 Đã gộp {c} chương vào: {p}")
    log(f"📁 {out_dir}")
    log("=" * 64)
    return {"ok": True, "out_dir": out_dir, **res}


def _fetch_with_block_retry(site, url, referer, log, tries=4):
    res = None
    for t in range(1, tries + 1):
        res = site.fetch_chapter(url, referer)
        if res["ok"] or not res.get("blocked"):
            return res
        wait = min(180, 30 * t)
        tqdm.write(f"🚧 Bị web chặn tạm thời, nghỉ {wait}s rồi thử lại... (mẹo: đổi IP / bật 4G sẽ nhanh hơn)")
        time.sleep(wait)
    return res


def _crawl_list(site, info, out_dir, start, end, workers, overwrite, log, changed=()):
    chs = info["chapters"]
    todo, skipped = [], 0
    for n in range(start, end + 1):
        if not overwrite and n not in changed and is_valid_file(chapter_path(out_dir, n)):
            skipped += 1
        else:
            todo.append(n)
    log(f"🎯 Chương {start} -> {end}: cần tải {len(todo)}, bỏ qua {skipped} chương đã có\n")
    ok, failed = 0, []

    def job(n):
        c = chs[n - 1]
        r = _fetch_with_block_retry(site, c["url"], info["url"], log)
        if r["ok"]:
            save_chapter(out_dir, n, r["title"] or c["title"], r["paragraphs"])
        return n, c["url"], r

    retry = []
    if todo:
        with ThreadPoolExecutor(max_workers=workers) as ex, \
                tqdm(total=len(todo), desc="Đang tải", unit="ch") as bar:
            futs = [ex.submit(job, n) for n in todo]
            for f in as_completed(futs):
                n, u, r = f.result()
                if r["ok"]:
                    ok += 1
                else:
                    retry.append((n, u, r["error"]))
                bar.update(1)

    # Vòng 2: thử lại tuần tự, chậm hơn
    if retry:
        log(f"\n🔁 Thử lại {len(retry)} chương lỗi (chậm hơn)...")
        site.fx.delay = max(site.fx.delay * 2, 1.0)
        for n, u, err in sorted(retry):
            n2, u2, r = job(n)
            if r["ok"]:
                ok += 1
            else:
                failed.append((n, u, r["error"]))
                tqdm.write(f"⚠️  Chương {n}: {r['error']}")
    return {"ok": ok, "skipped": skipped, "failed": failed}


def _crawl_next(site, info, state, out_dir, start, end, overwrite, log):
    end = end or 10 ** 6
    n = start
    cur = state.get_url(n) or info["first_url"]
    if start > 1 and not state.get_url(n):
        log(f"ℹ️  Link bắt đầu sẽ được đánh số là Chương {start}")
    ok = skipped = 0
    failed, visited = [], set()
    referer = info["url"]
    bar = tqdm(desc="Đang tải (theo chương sau)", unit="ch", total=None if end >= 10 ** 6 else end - start + 1)
    try:
        while cur and n <= end:
            if cur in visited:
                break
            visited.add(cur)
            state.set_url(n, cur)
            nxt_known = state.get_url(n + 1)
            if not overwrite and nxt_known and is_valid_file(chapter_path(out_dir, n)):
                skipped += 1
                n, referer, cur = n + 1, cur, nxt_known
                bar.update(1)
                continue
            r = _fetch_with_block_retry(site, cur, referer, log)
            if r["ok"]:
                save_chapter(out_dir, n, r["title"], r["paragraphs"])
                ok += 1
            else:
                failed.append((n, cur, r["error"]))
                tqdm.write(f"⚠️  Chương {n}: {r['error']}")
                if not r.get("next_url"):
                    break
            nxt = r.get("next_url")
            if nxt and (nxt.rstrip("/") == info["url"].rstrip("/") or nxt in visited):
                nxt = None
            if nxt:
                state.set_url(n + 1, nxt)
            if n % 20 == 0:
                state.save()
            bar.update(1)
            referer, cur = cur, nxt
            n += 1
    except KeyboardInterrupt:
        tqdm.write("\n⏸️  Đã dừng. Chạy lại cùng lệnh sẽ tải tiếp từ chỗ dừng.")
    finally:
        bar.close()
        state.save()
    return {"ok": ok, "skipped": skipped, "failed": failed, "last": n - 1}
