---
name: novel-video-production
description: >-
  Quy trình tự động trọn gói biến một bộ truyện đã cào trong `output/<Tên Truyện>` thành
  kịch bản phân cảnh, bộ ảnh scene sạch không chữ (ưu tiên Antigravity CLI `agy`, hết quota
  tự fallback sang Claude CLI / Codex CLI với model và effort tiết kiệm token), bộ thumbnail
  tiếng Việt chuẩn style `thumbnails_v3`, và video `.mp4` 1080p 30fps không âm thanh có nhãn
  tên truyện ở góc trên bên phải. Kích hoạt khi người dùng yêu cầu tạo thumbnail, kịch bản scene
  và video cho một bộ truyện bất kỳ trong thư mục `output/`.
---

# Quy trình sản xuất Thumbnails & Video Scene cho truyện chữ

Quy trình này chuyển bất kỳ bộ truyện nào nằm trong `output/<Tên Truyện>` thành:
1. Văn bản chương sạch (đã lọc watermark quảng cáo web truyện).
2. Kịch bản phân cảnh chi tiết (`production/kich_ban_scenes.md`, `parts_manifest.json`, `thumbnails.json`).
3. Bộ ảnh minh họa 16:9 sạch, **tuyệt đối không chữ** (`art/p01.png`..`pNN.png`).
4. Bộ thumbnail YouTube 1920x1080 có chữ hook tiếng Việt + badge `PHẦN XX` đặt tên theo chuẩn `thumbnails/Chuong_<start:04d>-<end:04d>_Tap<tap:03d>.png` (ví dụ `Chuong_0001-0040_Tap001.png`, `Chuong_0941-0956_Tap048.png`).
5. Video `.mp4` 1920x1080 30fps không âm thanh (Ken Burns + crossfade `0.5s`) kèm nhãn tên truyện ở góc trên bên phải.

---

## Chính sách tiết kiệm token & thứ tự CLI

Ưu tiên **Antigravity CLI (`agy`)** trước với model nhẹ và `--effort low`; chỉ tự động fallback khi gặp lỗi hết quota (`429` / `RESOURCE_EXHAUSTED`):

| Công đoạn | CLI ưu tiên (Primary) | Model & Effort tiết kiệm | CLI dự phòng (Fallback khi hết quota) |
| :--- | :--- | :--- | :--- |
| **Viết kịch bản / tóm tắt JSON (Bước 2)** | `agy` | `gemini-3.8-flash-medium` *(effort `medium` sẵn trong tên model)* | `claude` (`--model sonnet --effort low`) |
| **Sinh ảnh scene sạch không chữ (Bước 3)** | `agy` (`image-generator`) | `gemini-3.8-flash-low` *(effort `low` sẵn trong tên model)* | `codex exec` (`model_reasoning_effort="low"`, `image_gen`) |

*(Lưu ý: `claude` CLI hiện không có công cụ sinh ảnh tích hợp nên Bước 3 fallback sang `codex exec`.)*

---

## Bước 0 — Xác định thông số đầu vào

Trước khi chạy, xác định rõ các thông số sau:
- **Thư mục truyện nguồn:** `output/<Tên Truyện>` (chứa `Chuong_*.txt`).
- **Tên hiển thị trên video:** chữ in hoa có dấu tiếng Việt (ví dụ `"BÍ THƯ TRÙNG SINH"`).
- **Thư mục đầu ra dự án:** `video_<slug_ten_truyen>/` ở gốc workspace.
- **Số chương mỗi phần (`--chapters-per-part`):** **không cố định** — lấy đúng số chương/phần mà người dùng chỉ định trong prompt (ví dụ 20, 30, 40, 50 chương/phần). Nếu người dùng chưa nói rõ một phần bao nhiêu chương, **phải hỏi người dùng trước khi chạy Bước 2**.

---

## Bước 1 — Lọc sạch watermark trên toàn bộ chương

```powershell
python clean_watermark.py --path "output/<Tên Truyện>"
```

Kiểm tra nhanh còn sót chuỗi `truyenfull`, `truyện full`, `chấm c.o.m`, `copy tại`, `được lấy tại`, `t u n g h o a n h` hay không (phải ra `0` kết quả).

---

## Bước 2 — Tạo digest nguồn & biên soạn kịch bản từng phần

1. Tách digest bằng [build_digests.py](./scripts/build_digests.py):

```powershell
python ".agents/skills/novel-video-production/scripts/build_digests.py" `
  --novel-dir "output/<Tên Truyện>" `
  --work-dir "video_<slug>" `
  --chapters-per-part <SO_CHUONG_MOI_PHAN>
```

2. Sinh `production/summaries/p01.json..pNN.json` bằng [generate_summaries_cli.py](./scripts/generate_summaries_cli.py) (tự ưu tiên `agy` model `gemini-3.8-flash-medium --effort low`, hết quota tự chuyển sang `claude --model sonnet --effort low`):

```powershell
python ".agents/skills/novel-video-production/scripts/generate_summaries_cli.py" `
  --work-dir "video_<slug>" `
  --novel-title "<Tên Truyện>" `
  --source-chapters <TONG_CHUONG> `
  --chapters-per-part <SO_CHUONG_MOI_PHAN> `
  --protagonist-brief "<Mô tả ngoại hình, tuổi tác, trang phục nhân vật chính theo từng giai đoạn>" `
  --providers "agy,claude" `
  --agy-model "gemini-3.8-flash-medium" `
  --claude-model "sonnet" `
  --effort "low"
```

3. Kiểm tra & xuất bộ tài liệu kịch bản bằng [validate_and_export_script.py](./scripts/validate_and_export_script.py):

```powershell
python ".agents/skills/novel-video-production/scripts/validate_and_export_script.py" `
  --work-dir "video_<slug>" `
  --novel-title "<Tên Truyện>" `
  --source-chapters <TONG_CHUONG> `
  --chapters-per-part <SO_CHUONG_MOI_PHAN> `
  --forbidden-names "<Tên nhân vật chính>,<Tên phụ>"
```

---

## Bước 3 — Sinh ảnh scene sạch (không chữ) qua `agy` → fallback `codex`

1. **Sinh ảnh chuẩn `p01.png` trước** bằng [generate_art.py](./scripts/generate_art.py):

```powershell
python ".agents/skills/novel-video-production/scripts/generate_art.py" `
  --work-dir "video_<slug>" `
  --parts 1 `
  --ref ".agents/skills/novel-video-production/resources/style_ref.png" `
  --style-only `
  --providers "agy,codex" `
  --agy-model "gemini-3.8-flash-low" `
  --effort "low"
```

   Mở `video_<slug>/art/p01.png` bằng `read_file` để kiểm tra: đúng 16:9, tạo hình nhân vật chính sắc nét ở bên phải, bên trái tối thoáng, **0 chữ**.

2. **Sinh toàn bộ các phần còn lại (`p02..pNN`)** dùng chính `art/p01.png` làm chuẩn khuôn mặt & phong cách (ưu tiên `agy`, tự chuyển `codex` ngay khi `agy` chạm quota):

```powershell
python ".agents/skills/novel-video-production/scripts/generate_art.py" `
  --work-dir "video_<slug>" `
  --workers 4 `
  --providers "agy,codex" `
  --agy-model "gemini-3.8-flash-low" `
  --effort "low"
```

3. **Kiểm tra QA ảnh scene:** script tự tạo các bảng `production/qa_art_01.jpg..`. Bắt buộc dùng `read_file` xem toàn bộ các bảng QA; nếu cảnh nào dính chữ, lỗi giải phẫu hoặc nhân vật dạt sang trái quá nhiều, chạy lại bằng `--parts <số> --force`.

---

## Bước 4 — Render bộ Thumbnails (`thumbnails/Chuong_XXXX-YYYY_TapZZZ.png`)

Chạy [render_thumbnails.py](./scripts/render_thumbnails.py) (tự dùng font [Anton-Regular.ttf](./resources/Anton-Regular.ttf) đã đóng gói sẵn, căn chữ không rớt chữ lẻ, xuất tên file theo chuẩn `Chuong_<start:04d>-<end:04d>_Tap<tap:03d>.png`):

```powershell
python ".agents/skills/novel-video-production/scripts/render_thumbnails.py" `
  --work-dir "video_<slug>"
```

Mở thumbnail đầu tiên (`Chuong_0001-..._Tap001.png`), thumbnail thứ hai và các bảng `production/qa_thumbnails_*.jpg` bằng `read_file` để kiểm tra chuẩn dấu tiếng Việt, không cắt dấu, không che mặt nhân vật, badge đỏ `PHẦN XX` rõ nét.

---

## Bước 5 — Ghép video MP4 không âm thanh + nhãn tên truyện góc trên bên phải

Chạy [build_video.py](./scripts/build_video.py) (chỉ ghép từ `art/p01.png..pNN.png`, tuyệt đối không lấy thumbnail, tự tạo overlay `production/title_badge.png` ở góc trên bên phải rồi ghép bằng `ffmpeg` + `ffprobe` + trích xuất khung hình QA):

```powershell
python ".agents/skills/novel-video-production/scripts/build_video.py" `
  --work-dir "video_<slug>" `
  --title "<TÊN TRUYỆN IN HOA>"
```

*(Nếu đã có file `.mp4` và chỉ cần đóng dấu hoặc đổi nhãn tên truyện góc trên bên phải mà không muốn render lại từng clip, dùng thêm cờ `--overlay-only "<đường_dẫn_mp4>"`.)*

**Kiểm tra hoàn tất:**
- Xác nhận đầu ra `ffprobe`: `codec_name=h264`, `width=1920`, `height=1080`, `avg_frame_rate=30/1`, `pix_fmt=yuv420p`, `nb_streams=1` (không có audio).
- Dùng `read_file` mở `production/qa_badge_crop.png` và `production/qa_video_frames.jpg` để xác nhận nhãn tên truyện ở góc trên bên phải sắc nét, cân đối, còn phần thân video sạch hoàn toàn không chữ.
