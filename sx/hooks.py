app_name = "sx"
app_title = "SX"
app_publisher = "Rong Vang Hoang Gia"
app_description = "Portal San Xuat RVHG - so hoa + truy xuat nguon goc banh & bot dau xanh"
app_email = "mrhuychien@gmail.com"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# ═══ DocType Events ═══
doc_events = {
    # D120: BOM / Item đổi giữa request -> bỏ bộ nhớ tạm get_bom_active / items_tp.
    "BOM": {"on_submit": "sx.utils.xoa_nho", "on_cancel": "sx.utils.xoa_nho",
            "on_update_after_submit": "sx.utils.xoa_nho"},
    "Item": {"on_update": "sx.utils.xoa_nho"},
    "SX Bang Don Gia": {"on_update": "sx.utils.xoa_nho", "on_trash": "sx.utils.xoa_nho"},
    # D121: QC chấm (lưu / chốt bảng vào hộp) -> trừ nợ vào hộp ngay lúc đó, thay vì
    # mỗi lần mở thẻ sổ nợ.
    # D123: lưu / xoá bảng -> ngày đó cần đồng bộ lương (không còn chốt Vào hộp).
    "SX Bang Vao Hop": {"on_update": ["sx.api.khotp.doi_soat_sau_cham",
                                      "sx.api.dongbo.sau_luu_bang"],
                        "on_submit": "sx.api.khotp.doi_soat_sau_cham",
                        "on_trash": "sx.api.dongbo.sau_luu_bang"},
    "SX Nhap Bot": {
        "on_submit": "sx.api.tang1.on_submit_nhap_bot",
        "on_cancel": "sx.api.tang1.on_cancel_nhap_bot",
    },
    # BM.07.03 — kiểm nguyên liệu đầu vào. W10 (D138): chuyển sang phiếu nhập mua
    # (Purchase Receipt); hoá đơn mua có trừ kho (đường cũ) vẫn kiểm như trước.
    # W09 (D138): mua của NCC chưa duyệt BM.07.02 → chỉ cảnh báo.
    # W14 (D139): kiểm xe BM.09.01 — chạy TRƯỚC tiep_nhan: xe không đạt ép dòng Cách ly,
    # tiep_nhan mới đưa dòng Cách ly vào kho cách ly.
    "Purchase Receipt": {
        "validate": ["sx.qc.kiem_xe.validate", "sx.qc.tiep_nhan.validate", "sx.qc.ncc.canh_bao_mua"],
        "before_submit": "sx.qc.kiem_xe.before_submit",
        "on_submit": "sx.qc.tiep_nhan.on_submit",
    },
    "Purchase Invoice": {
        "validate": ["sx.qc.tiep_nhan.validate", "sx.qc.ncc.canh_bao_mua"],
        "on_submit": "sx.qc.tiep_nhan.on_submit",
    },
    "Purchase Order": {"validate": "sx.qc.ncc.canh_bao_mua"},
    "Supplier": {"validate": "sx.qc.ncc.validate_supplier"},
    # W13 (D135): sổ khiếu nại BM.11.01 trên Issue — tự tìm lô theo (sản phẩm, HSD),
    # đóng / mở lại chỉ Ban ISO hoặc người được giao (chặn cả Desk).
    "Issue": {"validate": "sx.qc.khieu_nai.validate"},
    # W06 (D132): bán trừ kho thành phẩm phải chọn đúng lô (HSD) — truy xuất xuôi.
    # W26 (D136): hàng trả về nhập kho riêng; lô thu hồi bị khoá xuất — kiểm cả lúc
    # on_submit vì lô do ERPNext tự chọn chỉ có bundle trong on_submit.
    # W08 (D137): lô thành phẩm chưa duyệt kiểm tra xuất xưởng BM.08.04 → không bán.
    "Sales Invoice": {"validate": ["sx.api.thuhoi.kho_tra_ve", "sx.qc.kiem_xe.validate"],
                      "before_submit": ["sx.api.banhang.kiem_lo_ban", "sx.api.thuhoi.kiem_xuat",
                                        "sx.api.xuatxuong.kiem_ban", "sx.qc.kiem_xe.before_submit"],
                      "on_submit": ["sx.api.thuhoi.kiem_xuat", "sx.api.xuatxuong.kiem_ban"]},
    "Delivery Note": {"validate": "sx.api.thuhoi.kho_tra_ve",
                      "before_submit": ["sx.api.banhang.kiem_lo_ban", "sx.api.thuhoi.kiem_xuat",
                                        "sx.api.xuatxuong.kiem_ban"],
                      "on_submit": ["sx.api.thuhoi.kiem_xuat", "sx.api.xuatxuong.kiem_ban"]},
    "POS Invoice": {"before_submit": ["sx.api.thuhoi.kiem_xuat", "sx.api.xuatxuong.kiem_ban"],
                    "on_submit": ["sx.api.thuhoi.kiem_xuat", "sx.api.xuatxuong.kiem_ban"]},
    "Stock Entry": {"before_submit": "sx.api.thuhoi.kiem_xuat",
                    "on_submit": "sx.api.thuhoi.kiem_xuat"},
    "Batch": {"validate": "sx.api.thuhoi.kiem_sua_batch"},
}

# D123: lưới an toàn của đồng bộ ngầm — ngày còn dấu "cần đồng bộ" (job nền lỡ,
# worker vừa khởi động lại…) được làm trong vòng 5 phút.
scheduler_events = {
    "cron": {"*/5 * * * *": ["sx.api.dongbo.chay_tat_ca"]},
    # W17 (D143): thiết bị đo quá hạn kiểm → ngừng dùng + phiếu sự cố (một phiếu gộp mỗi ngày).
    "daily": ["sx.qc.thiet_bi.quet_qua_han"],
}

# Tạo role còn thiếu — chỉ TẠO, không sửa role đã có (D105).
after_install = ["sx.setup.dam_bao_role", "sx.api.mfg.bat_lo_he_thong"]
after_migrate = ["sx.setup.dam_bao_role", "sx.api.mfg.bat_lo_he_thong"]

# ═══ Fixtures ═══
fixtures = [
    # Role KHÔNG còn là fixture (D105): fixtures bị xoá-tạo-lại mỗi lần migrate,
    # và tạo lại role là Frappe đăng xuất người giữ role đó. Xem sx.setup.dam_bao_role.
    # Hai module: SX (cũ) và QC (D85+). Để "=" "SX" thì lần export-fixtures sau
    # lặng lẽ xoá sạch custom field của QC khỏi file.
    {"doctype": "Custom Field", "filters": [["module", "in", ["SX", "QC"]]]},
    {"doctype": "Print Format", "filters": [["module", "in", ["SX", "QC"]]]},
]

# www/sx.html tu serve /sx
website_route_rules = []
