app_name = "sx"
app_title = "SX"
app_publisher = "Rong Vang Hoang Gia"
app_description = "Portal San Xuat RVHG - so hoa + truy xuat nguon goc banh & bot dau xanh"
app_email = "mrhuychien@gmail.com"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# ═══ DocType Events ═══
doc_events = {
    "SX Ngay San Xuat": {"on_cancel": "sx.api.chot.on_cancel_ngay"},
    "SX Nhap Bot": {
        "on_submit": "sx.api.tang1.on_submit_nhap_bot",
        "on_cancel": "sx.api.tang1.on_cancel_nhap_bot",
    },
}

# ═══ Fixtures ═══
fixtures = [
    {
        "doctype": "Role",
        "filters": [["name", "in", ["SX Ghi So", "SX Vao Hop", "SX Quan Ly"]]],
    },
    {"doctype": "Custom Field", "filters": [["module", "=", "SX"]]},
    {"doctype": "Print Format", "filters": [["module", "=", "SX"]]},
]

# www/sx.html tu serve /sx
website_route_rules = []
