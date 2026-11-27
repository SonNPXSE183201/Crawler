# 📖 HƯỚNG DẪN SỬ DỤNG TOOL CÀO TRUYỆN

Hướng dẫn từng bước cho người không rành kỹ thuật. Tổng quan và danh sách tham số xem ở [README.md](README.md).

---

## Mục lục
1. [Cài đặt lần đầu](#1-cài-đặt-lần-đầu)
2. [Cách 1 – Nhấp đúp file .bat (dễ nhất)](#2-cách-1--nhấp-đúp-file-bat-dễ-nhất)
3. [Cách 2 – Gõ lệnh](#3-cách-2--gõ-lệnh)
4. [Nên dán link nào?](#4-nên-dán-link-nào)
5. [Kết quả nằm ở đâu, định dạng ra sao](#5-kết-quả-nằm-ở-đâu-định-dạng-ra-sao)
6. [Bị ngắt giữa chừng / tải bù chương lỗi](#6-bị-ngắt-giữa-chừng--tải-bù-chương-lỗi)
7. [Cào nhiều truyện một lúc](#7-cào-nhiều-truyện-một-lúc)
8. [Web khó: chặn bot, captcha, nhà mạng chặn](#8-web-khó-chặn-bot-captcha-nhà-mạng-chặn)
9. [Thêm một trang web mới](#9-thêm-một-trang-web-mới)
10. [Xử lý lỗi thường gặp](#10-xử-lý-lỗi-thường-gặp)
11. [Lọc watermark trên truyện đã cào sẵn (`clean_watermark.py`)](#11-lọc-watermark-trên-truyện-đã-cào-sẵn-clean_watermarkpy)
12. [Tự động tạo Kịch bản, Thumbnails & Video (`novel-video-production`)](#12-tự-động-tạo-kịch-bản-thumbnails--video-novel-video-production)

---

## 1. Cài đặt lần đầu

**Bước 1 – Cài Python** (bỏ qua nếu đã có)
- Tải ở https://www.python.org/downloads/ (bản 3.10 trở lên).
- Khi cài, **tích ô "Add Python to PATH"**.
- Kiểm tra: mở PowerShell, gõ `python --version`. Hiện `Python 3.x.x` là được.

**Bước 2 – Tải tool**
```bash
git clone https://github.com/SonNPXSE183201/Crawler.git
```
Không có git thì vào trang GitHub, bấm **Code → Download ZIP** rồi giải nén.

**Bước 3 – Cài thư viện.** Mở PowerShell trong thư mục tool rồi gõ:
```bash
pip install -r requirements.txt
```

**Bước 4 (tuỳ chọn) – Chế độ trình duyệt.** Tool dùng **Chrome hoặc Edge có sẵn trên máy**, không phải tải thêm trình duyệt. Chỉ khi máy không có cả Chrome lẫn Edge mới cần chạy:
```bash
python -m playwright install chromium
```

---

## 2. Cách 1 – Nhấp đúp file .bat (dễ nhất)

Nhấp đúp **`run_cao_truyen.bat`**. Tool sẽ hỏi lần lượt:

| Câu hỏi | Bạn nhập |
|---|---|
| `Link 1:` | Dán link truyện, Enter. Muốn tải nhiều truyện thì dán tiếp link 2, 3…; xong thì **Enter dòng trống**. |
| `Chương BẮT ĐẦU` | Enter = từ chương 1 |
| `Chương KẾT THÚC` | Enter = đến hết |
| `Tốc độ` | `1` tự động theo web (khuyên dùng) · `2` an toàn (web hay chặn IP) · `3` nhanh |
| `Gộp tất cả chương thành 1 file FULL?` | `y` nếu muốn thêm 1 file gộp để biên tập |
| `Tải lại & ghi đè chương đã có?` | Thường để `N` |
| `Proxy` | Enter nếu không dùng |

Tool hiện tên truyện, tác giả, số chương, thanh tiến trình, và cuối cùng là tổng kết: tải mới / đã có / lỗi.

---

## 3. Cách 2 – Gõ lệnh

Mở PowerShell trong thư mục tool:

```bash
# Xem trước: tên truyện, tác giả, số chương, 5 chương đầu
python cao_truyen.py https://truyenhoan.com/dai-niet-ban.853/ --info

# Tải cả bộ
python cao_truyen.py https://truyenhoan.com/dai-niet-ban.853/

# Tải chương 1–200 và gộp thành 1 file
python cao_truyen.py https://truyenhoan.com/dai-niet-ban.853/ --start 1 --end 200 --merge

# Lưu vào thư mục khác
python cao_truyen.py <link> --output "D:/Truyen/Dai Niet Ban"

# Web hay chặn: 1 luồng, nghỉ 2 giây
python cao_truyen.py <link> --workers 1 --delay 2
```

> 💡 Link có dấu `&` hoặc khoảng trắng thì đặt trong ngoặc kép: `"https://..."`.

---

## 4. Nên dán link nào?

| Loại link | Ví dụ | Tool sẽ làm gì |
|---|---|---|
| ✅ **Trang giới thiệu truyện** (có danh sách chương) – **nên dùng** | `https://truyenfull.live/dai-niet-ban/` | Lấy toàn bộ danh sách chương, kể cả nhiều trang phân trang, sắp đúng thứ tự rồi tải đa luồng. |
| Link **1 chương** | `.../chuong-10/` | Bắt đầu từ chương đó rồi đi theo nút "Chương sau" (tải tuần tự, chậm hơn). Thêm `--start 10` để file được đánh số đúng. |

Gợi ý: luôn chạy `--info` trước để kiểm tra tên truyện, số chương và vài chương đầu có đúng không.

---

## 5. Kết quả nằm ở đâu, định dạng ra sao

Mặc định lưu ở `output/<Tên truyện>/`:

```
Chuong_0001.txt
Chuong_0002.txt
...
_nguon.json      ← đừng xoá: tool dùng để chạy tiếp
_loi.txt         ← chỉ có khi có chương lỗi
<Tên>_C1-956_FULL.txt   ← khi dùng --merge
```

Nội dung mỗi file:
```
Chương 1: Thời gian đảo ngược

Tích tắc thời gian khựng lại đó, cụ thể mà nói là không hề có cảm giác gì.

Tô Xán sửng sốt nhìn mình vẫn giữ nguyên tư thế...
```
- Dòng 1: `Chương N: Tên chương`. Nếu web lặp tiền tố kiểu "Chương 1: Chương 1: …" thì tool tự làm sạch.
- Các đoạn văn cách nhau 1 dòng trống, mã UTF-8.
- Đã lọc quảng cáo, watermark, nút điều hướng; từ bị che dấu `*` được khôi phục tự động.

---

## 6. Bị ngắt giữa chừng / tải bù chương lỗi

- Bấm **Ctrl + C** để dừng bất cứ lúc nào.
- **Chạy lại đúng lệnh cũ:** tool tự bỏ qua chương đã tải đủ và chỉ tải chương còn thiếu hoặc lỗi.
- Chương lỗi được liệt kê trong `_loi.txt` kèm lý do. Chạy lại lệnh để tải bù.
- Nếu web thay đổi danh sách chương, chương nào có link nguồn khác lần trước sẽ **tự tải lại**, dòng log báo `♻️`.
- Muốn tải lại toàn bộ thì thêm `--overwrite`.

---

## 7. Cào nhiều truyện một lúc

Tạo file `ds_link.txt`, mỗi dòng 1 link (dòng bắt đầu bằng `#` sẽ bị bỏ qua):
```
https://truyenhoan.com/dai-niet-ban.853/
https://truyenfull.live/ten-truyen-khac/
# https://... (tạm bỏ qua)
```
Chạy:
```bash
python cao_truyen.py --batch ds_link.txt
```
Mỗi truyện được lưu vào thư mục riêng theo tên truyện.

---

## 8. Web khó: chặn bot, captcha, nhà mạng chặn

| Hiện tượng | Cách xử lý |
|---|---|
| Log báo `🛡️ ... có tường chống bot -> chuyển sang trình duyệt thật` | Không cần làm gì, tool tự mở Chrome ẩn để tải. |
| Bị captcha, tool đứng lâu | `python cao_truyen.py <link> --browser --show-browser`, rồi tự bấm captcha trong cửa sổ Chrome hiện ra. |
| `HTTP 403/429 - bị chặn tạm thời` | Tool tự nghỉ rồi thử lại. Nếu bị liên tục: `--workers 1 --delay 2`, hoặc đổi IP (bật/tắt 4G, khởi động lại modem). |
| `Không mở được trang`, lỗi SSL/timeout | Web có thể bị nhà mạng chặn: bật **1.1.1.1 / WARP**, hoặc dùng `--proxy http://ip:port`. |
| `Chương bị khóa / cần đăng nhập (VIP)` | Chương trả phí, tool không tải được. |

---

## 9. Thêm một trang web mới

Phần lớn web tool tự nhận diện được. Nếu một web bị lấy sai nội dung hoặc thiếu danh sách, mở **`site_rules.json`** và thêm một mục. **Khoá** là một phần tên miền:

```json
{
  "tenweb.com": {
    "name": "Tên Web",
    "novel_title": "h1",
    "chapter_list": ".list-chapter a",
    "content": "#chapter-content",
    "title": ".chapter-title",
    "next": "a#next-chapter",
    "js": false,
    "workers": 3,
    "delay": 0.5
  }
}
```

| Trường | Ý nghĩa |
|---|---|
| `novel_title` | Selector tên truyện trên trang giới thiệu |
| `chapter_list` | Selector các thẻ `<a>` trong danh sách chương |
| `content` | Selector vùng nội dung chương |
| `title` | Selector tiêu đề chương |
| `next` | Selector nút "Chương sau" |
| `js` | `true` nếu web cần trình duyệt mới hiện nội dung |
| `workers`, `delay` | Số luồng, số giây nghỉ mặc định cho web này |

Mọi trường đều không bắt buộc; trường nào bỏ trống thì tool tự nhận diện.

**Cách lấy selector:** mở chương trong Chrome → chuột phải vào đoạn văn → **Inspect** → xem thẻ bao ngoài có `id="..."` (viết `#id`) hoặc `class="..."` (viết `.class`).

---

## 10. Xử lý lỗi thường gặp

| Lỗi | Nguyên nhân / cách sửa |
|---|---|
| `'python' is not recognized` | Chưa cài Python hoặc chưa tích "Add to PATH". Cài lại Python. |
| `ModuleNotFoundError: curl_cffi` (hoặc bs4, tqdm…) | Chạy lại `pip install -r requirements.txt`. |
| `Chưa cài Playwright` | `pip install playwright`. Chỉ cần cho web chặn bot hoặc dùng JavaScript. |
| `Không mở được Chrome/Edge` | Cài Chrome, hoặc chạy `python -m playwright install chromium`. |
| `Không tìm thấy danh sách chương lẫn link chương đầu` | Dán thẳng link **chương 1** (chế độ "Chương sau"), hoặc thêm `chapter_list` vào `site_rules.json`. |
| `Không tìm thấy nội dung chương` | Thêm selector `content` cho web đó vào `site_rules.json`. |
| Tiếng Việt lỗi font trong cửa sổ đen | Dùng `run_cao_truyen.bat` (đã bật UTF-8), hoặc mở bằng Windows Terminal. |
| Nội dung chương lặp lại chương trước | Do **web nguồn** đăng trùng, ví dụ truyendich.space. Đổi sang nguồn khác. |

---

## 11. Lọc watermark trên truyện đã cào sẵn (`clean_watermark.py`)

Từ bản cập nhật mới, `novel_tool/extract.py` và `novel_tool/engine.py` đã tự động cắt bỏ các dòng/cụm watermark quảng cáo (`Truyện được copy tại Truyện FULL`, `Text được lấy tại Truyện FULL`, `Bạn đang xem truyện được sao chép tại: TruyenFull.vn chấm c.o.m`, `Nguồn tại http://Truyện FULL`, `nguồn t.u.n.g h.o.a.n.h (.) c.o.m`…) ngay lúc cào về.

Nếu bạn có thư mục truyện đã tải từ trước, dùng lệnh sau để làm sạch hàng loạt:

```bash
# Kiểm tra thử (chưa sửa file)
python clean_watermark.py --path "output/<Tên Truyện>" --dry-run

# Lọc sạch toàn bộ các file Chuong_*.txt trong thư mục
python clean_watermark.py --path "output/<Tên Truyện>"
```

---

## 12. Tự động tạo Kịch bản, Thumbnails & Video (`novel-video-production`)

Workspace đã cài sẵn skill **[`.agents/skills/novel-video-production/SKILL.md`](.agents/skills/novel-video-production/SKILL.md)** để biến bất kỳ bộ truyện nào trong `output/` thành bộ sản phẩm hoàn chỉnh gồm kịch bản phân cảnh, ảnh scene sạch không chữ, bộ thumbnail tiếng Việt và video `.mp4`.

**Chuẩn bị môi trường (làm 1 lần):**
- Cài thư viện ảnh: `pip install pillow numpy`
- Cài `ffmpeg` (và `ffprobe`) vào PATH (trên Windows có thể cài qua `winget install Gyan.FFmpeg`).
- Đã đăng nhập `agy` CLI (khuyên dùng; khi hết quota, skill tự fallback sang `claude` CLI cho phần viết kịch bản và `codex` CLI cho phần sinh ảnh với model/effort tiết kiệm token).

**Cách prompt ngắn gọn hằng ngày:**
```text
Dùng skill novel-video-production làm kịch bản, thumbnails và video cho bộ @output/<Tên Truyện>, chia 20 chương/phần.
```
*(Thay `20` bằng bất kỳ số chương/phần nào bạn muốn: `15`, `20`, `30`, `40`, `50`…)*

**Cách dùng `/goal` cho bộ truyện dài (chạy tự động xuyên suốt đến khi xong hẳn):**
```text
/goal Dùng skill novel-video-production làm trọn gói kịch bản, thumbnails và video cho bộ @output/<Tên Truyện>, chia 20 chương/phần. Chỉ kết thúc khi đã: (1) lọc sạch 0 watermark toàn bộ chương, (2) sinh xong kịch bản JSON (ưu tiên agy, hết quota sang claude), (3) sinh và kiểm tra QA đủ toàn bộ ảnh scene sạch không chữ (ưu tiên agy, hết quota sang codex), (4) render đủ bộ thumbnails chuẩn Chuong_XXXX-YYYY_TapZZZ.png, và (5) xuất xong video .mp4 1080p 30fps không âm thanh có nhãn tên truyện góc trên bên phải đã kiểm tra bằng ffprobe và ảnh khung hình.
```

**Đầu ra được tạo tại `video_<ten_truyen>/`:**
- `production/kich_ban_scenes.md`, `parts_manifest.json`, `scene_order.csv`, `thumbnails.json`
- `art/p01.png`… — ảnh minh họa 16:9 sạch, tuyệt đối không chữ
- `thumbnails/Chuong_XXXX-YYYY_TapZZZ.png` — bộ thumbnail 1920×1080 chữ hook tiếng Việt + badge `PHẦN XX`
- `<Ten_Truyen>_<N>_Scenes.mp4` — video 1920×1080 30fps H.264 không âm thanh (Ken Burns + crossfade `0.5s`) có pill tên truyện ở góc trên bên phải.
