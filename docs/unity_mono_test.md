# Chạy thử Unity Mono từ source

Bản này bổ sung backend `mono-legacy-ugui` cho Unity Mono x64 / Legacy Input / uGUI.
Chưa đóng gói EXE. DLL hỗ trợ `resource/unity_bridge/itm_unity_mono_v1.dll` đã được
biên dịch để `main.py` sử dụng trực tiếp.

## Run and Debug

1. Dừng phiên ITM cũ để tránh trùng hotkey hoặc hai chương trình cùng điều khiển game.
2. Trong VS Code, mở Run and Debug, chọn **ITM AutoClicker - Run and Debug**, nhấn F5.
   Cấu hình `.vscode/launch.json` dùng `.venv/Scripts/python.exe`, chạy `main.py`
   với thư mục làm việc là repository.
3. Chọn target **Vạn Thắng Nam Đế**. Trong **Unity Clients**, chọn **Auto detect**,
   bật **Allow experimental Unity profiles**. Kết quả dự kiến là Mono, x64,
   Unity 6000.4.7f1 và profile **Unity 6 / Mono / Legacy UI (mouse + keys)**.
4. Trong Settings → Runtime, tắt **Use real mouse**, bật
   **Unity virtual mouse — compatibility profiles**. Chỉ bật Background mouse
   compatibility sẽ vẫn dùng thông điệp Windows thông thường.
5. Giữ game mở, không minimize. Tạo Image Direct nhận diện avatar góc trên bên trái,
   Limit = 1. Đặt chuột ra ngoài game, chuyển sang ứng dụng khác rồi nhấn Home.
   Bảng **Hồ Sơ Thủ Lĩnh** phải mở dù con trỏ thật không nằm trên avatar.
6. Thử riêng action bàn phím **Esc**, Limit = 1: bảng hồ sơ phải đóng. Dùng End để
   dừng. Có thể thử giữ phím hoặc hotkey nếu game có chức năng tương ứng.

Có thể chạy từ terminal bằng:

```powershell
.\.venv\Scripts\python.exe main.py
```

Không cần build lại DLL khi chỉ sửa Python. Khi sửa native, dừng ITM và thoát game
trước khi thay DLL, rồi chạy:

```powershell
.\.venv\Scripts\python.exe tools/build_unity_bridge.py --backend mono
```

Nếu gặp `stage -6, code 0` từ bản DLL cũ, thoát hẳn game rồi mở lại trước khi thử
bản sửa. Một phiên Vạn Thắng Nam Đế đã tái hiện lỗi cấp phát trampoline cho
`EventSystem.Update`: vùng JIT không còn chỗ phù hợp trong tầm nhảy tương đối.
Bản sửa bổ sung nhảy tuyệt đối có kiểm tra prologue khi hết vùng cấp phát gần;
log mới ghi tên hàm và mã MinHook thật. Chỉ Stop/Start ITM không thay DLL đã nạp.

## Phạm vi

- Chuột: click trái/phải/giữa, giữ, kéo và cuộn qua Legacy Input.
- Mono bàn phím: nhấn, giữ lặp, giữ liên tục, tổ hợp phím qua `Input.GetKey(KeyCode)`,
  `GetKeyDown`, `GetKeyUp`. Dùng KeyCode của Unity, không dùng mã phím Windows.
- Stop/Pause/hủy thao tác nhả đầu vào ảo; mất heartbeat cũng tự nhả. Không tự chuyển
  sang SendInput, không di chuyển con trỏ thật và không kích hoạt cửa sổ game.
- Chưa hỗ trợ nhập văn bản/IME, `GetKey(string)`, `GetAxis`, cấu hình Input Manager
  riêng, New Input System, client x86/ARM, target Full Screen hoặc game minimize.
- Bàn phím IL2CPP vẫn chưa được bổ sung. Các profile Mono luôn là experimental
  cho đến khi người dùng xác nhận bản game cụ thể; không bảo đảm mọi game Mono.

## Kết quả đã kiểm tra

Trên client Vạn Thắng Nam Đế đang mở, Unity 6000.4.7f1 / Mono / Legacy Input:

- Kết nối, ngắt và kết nối lại được với helper.
- Click avatar mở đúng Hồ Sơ Thủ Lĩnh, sau đó Esc ảo đóng được bảng.
- Thử lại qua đường thực thi **Image Direct** và action bàn phím của `AutoClicker`
  cũng thành công, không chỉ qua công cụ gọi helper.
- Game nằm ở màn hình có tọa độ âm. Client và render đều 1440 × 810; con trỏ thật
  ở `(1646, 600)`, ngoài game. Vị trí con trỏ và HWND foreground không đổi trong
  các lần thao tác. Ảnh kiểm tra nằm trong `build/mono_probe/`.

Fixture Mono riêng kiểm tra client 960 × 540 với render 1280 × 720, chuyển tọa độ,
trạng thái down/up, giữ liên tục, giữ lặp, hotkey, nhả khi mất heartbeat và reconnect.
Fixture khác từ chối New Input System và field sai trước khi nhấn chuột/phím.
Đây là runtime tổng hợp, không phải bằng chứng đã kiểm tra các game Mono khác.

API tham khảo: [Mono embedding](https://www.mono-project.com/docs/advanced/embedding/)
và [Unity Legacy Input bindings](https://github.com/Unity-Technologies/UnityCsReference/blob/master/Modules/InputLegacy/Input.bindings.cs).
