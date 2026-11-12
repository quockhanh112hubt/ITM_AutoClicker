# Khảo sát đầu vào MongThienKiem và khả năng điều khiển không chiếm chuột

Ngày khảo sát: 2026-11-13 (UTC+7).

> Cập nhật sau khảo sát: đã triển khai và thử thành công nguyên mẫu, xem phần
> “Kết quả nguyên mẫu” cuối tài liệu. Các phần “chưa thực hiện” bên dưới ghi lại
> trạng thái tại thời điểm khảo sát ban đầu.

## Kết luận

Có cơ sở kỹ thuật để thử một bộ điều khiển dành riêng cho client này: cấp vị trí
và trạng thái chuột ảo cho lớp Input của Unity bên trong tiến trình game. Đây là
đánh giá tính khả thi, chưa có nguyên mẫu chạy trong game và chưa chứng minh thành công.

Chỉ gửi WM_MOUSEMOVE/WM_LBUTTONDOWN/WM_LBUTTONUP từ Python chưa giải quyết được
việc game đọc Input.mousePosition và kiểm tra focus. Không thể coi việc gửi lệnh
thành công là bằng chứng UI/gameplay đã nhận thao tác.

Khảo sát chỉ đọc tên cửa sổ, danh sách module, thông tin PE, file cấu hình build
và mã C++ được đóng kèm client. Không ghi vào bộ nhớ tiến trình, không sửa file game,
không nạp DLL vào game và không gửi click trong lần khảo sát này.

## Mẫu client đã kiểm tra

| Thuộc tính | Bằng chứng |
| --- | --- |
| Thư mục bản phát hành | `MTK_113_1211` |
| Tiến trình/cửa sổ | `MongThienKiem.exe`, lớp `UnityWndClass` |
| Kiến trúc | PE machine `0x8664` (x64) trên EXE, UnityPlayer.dll và GameAssembly.dll |
| Unity | `6000.3.25f1 (e1dba0a9aba4)` trong ProductVersion của UnityPlayer.dll; header globalgamemanagers cũng ghi `6000.3.25f1` |
| Scripting backend | GameAssembly.dll đang nạp, kèm il2cpp_data/Metadata/global-metadata.dat và mã IL2CPP sinh ra |
| Assembly đầu vào | ScriptingAssemblies.json có UnityEngine.InputLegacyModule.dll, UnityEngine.InputModule.dll, UnityEngine.InputForUIModule.dll |
| New Input System | Không thấy Unity.InputSystem.dll trong danh sách assembly hoặc thư mục Managed đã kiểm tra |
| Thông tin build kèm theo | Có thư mục `MongThienKiem_BackUpThisFolder_ButDontShipItWithYourGame`, gồm Managed, il2cppOutput và GameAssembly.pdb |

Không diễn giải việc có DLL/API trong client thành bằng chứng API đó đang được gọi
ở thời điểm chạy. Mã IL2CPP đóng kèm cung cấp bằng chứng tĩnh về đường xử lý có trong
bản build; chưa quan sát đối tượng InputModule đang hoạt động của scene hiện tại.

Fingerprint SHA-256 của các file đã kiểm tra:

```text
UnityPlayer.dll  3fc09d493e387c33b2c0df29d9ec75803158a3a98ad885917b1039d13bfc6c6d
GameAssembly.dll 802f3a21bd70ca083b4f1cc748acc6a2c8c32cece75ce38c9ab656a27694cc2d
```

## Bằng chứng về đường đọc chuột

Các tên file và số dòng dưới đây thuộc thư mục `il2cppOutput` của thư mục backup
đóng kèm client. Không sao chép mã nguồn của game vào repository ITM_AutoClicker.

| File và dòng | Nội dung đã kiểm tra | Ý nghĩa |
| --- | --- | --- |
| UnityEngine.InputLegacyModule.cpp:1520 | Wrapper GetMouseButtonDown gọi internal call của Unity | Trạng thái nhấn đi qua Unity Input |
| UnityEngine.InputLegacyModule.cpp:1531 | Wrapper GetMouseButtonUp gọi internal call của Unity | Trạng thái thả được đọc riêng |
| UnityEngine.InputLegacyModule.cpp:1932 | Wrapper get_mousePosition_Injected gọi internal call trả Vector3 | Có điểm trung gian dành cho vị trí chuột trong engine |
| UnityEngine.UI__3.cpp:18138 | BaseInput.GetMouseButtonDown đọc Unity Input | UI dùng trạng thái chuột theo frame |
| UnityEngine.UI__3.cpp:18171 | BaseInput.mousePosition đọc Input.mousePosition | Vị trí UI lấy từ Input, không trực tiếp từ LPARAM của lệnh click |
| UnityEngine.UI__3.cpp:18291 | BaseInputModule.input ưu tiên m_InputOverride khi được gán | Có điểm mở rộng đầu vào UI trong client |
| UnityEngine.UI__3.cpp:18446 | Có setter BaseInputModule.inputOverride | Có khả năng cấp bộ Input riêng cho UI nếu tích hợp được vào runtime |
| UnityEngine.UI__3.cpp:20318 | PointerInputModule lấy vị trí từ BaseInput để tạo dữ liệu pointer và raycast | Click UI phụ thuộc vị trí mà BaseInput cung cấp |
| UnityEngine.UI__3.cpp:21804 | ShouldIgnoreEventsOnNoFocus trả true | Có điều kiện bỏ qua đầu vào khi mất focus |
| UnityEngine.UI__3.cpp:22519 | StandaloneInputModule.Process kiểm tra EventSystem.isFocused trước khi xử lý | Chỉ cấp tọa độ ảo chưa chắc đủ để thao tác nền |
| Assembly-CSharp__20.cpp:10776 | MonoClickable.GetClickedObject lấy Input.mousePosition rồi tạo ray từ camera | Một số thao tác gameplay bỏ qua BaseInput của UI |
| Assembly-CSharp__32.cpp:11323 | BattleHero.Update có lời gọi GetMouseButtonDown | Có đường xử lý gameplay đọc Input trực tiếp |

`Injected` trong tên wrapper là cách Unity sinh lớp kết nối managed/native; nó
không có nghĩa là có phần mềm bên ngoài chèn mã vào game.

Unity xác định Input.mousePosition là thuộc tính chỉ đọc của Legacy Input,
có gốc tọa độ ở góc dưới trái của cửa sổ. Vì vậy một bộ điều khiển riêng cần
chuyển tọa độ client Windows (góc trên trái) sang tọa độ render Unity, tính đến
chiều cao, DPI và tỷ lệ render thực tế. Xem [tài liệu Input.mousePosition](https://docs.unity.com/en-us/engine/6000.3/script-reference/unityengine/input/mouseposition).

## Bằng chứng ở lớp Windows/native

Import table của UnityPlayer.dll có GetCursorPos, ScreenToClient, ClientToScreen,
GetAsyncKeyState, GetKeyState, RegisterRawInputDevices, GetRawInputData,
GetRawInputBuffer, GetPointerInfo, GetFocus, GetForegroundWindow và SetCursorPos.

Sự hiện diện đồng thời của API chuột truyền thống và Raw Input không đủ để kết
luận đường nào đang cấp tọa độ cho scene. Chưa có trace runtime xác nhận
get_mousePosition của Unity gọi GetCursorPos trong phiên đang chạy.

GameAssembly.dll còn export các API runtime như il2cpp_domain_get,
il2cpp_domain_get_assemblies, il2cpp_class_from_name,
il2cpp_class_get_method_from_name, il2cpp_runtime_invoke, il2cpp_resolve_icall,
il2cpp_thread_attach và il2cpp_thread_detach. Chỉ kiểm tra export table trên đĩa;
không gọi các hàm này trong tiến trình game. Export tồn tại không tự tạo ra API
điều khiển từ một tiến trình Python khác.

GetRegisteredRawInputDevices chỉ báo đăng ký của ứng dụng gọi nó. Gọi hàm đó từ
ITM_AutoClicker không xác nhận được cấu hình Raw Input của game khác. Xem
[tài liệu Microsoft](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-getregisteredrawinputdevices).

## Các phương án và phạm vi khả thi

| Phương án | Đánh giá cho client hiện tại | Hạn chế cần giải quyết |
| --- | --- | --- |
| Tiếp tục gửi thông điệp chuột Windows | Đã có cải thiện về nhận trạng thái nút theo phản hồi người dùng | Chưa tách được tọa độ khỏi con trỏ thật |
| Chỉ can thiệp GetCursorPos ở lớp Windows | Là giả thuyết cần trace, chưa phải giải pháp đã xác nhận | Unity có thể dùng bộ đệm/vị trí khác; vẫn còn kiểm tra focus và trạng thái nút |
| BaseInput/inputOverride cho uGUI | Có điểm mở rộng rõ trong mã đóng kèm | Phải có thành phần trong runtime game; không bao phủ MonoClickable/BattleHero đọc Input trực tiếp; còn focus gate |
| Bộ điều khiển ở lớp Unity Legacy Input | Hướng khảo sát tiếp được đề xuất cho phạm vi UI và gameplay rộng hơn | Cần thành phần native x64 trong game, đồng bộ frame, điều kiện focus và cách nạp tương thích với bản build |
| InputSystem.QueueStateEvent | Có API cho New Input System nhưng không phải lựa chọn hiện có của client này | Không thấy package Unity.InputSystem trong assembly list; API đó chạy bên trong Unity |
| Touch injection của Windows | Có thể thử riêng để kiểm tra thao tác không di chuyển con trỏ trong một số ứng dụng | Là đầu vào theo tọa độ desktop, không phải gửi riêng HWND nền; có thể đổi focus; chưa thử trên game |

Unity cung cấp BaseInput/inputOverride để thay nguồn đầu vào UI. Xem
[mã BaseInput của Unity](https://github.com/Unity-Technologies/uGUI/blob/main/com.unity.ugui/Runtime/UGUI/EventSystem/InputModules/BaseInput.cs)
và [BaseInputModule](https://github.com/Unity-Technologies/uGUI/blob/main/com.unity.ugui/Runtime/UGUI/EventSystem/InputModules/BaseInputModule.cs).
Điều kiện focus có thể đối chiếu với
[StandaloneInputModule](https://github.com/Unity-Technologies/uGUI/blob/main/com.unity.ugui/Runtime/UGUI/EventSystem/InputModules/StandaloneInputModule.cs).

Touch injection được Windows gửi vào desktop của session, không có tham số target HWND:
[InjectTouchInput](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-injecttouchinput).
New Input System xử lý sự kiện được xếp hàng trong vòng cập nhật của Unity:
[Input events](https://docs.unity3d.com/Packages/com.unity.inputsystem@1.7/manual/Events.html).

## Thiết kế thử nghiệm tiếp theo

Mục tiêu ban đầu là một thao tác mở menu, không phải triển khai toàn bộ action ngay.
Kiến trúc dự kiến:

```text
ITM_AutoClicker: nhận diện ảnh và tọa độ đích
    -> kênh IPC cục bộ có mã phiên/lệnh và xác nhận
    -> thành phần x64 trong client cụ thể
    -> trạng thái pointer ảo theo từng frame của Unity
    -> đường đọc Input/UI của game
```

Trình tự cần kiểm chứng:

1. Xác định InputModule thực tế trong scene và quan sát mousePosition, Down/Up,
   EventSystem.isFocused trong lúc thao tác. Chưa thực hiện bước quan sát runtime này.
2. Chứng minh có thể cấp một vị trí ảo cho game khi con trỏ thật đứng ngoài cửa sổ.
   Không gọi SetCursorPos, SendInput hoặc SetForegroundWindow trong thử nghiệm.
3. Cấp nhấn/thả ở các frame khác nhau; kiểm tra cả UI thông thường và một đường
   gameplay đọc Input trực tiếp. Không coi internal-call wrapper là bằng chứng đủ.
4. Kiểm tra game ở foreground và background tách biệt; nếu phải đưa game lên trước
   thì chưa đạt yêu cầu không làm gián đoạn công việc của người dùng.
5. Có hủy lệnh, heartbeat, thả mọi nút khi Stop/ngắt kết nối và khôi phục nguồn Input
   gốc khi thành phần thử nghiệm dừng. Không tự chuyển sang chuột thật khi lỗi.
6. Chỉ đưa backend vào ITM sau khi thử nghiệm đạt. Backend phải nhận diện đúng bản
   build và dừng nếu fingerprint không khớp, thay vì dùng địa chỉ cố định cho mọi game.

Cách nạp thành phần và khả năng hoạt động của nó trong client chưa được kiểm chứng.
Nếu có thể tích hợp từ project game, dùng plugin/component của game là đường triển
khai trực tiếp. Với bản IL2CPP đã build, cần nghiên cứu riêng việc tích hợp runtime;
không thể chỉ chép một script C# vào thư mục Managed rồi coi như game sẽ chạy nó.

Tiêu chí thành công: menu đúng mở khi con trỏ thật ở ngoài game, người dùng vẫn
làm việc ở ứng dụng khác, không đổi foreground, và Stop không để lại trạng thái
nhấn. Cần kiểm tra cả khi cửa sổ game di chuyển, đổi kích thước và ở màn hình phụ
có tọa độ âm. Minimize/che khuất là các tình huống kiểm tra riêng, không mặc định hỗ trợ.

## Giới hạn kết luận

Đã xác nhận cấu trúc bản build và đường xử lý có trong mã sinh ra. Chưa xác nhận
hàm native nào đang cung cấp vị trí chuột ở runtime, InputModule nào đang hoạt động,
hay khả năng cài bộ điều khiển riêng thành công. Không kết luận có anti-cheat hoặc
cơ chế bảo vệ nào chỉ từ hiện tượng không nhận click nền. Khảo sát này không thay đổi
mã thực thi của ITM_AutoClicker hoặc client game.

## Kết quả nguyên mẫu — 2026-11-13

Đã triển khai `src/unity_bridge.py` và helper x64 `native/unity_bridge/bridge.c`,
biên dịch sẵn tại `resource/unity_bridge/itm_unity_bridge.dll`. Người dùng bật rõ
ràng tùy chọn Unity virtual mouse trong Settings; Start mới kết nối/nạp helper.

Helper thay các native internal-call getter của Legacy Input cho vị trí, trạng
thái nút và scroll. EventSystem.Update được dùng để đồng bộ theo frame và tạm cấp
focus cho EventSystem trong quá trình xử lý; không thay foreground của Windows
trong backend. Khi tắt/ngắt kết nối, đầu vào ảo dừng và các hàm gọi qua nguồn Input
gốc. DLL không hoạt động vẫn nằm trong tiến trình đến khi game thoát.

Đã xác nhận trên client thực:

- Kết nối trong trạng thái idle: helper ready, EventSystem.Update tiếp tục chạy.
- Image Direct tìm ảnh nút Thành tựu và chuyển sang client `(62, 380)`.
- Menu Thành tựu thực sự mở sau một lần click ảo.
- Trong chính thao tác click: con trỏ giữ nguyên `(-774, 163)` ở ngoài cửa sổ game;
  foreground giữ nguyên HWND `262360`, khác HWND game `4589050`.
- Diagnostics sau thao tác ghi nhận position_reads=34, button_reads=109 và
  focus_overrides=11. Đây là các bộ đếm tích lũy trong helper, không phải số click.
- Không claim/mua vật phẩm, không gửi phím; thử nghiệm chỉ mở menu.

Thiết lập kiểm tra đã phải mở lại game vì cửa sổ bị minimize. Windows/game đã đưa
game lên trước khi mở lại; sau đó ứng dụng foreground trước đó được khôi phục trước
khi lấy mốc và gửi click. Bằng chứng foreground giữ nguyên phía trên áp dụng cho
thao tác click, không phải bước thiết lập cửa sổ. Backend vẫn không tự restore hoặc
activate game; minimize chưa được hỗ trợ.

Đã kiểm tra riêng bằng native fixture: DLL loading, hook thật, shared-memory IPC,
tọa độ, focus cục bộ, hai controller cạnh tranh, kết nối lại và tự thả nút khi
heartbeat hết hạn. Bộ kiểm tra Python còn xác nhận tắt fallback chuột thật, hủy
thao tác, chặn bàn phím/Full Screen và tọa độ ngoài client.

Giới hạn còn lại: chỉ fingerprint client trên; chưa xác nhận mọi scene, gameplay,
kéo thả, scroll, DPI/render scale và cấu hình nhiều màn hình trên game thật.
Không coi một menu đã mở là bằng chứng hỗ trợ mọi thao tác. Hướng dẫn chạy/build:
[native/unity_bridge/README.md](../native/unity_bridge/README.md).
