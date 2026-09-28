"""Thông tin CẤP NGÀY của QC — hiện chỉ có "hôm nay có sản xuất bột" (D98).

Vì sao tách riêng: trước D98 cờ này nằm trên TỪNG LƯỢT, và "hôm nay có bột" được
suy ra từ "đã có lượt nào bật bột chưa". Hệ quả: đầu ngày chưa có lượt nào thì bật
lên chẳng lưu vào đâu cả — tải lại trang là mất; và lượt đang làm dở thì không có
cách nào thêm phần bột vào. Có sản xuất bột hay không là chuyện của cả ngày, nên
nó phải sống ở cấp ngày.
"""

from frappe.model.document import Document


class SXQCNgay(Document):
    pass
