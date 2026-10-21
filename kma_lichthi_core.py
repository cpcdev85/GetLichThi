"""Bộ lọc và xử lý lịch thi từ kmaschedulev6(2).pyw của cPcDev; không có GUI/admin."""
import html as html_lib
import re
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from html.parser import HTMLParser

import pdfplumber

SCHEDULE_FIELDS = ("Môn thi", "Hình thức thi", "Khóa đào tạo", "Thời gian bắt đầu thi")
AUTO_SCHEDULE_HOME_URL = "https://ktdbcl.actvn.edu.vn/"
AUTO_SCHEDULE_LIST_URL = "https://ktdbcl.actvn.edu.vn/khao-thi/to-chuc-thi/lich-thi.html"
AUTO_SCHEDULE_MAX_PDF_BYTES = 49 * 1024 * 1024
AUTO_USER_AGENT = "Mozilla/5.0 (KMASchedule-LichThi-Actions)"


def clean(value):
    return " ".join(str(value or "").split())


WEEKDAY_MAP = {
    "hai": "T2",
    "ba": "T3",
    "tư": "T4",
    "tu": "T4",
    "năm": "T5",
    "nam": "T5",
    "sáu": "T6",
    "sau": "T6",
    "bảy": "T7",
    "bay": "T7",
}


def normalize_cohort(value):
    """Chuẩn hóa khóa đào tạo nhưng GIỮ đúng chi nhánh.

    Quy ước:
    - KMA: A22 / AT22  -> A22   (không có N)
    - KMP: A22N / AT22N / AT22N01 -> A22N (có N)

    Không tự thêm chữ N. Các mã ghép như A21C9D8, A22C10D9, C7, D8...
    được giữ nguyên như trong tài liệu gốc.
    """
    original = clean(value)
    raw = original.upper()
    compact = re.sub(r"[^A-Z0-9]", "", raw)
    compact = compact.replace("I", "1").replace("L", "1").replace("O", "0")

    # KMP: có N. Tesseract đôi khi đọc T -> 1, ví dụ AT22N02 -> A122N02.
    match = re.fullmatch(r"A[T1](\d{2})N\d*", compact)
    if match:
        return f"A{match.group(1)}N"

    match = re.fullmatch(r"A(\d{2})N\d*", compact)
    if match:
        return f"A{match.group(1)}N"

    # KMA: không có N. Tuyệt đối không tự thêm N.
    match = re.fullmatch(r"A[T1](\d{2})", compact)
    if match:
        return f"A{match.group(1)}"

    match = re.fullmatch(r"A(\d{2})", compact)
    if match:
        return f"A{match.group(1)}"

    # Các mã khóa ghép / hệ khác giữ nguyên để không làm sai dữ liệu PDF gốc.
    return original


def parse_schedule_time(value):
    """Tách giờ, thứ và ngày để phục vụ việc gộp các ca cùng ngày."""
    value = clean(value)
    if not value:
        return None

    match = re.fullmatch(
        r"((?:\d{1,2}\s*h)(?:\s*,\s*\d{1,2}\s*h)*)\s+(T[2-7]|CN)\s+(\d{1,2}/\d{1,2}/\d{4})",
        value,
        re.IGNORECASE,
    )
    if match:
        hours = [int(hour) for hour in re.findall(r"\d{1,2}", match.group(1))]
        return hours, match.group(2).upper(), match.group(3)

    match = re.fullmatch(
        r"(\d{1,2})\s*giờ\s+(?:thứ\s+([A-Za-zÀ-ỹ]+)|(chủ\s*nhật))\s+(?:ngày\s+)?(\d{1,2}/\d{1,2}/\d{4})",
        value,
        re.IGNORECASE,
    )
    if match:
        hour = int(match.group(1))
        if match.group(3):
            weekday = "CN"
        else:
            weekday = WEEKDAY_MAP.get(match.group(2).lower())
            if not weekday:
                return None
        return [hour], weekday, match.group(4)

    return None


def _subject_compare_key(value):
    """Khóa so sánh tên môn, bỏ khác biệt dấu/case/ký tự OCR thừa."""
    value = unicodedata.normalize("NFD", clean(value).lower())
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def _subject_quality(value):
    """Ưu tiên biến thể tên môn sạch và có dấu tiếng Việt đầy đủ hơn."""
    value = clean(value)
    letters = sum(ch.isalpha() for ch in value)
    vietnamese_marks = sum(ord(ch) > 127 and ch.isalpha() for ch in value)
    suspicious = sum(ch in "|Œ©=~_{}[]<>" for ch in value)
    # Các từ OCR tiếng Anh/không dấu kiểu 'hoc', 'toan', 'thuong' bị giảm nhẹ.
    accentless_words = len(re.findall(r"\b(?:hoc|toan|thuong|mai|dien|tri|nghia|xa|hoi|quan|ly)\b", value.lower()))
    return letters + vietnamese_marks * 3 - suspicious * 8 - accentless_words * 2


def _same_subject_for_merge(a, b):
    """Cho phép gộp hai tên môn bị sai OCR nhẹ nhưng thực chất là cùng môn."""
    ka = _subject_compare_key(a)
    kb = _subject_compare_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    # Chỉ dùng ngưỡng cao để tránh gộp nhầm hai môn khác nhau.
    return SequenceMatcher(None, ka, kb).ratio() >= 0.88


def merge_schedule_records(records):
    """Gộp lịch cùng môn + hình thức + khóa + ngày, chỉ khác giờ.

    Tên môn có thể sai OCR nhẹ giữa hai ca (ví dụ 'Toán rời rac' và
    'Toán rời rạc'). Khi các trường còn lại giống nhau, tên môn tương đồng
    cao cũng được coi là cùng môn và giữ lại biến thể sạch hơn.
    """
    merged = []

    for source_item in records:
        item = dict(source_item)
        item["Môn thi"] = clean(item.get("Môn thi", ""))
        item["Hình thức thi"] = _canonical_exam_form(item.get("Hình thức thi", ""))
        item["Khóa đào tạo"] = normalize_cohort(item.get("Khóa đào tạo", ""))

        parsed = parse_schedule_time(item.get("Thời gian bắt đầu thi", ""))
        if not parsed:
            merged.append(item)
            continue

        hours, weekday, exam_date = parsed
        match_index = None
        for index, target in enumerate(merged):
            if "_hours" not in target:
                continue
            if clean(target.get("Hình thức thi", "")) != clean(item.get("Hình thức thi", "")):
                continue
            if clean(target.get("Khóa đào tạo", "")) != clean(item.get("Khóa đào tạo", "")):
                continue
            if target.get("_weekday") != weekday or target.get("_exam_date") != exam_date:
                continue
            if _same_subject_for_merge(target.get("Môn thi", ""), item.get("Môn thi", "")):
                match_index = index
                break

        if match_index is None:
            item["_hours"] = list(dict.fromkeys(hours))
            item["_weekday"] = weekday
            item["_exam_date"] = exam_date
            merged.append(item)
        else:
            target = merged[match_index]
            if _subject_quality(item["Môn thi"]) > _subject_quality(target["Môn thi"]):
                target["Môn thi"] = item["Môn thi"]
            for hour in hours:
                if hour not in target["_hours"]:
                    target["_hours"].append(hour)

    for item in merged:
        if "_hours" not in item:
            continue
        hours = sorted(item.pop("_hours"))
        weekday = item.pop("_weekday")
        exam_date = item.pop("_exam_date")
        item["Thời gian bắt đầu thi"] = (
            f"{', '.join(f'{hour}h' for hour in hours)} {weekday} {exam_date}"
        )

    return merged


def extract_schedule(pdf_path):
    """Giữ cách xử lý dòng gộp và khóa đào tạo của main.py."""
    records = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                if max((len(row) for row in table if row), default=0) < 8:
                    continue
                for row in table:
                    if not row or len(row) < 5:
                        continue
                    subject, form, cohort, start = (clean(row[i]) for i in range(1, 5))
                    if "Môn thi" in subject:
                        continue
                    if subject:
                        parts = subject.split(" ", 1)
                        if len(parts) == 2 and len(parts[0]) == 1:
                            subject = parts[0] + parts[1]
                        records.append(dict(zip(SCHEDULE_FIELDS, (subject, form, cohort, start))))
                    elif records:
                        if form:
                            records.append(dict(zip(SCHEDULE_FIELDS, (
                                records[-1]["Môn thi"], form,
                                cohort or records[-1]["Khóa đào tạo"], start,
                            ))))
                        elif start:
                            records[-1]["Thời gian bắt đầu thi"] += " " + start

    non_empty = [i for i, item in enumerate(records) if item["Khóa đào tạo"]]
    if non_empty:
        current = records[non_empty[0]]["Khóa đào tạo"]
        for i in range(non_empty[0]):
            records[i]["Khóa đào tạo"] = current
        for i in range(non_empty[0], len(records)):
            if records[i]["Khóa đào tạo"]:
                current = records[i]["Khóa đào tạo"]
            else:
                records[i]["Khóa đào tạo"] = current
    if not records:
        raise ValueError("Không tìm thấy bảng lịch thi trong PDF")
    return records


def _ascii_text(value):
    value = unicodedata.normalize("NFD", clean(value).lower())
    return "".join(ch for ch in value if unicodedata.category(ch) != "Mn")


def _canonical_exam_form(value):
    raw = clean(value)
    normalized = _ascii_text(raw)
    if "bao cao" in normalized:
        return "Báo cáo"
    if "thuc hanh" in normalized or ("thuc" in normalized and "hanh" in normalized):
        return "Thực hành"
    if "tu luan" in normalized or ("tu" in normalized and "luan" in normalized):
        return "Tự luận"
    if "trac" in normalized and "giay" in normalized:
        return "Trắc nghiệm giấy"
    if "trac" in normalized and ("may" in normalized or "tinh" in normalized):
        return "Trắc nghiệm máy tính"
    return raw


def _schedule_text(value):
    value = unicodedata.normalize("NFD", str(value or "").lower().replace("đ", "d"))
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def _is_schedule_notice(title, category=False):
    """Chỉ chọn kế hoạch/lịch THI KẾT THÚC HỌC PHẦN, không lấy thông báo khác."""
    value = _schedule_text(title)
    if any(term in value for term in (
        "phuc khao", "dinh chinh", "nop phi", "le phi", "hoc phi", "thanh toan",
        "tot nghiep", "sat hach", "danh sach thi", "ket qua thi", "diem thi",
        "bang diem", "thi thpt", "thoi khoa bieu", "bao cao hoc phan",
    )):
        return False
    if "thi" not in value.split():
        return False
    has_kthp = "kthp" in value.split() or "ket thuc hoc phan" in value
    # Nhánh category: chấp nhận một số tiêu đề lịch thi viết thiếu chữ KTHP.
    if not has_kthp and not category:
        return False
    has_plan = ("ke hoach" in value or "lich thi" in value
                or (category and "dieu chinh" in value and "hinh thuc thi" in value))
    return has_plan and (has_kthp or category)


class _ScheduleAnchorParser(HTMLParser):
    def __init__(self, html_text):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.href = None
        self.title = ""
        self.fragments = []
        self.feed(html_text)

    def handle_starttag(self, tag, attrs):
        if tag == "a" and self.href is None:
            data = dict(attrs)
            self.href = data.get("href")
            self.title = data.get("title", "")
            self.fragments = []

    def handle_data(self, data):
        if self.href is not None:
            self.fragments.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href is not None:
            self.links.append((self.href, clean(" ".join(self.fragments)), self.title))
            self.href = None
            self.title = ""
            self.fragments = []


def _schedule_article_links(page_html, base_url, category=False):
    articles = []
    ids = set()
    for href, text, tooltip in _ScheduleAnchorParser(page_html).links:
        url = urllib.parse.urljoin(base_url, html_lib.unescape(href or ""))
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != "https" or parsed.netloc.lower() != "ktdbcl.actvn.edu.vn":
            continue
        # Chỉ bài viết Joomla, không chọn menu, tài khoản, trang phân trang...
        match = re.search(r"(?:^|/)(\d{2,})-([^/]+)\.html$", parsed.path, re.I)
        if not match:
            continue
        article_id = int(match.group(1))
        if article_id in ids:
            continue
        slug = urllib.parse.unquote(match.group(2)).replace("-", " ")
        combined = " ".join((text, tooltip, slug))
        in_schedule_section = "/to-chuc-thi/lich-thi/" in parsed.path
        if not _is_schedule_notice(combined, category=category and in_schedule_section):
            continue
        ids.add(article_id)
        articles.append({"id": article_id, "url": urllib.parse.urlunsplit(
            (parsed.scheme, parsed.netloc, parsed.path, "", "")),
            "title": text if len(text) > 12 and "chi tiết" not in text.lower() else slug})
    return articles


class _SchedulePDFParser(HTMLParser):
    def __init__(self, page_html):
        super().__init__(convert_charrefs=True)
        self.targets = []
        self.feed(page_html)

    def handle_starttag(self, tag, attrs):
        props = dict(attrs)
        for key in ("href", "src", "data"):
            if props.get(key):
                self.targets.append(html_lib.unescape(props[key]))


def _schedule_pdf_urls(page_html, article_url):
    """Hỗ trợ PDF link trực tiếp và PDF.js iframe viewer.html?file=..."""
    result = []
    for raw in _SchedulePDFParser(page_html).targets:
        url = urllib.parse.urljoin(article_url, raw)
        parsed = urllib.parse.urlsplit(url)
        possibilities = []
        if parsed.path.lower().endswith(".pdf"):
            possibilities.append(url)
        # PDF nhúng: /plugins/content/pdfviewer/.../viewer.html?file=%2Ffiles%2F...
        if parsed.path.lower().endswith("viewer.html"):
            for target in urllib.parse.parse_qs(parsed.query).get("file", []):
                possibilities.append(urllib.parse.urljoin(article_url, target))
        for candidate in possibilities:
            parts = urllib.parse.urlsplit(candidate)
            # Chỉ tải PDF chính chủ, chặn SSRF và link ngoài.
            if (parts.scheme != "https" or parts.netloc.lower() != "ktdbcl.actvn.edu.vn"
                    or not parts.path.lower().endswith(".pdf")
                    or not parts.path.startswith("/files/")):
                continue
            canonical = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
            if canonical not in result:
                result.append(canonical)
    return result


class _ScheduleRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != "https" or target.netloc.lower() != "ktdbcl.actvn.edu.vn":
            raise ValueError("Đã chặn chuyển hướng PDF/trang lịch thi ra ngoài website KTĐBCL.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _schedule_request(url, method="GET", timeout=30):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc.lower() != "ktdbcl.actvn.edu.vn":
        raise ValueError("Đường dẫn lịch thi không thuộc website được phép.")
    safe_url = urllib.parse.urlunsplit((
        parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe="/%:@+,;=~"),
        parts.query, ""))
    request = urllib.request.Request(safe_url, method=method,
                                     headers={"User-Agent": AUTO_USER_AGENT})
    opener = urllib.request.build_opener(_ScheduleRedirect())
    return opener.open(request, timeout=timeout)


def _schedule_fetch(url, binary=False):
    with _schedule_request(url, timeout=90 if binary else 30) as response:
        max_bytes = AUTO_SCHEDULE_MAX_PDF_BYTES if binary else 4 * 1024 * 1024
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError("Tệp lịch thi vượt giới hạn kích thước cho phép.")
        if binary:
            if not content.startswith(b"%PDF-"):
                raise ValueError("Liên kết không trả về tệp PDF hợp lệ.")
            return content
        charset = response.headers.get_content_charset() or "utf-8"
        return content.decode(charset, errors="replace")


def _schedule_candidate_articles():
    collected = {}
    failures = []
    for url, category in ((AUTO_SCHEDULE_HOME_URL, False), (AUTO_SCHEDULE_LIST_URL, True)):
        try:
            page = _schedule_fetch(url)
            for article in _schedule_article_links(page, url, category):
                collected.setdefault(article["id"], article)
        except Exception as exc:
            failures.append(f"{url}: {exc}")
    if not collected:
        if failures:
            raise ValueError("Không đọc được thông báo lịch thi: " + " ; ".join(failures))
        raise ValueError("Không tìm thấy thông báo lịch thi KTHP phù hợp trên các trang đang theo dõi.")
    return sorted(collected.values(), key=lambda entry: entry["id"], reverse=True)


def _schedule_valid_records(records):
    # Tránh xuất bảng từ một PDF kế hoạch chung không chứa dữ liệu lịch thi.
    return any(clean(item.get("Môn thi")) and clean(item.get("Khóa đào tạo"))
               and bool(re.search(r"\d", clean(item.get("Thời gian bắt đầu thi"))))
               for item in records)
