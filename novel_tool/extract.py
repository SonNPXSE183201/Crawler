# -*- coding: utf-8 -*-
"""
Bóc tách nội dung "thông minh" dùng chung cho mọi trang web truyện:
  - Tìm vùng nội dung chương (theo bộ selector phổ biến + thuật toán mật độ chữ).
  - Tìm tiêu đề chương, link "Chương sau".
  - Tìm danh sách chương và các trang phân trang của danh sách.
"""

import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, NavigableString, Comment

try:
    import lxml  # noqa: F401
    PARSER = "lxml"
except Exception:
    PARSER = "html.parser"


def soup_of(html):
    return BeautifulSoup(html, PARSER)


# Selector vùng nội dung chương của các web truyện phổ biến (VN + Trung)
CONTENT_SELECTORS = [
    "#chapter-c", ".chapter-c", "#chapter-content", ".chapter-content", "#chapterContent",
    "#original-content-tab", "#chr-content", ".chr-c", "#chaptercontent", ".box-chap",
    ".reading-content", ".text-left .chapter-c", "#vungdoc", "#content-chapter",
    ".content-chapter", "#chapter_content", ".chapter_content", ".chapter-body",
    "#article", ".txtnav", "#content", ".content", ".entry-content", ".reading",
    "#bookContent", ".read-content", "#htmlContent", "#TextContent", "article",
]

TITLE_SELECTORS = [
    ".chapter-title", ".chapter-name", "#chapter-title", ".chr-title", "h1[itemprop=name]",
    ".current-chapter", "h1", "h2", ".title",
]

JUNK_TAGS = ["script", "style", "noscript", "iframe", "ins", "form", "button", "svg",
             "select", "input", "textarea", "nav", "footer", "header", "aside", "img"]

JUNK_ATTR_RE = re.compile(
    r"(^|[-_ ])(ads?|adsbygoogle|advert|quang-?cao|qc|banner|comment|binh-?luan|share|social|"
    r"rating|breadcrumb|chapter-nav|chapter_nav|btn-group|toolbar|related|recommend|sidebar|"
    r"popup|modal|report|bao-loi|navigation|pagination|menu)([-_ ]|$)", re.I)

JUNK_LINE_RE = re.compile(
    r"(truyenfull\.|truyen\w*\.(vn|com|net|io|org|live|space|info)|copy\s*tại|chúc bạn đọc truyện|"
    r"bạn đang đọc truyện|đọc truyện online|nguồn\s*:|source\s*:|tải app|cài đặt app|"
    r"^chương\s*(trước|sau|tiếp)$|^(trước|sau|tiếp|next|prev|previous)$|"
    r"báo lỗi chương|bình luận|ủng hộ tác giả|donate|^\s*-{3,}\s*$|^\*{3,}$|"
    r"请收藏|天才一秒记住|最新章节|手机阅读|本章未完|点击下一页)", re.I)

LOCK_RE = re.compile(
    r"(chương (này )?(đã )?bị khóa|chương vip|mua chương|mở khóa chương|đăng nhập để (đọc|xem)|"
    r"nội dung chương này hiện chưa có|chương này chưa được|cần đăng nhập|vui lòng đăng nhập)", re.I)

NEXT_TEXT_RE = re.compile(r"^\s*(chương\s*(sau|tiếp(\s*theo)?|kế(\s*tiếp)?)|tiếp\s*theo|"
                          r"next(\s*chapter)?|下一章|下一页|下一節|下一节)\s*[>»›→]*\s*$", re.I)
NEXT_ATTR_RE = re.compile(r"(next[-_]?chap|next[-_]?chapter|btn[-_]?next|chap[-_]?next|nextchap|nextchapter|"
                          r"^next$|[-_]next$)", re.I)

CHAPTER_HREF_RE = re.compile(r"(chuong|chapter|chap|/c\d+|_\d+\.html|/\d+\.html|/\d+/?$)", re.I)
CHAPTER_TEXT_RE = re.compile(r"^\s*(chương|chuong|chapter|chap|hồi|quyển|tiết|đệ|第)\s*[\d一二三四五六七八九十百千零〇]", re.I)
NUM_RE = re.compile(r"(?:chương|chuong|chapter|chap|hồi|第)[\s\-_.:]*(\d+)", re.I)
PAGE_HREF_RE = re.compile(r"(trang[-_]?\d+|[?&](page|p|trang)=\d+|/page/\d+|/p\d+/?$|_\d+/?$|#list-chapter)", re.I)


def _attr_str(tag):
    if not getattr(tag, "attrs", None):
        return ""
    cls = tag.get("class") or []
    if isinstance(cls, str):
        cls = [cls]
    return " ".join(cls) + " " + (tag.get("id") or "")


def strip_junk(root):
    for c in root.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()
    for t in root.find_all(JUNK_TAGS):
        t.decompose()
    for t in list(root.find_all(True)):
        if getattr(t, "decomposed", False):
            continue
        try:
            a = _attr_str(t)
        except Exception:
            continue
        if a.strip() and JUNK_ATTR_RE.search(a):
            t.decompose()
        else:
            st = (t.get("style") or "").replace(" ", "").lower() if t.attrs else ""
            if "display:none" in st or "font-size:0" in st or "visibility:hidden" in st:
                t.decompose()


def element_to_paragraphs(el):
    """Chuyển 1 element thành danh sách đoạn văn, giữ đúng tách dòng của <p>, <br>, <div>."""
    for br in el.find_all("br"):
        br.replace_with("\n")
    for blk in el.find_all(["p", "div", "li", "h3", "h4", "h5", "blockquote"]):
        blk.insert_before("\n")
        blk.insert_after("\n")
    text = el.get_text()
    text = text.replace("\xa0", " ").replace("　", " ").replace("​", "")
    paras, prev = [], None
    for line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line or line == prev:
            continue
        if len(line) < 120 and JUNK_LINE_RE.search(line):
            continue
        paras.append(line)
        prev = line
    return paras


def _text_score(el):
    """Điểm mật độ chữ: nhiều chữ thuần, ít link -> khả năng là nội dung chương."""
    text = el.get_text(" ", strip=True)
    if len(text) < 200:
        return 0
    link_len = sum(len(a.get_text(" ", strip=True)) for a in el.find_all("a"))
    density = link_len / max(1, len(text))
    if density > 0.25:
        return 0
    # Ưu tiên phần tử có chữ nằm trực tiếp trong nó (hoặc trong <p> con trực tiếp)
    direct = sum(len(s.strip()) for s in el.find_all(string=True, recursive=False) if isinstance(s, NavigableString))
    direct += sum(len(p.get_text(strip=True)) for p in el.find_all("p", recursive=False))
    return direct * (1 - density)


def find_content(soup, selector=None):
    """Trả về element chứa nội dung chương (đã lọc rác) hoặc None."""
    sels = [selector] if selector else []
    sels += CONTENT_SELECTORS
    for sel in sels:
        try:
            el = soup.select_one(sel)
        except Exception:
            el = None
        if el is not None and len(el.get_text(strip=True)) >= 300:
            # Với selector chung chung (#content, article...) vẫn kiểm tra mật độ link
            if sel in ("#content", ".content", "article", ".entry-content", ".reading"):
                if _text_score(el) <= 0:
                    continue
            return el
    best, best_score = None, 0
    for el in soup.find_all(["div", "article", "section", "td", "main"]):
        sc = _text_score(el)
        if sc > best_score:
            best, best_score = el, sc
    return best if best_score >= 300 else None


def find_title(soup, selector=None):
    if selector:
        el = soup.select_one(selector)
        if el and el.get_text(strip=True):
            return el.get_text(" ", strip=True)
    # Ưu tiên tiêu đề có dạng "Chương N ..."
    for el in soup.select(".chapter-title, .chapter-name, h1, h2, h3, h4"):
        t = el.get_text(" ", strip=True)
        if 0 < len(t) < 200 and CHAPTER_TEXT_RE.match(t):
            return t
    sels = TITLE_SELECTORS
    for sel in sels:
        try:
            el = soup.select_one(sel)
        except Exception:
            el = None
        if el:
            t = el.get_text(" ", strip=True)
            if 0 < len(t) < 200:
                return t
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        return og["content"].strip()
    return soup.title.get_text(strip=True) if soup.title else ""


def find_next(soup, base_url, selector=None):
    """Tìm URL chương kế tiếp."""
    if selector:
        el = soup.select_one(selector)
        if el and el.get("href"):
            return urljoin(base_url, el["href"])
    cand = []
    link = soup.find("link", rel="next") or soup.find("a", rel="next")
    if link and link.get("href"):
        cand.append(link["href"])
    for a in soup.find_all("a", href=True):
        txt = a.get_text(" ", strip=True)
        attrs = _attr_str(a) + " " + (a.get("title") or "")
        if NEXT_TEXT_RE.match(txt) or (NEXT_ATTR_RE.search(attrs.strip()) if attrs.strip() else False):
            cand.append(a["href"])
    for h in cand:
        h = h.strip()
        if not h or h.startswith(("javascript", "#")):
            continue
        u = urljoin(base_url, h)
        if u.rstrip("/") != base_url.rstrip("/"):
            return u
    return None


def chapter_number(text_or_url):
    m = NUM_RE.search(text_or_url or "")
    if m:
        return int(m.group(1))
    return None


def _path_group(url):
    p = urlparse(url).path.rstrip("/")
    return p.rsplit("/", 1)[0]


def find_chapter_links(soup, base_url, selector=None):
    """Lấy danh sách (tiêu đề, url) các chương trên 1 trang danh sách. Đã lọc link rác, giữ thứ tự."""
    dom = urlparse(base_url).netloc
    anchors = soup.select(selector) if selector else soup.find_all("a", href=True)
    items, seen = [], set()
    for a in anchors:
        href = a.get("href")
        if not href or href.startswith(("javascript", "#", "mailto")):
            continue
        u = urljoin(base_url, href).split("#")[0]
        if urlparse(u).netloc != dom:
            continue
        txt = a.get_text(" ", strip=True) or (a.get("title") or "")
        if NEXT_TEXT_RE.match(txt):
            continue
        if not selector and not (CHAPTER_TEXT_RE.match(txt) or (CHAPTER_HREF_RE.search(urlparse(u).path) and len(txt) > 2)):
            continue
        if u in seen:
            continue
        seen.add(u)
        items.append((txt, u))
    if not items or selector:
        return items
    # Giữ nhóm link có cùng "thư mục cha" chiếm đa số (loại link ở sidebar/truyện khác)
    groups = {}
    for t, u in items:
        groups.setdefault(_path_group(u), []).append((t, u))
    best = max(groups.values(), key=len)
    if len(best) < 2:
        return []
    return best


def find_list_pages(soup, base_url, novel_path):
    """Các trang phân trang của danh sách chương (cùng đường dẫn truyện)."""
    dom = urlparse(base_url).netloc
    out = []
    for a in soup.find_all("a", href=True):
        u = urljoin(base_url, a["href"])
        pu = urlparse(u)
        if pu.netloc != dom:
            continue
        if not pu.path.startswith(novel_path.rstrip("/")):
            continue
        full = pu.path + ("?" + pu.query if pu.query else "")
        if PAGE_HREF_RE.search(full) and not CHAPTER_TEXT_RE.match(a.get_text(strip=True)):
            out.append(u.split("#")[0])
    return out


def normalize_order(items):
    """
    Sắp xếp danh sách chương đúng thứ tự đọc.
    - Web thường chèn ô "chương mới nhất" (xếp giảm dần) trước danh sách chính, hoặc xếp
      mới -> cũ. Nếu đa số chương đọc được số thứ tự (từ tiêu đề hoặc link) và số không lặp
      (không đánh lại theo quyển) thì sắp theo số chương; chương không có số giữ vị trí sau
      chương liền trước nó.
    - Nếu số chương lặp lại nhiều (mỗi quyển đánh lại từ 1) thì giữ thứ tự trên trang, chỉ đảo
      ngược khi phần lớn các cặp liền kề đang giảm dần.
    """
    if len(items) < 2:
        return items
    nums = [chapter_number(t) if chapter_number(t) is not None else chapter_number(u) for t, u in items]

    # Bỏ ô "chương mới nhất" ở đầu/cuối: khối liền nhau (≤ 30 mục) mà mọi số chương trong đó
    # đều xuất hiện lại ở phần còn lại của danh sách.
    def _block_len(seq):
        best = 0
        for k in range(1, min(30, len(seq) // 2) + 1):
            head, rest = seq[:k], set(x for x in seq[k:] if x is not None)
            rest_sorted = sorted(rest)
            median = rest_sorted[len(rest_sorted) // 2] if rest_sorted else 0
            # chỉ coi là ô "mới nhất" khi toàn số chương lớn (không phải Quyển 1 đánh số lại)
            if all(x is not None and x in rest for x in head) and min(head) > median:
                best = k
            else:
                break
        return best

    k = _block_len(nums)
    if k:
        items, nums = items[k:], nums[k:]
    k = _block_len(nums[::-1])
    if k:
        items, nums = items[:-k], nums[:-k]
    known = [n for n in nums if n is not None]
    if len(known) >= max(3, 0.8 * len(items)):
        repeats = len(known) - len(set(known))
        if repeats <= 0.05 * len(known):
            keys, last = [], 0.0
            for i, n in enumerate(nums):
                if n is not None:
                    last = float(n)
                    keys.append((last, 0, i))
                else:
                    keys.append((last, 1, i))
            order = sorted(range(len(items)), key=lambda i: keys[i])
            out, seen_num = [], set()
            for i in order:
                n = nums[i]
                # Ô "chương mới nhất" có thể trùng số với danh sách chính nhưng khác link -> bỏ bản trùng số
                if n is not None and n in seen_num and repeats:
                    continue
                if n is not None:
                    seen_num.add(n)
                out.append(items[i])
            return out
    pairs = [(a, b) for a, b in zip(known, known[1:]) if a != b]
    if pairs and sum(1 for a, b in pairs if a > b) > len(pairs) / 2:
        return list(reversed(items))
    return items


def clean_chapter_title(raw, num=None):
    """'Chương 12: Tên chương' -> 'Tên chương'"""
    t = (raw or "").strip()
    for _ in range(3):  # web hay lặp tiền tố: "Chương 1: Chương 1: Tên"
        before = t
        t = re.sub(r"^\s*(quyển|q)\s*\d+\s*[-:–.]?\s*", "", t, flags=re.I)
        t = re.sub(r"^\s*(chương|chapter|chap|ch\.?|hồi)\s*[\d\-–\s]+\s*[:\-–.]?\s*", "", t, flags=re.I)
        t = re.sub(r"^\s*第[\d一二三四五六七八九十百千零〇]+[章节回]\s*", "", t)
        t = t.strip(" -:–")
        if t == before:
            break
    return t


def is_locked(paragraphs):
    joined = " ".join(paragraphs[:8] + paragraphs[-4:])
    return bool(LOCK_RE.search(joined)) and sum(len(p) for p in paragraphs) < 1500
