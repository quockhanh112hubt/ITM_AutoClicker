# ITM AutoClicker

Ứng dụng tự động hóa thao tác trên **cửa sổ mục tiêu** (target window) bằng click chuột, kéo thả, phím tắt và OCR.

## Tính năng chính

- **Click theo vị trí** (Position Based).
- **Click theo hình ảnh**:
  - **Image Based**: phát hiện ảnh rồi click tại vị trí đã ghi.
  - **Image Direct**: phát hiện ảnh rồi click trực tiếp vào ảnh.
- **Image Recognition (OCR)**: quét vùng ảnh và đọc chữ/số, cập nhật giá trị vào Details.
- **Record screen action**: ghi thao tác chuột/phím trên màn hình và phát lại.
- **Advanced actions** (toolbar kéo‑thả):
  - Left/Right/Middle Click
  - Scroll Up/Down
  - Mouse Hold Left/Right
  - Drag & Drop
  - Key Press
  - Hotkey
  - Key Hold
- **IF / IF NOT** dựa trên ảnh hoặc OCR để điều khiển luồng (chạy Branch/Action hoặc Stop).
- **Branch & Action**: quản lý theo cây, kéo‑thả sắp xếp, chọn chạy theo nhánh.
- **Không chiếm chuột** (background click) hoặc **dùng chuột thật** (tùy chọn trong Settings).
- **Always on top** (tùy chọn).
- **Update tự động** qua GitHub Releases.
- **Floating panel** nhỏ khi chạy để không che màn hình (Start/Stop).

## Cách dùng nhanh

1. **Chọn Target Window** ở góc trên (Select Target).
2. **Tạo Action** bằng các nút trên thanh công cụ:
   - Record multi Action, Image Based, Image Direct, Image Recognition, Record screen action.
   - Hoặc dùng thanh toolbar kéo‑thả để tạo action nhanh (chuột/phím/drag/scroll...).
3. **Chọn/đổi Branch** nếu cần (Click Script List).
4. **Start** để chạy, **Stop** để dừng.
5. **Save Script** để lưu, **Load Script** để dùng lại.

## Phím tắt (có thể đổi trong Settings)

- **Record Confirm**: mặc định `Page Up`
- **Record Action Menu**: mặc định `Page Down`
- **Start / Pause / Resume**: mặc định `Home`
- **Stop**: mặc định `End`
- **Record Screen Toggle**: mặc định `F10`

## Image Recognition (OCR)

- Chọn **Image Recognition** → khoanh vùng cần đọc → lưu action.
- Khi chạy, chương trình sẽ cập nhật **giá trị OCR** vào cột Details.
- Có thể dùng giá trị này trong **IF** để điều khiển luồng.

## Ghi chú sử dụng

- Nếu target window bị đóng/minimize/che quá nhiều, một số thao tác có thể không chính xác.
- Với Drag & Drop, chế độ **Real drag** sẽ chiếm chuột (đúng thao tác nhất).
- Với chế độ **background click**, một số ứng dụng có thể không hỗ trợ đầy đủ.

## Cập nhật (Update)

Trong tab **About**, bấm **Check for Update**. Nếu có bản mới, chương trình sẽ tải về và tự cập nhật.

## Yêu cầu hệ thống

- Windows 10/11
- Không cần cài thêm khi dùng file `.exe` đã build

---

Nếu cần hỗ trợ hoặc báo lỗi, vui lòng gửi kèm ảnh/chụp màn hình để mô tả rõ vấn đề.
