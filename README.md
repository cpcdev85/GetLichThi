# GetLichThi — Tự động theo dõi lịch thi KMA

Dự án KMA Schedule được phát triển bởi cPcDev.

**GetLichThi** theo dõi thông báo thi kết thúc học phần của Học viện Kỹ thuật Mật mã, xử lý PDF thành JSON và gửi kết quả vào nhóm Telegram. Hệ thống chạy bằng **GitHub Actions**, được kích hoạt định kỳ từ **cron hosting**, không cần bật máy tính cá nhân.

Repository: [cpcdev85/GetLichThi](https://github.com/cpcdev85/GetLichThi)

## 1. Cách hoạt động

Mỗi lần cron kích hoạt workflow, hệ thống thực hiện:

1. Đọc trang thông báo chung và chuyên mục Lịch thi của trường.
2. Lọc các bài phù hợp với thông báo kế hoạch/lịch thi kết thúc học phần.
3. Lấy liên kết PDF trực tiếp hoặc PDF nhúng trong bài.
4. Tải PDF, so sánh mã SHA-256 với lịch sử gửi.
5. Trích bảng lịch thi, chuẩn hóa khóa đào tạo và gộp các ca phù hợp thành JSON.
6. Gửi thông báo, PDF gốc và JSON đã xử lý vào nhóm Telegram.
7. Ghi trạng thái vào `json/lichthi_state.json` trên nhánh **`main`** để tránh gửi lặp.

Hệ thống kiểm tra theo chu kỳ, không theo dõi liên tục theo thời gian thực. Thời điểm phát hiện phụ thuộc chu kỳ cron, hàng đợi GitHub và thời gian xử lý.

**Nguồn theo dõi:**

- [Trang thông báo chung](https://ktdbcl.actvn.edu.vn/)
- [Chuyên mục Lịch thi](https://ktdbcl.actvn.edu.vn/khao-thi/to-chuc-thi/lich-thi.html)

GetLichThi hoạt động độc lập với repository `GetDanhSachThi`. Kết quả lịch thi được gửi về Telegram, không tự nhập lên web admin.

## 2. Yêu cầu triển khai

- Repository **`cpcdev85/GetLichThi`**, nhánh mặc định **`main`**.
- GitHub Actions được bật và được phép ghi nội dung repository.
- Hosting có Cron Jobs, hỗ trợ `curl` và kết nối HTTPS đến `api.github.com`.
- Bot Telegram có quyền gửi tin nhắn và tài liệu vào nhóm nhận.
- Token bot và ID nhóm đã được chuẩn bị.

Ba loại thông tin xác thực được sử dụng:

| Thông tin | Nơi cấu hình | Mục đích |
|---|---|---|
| Token bot Telegram | Repository Secrets | Gửi thông báo và tài liệu |
| Personal access token GitHub (PAT) | Cron trên hosting | Kích hoạt workflow |
| `GITHUB_TOKEN` | GitHub tự cấp từng lượt chạy | Đọc và ghi lịch sử xử lý |

Không cần tài khoản, mật khẩu hoặc URL admin của KMA Schedule cho repository này.

## 3. Tải mã nguồn lên GitHub

Tạo repository tên **GetLichThi**, sau đó đưa các file vào đúng đường dẫn:

| Đường dẫn | Chức năng |
|---|---|
| `kma_lichthi_actions.py` | Điều phối lượt kiểm tra, gửi Telegram và lưu ghi nhớ |
| `kma_lichthi_core.py` | Lọc thông báo, đọc PDF, chuẩn hóa và gộp lịch thi |
| `requirements-lichthi.txt` | Các thư viện Python cần cài |
| `.github/workflows/check_lichthi.yml` | Cấu hình workflow GitHub Actions |
| `README.md` | Tài liệu cài đặt và vận hành |
| `json/lichthi_state.json` | Hệ thống tự tạo trên main khi bắt đầu hoạt động gửi |

**Các bước tải lên bằng giao diện GitHub:**

1. Giải nén bộ mã nguồn.
2. Vào repository → **Code → Add file → Upload files**.
3. Tải các file ở thư mục gốc lên, rồi **Commit changes** vào `main`.
4. Nếu thư mục `.github` chưa được tải lên, chọn **Add file → Create new file**.
5. Nhập tên `.github/workflows/check_lichthi.yml`, dán nội dung workflow tương ứng và commit.
6. Vào **Actions**, kiểm tra đã xuất hiện workflow **KMA Lich Thi Telegram**.

Đưa các file trực tiếp vào thư mục gốc; không tải nguyên ZIP hoặc đặt thêm một thư mục bao ngoài. Không tạo thủ công file ghi nhớ rỗng.

## 4. Cấu hình Secrets và Variable

### Secrets Telegram

Trong repository **GetLichThi**, mở:

**Settings → Secrets and variables → Actions → Secrets → New repository secret**

| Name | Giá trị |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram đang sử dụng |
| `TELEGRAM_CHAT_ID` | ID nhóm nhận thông báo; thường là số âm |
| `TELEGRAM_THREAD_ID` | Tùy chọn: ID topic trong nhóm forum; không dùng thì bỏ qua |

Nhập giá trị trực tiếp, không thêm dấu nháy. Token và ID nhóm được giữ trong Secrets, không đưa vào mã nguồn hoặc file JSON.

Có thể dùng chung token với bot webhook hiện có. GetLichThi chỉ gọi API gửi tin/tài liệu, không đăng ký lại webhook hoặc nhận cập nhật bằng `getUpdates`.

### Variable bật tự động

Mở **Settings → Secrets and variables → Actions → Variables → New repository variable**:

| Name | Value |
|---|---|
| `KMA_ENABLE_LICHTHI` | `true` |

Đây là **Variable**, không phải Secret. Đặt `false` để các lượt chạy chế độ `auto` thoát ngay. Biến này độc lập với cấu hình của repository danh sách thi.

## 5. Quyền ghi lịch sử xử lý

Workflow khai báo `contents: write` và sử dụng `${{ github.token }}` cho biến `GH_STATE_TOKEN`. Không cần tự tạo Secret có tên này.

Nếu workflow báo không có quyền ghi, kiểm tra:

**Settings → Actions → General → Workflow permissions → Read and write permissions → Save**

Chính sách tổ chức hoặc quy tắc bảo vệ nhánh có thể hạn chế quyền ghi. Nếu main bị chặn cập nhật trực tiếp, cần cấu hình quyền phù hợp trước khi sử dụng. Khi không lưu được trạng thái, hệ thống sẽ dừng trước lần gửi tiếp theo.

## 6. Chạy thử và kiểm tra kết quả

Mở **Actions → KMA Lich Thi Telegram → Run workflow**, chọn nhánh **main**.

| Chế độ | Hành vi |
|---|---|
| `preview` | Đọc bài mới nhất, xử lý PDF và hiển thị thông tin trong log; không gửi Telegram, không tạo hoặc chuyển ghi nhớ |
| `send` | Gửi các mục chưa hoàn tất; vẫn chống lặp và không phụ thuộc Variable bật/tắt |
| `auto` | Chạy khi `KMA_ENABLE_LICHTHI=true`; thiếu biến hoặc false thì thoát |

**Trình tự kiểm tra:**

1. Chạy `preview`, giữ **retry_uncertain=false**.
2. Mở lượt chạy → job **check-lichthi** → bước **Check lichthi and send Telegram**.
3. Kiểm tra tiêu đề, link nguồn, ngày và số dòng JSON trong log.
4. Chạy `send`, giữ **retry_uncertain=false** để thử gửi thật.
5. Kiểm tra nhóm nhận đủ thông báo, PDF và JSON.
6. Chạy lại `send`: PDF không đổi và đã gửi đủ sẽ được bỏ qua.
7. Vào **Code → main → json → lichthi_state.json** để xem ghi nhớ.

Preview thành công chỉ xác nhận khả năng đọc/xử lý nguồn, chưa xác nhận quyền gửi Telegram. Không thấy thư mục `json` sau preview là bình thường.

Lần gửi đầu chỉ xử lý bài phù hợp mới nhất, kể cả bài đó đã đăng từ nhiều ngày trước.

## 7. Cấu hình cron hosting

Workflow sử dụng **`workflow_dispatch`**. Bộ mã hiện tại không cấu hình lịch `schedule` của GitHub; hosting sẽ chủ động gọi API kích hoạt.

### Quyền PAT GitHub

PAT dùng trên hosting cần truy cập repository **GetLichThi** và quyền **Actions: Read and write**.

Với fine-grained PAT:

1. Mở GitHub cá nhân → **Settings → Developer settings → Personal access tokens → Fine-grained tokens**.
2. Tạo token mới hoặc chỉnh token đang dùng.
3. Trong **Repository access → Only select repositories**, chọn **GetLichThi**.
4. Trong **Repository permissions**, đặt **Actions: Read and write**.
5. Lưu và dùng token đó trong lệnh cron.

Nếu dùng chung PAT với cron danh sách thi, giữ cả hai repository trong danh sách được phép truy cập. Không thay PAT bằng token bot Telegram.

### Chu kỳ kiểm tra

Có thể đặt mỗi 30 phút cho lịch thi. Điền các trường trong Cron Jobs:

| Chu kỳ | Minute | Hour | Day | Month | Weekday |
|---|---|---|---|---|---|
| 5 phút | `*/5` | `*` | `*` | `*` | `*` |
| 10 phút | `*/10` | `*` | `*` | `*` | `*` |
| 30 phút | `*/30` | `*` | `*` | `*` | `*` |
| 1 giờ | `0` | `*` | `*` | `*` | `*` |

### Lệnh kích hoạt

Thay `TOKEN_CUA_BAN` bằng PAT GitHub, rồi dán toàn bộ lệnh dưới đây thành **một dòng** vào trường Command:

```bash
curl --fail --silent --show-error --max-time 30 -X POST -H "Accept: application/vnd.github+json" -H "Authorization: Bearer TOKEN_CUA_BAN" -H "Content-Type: application/json" "https://api.github.com/repos/cpcdev85/GetLichThi/actions/workflows/check_lichthi.yml/dispatches" -d '{"ref":"main","inputs":{"mode":"auto"}}' >/dev/null 2>&1
```

Nếu đổi tên tài khoản/repository, cập nhật URL API tương ứng. Bản mã hiện tại lưu ghi nhớ cố định vào nhánh `main`; thay nhánh triển khai cần cập nhật cả code ghi nhớ và cấu hình liên quan.

`>/dev/null 2>&1` bỏ đầu ra của curl trên hosting. Khi kiểm tra lỗi gọi API, có thể tạm bỏ phần này và chạy lệnh trong terminal riêng. Log xử lý PDF/Telegram vẫn xem trong GitHub Actions.

Hosting gọi API chỉ tạo yêu cầu chạy; workflow có thể chờ runner. Các lượt do hosting kích hoạt hiển thị dưới sự kiện `workflow_dispatch`, không phải `schedule`.

## 8. Nội dung gửi Telegram

Mỗi PDF hợp lệ tạo một bộ gồm **thông báo → PDF gốc → JSON đã xử lý**. Hai tài liệu được gửi dưới dạng file, gắn trả lời vào thông báo khi có message ID.

Ví dụ minh họa:

```text
📢 CÓ LỊCH THI MỚI

Kế hoạch Tổ chức thi KTHP Học kỳ 1 năm học 2026-2027. Đợt1 (Hệ KTXH)
🔗 https://ktdbcl.actvn.edu.vn/457-ke-hoach-to-chuc-thi-kthp-hoc-ky-1-nam-hoc-2026-2027-dot1-he-ktxh.html
Ngày chỉnh sửa: 06/Oct/2026
Kiểm tra: 21/10/2026 18:00:02 (giờ Việt Nam)

📎 File: https://ktdbcl.actvn.edu.vn/files/thong-bao/ke-hoach-thi/ke-hoach-thi-kthp-dot1-hk1-nh2627.pdf
```

| Thông tin | Cách xác định |
|---|---|
| Tiêu đề | Lấy từ bài thông báo |
| Link bài | Đường dẫn mở thông báo gốc |
| Ngày chỉnh sửa | Ưu tiên Last-Modified của PDF; nếu thiếu dùng metadata ngày sửa bài |
| Thời điểm kiểm tra | Thời gian bắt đầu lượt chạy, theo giờ Việt Nam |
| File PDF | Tài liệu gốc tải từ website trường |
| File JSON | Dữ liệu lịch thi đã trích xuất, chuẩn hóa và gộp ca |

Nếu nguồn không có thông tin ngày sửa, thông báo ghi **Không có thông tin từ nguồn**. Không lấy thời điểm kiểm tra thay cho ngày sửa.

JSON gồm bốn trường: `Môn thi`, `Hình thức thi`, `Khóa đào tạo`, `Thời gian bắt đầu thi`. Bài có nhiều PDF đọc được sẽ tạo một bộ tin cho mỗi PDF có nội dung chưa gửi.

## 9. Phạm vi theo dõi và xử lý PDF

### Chọn thông báo

Bộ lọc tìm các tiêu đề/link liên quan kế hoạch hoặc lịch thi **KTHP / kết thúc học phần**. Trong đúng chuyên mục Lịch thi, một số tiêu đề thiếu chữ KTHP hoặc điều chỉnh hình thức thi vẫn có thể được nhận.

Các nhóm thông báo bị loại gồm: phúc khảo, đính chính, nộp phí/học phí, tốt nghiệp, sát hạch, danh sách thi, kết quả/điểm thi và thời khóa biểu. Theo bộ lọc hiện tại, tiêu đề có chữ **đính chính** cũng bị loại dù có liên quan lịch thi.

Chỉ tải PDF trên tên miền `ktdbcl.actvn.edu.vn`, trong đường dẫn `/files/`. Hỗ trợ cả link trực tiếp và PDF nhúng qua PDF.js.

### Theo dõi bài mới và bản sửa

- **Lần đầu:** xử lý bài phù hợp có ID lớn nhất; ghi nhận các bài cũ đang thấy để tránh gửi toàn bộ lịch sử.
- **Các lần sau:** nhận bài mới chưa ghi nhận, kiểm tra lại các bài đã theo dõi nằm trong ba bài phù hợp mới nhất.
- **Bài đang lỗi:** tiếp tục thử lại, kể cả khi bài đã rời trang đầu.
- **PDF thay đổi:** so SHA-256 để nhận ra nội dung mới ngay cả khi URL giữ nguyên.
- **PDF trùng nội dung:** chỉ gửi một lần cho cùng nhóm/topic. Chỉ sửa tiêu đề hoặc metadata mà PDF không đổi thì không gửi lại.

Không quét lại toàn bộ bài cũ; sửa đổi ở bài ngoài phạm vi theo dõi có thể không được phát hiện.

### Định dạng hỗ trợ

Công cụ đọc **PDF có bảng và văn bản**, sử dụng cách chuẩn hóa khóa KMA/KMP và gộp ca từ công cụ desktop. Chưa có OCR tự động cho ảnh hoặc PDF scan.

PDF không đọc được theo định dạng hỗ trợ sẽ báo lỗi, chưa gửi bộ tin tương ứng và được thử lại sau. Với bố cục mới, cần kiểm tra nội dung JSON trước khi sử dụng. Giới hạn tải PDF hiện tại là **49 MiB**.

## 10. Ghi nhớ và chống gửi lặp

Đường dẫn lưu: **`main/json/lichthi_state.json`**.

File chứa ID/URL/tiêu đề bài công khai, mã băm nội dung, thời gian và trạng thái/message ID Telegram. Không lưu token, chat ID gốc, PDF hoặc các dòng JSON lịch thi vào ghi nhớ.

Workflow không commit PDF/JSON kết quả hoặc tải chúng lên GitHub Artifacts. Tài liệu được xử lý tạm trên runner để gửi Telegram.

Mỗi bộ tin có ba bước:

| Bước | Nội dung | Trạng thái |
|---|---|---|
| `notice` | Tin thông báo | `sending` trước khi gửi, `sent` sau khi xác nhận |
| `pdf` | PDF gốc | `sending` trước khi gửi, `sent` sau khi xác nhận |
| `json` | JSON đã xử lý | `sending` trước khi gửi, `sent` sau khi xác nhận |

Bước đã `sent` không tự gửi lại. Ví dụ thông báo và PDF đã hoàn tất nhưng JSON bị từ chối rõ ràng, lần sau chỉ thử gửi JSON.

Nếu mất kết nối hoặc không lưu được xác nhận sau khi gửi, trạng thái có thể còn `sending`. Hệ thống dừng để tránh tự gửi lặp vì chưa biết Telegram đã nhận hay chưa. Không thể bảo đảm gửi đúng một lần trong mọi tình huống gián đoạn mạng.

### Xử lý trạng thái sending

1. Tạm tắt cron lịch thi và chờ/hủy các lượt đang chạy.
2. Kiểm tra trong nhóm xem bước tương ứng đã nhận hay chưa.
3. **Chưa nhận:** chạy `send`, bật `retry_uncertain=true` để thử lại bước chưa xác nhận. Nếu thực tế đã nhận thì thao tác này có thể tạo bản trùng.
4. **Đã nhận:** mở file ghi nhớ trên main, tìm delivery có mã đầu tương ứng trong log, đổi riêng trạng thái bước đó từ `sending` thành `sent`. Có thể điền `message_id` dạng số nếu biết; thiếu ID thì tài liệu tiếp theo có thể không gắn reply.
5. Chạy lại `send` với `retry_uncertain=false` để hoàn tất phần còn thiếu, rồi bật lại cron.

Không xóa toàn bộ ghi nhớ để kiểm tra cron hoặc xử lý một bước lỗi.

## 11. Cập nhật, tạm dừng và ngừng sử dụng

### Cập nhật mã nguồn

1. Tạm tắt cron GetLichThi, chờ/hủy các lượt đang chạy.
2. Thay các file cần cập nhật trên `main`; giữ nguyên `json/lichthi_state.json`.
3. Chạy `preview`, sau đó `send` nếu cần xác nhận hoạt động gửi.
4. Kiểm tra log, trạng thái và nhóm nhận trước khi bật lại cron.

Chỉ cập nhật README thì thay riêng `README.md`; không cần thay code, Secrets hoặc cron.

### Chuyển ghi nhớ từ bản dùng nhánh riêng

Bản hiện tại tự chuyển ghi nhớ từ nhánh cũ **`kma-lichthi-state`** khi main chưa có file:

1. Giữ nguyên nhánh cũ, cập nhật `kma_lichthi_actions.py` trên main.
2. Chạy `send` hoặc `auto` đang bật.
3. Công cụ đọc, kiểm tra và sao chép ghi nhớ sang main trước khi gửi tiếp.
4. Kiểm tra file `json/lichthi_state.json` trên main và log chuyển ghi nhớ.

Giữ nguyên trạng thái `sent`/`sending` trong quá trình chuyển. Nếu main đã có file thì ưu tiên main, không ghi đè bằng bản cũ. Nhánh cũ không bị tự xóa. Preview không thực hiện chuyển ghi nhớ.

### Tạm dừng

- Đặt Variable `KMA_ENABLE_LICHTHI=false` để các lượt `auto` thoát ngay.
- Tắt cron hosting của GetLichThi để ngừng tạo lượt chạy.
- Có thể Disable workflow **KMA Lich Thi Telegram** trong Actions.

Mode `send` thủ công vẫn gửi khi Variable false. Muốn dừng ngay lượt đã bắt đầu thì hủy lượt đó trong Actions.

### Ngừng sử dụng

Tắt cron và workflow rồi có thể Archive repository để giữ mã nguồn, cấu hình và lịch sử. Nếu xóa repo, ghi nhớ cũng mất; cài lại có thể gửi lại lịch cũ.

Không thu hồi PAT hoặc token bot đang được hệ thống khác sử dụng. Hai repository độc lập về code và ghi nhớ nhưng vẫn chia sẻ tài nguyên/giới hạn theo tài khoản GitHub và giới hạn gửi của bot Telegram dùng chung.

## 12. Khắc phục sự cố

| Hiện tượng | Nguyên nhân hoặc hướng kiểm tra |
|---|---|
| Preview xanh nhưng Telegram chưa nhận | Preview không gửi; chạy send để kiểm tra bot |
| Auto kết thúc ngay | Variable KMA_ENABLE_LICHTHI thiếu hoặc không bằng true |
| Không thấy workflow | Kiểm tra đường dẫn `.github/workflows/check_lichthi.yml` trên nhánh mặc định |
| Cron không tạo lượt chạy | Kiểm tra PAT, quyền Actions, repository, ref main và trạng thái workflow |
| Không thấy thư mục json | Preview không tạo; send/auto cần ghi thành công trên main |
| Không ghi được trạng thái | Kiểm tra contents: write, chính sách repository và bảo vệ nhánh |
| Telegram báo 400/401/403/404 | Kiểm tra token, ID nhóm/topic, quyền gửi và tư cách thành viên của bot |
| Telegram báo 429 | Chờ hết giới hạn gửi rồi chạy lại; công cụ không gửi dồn ngay trong cùng lượt |
| Log báo sending | Kiểm tra nhóm và làm theo mục 10; không xóa ghi nhớ |
| PDF không đọc được | Kiểm tra PDF scan, bố cục bảng và giới hạn kích thước |
| Bài mong muốn không được nhận | Đối chiếu bộ lọc và phạm vi theo dõi ở mục 9 |
| Bản cũ không chuyển được ghi nhớ | Giữ bản cũ; kiểm tra quyền đọc và dữ liệu hợp lệ trước khi chạy tiếp |

## 13. Tài liệu tham khảo

- [Telegram Bot API — sendDocument](https://core.telegram.org/bots/api#senddocument)
- [GitHub — Workflow dispatch](https://docs.github.com/en/rest/actions/workflows#create-a-workflow-dispatch-event)
- [GitHub — Sử dụng Secrets trong Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions)
- [GitHub — Cú pháp workflow](https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions)
