#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto Uncensor / De-censor Tool for Web Novels
Phục hồi tự động các từ khóa bị che dấu sao (*) từ các web truyện (TruyenFull, Tangthuvien...)
Chuẩn hóa văn bản tiếng Việt để các công cụ đọc AI (Edge TTS, Google TTS, Viettel AI...) đọc tự nhiên, không bị lỗi.
"""

import os
import sys
import re
import glob
import argparse
from tqdm import tqdm

# Bảng quy tắc giải mã từ bị che (Thứ tự ưu tiên: cụm từ dài trước, từ đơn sau)
UNCENSOR_RULES = [
    # Cụm từ phức tạp / vị trí cơ thể
    (r'(?<!\w)g\*{2,4}\s+h\*{1,3}\s+ch\*n(?!\w)', 'giữa hai chân'),
    (r'(?<!\w)chiếc\s+q\*{1,2}n\s+l\*t(?!\w)', 'chiếc quần lót'),
    (r'(?<!\w)cái\s+q\*{1,2}n\s+l\*t(?!\w)', 'cái quần lót'),
    (r'(?<!\w)mặc\s+q\*{1,2}n\s+l\*t(?!\w)', 'mặc quần lót'),
    (r'(?<!\w)kéo\s+q\*{1,2}n\s+l\*t(?!\w)', 'kéo quần lót'),
    (r'(?<!\w)mép\s+q\*{1,2}n\s+l\*t(?!\w)', 'mép quần lót'),
    (r'(?<!\w)q\*{1,2}n\s+l\*t(?!\w)', 'quần lót'),
    (r'(?<!\w)c\*{1,2}\s+q\*{1,2}n(?!\w)', 'cởi quần'),
    (r'(?<!\w)k\*{1,2}\s+kh\*{1,2}\s+q\*{1,2}n(?!\w)', 'kéo khóa quần'),
    (r'(?<!\w)k\*{1,2}\s+q\*{1,2}n(?!\w)', 'kéo quần'),
    (r'(?<!\w)chiếc\s+q\*{1,2}n(?!\w)', 'chiếc quần'),
    (r'(?<!\w)cái\s+q\*{1,2}n(?!\w)', 'cái quần'),
    (r'(?<!\w)đ\*ng\s+q\*{1,2}n(?!\w)', 'đũng quần'),

    # Thân thể & Mông & Vú & Đùi
    (r'(?<!\w)h\*\s+th\*n(?!\w)', 'hạ thân'),
    (r'(?<!\w)c\*{1,2}p\s+m\*ng\s+tr\*n\s+lẳn(?!\w)', 'cặp mông tròn lẳn'),
    (r'(?<!\w)c\*{1,2}p\s+m\*ng\s+tr\*n(?!\w)', 'cặp mông tròn'),
    (r'(?<!\w)c\*{1,2}p\s+m\*ng(?!\w)', 'cặp mông'),
    (r'(?<!\w)b\*\s+m\*ng\s+tr\*n(?!\w)', 'bờ mông tròn'),
    (r'(?<!\w)b\*\s+m\*ng(?!\w)', 'bờ mông'),
    (r'(?<!\w)m\*ng\s+tr\*n\s+trịa(?!\w)', 'mông tròn trịa'),
    (r'(?<!\w)m\*ng\s+tr\*n\s+lẳn(?!\w)', 'mông tròn lẳn'),
    (r'(?<!\w)m\*ng\s+tr\*n(?!\w)', 'mông tròn'),
    (r'(?<!\w)n\*ng\s+m\*ng(?!\w)', 'nâng mông'),
    (r'(?<!\w)m\*ng\s+đít(?!\w)', 'mông đít'),
    (r'(?<!\w)m\*ng(?!\w)', 'mông'),

    (r'(?<!\w)hai\s+b\*{1,2}\s+v\*(?!\w)', 'hai bầu vú'),
    (r'(?<!\w)b\*{1,2}\s+v\*(?!\w)', 'bầu vú'),
    (r'(?<!\w)hai\s+n\*m\s+v\*(?!\w)', 'hai núm vú'),
    (r'(?<!\w)n\*m\s+v\*(?!\w)', 'núm vú'),
    (r'(?<!\w)q\*{1,2}ng\s+v\*(?!\w)', 'quầng vú'),
    (r'(?<!\w)đôi\s+v\*(?!\w)', 'đôi vú'),
    (r'(?<!\w)hai\s+b\*{1,2}\s+ng\*c(?!\w)', 'hai bầu ngực'),
    (r'(?<!\w)b\*{1,2}\s+ng\*c(?!\w)', 'bầu ngực'),
    (r'(?<!\w)b\*\s+ng\*c(?!\w)', 'bộ ngực'),
    (r'(?<!\w)c\*{1,2}p\s+t\*{2,3}t\s+l\*(?!\w)', 'cặp tuyết lê'),
    (r'(?<!\w)g\*\s+b\*ng\s+đ\*{1,2}(?!\w)', 'gò bồng đảo'),
    (r'(?<!\w)b\*p\s+đ\*{1,2}\s+tr\*ng\s+n\*n(?!\w)', 'bắp đùi trắng nõn'),
    (r'(?<!\w)b\*p\s+đ\*{1,2}(?!\w)', 'bắp đùi'),
    (r'(?<!\w)tr\*ng\s+n\*n(?!\w)', 'trắng nõn'),
    (r'(?<!\w)c\*{1,2}\s+nh\*(?!\w)', 'cậu nhỏ'),
    (r'(?<!\w)d\*ng\s+h\*ng(?!\w)', 'dạng háng'),
    (r'(?<!\w)v\*ng\s+eo(?!\w)', 'vòng eo'),

    # Hành vi & Cảm giác & Rên rỉ
    (r'(?<!\w)tiếng\s+r\*n\s+r\*(?!\w)', 'tiếng rên rỉ'),
    (r'(?<!\w)r\*n\s+r\*(?!\w)', 'rên rỉ'),
    (r'(?<!\w)tiếng\s+r\*n(?!\w)', 'tiếng rên'),
    (r'(?<!\w)v\*{1,2}t\s+v\*(?!\w)', 'vuốt ve'),
    (r'(?<!\w)thể\s+tr\*n\s+tr\*{1,2}ng(?!\w)', 'thể trần truồng'),
    (r'(?<!\w)tr\*n\s+tr\*{1,2}ng(?!\w)', 'trần truồng'),
    (r'(?<!\w)tr\*n\s+tr\*{1,2}(?!\w)', 'trần trụi'),
    (r'(?<!\w)k\*ch\s+th\*ch(?!\w)', 'kích thích'),
    (r'(?<!\w)k\*ch\s+t\*nh(?!\w)', 'kích tình'),
    (r'(?<!\w)kh\*{2,4}\s+c\*m(?!\w)', 'khoái cảm'),
    (r'(?<!\w)c\*c\s+kh\*{2,4}(?!\w)', 'cực khoái'),
    (r'(?<!\w)đ\*t\s+c\*{1,2}\s+tr\*+(?!\w)|đạt cao trào\*+', 'đạt cao trào'),
    (r'(?<!\w)x\*{1,2}n\s+t\*nh(?!\w)', 'xuân tình'),
    (r'(?<!\w)đ\*ng\s+t\*nh(?!\w)', 'động tình'),
    (r'(?<!\w)t\*nh\s+d\*c(?!\w)', 'tình dục'),
    (r'(?<!\w)d\*c\s+v\*ng(?!\w)', 'dục vọng'),
    (r'(?<!\w)d\*c\s+d\*c(?!\w)', 'dâm dục'),
    (r'(?<!\w)l\*m\s+t\*nh(?!\w)', 'làm tình'),
    (r'(?<!\w)t\*nh\s+nh\*n(?!\w)', 'tình nhân'),
    (r'(?<!\w)c\*{1,2}\s+th\*t\s+l\*ng(?!\w)', 'cởi thắt lưng'),
    (r'(?<!\w)kh\*{2,4}\s+g\*(?!\w)', 'khiêu gợi'),
    (r'(?<!\w)th\*c\s+m\*nh(?!\w)', 'thúc mạnh'),
    (r'(?<!\w)x\*{1,2}\s+n\*n(?!\w)', 'xoa nắn'),
    (r'(?<!\w)c\*n\s+l\*n(?!\w)', 'cắn lên'),
    (r'(?<!\w)c\*nh\s+m\*{1,2}(?!\w)', 'cánh môi'),
    (r'(?<!\w)l\*{1,2}m\s+cánh\s+môi(?!\w)', 'liếm cánh môi'),
    (r'(?<!\w)l\*{1,2}m\s+môi(?!\w)', 'liếm môi'),
    (r'(?<!\w)l\*{1,2}m(?!\w)', 'liếm'),
    (r'(?<!\w)m\*t\s+tay(?!\w)', 'mút tay'),
    (r'(?<!\w)m\*t\s+lấy(?!\w)', 'mút lấy'),
    (r'(?<!\w)m\*t(?!\w)', 'mút'),
    (r'(?<!\w)th\*\s+d\*c(?!\w)', 'thở dốc'),

    # Từ ngữ bị bot lọc nhầm
    (r'(?<!\w)ch\*{1,2}\s+n\*{1,2}c\s+mắt(?!\w)', 'chảy nước mắt'),
    (r'(?<!\w)ch\*{1,2}\s+n\*{1,2}c(?!\w)', 'chảy nước'),
    (r'(?<!\w)chính\s+q\*{1,2}(?!\w)', 'chính quy'),
    (r'(?<!\w)đ\*{1,2}\s+tiên(?!\w)', 'đầu tiên'),
    (r'(?<!\w)b\*{1,3}\s+chiều(?!\w)', 'buổi chiều'),
    (r'(?<!\w)quái\s+v\*t(?!\w)', 'quái vật'),
    (r'(?<!\w)t\*\s+l\*n(?!\w)', 'to lớn'),
    (r'(?<!\w)c\*n\s+tr\*m(?!\w)', 'cắn trộm'),
    (r'(?<!\w)c\*\s+li(?!\w)', 'cự li'),
    (r'(?<!\w)phản\*ng(?!\w)', 'phản ứng'),
    (r'(?<!\w)th\*ng\s+9(?!\w)', 'tháng 9'),
    (r'(?<!\w)th\*\s+t\*c(?!\w)', 'thô tục'),

    # Tệ nạn / Chửi bậy / Nhạy cảm xã hội
    (r'(?<!\w)uy\s+h\*{1,2}p(?!\w)', 'uy hiếp'),
    (r'(?<!\w)ức\s+h\*{1,2}p(?!\w)', 'ức hiếp'),
    (r'(?<!\w)hãm\s+h\*{1,2}p(?!\w)', 'hãm hiếp'),
    (r'(?<!\w)c\*{1,2}ng\s+b\*c(?!\w)', 'cưỡng bức'),
    (r'(?<!\w)b\*p\s+ch\*t(?!\w)', 'bóp chết'),
    (r'(?<!\w)kh\*ng\s+b\*(?!\w)', 'khủng bố'),
    (r'(?<!\w)th\*m\s+nh\*ng(?!\w)', 'tham nhũng'),
    (r'(?<!\w)tửu\s+đ\*{1,2}m(?!\w)', 'tửu điếm'),
    (r'(?<!\w)con\s+đ\*{1,2}m(?!\w)', 'con điếm'),
    (r'(?<!\w)b\*n\s+d\*m(?!\w)', 'bán dâm'),
    (r'(?<!\w)m\*{1,2}\s+d\*m(?!\w)', 'mại dâm'),
    (r'(?<!\w)m\*\s+t\*{1,2}(?!\w)', 'ma túy'),
    (r'(?<!\w)b\*{1,2}n\s+th\*{1,2}(?!\w)', 'biến thái'),
    (r'(?<!\w)d\*m\s+t\*c(?!\w)', 'dâm tặc'),
    (r'(?<!\w)d\*m\s+đãng(?!\w)', 'dâm đãng'),
    (r'(?<!\w)ph\*{1,2}ng\s+đ\*{1,2}ng(?!\w)', 'phóng đãng'),
    (r'(?<!\w)ch\*\\s+đ\*(?!\w)', 'chó đẻ'),
    (r'(?<!\w)đ\*\s+h\*{1,2}\s+s\*c(?!\w)', 'đại háo sắc'),
    (r'(?<!\w)s\*x\*(?!\w)', 'sexy'),
    (r'(?<!\w)j\*v(?!\w)', 'JAV'),
    (r'(?<!\w)fuc\*|f\*\*ck|fu\*k(?!\w)', 'fuck'),

    # Dọn dẹp dòng rác dấu sao
    (r'^\s*\*+\s*$', ''),
    (r'^\*+([a-zA-ZÀ-ỹ])', r'Chú thích: \1'),
    (r'(\(\*\)|\*chương này có nội dung ảnh[^\n]*)', ''),
]

def uncensor_text(text: str) -> str:
    """Hàm lõi: Phục hồi toàn bộ từ khóa bị che trong chuỗi văn bản."""
    cleaned = text
    for pattern, replacement in UNCENSOR_RULES:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE | re.MULTILINE)
    return cleaned

def clean_file(filepath: str) -> tuple:
    """Làm sạch 1 file txt. Trả về: (modified, asterisks_removed)"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        before_cnt = content.count('*')
        if before_cnt == 0:
            return False, 0
            
        cleaned = uncensor_text(content)
        after_cnt = cleaned.count('*')
        
        if cleaned != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(cleaned)
            return True, (before_cnt - after_cnt)
    except Exception as e:
        print(f"Lỗi khi xử lý {filepath}: {e}")
        
    return False, 0

def clean_folder(folder_path: str):
    """Quét và làm sạch toàn bộ các file Chuong_*.txt trong thư mục."""
    if not os.path.exists(folder_path):
        print(f"❌ Thư mục không tồn tại: {folder_path}")
        return
        
    files = sorted(glob.glob(os.path.join(folder_path, "Chuong_*.txt")))
    if not files:
        print(f"⚠️ Không tìm thấy file Chuong_*.txt nào trong: {folder_path}")
        return
        
    print(f"\n📁 Đang quét thư mục: {folder_path}")
    print(f"📊 Tìm thấy {len(files)} chương. Bắt đầu làm sạch từ khóa bị che...")
    
    modified_files = 0
    total_stars_removed = 0
    
    for f in tqdm(files, desc="Đang phục hồi từ bị che", unit="ch"):
        mod, removed = clean_file(f)
        if mod:
            modified_files += 1
            total_stars_removed += removed
            
    print("\n" + "=" * 60)
    print(f"🎉 HOÀN TẤT LÀM SẠCH VĂN BẢN!")
    print(f"✅ Số chương đã sửa: {modified_files} / {len(files)} chương")
    print(f"✨ Số ký tự dấu sao (*) đã được giải mã: {total_stars_removed} ký tự")
    print(f"🔊 Văn bản đã sẵn sàng cho giọng đọc AI chuẩn mượt mà 100%!")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tool tự động phục hồi từ bị che (*) cho truyện chữ để đọc AI")
    parser.add_argument("--path", type=str, default=None, help="Đường dẫn thư mục hoặc file cần làm sạch")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "output")
    
    if args.path:
        target = args.path
        if os.path.isfile(target):
            clean_file(target)
            print(f"✅ Đã làm sạch file: {target}")
        else:
            clean_folder(target)
    else:
        # Tự động quét tất cả các thư mục truyện trong output
        subdirs = [os.path.join(output_dir, d) for d in os.listdir(output_dir) if os.path.isdir(os.path.join(output_dir, d))]
        if not subdirs:
            print(f"Chưa có thư mục truyện nào trong {output_dir}")
        for s in subdirs:
            clean_folder(s)
