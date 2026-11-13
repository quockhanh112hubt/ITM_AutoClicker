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

### Thử click nền với client game

Trong **Settings → Runtime**, tắt **Use real mouse for all actions** rồi bật
**Background mouse compatibility (experimental)**. Chế độ thử nghiệm này áp dụng
cho thao tác chuột của Position, Image Based và Image Direct: gửi thông điệp có
giới hạn chờ, nghỉ 30 ms sau khi di chuyển và giữ click 50 ms để client có thời gian
xử lý. Mouse Hold vẫn dùng thời gian giữ đã cấu hình. Không di chuyển con trỏ thật
hoặc kích hoạt cửa sổ đích trong đường xử lý này.

Để thử kéo thả nền, chọn **Background only** hoặc **Hybrid** ở Drag Mode. Khi bật
chế độ tương thích, Hybrid sẽ báo lỗi nếu gửi kéo thả nền thất bại, không tự đổi
sang kéo bằng chuột thật. **Real drag** vẫn là chế độ dùng chuột thật được chọn rõ ràng.
Các action bàn phím vẫn có thể đưa cửa sổ đích lên trước như trước đây.

Hãy thử một action trên nút mở menu không mua vật phẩm, với con trỏ thật đặt ngoài
game. Count tăng chỉ thể hiện việc gửi lệnh, cần quan sát menu thực sự mở để xác nhận.
Chế độ này không bảo đảm hỗ trợ game dùng Raw Input hoặc bỏ qua thông điệp chuột.
Trình duyệt/Office có thể tiếp tục dùng chế độ mặc định (tắt tùy chọn thử nghiệm).

## Bản thử nghiệm nhận diện client và profile Unity

Mở `dist/ITM_AutoClicker_Unity_Profiles_Test.exe` hoặc chạy mã nguồn mới bằng
`.\.venv\Scripts\python.exe main.py`, sau đó:

1. Chọn target trong **Main**; tab **Unity Clients** tự nhận diện phiên bản Unity,
   x64/x86, IL2CPP/Mono và dấu hiệu Legacy/New Input System.
2. Giữ **Compatibility profile = Auto detect**. MongThienKiem đúng bản đã kiểm tra
   dùng profile `verified`. Client khác phù hợp nhóm IL2CPP x64 + Legacy Input/uGUI
   sẽ có profile `experimental`; bật **Allow experimental Unity profiles** để thử.
3. Trong **Settings → Runtime**, tắt **Use real mouse** và bật
   **Unity virtual mouse — compatibility profiles**.
4. Tạo một action Position/Image Based/Image Direct trên nút mở menu, đặt **Limit = 1**.
   Đặt chuột ngoài game, chuyển sang ứng dụng khác rồi dùng Home để chạy, End để dừng.
5. Sau khi quan sát thao tác thành công, dùng **Mark client as tested** để lưu
   profile `user-tested` cho đúng bản client. **Export detection report** xuất báo cáo JSON khi cần phân tích.

Các profile tổng quát hiện bao phủ nhóm Unity 2019–2023 và Unity 6 (`6000.x`),
vẫn cần kiểm thử trên từng game. Mono, x86 và New Input System-only được nhận diện
nhưng chưa có backend chuột ảo. Không hỗ trợ bàn phím, Full Screen hay game minimize.

Nếu đã dùng bản test MongThienKiem trước đó, **thoát và mở lại game một lần** trước
khi dùng helper profile mới. Stop tắt đầu vào ảo; DLL không hoạt động vẫn ở trong
game tới khi game thoát. Không sửa file game trên đĩa.

Xem [hướng dẫn profile và giới hạn](docs/unity_client_profiles.md) hoặc
[tài liệu build/kiểm tra native](native/unity_bridge/README.md).

## Cập nhật (Update)

Trong tab **About**, bấm **Check for Update**. Nếu có bản mới, chương trình sẽ tải về và tự cập nhật.

## Yêu cầu hệ thống

- Windows 10/11
- Không cần cài thêm khi dùng file `.exe` đã build

---

Nếu cần hỗ trợ hoặc báo lỗi, vui lòng gửi kèm ảnh/chụp màn hình để mô tả rõ vấn đề.
