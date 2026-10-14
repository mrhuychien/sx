"""Đo tốc độ tải portal (D210) — chỉ khi trình duyệt xin đo: `?do=1` trên trang /sx, header `X-Sx-Do` trên lời gọi API.

Hook before_request / after_request (sx/hooks.py): thời gian máy chủ xử lý yêu cầu, số câu SQL và thời gian SQL → header
`Server-Timing: sx;dur=…, sql;dur=…;desc="<số câu>"`. Trình duyệt đọc được qua Resource Timing; bảng đo của portal
(public/sx/lib/do.js) tách mỗi lời gọi thành: máy chủ (trong đó SQL bao nhiêu câu, bao lâu) và đường truyền.

Yêu cầu bình thường không đo, không thêm gì. Đếm SQL bằng cách bọc execute_query của ĐÚNG đối tượng frappe.db của yêu
cầu đó (thuộc tính riêng của đối tượng, không đụng lớp Database), gỡ ra ở after_request. Không bao giờ ném lỗi: hai hook
này chạy quanh MỌI yêu cầu.
"""

import time

import frappe


def _xin_do():
    rq = getattr(frappe.local, "request", None)
    if rq is None:
        return False
    return bool(rq.headers.get("X-Sx-Do")) or rq.args.get("do") == "1"


def bat_dau(*args, **kwargs):
    """before_request: bắt đầu đo nếu được xin."""
    try:
        frappe.local.sx_do = None
        if not _xin_do():
            return
        frappe.local.sx_do = do = frappe._dict(t0=time.perf_counter(), sql=0, sql_ms=0.0, db=None)
    except Exception:
        return
    try:                       # đếm SQL hỏng thì vẫn đo được thời gian máy chủ
        db = frappe.local.db
        goc = db.execute_query

        def execute_query(query, values=None):
            t = time.perf_counter()
            try:
                return goc(query, values)
            finally:
                do.sql += 1
                do.sql_ms += (time.perf_counter() - t) * 1000

        db.execute_query = execute_query
        do.db = db
    except Exception:
        do.db = None


def ket_thuc(response=None, request=None, *args, **kwargs):
    """after_request: gỡ bộ đếm SQL, ghi Server-Timing vào câu trả lời."""
    do = getattr(frappe.local, "sx_do", None)
    if not do:
        return
    try:
        frappe.local.sx_do = None
        if do.db is not None:
            do.db.__dict__.pop("execute_query", None)      # về lại phương thức của lớp
        ms = (time.perf_counter() - do.t0) * 1000
        sql = f', sql;dur={do.sql_ms:.1f};desc="{do.sql}"' if do.db is not None else ""
        if response is not None:
            response.headers["Server-Timing"] = f"sx;dur={ms:.1f}{sql}"
    except Exception:
        pass
