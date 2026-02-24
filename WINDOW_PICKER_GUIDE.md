# Window Picker - Image Recording Enhancement

## Tổng Quan

Thay đổi từ **Region Selector Overlay (toàn màn hình)** sang **Window Picker + Window Region Selector (trong cửa sổ cụ thể)**.

## Tại Sao Thay Đổi Này?

### Lợi Ích:
1. **Chọn cửa sổ mục tiêu trước** - Người dùng biết chính xác sẽ capture từ cửa sổ nào
2. **Tập trung vào 1 cửa sổ** - Region selector chỉ hoạt động trong cửa sổ đã chọn
3. **Dễ phát triển** - Cơ sở hạ tầng sẵn sàng cho chức năng không chiếm chuột sau
4. **Trực quan hơn** - Người dùng chọn cửa sổ trước, sau đó chọn vùng

## Luồng Công Việc Mới

```
┌─────────────────────────────────────────────┐
│ Người dùng: Click "Add Action"              │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────┐
│ Chọn "Image Based Click"                    │
└────────────────────┬────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ WindowPickerDialog xuất hiện                        │
│ ┌──────────────────────────────────────────────┐   │
│ │ Select a window to capture images from:      │   │
│ ├──────────────────────────────────────────────┤   │
│ │ [Window List]                                │   │
│ │ - Notepad (Edit)                            │   │
│ │ - Chrome (Chrome_WidgetWin_1)               │   │
│ │ - VS Code (vsCodeMainWindow)                │   │
│ │ - ...                                        │   │
│ ├──────────────────────────────────────────────┤   │
│ │ [Refresh] [OK] [Cancel]                      │   │
│ └──────────────────────────────────────────────┘   │
└────────────────────┬────────────────────────────────┘
                     │
         ┌───────────┴─────────────┐
         │ (User chọn cửa sổ)      │
         │ (Double-click hoặc      │
         │  Click OK)              │
         │                         │
┌────────▼─────────────────────────────────────┐
│ WindowRegionSelector xuất hiện trong cửa sổ │
│                                              │
│ ┌──────────────────────────────────────────┐│
│ │ [Cửa sổ đã chọn - VD: Notepad]          ││
│ │                                          ││
│ │  (Người dùng kéo chuột để chọn vùng)    ││
│ │                                          ││
│ │  ┌──────────────────────┐                ││
│ │  │ 200 x 150           │ ← Hiển thị kích │
│ │  │                      │   thước         │
│ │  └──────────────────────┘                ││
│ │                                          ││
│ └──────────────────────────────────────────┘│
└────────┬─────────────────────────────────────┘
         │
┌────────▼─────────────────────────────────────┐
│ Image captured → Preview Dialog              │
│ (giống như trước)                           │
└────────┬─────────────────────────────────────┘
         │
    ┌────┴────┐
    │ OK/Cancel│
    └────┬────┘
         │
┌────────▼──────────────────────────────────────┐
│ Click Position Dialog (giống như trước)      │
└────────┬──────────────────────────────────────┘
         │
    ┌────┴──────────────────┐
    │ Continue Recording?   │
    ├──────────────────────┤
    │ Yes → Lặp lại        │
    │ No  → Kết thúc       │
    └──────────────────────┘
```

## File Mới Tạo

### 1. `src/window_picker.py` (210 dòng)
- **Window class**: Đại diện cho một cửa sổ
  - `get_rect()` - Lấy vị trí cửa sổ
  - `is_visible()` - Kiểm tra cửa sổ có hiển thị không
  - `get_display_name()` - Tên hiển thị

- **WindowPicker class**: Lấy danh sách cửa sổ
  - `get_windows()` - Lấy tất cả cửa sổ hiển thị

- **WindowPickerDialog class** (PyQt6): Dialog chọn cửa sổ
  - Hiển thị danh sách cửa sổ
  - Người dùng double-click hoặc click OK để chọn
  - Signal: `window_selected`

### 2. `src/window_region_selector.py` (140 dòng)
- **WindowRegionSelector class** (PyQt6): Chọn vùng trong cửa sổ
  - Overlay trên cửa sổ đã chọn (không phải toàn màn hình)
  - Vẽ hình chữ nhật chọn với kích thước
  - Hỗ trợ ESC để hủy
  - Signal: `region_selected(x1, y1, x2, y2)`

## File Cập Nhật

### 1. `src/image_recording_manager.py`
**Thay đổi chính:**

```python
# CŨ: Bắt đầu trực tiếp với region selector
def start(self):
    self.is_recording = True
    self._start_next_image()
    self._show_region_selector()  # Toàn màn hình

# MỚI: Bắt đầu với window picker
def start(self):
    self.is_recording = True
    self._show_window_picker()    # Chọn cửa sổ trước

def _show_window_picker(self):
    """Hiển thị dialog chọn cửa sổ"""
    dialog = WindowPickerDialog()
    if dialog.exec():
        self.target_window = dialog.get_selected_window()
        if self.target_window:
            self._start_next_image()
```

**Ưu điểm:**
- Lưu `target_window` để dùng cho các hình ảnh tiếp theo
- Region selector giới hạn trong cửa sổ đã chọn
- Dễ mở rộng cho chức năng khác sau này

### 2. `requirements.txt`
**Thêm:**
```
pywin32  # Để truy cập Windows API (win32gui, etc.)
```

## Chi Tiết Kỹ Thuật

### Window API (pywin32)
```python
import win32gui

# Lấy tất cả cửa sổ
win32gui.EnumWindows(callback, param)

# Lấy tên cửa sổ
title = win32gui.GetWindowText(hwnd)

# Lấy class cửa sổ
class_name = win32gui.GetClassName(hwnd)

# Lấy vị trí cửa sổ
rect = win32gui.GetWindowRect(hwnd)  # (left, top, right, bottom)

# Kiểm tra cửa sổ hiển thị
is_visible = win32gui.IsWindowVisible(hwnd)
```

### Điều Chỉnh Tọa Độ
```python
# Tọa độ cục bộ trong cửa sổ (0-based)
local_x, local_y = event.pos()

# Chuyển sang tọa độ toàn cầu (cho ImageMatcher.capture_region)
global_x = window_x + local_x
global_y = window_y + local_y
```

## Luồng Dữ Liệu

```
User chọn cửa sổ
    ↓
WindowPickerDialog.window_selected signal
    ↓
ImageRecordingManager._show_window_picker()
    ↓
Lưu: self.target_window = Window
    ↓
Gọi: _start_next_image()
    ↓
Hiển thị: WindowRegionSelector(target_window.hwnd)
    ↓
User kéo chuột trong cửa sổ
    ↓
WindowRegionSelector.region_selected(x1, y1, x2, y2)
    ↓
Capture region từ toàn màn hình (tọa độ global)
    ↓
Hiển thị: ImageConfirmationDialog
    ↓
... (giống như trước)
```

## Kiểm Tra

### Import Test
```bash
python -c "from src.window_picker import WindowPickerDialog; print('OK')"
python -c "from src.window_region_selector import WindowRegionSelector; print('OK')"
python -c "from src.image_recording_manager import ImageRecordingManager; print('OK')"
```

### Chạy Ứng Dụng
```bash
python main.py
```

**Các bước kiểm tra:**
1. Click "Add Action" → "Image Based Click"
2. ✓ WindowPickerDialog hiện lên
3. ✓ Danh sách cửa sổ hiển thị
4. ✓ Chọn cửa sổ (double-click hoặc click OK)
5. ✓ WindowRegionSelector xuất hiện **TRONG cửa sổ đó** (không phải toàn màn hình)
6. ✓ Kéo chuột để chọn vùng
7. ✓ ImageConfirmationDialog hiển thị preview
8. ✓ Tiếp tục như trước

## Lợi Ích Dài Hạn

### 1. Không Chiếm Chuột (Planned)
```python
# Sau này, có thể thêm chế độ:
# "Capture from window without freezing mouse"
# - Window ở foreground, ta vẫn có thể di chuột
# - Ghi lại click positions tự động
```

### 2. Hỗ Trợ Nhiều Ứng Dụng
```python
# Có thể capture từ:
# - Chrome window
# - VS Code window
# - Notepad window
# - Custom applications
# - Game windows
```

### 3. Organized Workflow
```python
# Cấu trúc sẵn sàng cho:
# - Window-specific scripts
# - Multi-window automation
# - Application switching automation
```

## Khả Năng Mở Rộng

### A. Không Chiếm Chuột
```python
# ImageRecordingManager có thể extended:
class NonBlockingImageRecorder(ImageRecordingManager):
    def record_without_blocking(self):
        # Ghi vùng từ window mà không block
        # Ghi lại chuột movements
        # Ghi lại click positions
        pass
```

### B. Template Matching
```python
# Có thể search ảnh trong window cụ thể:
ImageMatcher.find_image_in_window(
    template_image,
    window_hwnd,
    confidence=0.8
)
```

### C. Multi-Window Scripts
```python
# Script có thể target cửa sổ khác nhau:
script = [
    ImageAction(window="Notepad", image="button.png"),
    ImageAction(window="Chrome", image="link.png"),
    ImageAction(window="Excel", image="cell.png")
]
```

## Compatibility

- ✅ Windows 10/11
- ✅ Python 3.13
- ✅ PyQt6 6.7.0
- ✅ pywin32 (mới thêm)
- ✅ Tất cả phần khác unchanged

## Dependencies Mới

```
pywin32  # Windows API access
         # Cho: win32gui.EnumWindows, GetWindowRect, etc.
```

**Cài đặt:**
```bash
pip install pywin32
```

**Đã cập nhật:** `requirements.txt`

## Status

✅ **COMPLETE** - Sẵn sàng để test

### Files
- ✅ `src/window_picker.py` - Tạo mới
- ✅ `src/window_region_selector.py` - Tạo mới  
- ✅ `src/image_recording_manager.py` - Cập nhật
- ✅ `requirements.txt` - Thêm pywin32

### Testing
- ✅ Import tests - Tất cả PASSED
- ✅ Syntax validation - Tất cả PASSED
- ⏳ Manual testing - Chờ user feedback

---

## Tóm Tắt Thay Đổi

| Aspect | Cũ | Mới |
|--------|-----|-----|
| Bước đầu tiên | Region selector (toàn màn) | Window picker dialog |
| Chọn vùng | Bất kỳ nơi nào trên màn | Chỉ trong cửa sơ đã chọn |
| Giao diện | Overlay trực tiếp | Dialog → Overlay |
| Mục tiêu | Mặc định là toàn màn hình | Cửa sổ cụ thể |
| Mở rộng | Khó | Dễ (có target window) |
| UX | Trực tiếp | Tập trung hơn |
