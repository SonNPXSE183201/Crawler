# -*- coding: utf-8 -*-
"""
Cấu hình từng trang web + bộ cào "thông minh" dùng chung.

Muốn thêm/sửa web mà không cần code: mở file site_rules.json (cùng thư mục tool) và thêm
domain với các CSS selector. Web không có trong danh sách vẫn cào được nhờ chế độ tự nhận diện.
"""

import os
import re
import json
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor

from . import extract as X
from .fetcher import FetchError, domain_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_FILE = os.path.join(ROOT, "site_rules.json")

# Cấu hình tích hợp sẵn. Khóa là 1 phần của domain (vd 'truyenfull' khớp truyenfull.live, truyenfull.vision...)
BUILTIN_RULES = {
    "truyenfull": {
        "name": "TruyenFull",
        "novel_title": "h3.title, h1.title",
        "author": "a[itemprop=author]",
        "chapter_list": "ul.list-chapter li a",
        "content": "#chapter-c, .chapter-c",
        "title": "a.chapter-title, .chapter-title",
        "next": "#next_chap",
        "workers": 6, "delay": 0.15,
    },
    "truyenfulls": {"same_as": "truyenfull"},
    "truyenchu": {
        "name": "Truyện Chữ", "js": True,
        "workers": 1, "delay": 0.6,
    },
    "truyencv": {
        "name": "TruyenCV", "js": True,
        "workers": 1, "delay": 0.8,
    },
    "tangthuvien": {
        "name": "Tàng Thư Viện",
        "novel_title": "h1",
        "chapter_list": "ul.cf li a, #max-volume a, .volume-wrap a",
        "content": ".box-chap",
        "title": "h2, h5",
        "workers": 3, "delay": 0.5,
    },
    "sstruyen": {
        "name": "SSTruyen",
        "content": ".content.container1, .truyen, #content",
        "chapter_list": ".list-chap a, .chapter-list a",
        "workers": 3, "delay": 0.5,
    },
    "69shu": {
        "name": "69书吧 (raw Trung)",
        "novel_title": "h1",
        "chapter_list": "#catalog ul li a",
        "content": ".txtnav",
        "title": "h1",
        "workers": 2, "delay": 1.0,
    },
    "uukanshu": {"name": "UU看书", "content": "#contentbox, .readcotent", "chapter_list": "#chapterList a, .chapterlist a"},
    "piaotia": {"name": "飘天文学", "content": "#content", "chapter_list": ".centent ul li a"},
    "wikidich": {"name": "WikiDịch", "js": True, "content": "#bookContentBody", "workers": 1, "delay": 1.0},
    "wikicv": {"same_as": "wikidich"},
    "metruyen": {"name": "MeTruyenCV", "js": True, "content": "#chapter-content, #article", "workers": 1, "delay": 1.0},
    "bachngocsach": {"name": "Bạch Ngọc Sách", "content": "#noi-dung, .truyen-noidung", "workers": 2, "delay": 0.8},
    "dtruyen": {"name": "DTruyen", "content": "#chapter-content, .chapter-content", "workers": 2, "delay": 0.6},
    "truyenyy": {"name": "TruyenYY", "content": "#inner_chap_content_1, .chap-content", "js": True, "workers": 1, "delay": 1.0},
}


def load_rules():
    rules = dict(BUILTIN_RULES)
    if os.path.exists(RULES_FILE):
        try:
            with open(RULES_FILE, "r", encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if not k.startswith("_") and isinstance(v, dict):
                    rules[k.lower()] = {**rules.get(k.lower(), {}), **v}
        except Exception as e:
            print(f"⚠️ Không đọc được site_rules.json: {e}")
    return rules


def rule_for(url, rules=None):
    rules = rules or load_rules()
    dom = domain_of(url)
    best_key = None
    for key in rules:
        if key in dom and (best_key is None or len(key) > len(best_key)):
            best_key = key
    if not best_key:
        return "generic", {"name": "Tự nhận diện"}
    r = rules[best_key]
    if "same_as" in r:
        r = {**rules.get(r["same_as"], {}), **{k: v for k, v in r.items() if k != "same_as"}}
    return best_key, r


CHAPTER_URL_RE = re.compile(r"(chuong[-_]?\d+|chapter[-_]?\d+|chap[-_]?\d+|/c\d+(\.html)?/?$|/\d+\.html$)", re.I)
START_READ_RE = re.compile(r"^\s*(đọc từ đầu|đọc truyện|bắt đầu đọc|đọc ngay|chương\s*0*1\b|chapter\s*0*1\b|第一章|开始阅读)", re.I)


class Site:
    """Bộ cào cho 1 trang web (dựa theo rule; rule trống = tự nhận diện hoàn toàn)."""

    def __init__(self, url, fetcher, log=print):
        self.key, self.rule = rule_for(url)
        self.fx = fetcher
        self.log = log
        self.name = self.rule.get("name", self.key)
        self.headers = self.rule.get("headers")
        if self.rule.get("js"):
            fetcher.force_browser(url)

    # ------------------------------------------------------------ helpers
    def _get(self, url, **kw):
        return self.fx.get(url, headers=self.headers, **kw)

    def _sel_text(self, soup, sel):
        if not sel:
            return ""
        try:
            el = soup.select_one(sel)
        except Exception:
            return ""
        return el.get_text(" ", strip=True) if el else ""

    def default_workers(self):
        return int(self.rule.get("workers", 3))

    def default_delay(self):
        return float(self.rule.get("delay", 0.6))

    @staticmethod
    def looks_like_chapter_url(url):
        return bool(CHAPTER_URL_RE.search(urlparse(url).path))

    # ------------------------------------------------------------ novel info
    def novel_info(self, url, chapter_mode=None):
        """
        Trả về dict: title, author, chapters [ {title,url} ], mode ('list' | 'next'), first_url
        chapter_mode: None = tự đoán; True = link là 1 chương (đi theo nút chương sau)
        """
        if chapter_mode is None:
            chapter_mode = self.looks_like_chapter_url(url)

        page = self._get(url)
        soup = X.soup_of(page.html)

        if chapter_mode:
            return {
                "title": self._novel_title_from_chapter(soup, page.url),
                "author": "",
                "chapters": [],
                "mode": "next",
                "first_url": page.url,
                "url": page.url,
            }

        info = self._parse_novel_page(page)
        if not info["chapters"] and self.fx.mode == "auto" and page.via != "browser":
            self.log("🔎 Không thấy danh sách chương bằng HTTP, thử lại bằng trình duyệt (web dùng JavaScript)...")
            try:
                self.fx.force_browser(url)
                page = self._get(url)
                info2 = self._parse_novel_page(page)
                if info2["chapters"] or info2.get("first_url"):
                    info = info2
            except FetchError as e:
                self.log(f"   -> Trình duyệt cũng không được: {e}")
        return info

    def _novel_title_from_chapter(self, soup, url):
        for sel in [self.rule.get("novel_title_on_chapter"), "a.truyen-title", ".truyen-title", ".book-title",
                    ".breadcrumb li:nth-last-child(2)", "[itemprop=itemListElement]:nth-last-child(2)"]:
            t = self._sel_text(soup, sel) if sel else ""
            if t and len(t) < 150 and not X.CHAPTER_TEXT_RE.match(t):
                return t
        raw = soup.title.get_text(strip=True) if soup.title else ""
        parts = re.split(r"\s+[-|–]\s+", raw)
        for p in parts:
            if p and not X.CHAPTER_TEXT_RE.match(p) and len(p) > 2:
                return p
        path = [p for p in urlparse(url).path.split("/") if p]
        return (path[-2] if len(path) >= 2 else domain_of(url)).replace("-", " ").title()

    def _parse_novel_page(self, page):
        soup = X.soup_of(page.html)
        title = self._sel_text(soup, self.rule.get("novel_title")) or X.find_title(soup)
        title = re.split(r"\s+[|–]\s+", title)[0].strip()
        author = self._sel_text(soup, self.rule.get("author") or "[itemprop=author], a[href*='tac-gia']")

        novel_path = urlparse(page.url).path
        list_sel = self.rule.get("chapter_list")
        chapters = X.find_chapter_links(soup, page.url, list_sel)

        # Phân trang danh sách chương
        pages = self._list_pages(soup, page.url, novel_path)
        if pages:
            self.log(f"📑 Danh sách chương có {len(pages) + 1} trang, đang quét...")
            results = {}

            def load(u):
                try:
                    pg = self._get(u, referer=page.url)
                    return u, X.find_chapter_links(X.soup_of(pg.html), pg.url, list_sel)
                except Exception:
                    return u, []

            with ThreadPoolExecutor(max_workers=max(1, min(4, self.default_workers()))) as ex:
                for u, items in ex.map(load, pages):
                    results[u] = items
            seen = {u for _, u in chapters}
            for u in pages:
                for t, cu in results.get(u, []):
                    if cu not in seen:
                        seen.add(cu)
                        chapters.append((t, cu))

        chapters = X.normalize_order(chapters)
        info = {
            "title": title or "Truyen",
            "author": author,
            "chapters": [{"title": t, "url": u} for t, u in chapters],
            "mode": "list" if chapters else "next",
            "first_url": None,
            "url": page.url,
        }
        if not chapters:
            # Không có danh sách -> tìm nút "Đọc từ đầu" / "Chương 1" để đi theo chương sau
            for a in soup.find_all("a", href=True):
                if START_READ_RE.match(a.get_text(" ", strip=True)):
                    info["first_url"] = urljoin(page.url, a["href"])
                    break
        return info

    def _list_pages(self, soup, base_url, novel_path):
        links = X.find_list_pages(soup, base_url, novel_path)
        if not links:
            return []
        # Thử suy ra mẫu link có số trang lớn nhất rồi sinh đủ các trang 2..max
        best_n, best_tpl = 0, None
        for u in links:
            for m in re.finditer(r"\d+", u):
                pre, post = u[:m.start()], u[m.end():]
                if re.search(r"(trang[-_]?|page[=/]|[?&]p=|/p)$", pre, re.I):
                    n = int(m.group())
                    if n > best_n:
                        best_n, best_tpl = n, (pre, post)
        if best_tpl and best_n > 1:
            pre, post = best_tpl
            return [f"{pre}{i}{post}" for i in range(2, min(best_n, 3000) + 1)]
        out, seen = [], {base_url.rstrip("/")}
        for u in links:
            if u.rstrip("/") not in seen:
                seen.add(u.rstrip("/"))
                out.append(u)
        return out[:300]

    # ------------------------------------------------------------ chapter
    def fetch_chapter(self, url, referer=None):
        """Trả về dict: ok, title, paragraphs, next_url, error, blocked"""
        try:
            page = self._get(url, referer=referer, wait_selector=self.rule.get("content"))
        except FetchError as e:
            return {"ok": False, "error": str(e), "blocked": e.blocked, "next_url": None}
        res = self.parse_chapter(page.html, page.url)
        if not res["ok"] and page.via != "browser" and self.fx.mode == "auto" and not res.get("blocked"):
            # Có thể nội dung được nạp bằng JavaScript -> thử trình duyệt 1 lần
            try:
                page = self._get(url, referer=referer, need_js=True, wait_selector=self.rule.get("content"))
                res2 = self.parse_chapter(page.html, page.url)
                if res2["ok"]:
                    self.fx.force_browser(url)
                    self.log(f"🌐 {domain_of(url)} cần JavaScript -> các chương sau sẽ dùng trình duyệt")
                    return res2
            except FetchError:
                pass
        return res

    def parse_chapter(self, html, url):
        soup = X.soup_of(html)
        title = X.find_title(soup, self.rule.get("title"))
        next_url = X.find_next(soup, url, self.rule.get("next"))
        content = X.find_content(soup, self.rule.get("content"))
        if content is None:
            return {"ok": False, "error": "Không tìm thấy nội dung chương", "next_url": next_url, "blocked": False}
        X.strip_junk(content)
        paras = X.element_to_paragraphs(content)

        # Bỏ dòng đầu nếu trùng tiêu đề; nếu chưa có tiêu đề chương thì lấy dòng đầu dạng "Chương N"
        if paras and not X.CHAPTER_TEXT_RE.match(title or "") and X.CHAPTER_TEXT_RE.match(paras[0]) and len(paras[0]) < 150:
            title = paras.pop(0)
        while paras and title and X.clean_chapter_title(paras[0]) == X.clean_chapter_title(title):
            paras.pop(0)

        if not paras or sum(len(p) for p in paras) < 200:
            return {"ok": False, "error": "Nội dung chương trống/quá ngắn", "next_url": next_url, "blocked": False}
        if X.is_locked(paras):
            return {"ok": False, "error": "Chương bị khóa / cần đăng nhập (VIP)", "next_url": next_url, "blocked": False}
        return {"ok": True, "title": title, "paragraphs": paras, "next_url": next_url, "error": "", "blocked": False}


class TruyenDichSpace(Site):
    """truyendich.space: link chương dạng /doc-truyen/<slug>/chuong-N, có cấm chế 'Sát Ma Trận'."""

    def __init__(self, url, fetcher, log=print):
        super().__init__(url, fetcher, log)
        self.name = "TruyenDich.space"
        self.headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"}

    def default_workers(self):
        return 1

    def default_delay(self):
        return 1.5

    def novel_info(self, url, chapter_mode=None):
        path = urlparse(url).path
        slug = path.split("/doc-truyen/")[-1].split("/")[0] if "/doc-truyen/" in path else path.strip("/").split("/")[-1]
        base = f"https://{domain_of(url)}/doc-truyen/{slug}"
        page = self._get(base)
        soup = X.soup_of(page.html)
        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else slug.replace("-", " ").title()
        m = re.search(r"([\d,.]+)\s*chương", soup.get_text(), re.I)
        total = int(re.sub(r"[,.]", "", m.group(1))) if m else 0
        return {
            "title": title, "author": "",
            "chapters": [{"title": f"Chương {i}", "url": f"{base}/chuong-{i}"} for i in range(1, total + 1)],
            "mode": "list" if total else "next",
            "first_url": f"{base}/chuong-1", "url": base,
        }

    def parse_chapter(self, html, url):
        if "original-content-tab" not in html and ("Sát Ma Trận" in html or "Luân Hồi Chuyển Thế" in html):
            return {"ok": False, "error": "Bị cấm chế 'Sát Ma Trận' (cần nghỉ cho IP hạ nhiệt)", "blocked": True, "next_url": None}
        if "Nội dung chương này hiện chưa có hoặc đã bị gỡ" in html:
            return {"ok": False, "error": "Chương chưa có hoặc đã bị gỡ", "blocked": False, "next_url": None}
        soup = X.soup_of(html)
        title_tag = soup.find("h1", itemprop="name") or soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else ""
        tab = soup.find(id="original-content-tab")
        if tab is None:
            return super().parse_chapter(html, url)
        paras, prev = [], ""
        for p in tab.find_all("p"):
            if p.find("p"):
                continue
            t = p.get_text(strip=True)
            if not t or t == prev or re.match(r"^\d{2}:\d{2}\s+\d{2}/\d{2}/\d{4}", t):
                continue
            paras.append(t)
            prev = t
        if not paras:
            return {"ok": False, "error": "Nội dung chương trống", "blocked": False, "next_url": None}
        return {"ok": True, "title": title, "paragraphs": paras, "next_url": X.find_next(soup, url), "error": "", "blocked": False}


def make_site(url, fetcher, log=print):
    if "truyendich" in domain_of(url):
        return TruyenDichSpace(url, fetcher, log)
    return Site(url, fetcher, log)
