app_name = "sx"
app_title = "SX"
app_publisher = "Rong Vang Hoang Gia"
app_description = "Portal San Xuat RVHG - so hoa san xuat banh & bot dau xanh"
app_email = "mrhuychien@gmail.com"
app_license = "MIT"
required_apps = ["frappe", "erpnext"]

# ═══ DocType Events ═══
doc_events = {
    "SX Ngay San Xuat": {"on_cancel": "sx.api.chot.on_cancel_ngay"},
}

# ═══ Fixtures ═══
fixtures = [
    {
        "doctype": "Role",
        "filters": [
            ["name", "in", ["SX Thu Kho", "SX To Tron", "SX To Dong Goi", "SX Quan Ly"]]
        ],
    },
    {"doctype": "Custom Field", "filters": [["module", "=", "SX"]]},
    {"doctype": "Print Format", "filters": [["module", "=", "SX"]]},
]

# www/sx.html tu serve /sx — khong can route rule rieng
website_route_rules = []
