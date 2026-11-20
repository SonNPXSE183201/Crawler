# -*- coding: utf-8 -*-
"""
Tầng tải trang:
  - HTTP nhanh bằng curl_cffi (giả lập vân tay TLS của Chrome -> qua được phần lớn Cloudflare).
  - Tự chuyển sang trình duyệt thật (Playwright + Chrome/Edge có sẵn trên máy) khi gặp
    trang chặn Cloudflare hoặc trang dựng nội dung bằng JavaScript.
  - Giới hạn tốc độ theo từng domain, tự thử lại, tự nghỉ khi bị 403/429.
"""

import os
import re
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

try:
    from curl_cffi import requests as cffi_requests
except Exception:  # pragma: no cover
    cffi_requests = None

import urllib.request
import ssl

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

CHALLENGE_MARKERS = (
    "Just a moment...", "cf-browser-verification", "challenge-platform",
    "Attention Required! | Cloudflare", "cf_chl_opt", "Checking your browser",
    "DDoS protection by", "Đang kiểm tra trình duyệt",
)

PROFILE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".browser_profile")


class FetchError(Exception):
    def __init__(self, msg, status=None, blocked=False):
        super().__init__(msg)
        self.status = status
        self.blocked = blocked


class Page:
    __slots__ = ("url", "html", "status", "via")

    def __init__(self, url, html, status=200, via="http"):
        self.url, self.html, self.status, self.via = url, html, status, via


def domain_of(url):
    return urlparse(url).netloc.lower()


def is_challenge(html, status=200):
    if not html:
        return status in (403, 503)
    head = html[:20000]
    if any(m in head for m in CHALLENGE_MARKERS):
        return True
    return status in (403, 503) and len(html) < 15000


def decode_bytes(raw, header_ct=""):
    """Giải mã HTML: ưu tiên charset trong header, rồi thẻ meta, rồi utf-8, cuối cùng gb18030 (web Trung)."""
    cands = []
    m = re.search(r"charset=([\w-]+)", header_ct or "", re.I)
    if m:
        cands.append(m.group(1))
    m = re.search(rb"<meta[^>]+charset=[\"']?([\w-]+)", raw[:4000], re.I)
    if m:
        cands.append(m.group(1).decode("ascii", "ignore"))
    cands += ["utf-8", "gb18030"]
    for enc in cands:
        enc = enc.lower()
        if enc in ("gb2312", "gbk"):
            enc = "gb18030"
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


class Fetcher:
    """
    mode: 'auto'    -> HTTP trước, gặp chặn/JS thì tự bật trình duyệt
          'http'    -> chỉ HTTP
          'browser' -> luôn dùng trình duyệt
    """

    def __init__(self, mode="auto", proxy=None, delay=0.6, show_browser=False, timeout=25, log=print):
        self.mode = mode
        self.proxy = proxy
        self.delay = max(0.0, delay)
        self.show_browser = show_browser
        self.timeout = timeout
        self.log = log
        self._tl = threading.local()
        self._rate_lock = threading.Lock()
        self._next_slot = {}            # domain -> thời điểm được phép gửi request tiếp
        self._cooldown_until = {}       # domain -> nghỉ đến lúc nào
        self._browser_domains = set()   # domain bắt buộc dùng trình duyệt
        self._cookies = {}              # domain -> cookie lấy từ trình duyệt
        self._ua = {}                   # domain -> UA của trình duyệt
        self._pw_lock = threading.RLock()
        self._pw = None
        self._ctx = None
        self._browser_failed = False
        # Playwright chỉ chạy được trên 1 luồng cố định -> mọi thao tác trình duyệt đi qua luồng riêng này
        self._bx = ThreadPoolExecutor(max_workers=1, thread_name_prefix="browser")

    # ------------------------------------------------------------------ rate limit
    def _wait_turn(self, dom):
        while True:
            with self._rate_lock:
                now = time.time()
                cd = self._cooldown_until.get(dom, 0)
                slot = self._next_slot.get(dom, 0)
                start = max(now, cd, slot)
                if start <= now:
                    gap = self.delay * random.uniform(0.7, 1.4) if self.delay else 0
                    self._next_slot[dom] = now + gap
                    return
            time.sleep(min(start - now, 1.0))

    def cooldown(self, dom, seconds):
        with self._rate_lock:
            self._cooldown_until[dom] = max(self._cooldown_until.get(dom, 0), time.time() + seconds)

    # ------------------------------------------------------------------ HTTP
    def _session(self):
        s = getattr(self._tl, "s", None)
        if s is None and cffi_requests is not None:
            s = cffi_requests.Session(impersonate="chrome")
            self._tl.s = s
        return s

    def _http_get(self, url, referer=None, extra_headers=None):
        dom = domain_of(url)
        headers = dict(BASE_HEADERS)
        if extra_headers:
            headers.update(extra_headers)
        if referer:
            headers["Referer"] = referer
        if dom in self._ua:
            headers["User-Agent"] = self._ua[dom]
        cookies = self._cookies.get(dom)
        proxies = {"http": self.proxy, "https": self.proxy} if self.proxy else None

        s = self._session()
        if s is not None:
            r = s.get(url, headers=headers, cookies=cookies, proxies=proxies,
                      timeout=self.timeout, allow_redirects=True, verify=False)
            html = decode_bytes(r.content, r.headers.get("content-type", ""))
            return Page(str(r.url), html, r.status_code, "http")

        # Dự phòng khi thiếu curl_cffi
        headers["User-Agent"] = headers.get("User-Agent", UA)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        handlers = [urllib.request.HTTPSHandler(context=ctx)]
        if self.proxy:
            handlers.append(urllib.request.ProxyHandler(proxies))
        opener = urllib.request.build_opener(*handlers)
        try:
            with opener.open(urllib.request.Request(url, headers=headers), timeout=self.timeout) as res:
                return Page(res.geturl(), decode_bytes(res.read(), res.headers.get("content-type", "")), res.status, "http")
        except urllib.error.HTTPError as e:
            return Page(url, decode_bytes(e.read() or b""), e.code, "http")

    # ------------------------------------------------------------------ Browser
    def _ensure_browser(self):
        if self._ctx is not None:
            return self._ctx
        if self._browser_failed:
            raise FetchError("Không mở được trình duyệt")
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            self._browser_failed = True
            raise FetchError("Chưa cài Playwright. Chạy: pip install playwright")
        self._pw = sync_playwright().start()
        kw = dict(user_data_dir=PROFILE_DIR, headless=not self.show_browser,
                  viewport={"width": 1280, "height": 900}, locale="vi-VN",
                  args=["--disable-blink-features=AutomationControlled"])
        if self.proxy:
            kw["proxy"] = {"server": self.proxy}
        last = None
        for channel in ("chrome", "msedge", None):
            try:
                if channel:
                    self._ctx = self._pw.chromium.launch_persistent_context(channel=channel, **kw)
                else:
                    self._ctx = self._pw.chromium.launch_persistent_context(**kw)
                self.log(f"🌐 Đã mở trình duyệt ({channel or 'chromium'}) để tải trang chặn bot / trang JavaScript")
                return self._ctx
            except Exception as e:
                last = e
        self._browser_failed = True
        raise FetchError(f"Không mở được Chrome/Edge: {last}")

    def _browser_get(self, url, wait_selector=None):
        return self._bx.submit(self._browser_get_impl, url, wait_selector).result()

    def _browser_get_impl(self, url, wait_selector=None):
        with self._pw_lock:
            ctx = self._ensure_browser()
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=self.timeout * 2000)
                status = resp.status if resp else 200
                # Chờ Cloudflare tự giải (tối đa ~45s; nếu hiện captcha, người dùng bấm tay khi dùng --show-browser)
                t0 = time.time()
                while time.time() - t0 < 45:
                    html = page.content()
                    if not is_challenge(html, 200):
                        break
                    page.wait_for_timeout(1500)
                if wait_selector:
                    try:
                        page.wait_for_selector(wait_selector, timeout=8000)
                    except Exception:
                        pass
                try:
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                html = page.content()
                final = page.url
                # Chia sẻ cookie + UA cho tầng HTTP để các request sau chạy nhanh lại
                dom = domain_of(final)
                try:
                    self._cookies[dom] = {c["name"]: c["value"] for c in ctx.cookies(final)}
                    self._ua[dom] = page.evaluate("navigator.userAgent")
                except Exception:
                    pass
                if is_challenge(html, 200):
                    status = 403
                return Page(final, html, status, "browser")
            except FetchError:
                raise
            except Exception as e:
                raise FetchError(f"Lỗi trình duyệt: {e}")

    def close(self):
        try:
            self._bx.submit(self._close_impl).result(timeout=30)
        except Exception:
            pass
        self._bx.shutdown(wait=False)

    def _close_impl(self):
        with self._pw_lock:
            try:
                if self._ctx:
                    self._ctx.close()
                if self._pw:
                    self._pw.stop()
            except Exception:
                pass
            self._ctx = self._pw = None

    # ------------------------------------------------------------------ Public
    def force_browser(self, url):
        self._browser_domains.add(domain_of(url))

    def get(self, url, referer=None, retries=3, need_js=False, wait_selector=None, headers=None):
        """Tải 1 trang. Trả về Page hoặc ném FetchError."""
        dom = domain_of(url)
        last_err = None
        for attempt in range(1, retries + 1):
            self._wait_turn(dom)
            use_browser = (self.mode == "browser" or need_js or dom in self._browser_domains) and self.mode != "http"
            try:
                if use_browser:
                    pg = self._browser_get(url, wait_selector)
                else:
                    pg = self._http_get(url, referer, headers)
                    if is_challenge(pg.html, pg.status) and self.mode == "auto" and not self._browser_failed:
                        if dom not in self._browser_domains:
                            self.log(f"🛡️  {dom} có tường chống bot -> chuyển sang trình duyệt thật")
                        self._browser_domains.add(dom)
                        self._cookies.pop(dom, None)
                        pg = self._browser_get(url, wait_selector)

                if pg.status == 404:
                    raise FetchError("HTTP 404 - không tồn tại", 404)
                if pg.status in (403, 429, 503) or is_challenge(pg.html, pg.status):
                    wait = min(120, 15 * attempt)
                    self.cooldown(dom, wait)
                    raise FetchError(f"HTTP {pg.status} - bị chặn tạm thời (nghỉ {wait}s)", pg.status, blocked=True)
                if pg.status >= 400:
                    raise FetchError(f"HTTP {pg.status}", pg.status)
                return pg
            except FetchError as e:
                last_err = e
                if e.status == 404:
                    raise
            except Exception as e:
                last_err = FetchError(str(e))
            time.sleep(min(10, 1.5 * attempt))
        raise last_err or FetchError("Không tải được trang")
