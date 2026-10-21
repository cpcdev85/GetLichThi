# GetLichThi — KMA Lịch thi → Telegram

Dự án KMA Schedule được phát triển bởi cPcDev.

Dự án độc lập tại **`cpcdev85/GetLichThi`**, chạy trên GitHub Actions và được cron hosting gọi định kỳ. Nó theo dõi **lịch thi kết thúc học phần**, gửi thông báo, PDF gốc và JSON đã xử lý vào nhóm Telegram. Không đăng nhập hoặc nhập lịch thi lên web admin.

## 1. Tạo repository và tải mã nguồn

```text
.github/workflows/check_lichthi.yml
kma_lichthi_actions.py
kma_lichthi_core.py
requirements-lichthi.txt
README.md
```

Tạo repository tên **`GetLichThi`** trong tài khoản **`cpcdev85`**. Đưa 5 file này lên nhánh mặc định **`main`**, đúng cấu trúc trên. File Python và README phải ở ngay thư mục gốc; không upload cả ZIP hoặc thư mục `getlichthi_package` làm thư mục cha.

Nếu GitHub đã tạo README sẵn, thay bằng README trong ZIP. Code tự lấy repository đang chạy qua `GITHUB_REPOSITORY`, không cần nhập tên repo vào Python và không kết nối tới repo danh sách thi.

Repo `GetDanhSachThi` tiếp tục chạy riêng. **Không cần chép code, Secrets admin hoặc file ghi nhớ từ repo đó sang GetLichThi.** Nếu đã cài workflow lịch thi trong repo cũ, tắt cron/workflow lịch thi cũ trước khi bật repo mới để tránh hai nơi cùng gửi; giữ workflow danh sách thi hoạt động.

Cách tải bằng giao diện GitHub:

1. Giải nén ZIP.
2. Vào **cpcdev85/GetLichThi** → **Code → Add file → Upload files**. Tải 4 file ở thư mục gốc lên, rồi Commit changes.
3. Với workflow, chọn **Add file → Create new file**, đặt tên chính xác `.github/workflows/check_lichthi.yml`, dán nội dung file cùng tên trong ZIP rồi Commit changes. Có thể upload nguyên thư mục `.github` nếu giao diện nhận được.
4. Vào **Actions**, sẽ thấy workflow **KMA Lich Thi Telegram**. Nếu không thấy, kiểm tra workflow đã nằm trên nhánh mặc định và đúng đường dẫn ở bước 3.

Chưa tạo sẵn file ghi nhớ rỗng trong ZIP. Khi chạy mode send hoặc auto đang bật, workflow tự tạo **`json/lichthi_state.json` ngay trên nhánh `main`**. Không cần tạo nhánh ghi nhớ riêng.

**Cập nhật từ bản cũ:** tạm tắt cron lịch thi, chờ/hủy các lượt đang chạy, thay `kma_lichthi_actions.py` và README này trên main rồi chạy send. Nếu main chưa có file ghi nhớ, code tự đọc và sao chép ghi nhớ từ nhánh cũ `kma-lichthi-state` sang main trước khi gửi. Giữ nguyên các bước sent/sending; không tự gửi lại bước đã sent. Bản ghi nhớ cũ không bị xóa. Nếu main đã có file thì dùng bản trên main, không ghi đè bằng bản cũ. Sau khi kiểm tra file trên main và lượt chạy thành công, bật lại cron. Không xóa ghi nhớ cũ trước khi chuyển xong.

## 2. Cấu hình bot Telegram

Nếu bạn đã có bot đang gửi danh sách thi, có thể dùng lại bot và nhóm đó. Chức năng gửi này không nhận lệnh, không dùng `getUpdates`, không thay đổi webhook của bot hiện có.

Nếu chưa có bot: mở Telegram → tìm **@BotFather** chính thức → `/newbot` → làm theo hướng dẫn để lấy token.

Thêm bot vào nhóm nhận lịch thi, cho phép bot gửi tin nhắn và tài liệu. Nhóm thông thường không bắt buộc bot làm quản trị viên nếu quyền thành viên đã cho gửi. Với channel, bot cần quyền đăng bài phù hợp.

Tại repository **GetLichThi** → **Settings → Secrets and variables → Actions → Secrets → New repository secret**, thêm:

| Name | Secret cần điền |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token của bot, dạng `123456789:...`; không có chữ `bot` ở đầu, không có dấu nháy |
| `TELEGRAM_CHAT_ID` | ID nhóm, thường là số âm như `-1001234567890`; dùng đúng ID nhóm bạn muốn nhận |
| `TELEGRAM_THREAD_ID` | Không bắt buộc. ID topic nếu gửi vào một topic của nhóm forum; không dùng thì bỏ qua Secret này |

Token và chat ID lấy từ cấu hình bot cũ của bạn là thuận tiện nhất. Không đưa token vào file Python, README, commit, lệnh cron hoặc ảnh chụp công khai.

Nếu chưa biết ID nhóm và đang dùng **bot mới, không có webhook**:

1. Thêm bot vào nhóm; gửi `/check@TenUsernameBot` trong nhóm.
2. Chạy đoạn sau bằng Python trên máy bạn. Nhập token ở lời nhắc, token sẽ không hiển thị. Không đưa đoạn cấu hình chứa token thật lên GitHub.

```python
import getpass
import json
import urllib.request

token = getpass.getpass("Token bot: ").strip()
try:
    with urllib.request.urlopen(
        "https://api.telegram.org/bot" + token + "/getUpdates", timeout=30
    ) as response:
        result = json.load(response)
    for update in result.get("result", []):
        message = update.get("message", {})
        chat = message.get("chat", {})
        if chat.get("type") in ("group", "supergroup"):
            print("Nhóm:", chat.get("title"))
            print("TELEGRAM_CHAT_ID:", chat.get("id"))
            print("TELEGRAM_THREAD_ID (nếu có):", message.get("message_thread_id", ""))
except Exception:
    print("Không đọc được. Kiểm tra token, kết nối và bot có đang dùng webhook không.")
```

Nếu bot hiện có đang chạy webhook hoặc một chương trình khác nhận cập nhật, lấy ID từ cấu hình chương trình đó. Không cần gỡ webhook để sử dụng bộ lịch thi.

## 3. Bật/tắt tự động bằng Variable

Trong **GetLichThi**, vào **Settings → Secrets and variables → Actions → Variables → New repository variable**:

- Name: `KMA_ENABLE_LICHTHI`
- Value: `true`

Đây là **Variable**, không phải Secret. Nó độc lập với Variable `KMA_ENABLE_UPLOAD` của danh sách thi.

Các chế độ:

| mode | Hành vi |
|---|---|
| `preview` | Đọc bài lịch thi mới nhất, tải PDF để kiểm tra và xử lý JSON; chỉ log tiêu đề, link, ngày và số dòng. Không gửi Telegram, không ghi file ghi nhớ |
| `send` | Gửi thông báo + PDF + JSON cho các mục chưa gửi, kể cả khi Variable đang false; vẫn chống gửi lặp |
| `auto` | Chỉ hoạt động khi `KMA_ENABLE_LICHTHI=true`; false/thiếu biến thì thoát ngay |

Nếu repository chặn ghi, kiểm tra **Settings → Actions → General → Workflow permissions → Read and write permissions → Save**. YAML đã khai báo `contents: write`; nếu chính sách tổ chức chặn thì cần điều chỉnh chính sách tương ứng.

## 4. Kiểm tra trước khi đặt cron

1. Trong repo **GetLichThi**, vào **Actions → KMA Lich Thi Telegram → Run workflow**.
2. Chọn nhánh `main`, mode **preview**, giữ **retry_uncertain=false**.
3. Mở lượt chạy → job **check-lichthi** → bước **Check lichthi and send Telegram**.
4. Kiểm tra số dòng lịch thi và mẫu tin trong log. Preview thành công không chứng minh bot có quyền gửi, vì chưa gọi Telegram.
5. Chạy lại mode **send**, giữ retry_uncertain=false. Lần gửi đầu chỉ lấy bài lịch thi phù hợp mới nhất, tránh gửi toàn bộ bài cũ. Bài mới nhất có thể đã đăng từ nhiều ngày trước.
6. Nhóm sẽ nhận tin thông báo, một PDF và một JSON cho mỗi PDF hợp lệ trong bài.
7. Chạy lại mode **send** để thử chống lặp. Nội dung PDF không đổi sẽ báo đã gửi đủ và bỏ qua.

File ghi nhớ xem tại **Code → main → json → lichthi_state.json**. Không xóa file này để thử cron: mất ghi nhớ có thể làm gửi lại lịch cũ. Preview không tạo thư mục `json` là bình thường.

## 5. Nội dung gửi vào nhóm

Mỗi PDF lịch thi hợp lệ có một thông báo dạng:

```text
📢 CÓ LỊCH THI MỚI

Kế hoạch Tổ chức thi KTHP Học kỳ 1 năm học 2026-2027. Đợt1 (Hệ KTXH)
🔗 https://ktdbcl.actvn.edu.vn/457-...html
Ngày chỉnh sửa: 21/Oct/2026
Kiểm tra: 21/10/2026 18:00:02 (giờ Việt Nam)

📎 File: https://ktdbcl.actvn.edu.vn/files/...pdf
```

Sau đó bot gửi **PDF gốc** và **JSON đã xử lý** dưới dạng tài liệu, trả lời vào tin thông báo để dễ nhận biết. Bài có nhiều PDF thì gửi một bộ cho mỗi PDF đọc được. Tên file gửi được làm sạch và thêm mã nội dung để phân biệt các bản sửa.

- Tiêu đề lấy từ tiêu đề bài viết; có đường dẫn mở bài và đường dẫn PDF riêng.
- **Ngày chỉnh sửa** ưu tiên `Last-Modified` của PDF; nếu thiếu thì dùng metadata ngày sửa bài. Không có cả hai thì ghi rõ “Không có thông tin từ nguồn”, không lấy ngày kiểm tra thay ngày sửa.
- **Kiểm tra** là thời điểm bắt đầu lượt chạy, định dạng giờ Việt Nam, không phụ thuộc múi giờ máy runner.
- JSON gồm `Môn thi`, `Hình thức thi`, `Khóa đào tạo`, `Thời gian bắt đầu thi`.
- Dùng lại thuật toán trích bảng/gộp ca/chuẩn hóa khóa của file `kmaschedulev6(2).pyw` bạn cung cấp. Không dùng OCR ảnh hoặc PDF scan trên runner. PDF ngoài định dạng hỗ trợ sẽ báo lỗi và chưa gửi bộ tin đó; không gửi JSON giả/rỗng.
- Việc xử lý thành công không bảo đảm mọi dòng đều đúng nếu bố cục tài liệu khác mẫu; vẫn nên kiểm tra JSON trước khi nhập thủ công.

## 6. Cron hosting

Bộ này chỉ có `workflow_dispatch`, **không có cron GitHub**. Thêm một cron hosting riêng cho lịch thi, giữ cron danh sách thi hiện tại.

Có thể dùng lại PAT hosting đang gọi workflow danh sách thi, nhưng phải cấp quyền thêm cho **GetLichThi**. Với fine-grained PAT: vào GitHub cá nhân → **Settings → Developer settings → Personal access tokens → Fine-grained tokens** → chọn token → **Repository access → Only select repositories** → thêm **GetLichThi**, giữ **GetDanhSachThi** nếu cron cũ đang dùng chung → **Repository permissions → Actions: Read and write** → lưu. Hoặc tạo PAT riêng chỉ dành cho GetLichThi với quyền tương tự. Không cần dùng PAT làm Secret `GH_STATE_TOKEN`; trong workflow, GH_STATE_TOKEN đã được lấy từ `github.token` tự động.

Ví dụ mỗi 30 phút:

```text
Minute: */30
Hour: *
Day: *
Month: *
Weekday: *
```

Command dưới đây phải dán thành **một dòng**, thay `TOKEN_CUA_BAN` bằng PAT thật, không thêm dấu `\` nối dòng:

```bash
curl --fail --silent --show-error --max-time 30 -X POST -H "Accept: application/vnd.github+json" -H "Authorization: Bearer TOKEN_CUA_BAN" -H "Content-Type: application/json" "https://api.github.com/repos/cpcdev85/GetLichThi/actions/workflows/check_lichthi.yml/dispatches" -d '{"ref":"main","inputs":{"mode":"auto"}}' >/dev/null 2>&1
```

Tùy chọn chu kỳ:

| Chu kỳ | Minute | Hour |
|---|---|---|
| 5 phút | `*/5` | `*` |
| 10 phút | `*/10` | `*` |
| 30 phút | `*/30` | `*` |
| 1 giờ | `0` | `*` |

Day/Month/Weekday đều là `*`. Nếu đổi tên repo/nhánh, sửa URL và `ref` tương ứng. Cron chỉ yêu cầu GitHub tạo lượt chạy, không bảo đảm bắt đầu ngay đúng giây vì có thể xếp hàng. Độ trễ phát hiện gồm chu kỳ cron + thời gian chờ runner + tải/xử lý/gửi.

`>/dev/null 2>&1` bỏ toàn bộ đầu ra của curl trên hosting. Khi debug, tạm bỏ phần đó và chạy thử trong terminal riêng để xem HTTP lỗi; không đăng ảnh/lệnh có PAT thật. Log xử lý vẫn xem trong tab Actions. Lượt gọi từ hosting sẽ hiện là chạy qua `workflow_dispatch`.

## 7. Cách chọn bài và phát hiện bản sửa

Nguồn theo dõi:

- Trang chủ: https://ktdbcl.actvn.edu.vn/
- Chuyên mục Lịch thi: https://ktdbcl.actvn.edu.vn/khao-thi/to-chuc-thi/lich-thi.html

Giữ bộ lọc của file desktop:

- Tiêu đề/link phải liên quan thi KTHP hoặc thi kết thúc học phần, có kế hoạch/lịch thi.
- Trong đúng chuyên mục Lịch thi có thể chấp nhận một số tiêu đề thiếu chữ KTHP hoặc điều chỉnh hình thức thi.
- Loại các thông báo phúc khảo, đính chính, nộp phí, học phí, tốt nghiệp, sát hạch, danh sách thi, kết quả/điểm thi, thời khóa biểu… như file gốc. Vì vậy thông báo có từ “đính chính” cũng đang bị loại; muốn nhận loại này cần sửa bộ lọc sau.
- Chỉ lấy bài Joomla hợp lệ và PDF chính chủ ở `/files/`; hỗ trợ cả PDF nhúng qua PDF.js.

Lần gửi đầu: chỉ xử lý bài phù hợp có ID lớn nhất, ghi nhận các bài cũ đang thấy để không gửi hàng loạt lịch sử.

Các lần sau: nhận bài mới chưa ghi nhận, kiểm tra lại các bài đã theo dõi nằm trong 3 bài phù hợp mới nhất. Các bài đang lỗi sẽ tiếp tục được thử, kể cả đã rời trang đầu. Không quét lại toàn bộ lịch sử, không bảo đảm phát hiện sửa ở mọi bài cũ.

PDF được tải và so SHA256 mỗi lần kiểm tra bài tương ứng: đổi nội dung cùng URL vẫn được nhận ra. Cùng nội dung PDF ở nhiều link chỉ gửi một lần cho cùng nhóm/topic. Chỉ sửa tiêu đề hoặc metadata mà PDF không đổi sẽ không gửi lại. Đổi nhóm/topic được coi là đích nhận khác.

## 8. Ghi nhớ, lỗi giữa chừng và tránh spam

File riêng: **`json/lichthi_state.json` trên nhánh `main`** của repository GetLichThi. Không đọc hoặc ghi repository GetDanhSachThi. Khi nâng cấp, chỉ đọc nhánh cũ `kma-lichthi-state` để chuyển ghi nhớ nếu main chưa có file; mọi lần ghi đều vào main. Lỗi đọc bản cũ hoặc dữ liệu không hợp lệ sẽ dừng, không tự xóa lịch sử để bắt đầu lại.

File chứa ID/URL/tiêu đề bài công khai, mã băm, thời gian và trạng thái/message ID Telegram. Không chứa token, chat ID gốc, nội dung PDF hoặc các dòng JSON lịch thi. Workflow không upload PDF/JSON lên artifact GitHub hoặc commit chúng vào repo; file chỉ tồn tại tạm trên runner để gửi Telegram.

Mỗi bộ tin có 3 bước: `notice`, `pdf`, `json`. Trước mỗi lần gửi lưu `sending`; khi Telegram xác nhận thì lưu `sent`. Các bước `sent` không tự gửi lại. Ví dụ tin nhắn và PDF đã gửi, JSON bị Telegram từ chối rõ ràng thì lần sau chỉ thử gửi JSON.

Nếu timeout/mất kết nối hoặc không lưu được trạng thái sau khi gửi, không thể biết chắc Telegram đã nhận hay chưa. Tool giữ `sending` và dừng để không tự spam. Không thể bảo đảm tuyệt đối gửi đúng một lần khi mạng bị gián đoạn.

Cách xử lý khi log báo `sending`:

1. Tạm tắt cron lịch thi để tránh các lượt kiểm tra chen vào.
2. Kiểm tra tin/PDF/JSON trong nhóm.
3. Nếu bước đó **chưa nhận**, chạy thủ công mode `send` và bật `retry_uncertain=true`. Chỉ các bước đang sending/chưa gửi được thử; bước sent giữ nguyên. Nếu bước đó thực ra đã đến, thao tác này có thể tạo bản trùng.
4. Nếu bước đó **đã nhận**, chọn nhánh `main`, mở `json/lichthi_state.json`, tìm delivery có mã đầu tương ứng trong log và đổi riêng trạng thái bước đó từ `sending` sang `sent`. Có thể điền `message_id` dạng số nếu biết (lấy từ liên kết tin nhắn); nếu không thì bỏ qua message_id, các tài liệu tiếp theo vẫn gửi được nhưng có thể không gắn reply vào thông báo. Không xóa toàn bộ file hay delivery.
5. Chạy lại `send` với retry_uncertain=false để gửi những phần còn thiếu, rồi bật lại cron.

Telegram trả mã 400/401/403/404/429 rõ ràng: bước bị từ chối không đánh dấu sent; kiểm tra chat ID, token, quyền gửi/topic hoặc chờ hết giới hạn trước khi chạy lại. Lỗi 429 không tự gửi dồn/retry ngay trong cùng lượt.

Nếu không ghi được file ghi nhớ, tool dừng trước lần gửi tiếp theo. Nếu có thay đổi đồng thời trên main, bộ lịch thi chỉ thử lại khi chính file lịch thi vẫn không thay đổi. Không cần thay đổi repository danh sách thi.

## 9. Tắt hoặc xóa lịch thi về sau

Tạm tắt:

1. Đặt Variable `KMA_ENABLE_LICHTHI=false` để các lượt mode auto thoát ngay.
2. Tắt cron hosting gọi `check_lichthi.yml`.
3. Nếu muốn, vào Actions → KMA Lich Thi Telegram → menu ba chấm → Disable workflow.

Mode `send` thủ công vẫn có thể gửi dù Variable false. Nếu một lượt đã bắt đầu trước lúc tắt, hủy riêng lượt lịch thi đó trong Actions nếu cần dừng ngay.

Ngừng dùng lâu dài: tắt cron GetLichThi, hủy các lượt GetLichThi đang chạy rồi Disable workflow; có thể Archive repository GetLichThi để giữ code và ghi nhớ. Nếu quyết định xóa hẳn repo GetLichThi thì ghi nhớ cũng mất, cài lại có thể gửi lại lịch cũ. Không thao tác với repo GetDanhSachThi. Không thu hồi PAT hosting đang dùng chung hoặc thu hồi token bot còn được hệ thống khác sử dụng.

Hai repository chạy độc lập, không chờ nhau theo thiết kế. Chúng vẫn chia sẻ tài nguyên/giới hạn của tài khoản GitHub và truy cập cùng website nguồn, nên không thể cam kết tuyệt đối không có chờ đợi. Bộ này không thêm bước tải PDF/gửi Telegram vào luồng danh sách thi.

## 10. Kiểm tra lỗi nhanh

| Hiện tượng | Kiểm tra |
|---|---|
| Chạy preview xanh nhưng nhóm chưa có tin | Preview không gửi; chạy send sau khi thêm Secrets |
| Auto thoát ngay | KMA_ENABLE_LICHTHI phải nằm ở Variables và bằng true |
| Không có workflow lịch thi | Đường dẫn `.github/workflows/check_lichthi.yml` trên nhánh mặc định |
| Cron không tạo lượt | PAT còn hiệu lực, Actions read/write, đúng repo/nhánh/workflow, workflow không bị Disable |
| Không tạo file ghi nhớ | Preview không ghi; send cần contents write; xem main/json/lichthi_state.json |
| PDF lỗi hoặc JSON không đọc được | Mở nguồn kiểm tra; PDF scan/bố cục khác không có OCR tự động |
| Không phát hiện bài mong muốn | So điều kiện lọc ở mục 7; không quét tất cả trang lịch sử |
| Lượt bị đỏ, log có sending | Xử lý theo mục 8, không xóa ghi nhớ để thử lại |

Tài liệu chính thức:

- Telegram Bot API: https://core.telegram.org/bots/api#senddocument
- Tạo bot: https://core.telegram.org/bots/tutorial#obtain-your-bot-token
- Workflow dispatch: https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event
- GitHub Actions Secrets: https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions
