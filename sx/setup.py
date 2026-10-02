"""Việc chạy sau `bench install-app` / `bench migrate` (D105)."""

import frappe

from sx.config.roles import VAI_MAC_DINH


def dam_bao_role():
    """Tạo role của app nếu CHƯA có. Role đã có thì KHÔNG đụng tới.

    Không save lại role đã có là cả lý do của hàm này: save một role là Frappe tính
    lại kiểu tài khoản của mọi người giữ role đó, đổi kiểu là đăng xuất họ — xem
    chú thích VAI_MAC_DINH trong sx/config/roles.py. Và người quản trị bật / tắt
    Desk cho một role trên site thì phải giữ nguyên qua các lần deploy.
    """
    tao = []
    for ten, desk in VAI_MAC_DINH.items():
        if frappe.db.exists("Role", ten):
            continue
        frappe.get_doc({"doctype": "Role", "role_name": ten,
                        "desk_access": desk, "is_custom": 1}).insert(ignore_permissions=True)
        tao.append(ten)
    if tao:
        print("sx: đã tạo role " + ", ".join(tao))
    return tao
