# Nhận diện client và profile tương thích Unity

## Bản test và thao tác nhanh

Chạy `dist/ITM_AutoClicker_Unity_Profiles_Test.exe` hoặc
`.\.venv\Scripts\python.exe main.py`. Chọn cửa sổ game trong Main, sau đó mở
**Unity Clients**. Chương trình tự đọc thông tin client trên luồng riêng để không
chặn giao diện. Refresh detection quét lại sau khi client cập nhật hoặc thay đổi.

Việc nhận diện, chọn profile và xuất báo cáo chỉ đọc dữ liệu. Helper chỉ được nạp
khi Start chạy action chuột với tùy chọn Unity virtual mouse đã bật.

| Nội dung hiển thị | Ý nghĩa |
| --- | --- |
| Client/Executable | Cửa sổ, tiến trình và file thực thi đang được chọn |
| Unity | Phiên bản lấy từ UnityPlayer.dll hoặc header globalgamemanagers |
| Architecture | x64, x86 hoặc ARM64 của PE executable |
| Runtime | IL2CPP, Mono, unknown hoặc not-unity theo module đang nạp |
| Input | legacy, new, both hoặc unknown theo assembly/metadata |
| uGUI | Có bằng chứng assembly UnityEngine.UI |
| Selected profile | Profile khớp và mức độ kiểm thử |

Không thể khẳng định module Input đang hoạt động chỉ bằng danh sách assembly.
Các kết quả này là nhận diện tĩnh; native helper còn kiểm tra runtime lúc kết nối.

## Các profile có sẵn

| Profile | Phạm vi | Trạng thái |
| --- | --- | --- |
| MongThienKiem 6000.3.25f1 | Tên EXE và SHA-256 của UnityPlayer.dll/GameAssembly.dll phải khớp | verified: bản client đã thử trước đây |
| Unity 2019–2023 / IL2CPP / Legacy UI | Unity 2019.x–2023.x, x64, IL2CPP, có binding Legacy Input và uGUI | experimental |
| Unity 6 / IL2CPP / Legacy UI | Unity 6000.x, x64, IL2CPP, có binding Legacy Input và uGUI | experimental |
| Client đã lưu | Tên EXE và hai SHA-256 đúng bản game đã lưu | experimental hoặc user-tested |

**Auto detect** ưu tiên bản verified, tiếp theo bản user-tested khớp chính xác,
profile experimental riêng của client, rồi profile tổng quát theo nhóm engine.
Nếu bạn chọn một profile cụ thể, chương trình sẽ báo không khớp khi đổi client,
không âm thầm đổi sang profile khác. Dùng Auto detect khi chuyển giữa nhiều game.

Client experimental cần bật **Allow experimental Unity profiles**. Tùy chọn này
cho phép thử native runtime trên các client đủ điều kiện; không bỏ qua kiểm tra
kiến trúc, backend, API, kiểu trường dữ liệu hay địa chỉ hàm.

## Cách test một game mới

1. Dừng mọi script đang chạy, chọn target game và chờ Unity Clients nhận diện xong.
2. Chọn Auto detect. Nếu hiện experimental, bật Allow experimental Unity profiles.
3. Trong Settings → Runtime, tắt Use real mouse và bật
   **Unity virtual mouse — compatibility profiles**.
4. Tạo một action trên nút mở menu có thể đóng lại; đặt Limit = 1. Giữ game mở bình
   thường, đặt chuột ngoài game, làm việc ở ứng dụng khác và dùng Home để chạy.
5. Quan sát menu có thực sự mở không; Count/acknowledgement không phải bằng chứng
   thao tác đã thành công. Dùng End/Stop để dừng.
6. Nếu thao tác thành công, dùng **Mark client as tested**, nhập tên profile. Trạng
   thái user-tested ghi nhận đánh giá của bạn, không đổi thành built-in verified.
7. Nếu chưa muốn xác nhận thành công, dùng **Save client profile**. Profile vẫn giữ
   experimental và cần opt-in khi dùng.

Tùy chọn Unity dùng đầu vào ảo cho click/hold/scroll/drag và ghi đè cấu hình Real
drag đã lưu. Không tự đổi sang chuột thật khi lỗi. Bàn phím, Full Screen và cửa sổ
minimize chưa được hỗ trợ. Game dùng Mono/x86/ARM/New Input System-only được nhận
diện nhưng sẽ báo rõ chưa có backend phù hợp.

## Lưu và cập nhật profile

Profile có sẵn nằm ở `resource/unity_bridge/profiles.json`. Profile riêng được lưu
ở `config/unity_profiles.json`, cùng thư mục settings của ứng dụng. Với file EXE,
đó là thư mục config cạnh EXE; khi chạy source, là thư mục config của repository.

Profile riêng là dữ liệu JSON, không chứa mã thực thi, DLL tùy ý hay địa chỉ hook.
Chương trình ghi file qua file tạm và thay thế nguyên tử. Nếu file hiện tại hỏng,
chương trình báo lỗi và không ghi đè nó khi lưu profile mới.

Sau khi game cập nhật, hash đổi thì trạng thái user-tested cũ không áp dụng nữa.
Auto detect có thể đề xuất lại profile experimental nếu runtime còn đủ điều kiện.
Bạn cần thử lại và lưu profile của bản mới. Không sửa hash để giữ trạng thái tested
cho một bản client chưa được thử.

## Lỗi và báo cáo

**Export detection report** xuất phiên bản, kiến trúc, runtime, danh sách module/
assembly, hash và kết quả chọn profile ra JSON. Báo cáo có đường dẫn cục bộ của
client. Không được tự gửi lên mạng. Bạn có thể gửi báo cáo kèm mô tả màn hình/action
không hoạt động để khảo sát tiếp.

Nếu trước đó đã dùng `ITM_AutoClicker_Unity_Test.exe`, helper cũ có thể vẫn ở trong
game dù đã Stop/đóng ITM. **Thoát rồi mở lại game một lần** trước khi dùng bản profile.
Helper mới có tên `itm_unity_bridge_profiles.dll` và IPC riêng; không nạp chồng
helper mới lên helper cũ. Stop tắt đầu vào ảo; khởi động lại game gỡ DLL khỏi bộ nhớ.

Native probe từ chối trước khi bật hook nếu thiếu API, field focus/input module sai
kiểu hoặc offset vượt kích thước đối tượng, hay địa chỉ hàm không thuộc vùng mã
thực thi của đúng module. Khi scene dùng InputSystemUIInputModule, thử nghiệm bị
dừng trước lần nhấn nút. Khi scene không đọc Legacy Input ảo, bước hover cũng dừng.

Các kiểm tra runtime tăng khả năng phát hiện không tương thích nhưng không bảo đảm
mọi game Unity hoạt động. Chưa có backend riêng cho Mono/New Input System.

## Bằng chứng kiểm tra của bản profile

- Đã nhận diện client MongThienKiem đang mở và tự chọn đúng profile verified.
- Bộ kiểm tra Python kiểm tra lựa chọn profile, đổi hash sau cập nhật, opt-in,
  profile lỗi, lưu user-tested, xuất báo cáo và callback nhận diện bất đồng bộ.
- Native fixture dùng một EXE tên OtherUnityClient.exe, khai báo phiên bản
  2022.3.99f1 và tách module giả lập UnityPlayer/GameAssembly. Đã thử đường chọn
  profile tổng quát thực, DLL loading, tọa độ, trạng thái nút, focus cục bộ,
  reconnect và heartbeat; không dùng mock để bỏ qua bước nhận diện client.
- Fixture khác kiểm tra từ chối New Input System UI và field layout sai trước khi
  nhấn chuột. Fixture là runtime tổng hợp, không phải một game Unity khác đã phát hành.
- Phiên game MongThienKiem hiện tại vẫn nạp helper cũ; không chèn thêm helper profile
  hay tự đóng game để ép thử. Cần mở lại game để kiểm tra helper mới trên client thực.
