# ITM AutoClicker 🖱️🤖

Ứng dụng **Auto Clicker** tiên tiến cho phép tự động hóa các thao tác click chuột mà không chiếm đụng chuột. Ứng dụng hỗ trợ hai chế độ recording: click theo vị trí và click theo hình ảnh.

## ✨ Tính Năng Chính

### 1. **Click Theo Vị Trí**
- Di chuyển chuột đến vị trí cần click
- Ấn **PAGE UP** để ghi nhớ vị trí
- Lặp lại cho nhiều vị trí
- Ấn **ESC** để hoàn thành

### 2. **Click Theo Hình Ảnh**  
- Kéo chuột để chọn vùng hình ảnh trên màn hình
- Chương trình sẽ chụp lại khu vực đó
- Xác nhận vị trí click
- Lặp lại cho ảnh tiếp theo

### 3. **Thực Thi Kịch Bản**
- Ấn nút **Start** hoặc phím **END** để bắt đầu
- Chương trình tự động click lần lượt theo kịch bản
- Kịch bản lặp lại liên tục
- Ấn **Stop** hoặc **END** để dừng

## 🚀 Cài Đặt Nhanh

```bash
# Clone project
git clone https://github.com/quockhanh112hubt/ITM_AutoClicker.git
cd ITM_AutoClicker

# Tạo virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows

# Cài đặt dependencies
pip install -r requirements.txt

# Chạy ứng dụng
python main.py
```

## 📁 Cấu Trúc Project

```
ITM_AutoClicker/
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── src/
│   ├── main_window.py      # GUI chính
│   ├── click_script.py     # Quản lý kịch bản
│   ├── keyboard_listener.py # Lắng nghe phím
│   ├── auto_clicker.py     # Engine thực thi
│   ├── image_matcher.py    # Template matching
│   ├── region_selector.py  # Chọn vùng
│   └── config.py           # Cấu hình
├── scripts/                # Lưu kịch bản & ảnh
└── config/                 # Cài đặt app
```

## ⌨️ Phím Tắt Toàn Cục

| Phím | Chức Năng |
|------|-----------|
| **PAGE UP** | Ghi vị trí / Xác nhận click |
| **ESC** | Thoát chế độ recording |
| **END** | Bắt đầu/Dừng thực thi |

## 📚 Hướng Dẫn Chi Tiết

### Chế Độ Position-Based (Vị Trí)

1. Nhấp **Add Action** → **Position Based Click**
2. Di chuyển chuột đến vị trí mong muốn
3. Ấn **PAGE UP** để ghi
4. Lặp lại cho các vị trí khác
5. Ấn **ESC** để hoàn thành

### Chế Độ Image-Based (Hình Ảnh)

1. Nhấp **Add Action** → **Image Based Click**
2. **Kéo chuột** để chọn vùng chụp ảnh
3. **Thả chuột** → Ảnh được lưu
4. Di chuyển chuột đến vị trí click
5. Ấn **PAGE UP** để xác nhận
6. Chọn **Yes** để tiếp tục hoặc **No** để hoàn thành

## ⚙️ Cài Đặt

Trong tab **Settings**:
- **Click Delay (ms)**: Độ trễ giữa các click
- **Image Confidence**: Độ tin cậy template matching

File cấu hình: `config/settings.json`

## 🎮 Sử Dụng

1. **Tạo kịch bản** bằng cách thêm các action
2. **Nhấp Start** hoặc ấn **END** để chạy
3. **Nhấp Stop** hoặc ấn **END** để dừng
4. **Save Script** để lưu kịch bản
5. **Load Script** để tải lại sau này

## 🐛 Xử Lý Lỗi

| Lỗi | Giải Pháp |
|-----|----------|
| Click không hoạt động | Chạy as Administrator |
| Template không tìm | Tăng delay, kiểm tra ảnh rõ |
| Phím không hoạt động | Khởi động lại app |

## 📋 Yêu Cầu Hệ Thống

- Python 3.8+
- Windows 7+ / macOS 10.12+ / Linux
- RAM: 512 MB+
- Lưu trữ: 100 MB

## 🔮 Tính Năng Sắp Tới

- [ ] Click chuột phải/con lăn
- [ ] Ghi video thao tác
- [ ] Xử lý lỗi tự động
- [ ] Giao diện English
- [ ] Plugin system

## 📝 Giấy Phép

MIT License

## 👤 Tác Giả

**GitHub**: [@quockhanh112hubt](https://github.com/quockhanh112hubt)

---

⚠️ **Lưu Ý**: Chỉ sử dụng cho mục đích cá nhân/học tập. Đảm bảo có quyền tự động hóa trên ứng dụng mà bạn sử dụng.