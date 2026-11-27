# 📚 Crawler – Tool cào truyện chữ đa nguồn

Dán link truyện → tool tự nhận diện trang web, lấy **danh sách chương đúng thứ tự**, tải toàn bộ nội dung và lưu thành các file `Chuong_0001.txt`, `Chuong_0002.txt`… sẵn sàng để biên tập, chuyển giọng đọc AI hoặc dựng video. Không cần mở web copy/paste tay.

> 👉 Hướng dẫn từng bước cho người mới: xem **[HUONG_DAN.md](HUONG_DAN.md)**

---

## ✨ Tính năng

| | |
|---|---|
| 🌐 **Đa nguồn** | Có sẵn cấu hình cho TruyenFull, Tàng Thư Viện, SSTruyen, WikiDịch, 69shu…; web khác vẫn cào được nhờ **tự nhận diện** vùng nội dung và nút "Chương sau". |
| 🔢 **Đúng thứ tự chương** | Tự bỏ ô "chương mới nhất" mà nhiều web chèn trên danh sách, sắp theo số chương; web đánh số lại theo từng quyển vẫn giữ đúng thứ tự. |
| 🛡️ **Vượt chặn bot** | HTTP giả lập trình duyệt Chrome (`curl_cffi`) qua được phần lớn Cloudflare; gặp tường chống bot hoặc trang dựng bằng JavaScript thì **tự mở Chrome thật** (Playwright). |
| ⚡ **Nhanh & an toàn** | Tải đa luồng, giới hạn tốc độ theo từng web, tự nghỉ khi bị 403/429, tự thử lại. |
| ♻️ **Chạy tiếp (resume)** | Chạy lại lệnh cũ chỉ tải chương còn thiếu; chương nào đổi link nguồn sẽ tự tải lại; chương lỗi ghi vào `_loi.txt`. |
| 🧹 **Nội dung sạch** | Tự động lọc quảng cáo, nút điều hướng, watermark dính trong câu (`Truyện FULL`, `TruyenFull.vn`, `chấm c.o.m`, `tunghoanh`...); tự khôi phục từ bị che dấu `*`. |
| 📄 **Gộp file** | Tuỳ chọn `--merge` gộp các chương thành 1 file FULL để biên tập. |
| 🧩 **Thêm web không cần code** | Khai báo CSS selector trong `site_rules.json`. |
| 🎬 **Tự động dựng Thumbnails & Video** | Skill `.agents/skills/novel-video-production/` biến truyện đã cào thành kịch bản phân cảnh, ảnh scene sạch không chữ, bộ thumbnail tiếng Việt và video `.mp4` 1080p không âm thanh. |

Đã kiểm chứng: **truyenhoan.com**, **truyenfull.live** (bộ *Đại Niết Bàn* 956/956 chương, bộ *Bí Thư Trùng Sinh* 2.771/2.771 chương, đúng thứ tự, không trùng, không thiếu).

---

## 🚀 Bắt đầu nhanh

```bash
git clone https://github.com/SonNPXSE183201/Crawler.git
cd Crawler
pip install -r requirements.txt
```

**Windows:** nhấp đúp `run_cao_truyen.bat` → dán link truyện → trả lời vài câu hỏi.

**Dòng lệnh:**

```bash
python cao_truyen.py https://truyenhoan.com/dai-niet-ban.853/           # tải cả bộ
python cao_truyen.py <link> --start 1 --end 200 --merge                  # 1 đoạn + gộp file FULL
python cao_truyen.py <link> --info                                       # chỉ xem tên, tác giả, số chương
python cao_truyen.py <link CHƯƠNG đầu> --chapter                         # web không có danh sách chương
python cao_truyen.py --batch ds_link.txt                                 # nhiều truyện, mỗi dòng 1 link
python cao_truyen.py <link> --browser --show-browser                     # web chặn bot nặng / cần bấm captcha
```

---

## ⚙️ Tham số

| Tham số | Ý nghĩa | Mặc định |
|---|---|---|
| `url` | Link trang truyện (có danh sách chương) hoặc link 1 chương | – (không có = chế độ hỏi đáp) |
| `--start` / `--end` | Khoảng chương cần tải | 1 → hết |
| `--workers` | Số luồng tải song song | theo từng web |
| `--delay` | Số giây nghỉ giữa các request | theo từng web |
| `--output` | Thư mục lưu | `output/<Tên truyện>/` |
| `--merge` | Gộp các chương đã tải thành 1 file FULL | tắt |
| `--overwrite` | Tải lại cả các chương đã có | tắt |
| `--info` | Chỉ xem thông tin truyện, không tải | tắt |
| `--chapter` | Coi link là 1 chương, đi theo nút "Chương sau" | tự đoán |
| `--batch` | File `.txt` chứa nhiều link | – |
| `--proxy` | Proxy, vd `http://127.0.0.1:8080`, `socks5://127.0.0.1:1080` | – |
| `--browser` | Luôn dùng Chrome thật | tự động |
| `--http` | Chỉ dùng HTTP, không bao giờ mở trình duyệt | tự động |
| `--show-browser` | Hiện cửa sổ Chrome (để tự bấm captcha / đăng nhập) | ẩn |

---

## 📁 Kết quả

```
output/
└── Đại Niết Bàn/
    ├── Chuong_0001.txt      # dòng 1: "Chương 1: Thời gian đảo ngược", sau đó các đoạn văn cách nhau 1 dòng trống
    ├── Chuong_0002.txt
    ├── ...
    ├── _nguon.json          # link nguồn + link từng chương (dùng để chạy tiếp)
    ├── _loi.txt             # danh sách chương lỗi (nếu có)
    └── Đại Niết Bàn_C1-956_FULL.txt   # khi dùng --merge
```

---

## 🧹 Lọc watermark cho truyện đã cào sẵn (`clean_watermark.py`)

Tool cào hiện tự động lọc watermark inline ngay trong `extract.py` và `engine.py`. Với các bộ truyện đã tải từ trước, chạy thêm:

```bash
python clean_watermark.py --path "output/<Tên Truyện>" --dry-run   # kiểm tra thử
python clean_watermark.py --path "output/<Tên Truyện>"             # lọc sạch ghi đè
```

---

## 🎬 Workflow tự động dựng Kịch bản, Thumbnails & Video (`novel-video-production`)

Skill dựng sẵn tại [`.agents/skills/novel-video-production/SKILL.md`](.agents/skills/novel-video-production/SKILL.md) tự động biến một bộ truyện trong `output/<Tên Truyện>` thành:
- **Kịch bản phân cảnh** chia theo số chương/phần tuỳ chọn (`kich_ban_scenes.md`, `parts_manifest.json`, `thumbnails.json`).
- **Bộ ảnh scene sạch (không chữ)** 16:9 (`art/p01.png`…) + **bảng QA**.
- **Bộ thumbnails 1920×1080** chuẩn style chữ hook tiếng Việt + badge `PHẦN XX` đặt tên `thumbnails/Chuong_XXXX-YYYY_TapZZZ.png`.
- **Video `.mp4` 1080p 30fps không âm thanh** (Ken Burns + crossfade `0.5s`) có nhãn tên truyện ở góc trên bên phải.

**Yêu cầu bổ sung:** `pip install pillow numpy`, `ffmpeg` trong PATH, và `agy` CLI (tự fallback sang `claude` / `codex` khi hết quota):

| Công đoạn | CLI ưu tiên | Model & Effort tiết kiệm | CLI dự phòng (khi hết quota) |
|---|---|---|---|
| Viết kịch bản / JSON | `agy` | `gemini-3.8-flash-medium` | `claude` (`--model sonnet --effort low`) |
| Sinh ảnh scene không chữ | `agy` (`image-generator`) | `gemini-3.8-flash-low` | `codex exec` (`model_reasoning_effort="low"`) |

**Prompt mẫu khi dùng với AI Agent:**
```text
Dùng skill novel-video-production làm kịch bản, thumbnails và video cho bộ @output/<Tên Truyện>, chia 20 chương/phần.
```
*(Hoặc mở đầu bằng `/goal` để agent tự chạy xuyên suốt và kiểm tra đủ `ffprobe` + QA ảnh trước khi kết thúc.)*

---

## 🗂️ Cấu trúc mã nguồn

```
Crawler/
├── cao_truyen.py          # điểm chạy: CLI + chế độ hỏi đáp
├── run_cao_truyen.bat     # nhấp đúp để chạy trên Windows
├── novel_tool/
│   ├── fetcher.py         # tải trang: curl_cffi, tự chuyển Chrome (Playwright), rate-limit, retry
│   ├── extract.py         # bóc nội dung, lọc watermark inline, tiêu đề, nút chương sau, danh sách chương
│   ├── sites.py           # cấu hình từng web + bộ cào tự nhận diện
│   └── engine.py          # điều phối: chọn chương, tải đa luồng, resume, lọc & lưu file, gộp file
├── site_rules.json        # thêm/sửa web bằng CSS selector
├── clean_censor.py        # khôi phục từ bị che (*) khi lưu chương
├── clean_watermark.py     # lọc watermark quảng cáo web truyện khỏi các file Chuong_*.txt
├── .agents/skills/novel-video-production/
│   ├── SKILL.md           # hướng dẫn & quy trình skill dựng kịch bản, thumbnails, video
│   ├── resources/         # font Anton-Regular.ttf & ảnh tham chiếu phong cách style_ref.png
│   └── scripts/           # 6 script tự động (digest, sinh kịch bản, sinh ảnh, thumbnail, video)
└── requirements.txt
```

---

## ⚠️ Lưu ý

- Một số web dựng chương bằng nút JavaScript, không có link thật (vd truyenchu.com.vn), nên hiện chưa cào được.
- **truyendich.space tự đăng trùng nhiều chương** (vd chương 383 có nội dung giống chương 226), nên lấy nguồn khác.
- Một số web bị nhà mạng chặn: bật 1.1.1.1 / WARP hoặc dùng `--proxy`.
- Chương VIP / cần đăng nhập sẽ bị đánh dấu lỗi trong `_loi.txt`.
- Chỉ dùng cho mục đích cá nhân, tôn trọng bản quyền của tác giả và dịch giả.
