"""Ngưỡng và khung giờ QC. Đọc qua sx/qc/nguong.py, đừng đọc thẳng Single này:
site chưa migrate thì mọi ô là 0, mà 0 ở đây nghĩa là "tắt mọi ngưỡng"."""

from frappe.model.document import Document


class SXQCSetting(Document):
    pass
