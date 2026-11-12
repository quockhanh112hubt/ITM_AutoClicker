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

## Bản thử nghiệm chuột ảo Unity — MongThienKiem

Đã có helper x64 biên dịch sẵn tại `resource/unity_bridge/itm_unity_bridge.dll`.
Mở `dist/ITM_AutoClicker_Unity_Test.exe` hoặc chạy bản mã nguồn mới bằng
`.\.venv\Scripts\python.exe main.py`, sau đó:

1. Chọn target **MongThienKiem**, giữ cửa sổ game mở bình thường.
2. Trong **Settings → Runtime**, tắt **Use real mouse** và bật
   **Unity virtual mouse — MongThienKiem (experimental)**.
3. Tạo một action Position/Image Based/Image Direct trên nút mở menu, đặt **Limit = 1**.
4. Đặt chuột ngoài game, làm việc ở ứng dụng khác rồi dùng phím Home để chạy.
5. Dùng End/Stop để dừng. Tùy chọn Unity ghi đè Drag Mode bằng kéo thả ảo.

Chế độ này nạp DLL vào tiến trình game được chọn và thay đường đọc Input lúc chạy.
Stop/ngắt kết nối tắt đầu vào ảo; helper không hoạt động vẫn ở trong game tới khi
game thoát. Không sửa file game trên đĩa. Chỉ đúng bản MongThienKiem đã khảo sát
được chấp nhận; bản khác sẽ báo lỗi. Không hỗ trợ action bàn phím, Full Screen hoặc
cửa sổ game minimize. Tùy chọn Background mouse compatibility là một chế độ khác,
được bỏ qua khi dùng chuột ảo Unity.

Đã thử Image Direct mở menu **Thành tựu** khi chuột ở ngoài game và foreground
giữ nguyên ở ứng dụng khác. Chưa xác nhận mọi màn hình/action của game.
Xem [tài liệu build, kiểm tra và giới hạn](native/unity_bridge/README.md).

## Cập nhật (Update)

Trong tab **About**, bấm **Check for Update**. Nếu có bản mới, chương trình sẽ tải về và tự cập nhật.

## Yêu cầu hệ thống

- Windows 10/11
- Không cần cài thêm khi dùng file `.exe` đã build

---

Nếu cần hỗ trợ hoặc báo lỗi, vui lòng gửi kèm ảnh/chụp màn hình để mô tả rõ vấn đề.
