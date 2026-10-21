"""GetLichThi: theo dõi lịch thi KTHP và gửi Telegram trong repository độc lập."""
import base64
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

import kma_lichthi_core as core

VN = ZoneInfo("Asia/Ho_Chi_Minh")
STEPS = ("notice", "pdf", "json")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


class StopRun(ValueError):
    """Không tiếp tục gửi nếu không còn chắc chắn về ghi nhớ hoặc cấu hình."""


class TelegramRejected(ValueError):
    """Telegram trả lời rõ ràng rằng yêu cầu không được thực hiện."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise StopRun("Đã chặn chuyển hướng khi gửi yêu cầu có token.")


class State:
    def __init__(self):
        self.repo = os.environ.get("GITHUB_REPOSITORY", "")
        self.token = os.environ.get("GH_STATE_TOKEN", "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", self.repo) or not self.token:
            raise StopRun("Thiếu GITHUB_REPOSITORY hoặc GH_STATE_TOKEN.")
        self.branch = "main"
        self.path = "/contents/json/lichthi_state.json"
        self.sha = None
        migrated = False
        try:
            item = self.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise StopRun(f"Không đọc được ghi nhớ lịch thi: HTTP {exc.code}.") from None
            # Chỉ tìm bản cũ khi main chưa có file. Không xóa hoặc sửa nhánh cũ.
            try:
                item = self.read("kma-lichthi-state")
            except urllib.error.HTTPError as legacy_error:
                if legacy_error.code != 404:
                    raise StopRun("Không đọc được ghi nhớ cũ; dừng để tránh gửi lặp.") from None
                self.data = {"version": 1, "known_articles": [], "articles": {}, "deliveries": {}, "pdfs": {}}
                return
            migrated = True
        else:
            self.sha = item["sha"]
        try:
            self.data = json.loads(base64.b64decode(item["content"]))
            self.validate()
        except Exception:
            raise StopRun("Ghi nhớ lịch thi không hợp lệ; dừng để tránh gửi lặp.") from None
        if migrated:
            self.save()
            print("Đã chuyển ghi nhớ cũ sang json/lichthi_state.json trên main.", flush=True)

    def validate(self):
        d = self.data
        if not isinstance(d, dict) or d.get("version") != 1:
            raise ValueError("version")
        if not isinstance(d.get("known_articles"), list):
            raise ValueError("known_articles")
        for key in ("articles", "deliveries", "pdfs"):
            if not isinstance(d.get(key), dict):
                raise ValueError(key)
        for entry in d["deliveries"].values():
            if not isinstance(entry, dict) or not isinstance(entry.get("steps"), dict):
                raise ValueError("steps")
            for step in entry["steps"].values():
                if not isinstance(step, dict) or step.get("status") not in ("sending", "sent"):
                    raise ValueError("status")

    def api(self, method, suffix, payload=None):
        headers = {"Authorization": "Bearer " + self.token,
                   "Accept": "application/vnd.github+json",
                   "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "KMA-LichThi"}
        body = None if payload is None else encode(payload)
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request("https://api.github.com/repos/" + self.repo + suffix,
                                     data=body, headers=headers, method=method)
        with urllib.request.build_opener(NoRedirect()).open(req, timeout=45) as response:
            return json.load(response)

    def read(self, branch=None):
        return self.api("GET", self.path + "?" + urllib.parse.urlencode({"ref": branch or self.branch}))

    def save(self):
        payload = {"message": "Update KMA lichthi state [skip ci]", "branch": self.branch,
                   "content": base64.b64encode(encode(self.data)).decode("ascii")}
        if self.sha:
            payload["sha"] = self.sha
        for attempt in range(3):
            try:
                result = self.api("PUT", self.path, payload)
                self.sha = result["content"]["sha"]
                return
            except urllib.error.HTTPError as exc:
                # Chỉ thử lại xung đột khi chính file lịch thi vẫn giữ nguyên SHA.
                if exc.code not in (409, 422) or attempt == 2:
                    raise StopRun(f"Không lưu được ghi nhớ lịch thi: HTTP {exc.code}; đã dừng gửi.") from None
                try:
                    current = self.read()["sha"]
                except urllib.error.HTTPError as read_error:
                    if read_error.code != 404:
                        raise StopRun("Không xác minh được ghi nhớ sau xung đột.") from None
                    current = None
                if current != self.sha:
                    raise StopRun("File ghi nhớ lịch thi đã thay đổi ở lượt khác; dừng gửi.")
                time.sleep(1 + attempt)
            except Exception:
                raise StopRun("Chưa xác nhận lưu ghi nhớ; đã dừng gửi. Kiểm tra lần chạy sau.") from None


class ArticleMeta(HTMLParser):
    def __init__(self, page):
        super().__init__(convert_charrefs=True)
        self.h1 = False
        self.title = []
        self.modified = ""
        self.feed(page)

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        if tag == "h1":
            self.h1 = True
        key = props.get("itemprop", props.get("property", "")).lower()
        if key in ("datemodified", "article:modified_time"):
            self.modified = props.get("content", props.get("datetime", "")) or self.modified

    def handle_endtag(self, tag):
        if tag == "h1":
            self.h1 = False

    def handle_data(self, data):
        if self.h1:
            self.title.append(data)


def modified_date(raw):
    if not raw:
        return "Không có thông tin từ nguồn"
    try:
        dt = parsedate_to_datetime(raw)
    except (ValueError, TypeError, IndexError):
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return "Không có thông tin từ nguồn"
    # Ngày chỉnh sửa giữ theo nguồn; chỉ thời điểm kiểm tra đổi sang giờ Việt Nam.
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    return f"{dt.day:02d}/{months[dt.month - 1]}/{dt.year}"


def notice_text(article, pdf_url, modified, checked):
    title = core.clean(article["title"])[:600]
    return (f"📢 CÓ LỊCH THI MỚI\n\n{title}\n\n"
            f"🔗 {article['url']}\nNgày chỉnh sửa: {modified_date(modified)}\n"
            f"Kiểm tra: {checked} (giờ Việt Nam)\n\n📎 File: {pdf_url}")


class Telegram:
    def __init__(self):
        self.token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        self.thread = os.environ.get("TELEGRAM_THREAD_ID", "").strip()
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]+", self.token) or not re.fullmatch(r"-?\d+|@[A-Za-z0-9_]+", self.chat):
            raise StopRun("Thiếu/sai Secrets TELEGRAM_BOT_TOKEN hoặc TELEGRAM_CHAT_ID.")
        if self.thread and not re.fullmatch(r"[1-9]\d*", self.thread):
            raise StopRun("TELEGRAM_THREAD_ID phải là ID topic dạng số dương hoặc để trống.")

    def send(self, kind, text=None, filename=None, content=None, reply_id=None):
        fields = {"chat_id": self.chat}
        if self.thread:
            fields["message_thread_id"] = self.thread
        if reply_id:
            fields["reply_parameters"] = json.dumps({"message_id": reply_id, "allow_sending_without_reply": True})
        if kind == "notice":
            fields["text"] = text
            fields["link_preview_options"] = '{"is_disabled":true}'
            body = urllib.parse.urlencode(fields).encode("utf-8")
            content_type = "application/x-www-form-urlencoded"
            method = "sendMessage"
        else:
            method = "sendDocument"
            fields["caption"] = "📄 PDF lịch thi gốc" if kind == "pdf" else "🗂 JSON lịch thi đã xử lý"
            boundary = "KMA" + secrets.token_hex(24)
            parts = []
            for name, value in fields.items():
                parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
            mime = "application/pdf" if kind == "pdf" else "application/json"
            parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\nContent-Type: {mime}\r\n\r\n').encode("utf-8"))
            parts.extend((content, f"\r\n--{boundary}--\r\n".encode("ascii")))
            body = b"".join(parts)
            content_type = "multipart/form-data; boundary=" + boundary
        req = urllib.request.Request("https://api.telegram.org/bot" + self.token + "/" + method,
                                     data=body, headers={"Content-Type": content_type}, method="POST")
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=120) as response:
                result = json.loads(response.read(1024 * 1024))
        except urllib.error.HTTPError as exc:
            # Chỉ coi là từ chối chắc chắn nếu có response JSON chính chủ hợp lệ.
            # Không in exception/request vì URL chứa token.
            try:
                error = json.loads(exc.read(65536))
            except Exception:
                raise StopRun("Chưa rõ Telegram đã nhận hay chưa; giữ sending để tránh gửi lặp.") from None
            if error.get("ok") is False and error.get("error_code") in (400, 401, 403, 404, 429):
                raise TelegramRejected(f"Telegram từ chối: mã {error['error_code']}; kiểm tra bot, nhóm và quyền gửi.") from None
            raise StopRun("Telegram trả lỗi chưa xác định; giữ sending, kiểm tra nhóm trước khi gửi lại.") from None
        except Exception:
            raise StopRun("Mất kết nối/chưa rõ Telegram đã nhận hay chưa; giữ sending để tránh gửi lặp.") from None
        if result.get("ok") is False and result.get("error_code") in (400, 401, 403, 404, 429):
            raise TelegramRejected(f"Telegram từ chối: mã {result['error_code']}.")
        try:
            if result.get("ok") is not True:
                raise ValueError("ok")
            return int(result["result"]["message_id"])
        except Exception:
            raise StopRun("Thiếu xác nhận message_id; giữ sending, kiểm tra nhóm Telegram.") from None


def deliver(store, telegram, article, url, pdf, records, modified, checked, retry_uncertain=False):
    # Nội dung giống hệt ở các link khác nhau chỉ gửi một lần trong cùng nhóm/topic.
    destination = digest((telegram.chat + "|" + telegram.thread).encode())
    key = digest((destination + "|" + digest(pdf)).encode())
    entry = store.data["deliveries"].setdefault(key, {"steps": {}, "checked": checked})
    steps = entry["steps"]
    raw_json = json.dumps(records, ensure_ascii=False, indent=4).encode("utf-8")
    if len(raw_json) > 49 * 1024 * 1024:
        raise ValueError("JSON vượt giới hạn gửi Telegram.")
    stem = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem[:-4]).strip("._")[:100] or "lichthi"
    basename = stem + "_" + digest(pdf)[:10]
    text = notice_text(article, url, modified, entry["checked"])
    if len(text.encode("utf-16-le")) // 2 > 4096:
        raise ValueError("Tiêu đề/đường dẫn quá dài để gửi thông báo Telegram.")
    for step in STEPS:
        status = steps.get(step, {}).get("status")
        if status == "sent":
            continue
        if status == "sending" and not retry_uncertain:
            raise StopRun(f"Mục {key[:12]} bước {step} đang sending. Kiểm tra nhóm; xem hướng dẫn xử lý trong README.md.")
        steps[step] = {"status": "sending", "time": datetime.now(timezone.utc).isoformat()}
        store.save()  # Bắt buộc lưu bền trước mọi lần POST.
        try:
            kwargs = {"reply_id": steps.get("notice", {}).get("message_id")}
            if step == "notice":
                kwargs["text"] = text
            else:
                kwargs["filename"] = basename + ".pdf" if step == "pdf" else "lichthi_" + basename + ".json"
                kwargs["content"] = pdf if step == "pdf" else raw_json
            message_id = telegram.send(step, **kwargs)
        except TelegramRejected:
            del steps[step]
            store.save()
            raise
        steps[step] = {"status": "sent", "message_id": message_id,
                       "time": datetime.now(timezone.utc).isoformat()}
        store.save()
        time.sleep(3.1)  # Giãn tin dưới 20 tin/phút trong nhóm cho riêng workflow này.
    return key


def fetch_pdf(url):
    with core._schedule_request(url, timeout=90) as response:
        content = response.read(core.AUTO_SCHEDULE_MAX_PDF_BYTES + 1)
        modified = response.headers.get("Last-Modified", "")
    if len(content) > core.AUTO_SCHEDULE_MAX_PDF_BYTES or not content.startswith(b"%PDF-"):
        raise ValueError("PDF không hợp lệ hoặc vượt giới hạn 49MiB.")
    return content, modified


def parse_pdf(pdf):
    with tempfile.TemporaryDirectory(prefix="kma-lichthi-") as temp:
        path = Path(temp) / "source.pdf"
        path.write_bytes(pdf)
        records = core.merge_schedule_records(core.extract_schedule(str(path)))
    records = [r for r in records if core._schedule_text(r.get("Môn thi")) not in ("mon thi", "ten mon thi")]
    if not records or not core._schedule_valid_records(records):
        raise ValueError("PDF không có bảng lịch thi đọc được; có thể cần OCR hoặc xử lý thủ công.")
    return records


def run(mode="preview", retry_uncertain=False):
    if mode not in ("preview", "auto", "send"):
        raise ValueError("Chế độ không hợp lệ.")
    sending = mode == "send" or (mode == "auto" and os.environ.get("KMA_ENABLE_LICHTHI", "false").lower() == "true")
    if mode == "auto" and not sending:
        print("Lịch thi đang tắt (KMA_ENABLE_LICHTHI != true).", flush=True)
        return
    telegram = Telegram() if sending else None
    store = State() if sending else None
    checked = datetime.now(VN).strftime("%d/%m/%Y %H:%M:%S")
    articles = core._schedule_candidate_articles()
    if store is None or "initialized" not in store.data:
        selected = articles[:1]
    else:
        known = set(store.data["known_articles"])
        tracked = store.data["articles"]
        selected = [a for i, a in enumerate(articles) if str(a["id"]) not in known
                    or (i < 3 and str(a["id"]) in tracked)]
        selected_ids = {str(a["id"]) for a in selected}
        # Bài lỗi vẫn được thử tiếp kể cả khi đã rời trang đầu.
        selected += [a for aid, a in tracked.items() if a.get("pending") and aid not in selected_ids]
    if store:
        for article in selected:
            store.data["articles"][str(article["id"])] = {**article, "pending": True}
        store.data["known_articles"] = sorted(set(store.data["known_articles"]) | {str(a["id"]) for a in articles})
        store.data["initialized"] = True
        store.save()
    print(f"Kiểm tra {len(selected)} bài lịch thi. Chế độ: {'GỬI TELEGRAM' if sending else 'XEM THỬ'}. Giờ VN: {checked}", flush=True)
    errors = 0
    for article in selected:
        article_failed = False
        try:
            page = core._schedule_fetch(article["url"])
            meta = ArticleMeta(page)
            article = {**article, "title": core.clean(" ".join(meta.title)) or article["title"]}
            urls = core._schedule_pdf_urls(page, article["url"])
            if not urls:
                raise ValueError("Bài chưa có PDF; sẽ kiểm tra lại lần sau.")
            for index, url in enumerate(urls, 1):
                try:
                    pdf, modified = fetch_pdf(url)
                    pdf_hash = digest(pdf)
                    # Đọc SHA256 mỗi lượt để phát hiện thay PDF cùng URL, không lệ thuộc HEAD/cache.
                    if store:
                        dest = digest((telegram.chat + "|" + telegram.thread).encode())
                        key = digest((dest + "|" + pdf_hash).encode())
                        steps = store.data["deliveries"].get(key, {}).get("steps", {})
                        if all(steps.get(s, {}).get("status") == "sent" for s in STEPS):
                            print(f"Bài {article['id']} PDF {index}: đã gửi đủ, bỏ qua.", flush=True)
                            continue
                    records = parse_pdf(pdf)
                    print(f"Bài {article['id']} PDF {index}: {len(records)} dòng lịch thi; SHA256 {pdf_hash[:12]}.", flush=True)
                    if store:
                        deliver(store, telegram, article, url, pdf, records, modified or meta.modified,
                                checked, retry_uncertain=retry_uncertain)
                        store.data["pdfs"][digest(url.encode())] = {"sha256": pdf_hash, "article_id": article["id"]}
                        store.save()
                        print("Đã gửi thông báo + PDF + JSON.", flush=True)
                    else:
                        print(notice_text(article, url, modified or meta.modified, checked), flush=True)
                        print("Xem thử: không gửi Telegram, không ghi nhớ, không đưa PDF/JSON vào git.", flush=True)
                except StopRun:
                    raise
                except TelegramRejected:
                    raise  # Sai cấu hình/quá giới hạn: dừng, không gửi dồn các PDF tiếp theo.
                except Exception as exc:
                    article_failed = True
                    errors += 1
                    print(f"Bài {article['id']} PDF {index}: lỗi {type(exc).__name__}; chưa đánh dấu hoàn tất.", flush=True)
        except (StopRun, TelegramRejected):
            raise
        except Exception as exc:
            article_failed = True
            errors += 1
            print(f"Bài {article['id']}: lỗi {type(exc).__name__}; sẽ kiểm tra lại lần sau.", flush=True)
        if store:
            store.data["articles"][str(article["id"])]["pending"] = article_failed
            store.save()
    if errors:
        raise ValueError(f"Có {errors} lỗi khi đọc bài/PDF; chưa gửi đủ các mục tương ứng. Xem log phía trên.")
    print("Hoàn tất kiểm tra lịch thi.", flush=True)


if __name__ == "__main__":
    try:
        run(os.environ.get("KMA_LICHTHI_MODE", "preview"),
            retry_uncertain=os.environ.get("KMA_LICHTHI_RETRY_UNCERTAIN", "false").lower() == "true")
    except (StopRun, TelegramRejected) as exc:
        print("LỖI: " + str(exc), flush=True)
        sys.exit(1)
    except Exception as exc:
        # Không in exception/traceback ngoài kiểm soát vì URL Telegram chứa token.
        print("LỖI: " + type(exc).__name__ + ". Kiểm tra nguồn PDF, Secrets và quyền ghi của workflow.", flush=True)
        sys.exit(1)
