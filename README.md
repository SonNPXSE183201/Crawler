# ⭐ TOOL CÀO TRUYỆN ĐA NGUỒN (MỚI) – `cao_truyen.py`

Nhấp đúp **`run_cao_truyen.bat`** rồi dán link truyện (trang có danh sách chương) – tool tự nhận diện web, tự lấy danh sách chương **đúng thứ tự**, tải đa luồng, lưu `output/<Tên truyện>/Chuong_xxxx.txt`.

```bash
python cao_truyen.py https://truyenhoan.com/dai-niet-ban.853/          # cả bộ
python cao_truyen.py <link> --start 1 --end 200 --merge                 # 1 đoạn + gộp file FULL
python cao_truyen.py <link> --info                                      # chỉ xem tên/số chương
python cao_truyen.py <link CHƯƠNG đầu> --chapter                        # web không có danh sách -> đi theo nút "Chương sau"
python cao_truyen.py --batch ds_link.txt                                # nhiều truyện
python cao_truyen.py <link> --browser --show-browser                    # web chặn bot / cần đăng nhập
```

- Đã kiểm chứng: truyenhoan.com, truyenfull.live (956/956 chương Đại Niết Bàn, đúng thứ tự, không trùng).
- Tự bỏ ô "chương mới nhất" khi sắp xếp; web đánh số lại theo quyển vẫn giữ đúng thứ tự.
- Chạy lại = tự tải tiếp chương còn thiếu; chương nào link nguồn thay đổi sẽ tự tải lại. Lỗi ghi vào `_loi.txt`.
- Thêm web mới không cần code: sửa `site_rules.json`.
- ⚠️ truyendich.space tự đăng trùng nhiều chương (vd chương 383 = 226) – nên lấy nguồn khác.


## Cài đặt
```bash
pip install -r requirements.txt
```

## Cấu trúc
```
TruyenDich_Crawler/
├── cao_truyen.py        # chạy tool (CLI + chế độ hỏi đáp)
├── run_cao_truyen.bat   # nhấp đúp để chạy
├── novel_tool/          # fetcher (HTTP/Chrome), extract (bóc nội dung, sắp thứ tự), sites (cấu hình web), engine (tải/lưu/resume)
├── site_rules.json      # thêm web mới bằng CSS selector
├── clean_censor.py      # tự khôi phục từ bị che (*) khi lưu chương
└── output/              # tự tạo khi cào
```
