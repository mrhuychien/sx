"""Đợt huỷ mẫu lưu hằng tháng (W07, D133).

Mẫu hết hạn lưu không huỷ lẻ tẻ: QC gom mẫu đến hạn thành MỘT đợt (đề xuất), Trưởng
Ban ISO xác nhận thì mẫu mới thành "Đã huỷ" — người dọn tủ không tự quyết. Trả lại
thì mẫu về "Đang lưu". Mọi chuyển trạng thái đi qua sx/api/qc.py.
"""

from frappe.model.document import Document


class SXQCDotHuyMau(Document):
    pass
