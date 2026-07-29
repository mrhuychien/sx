# Prompt cho Stitch — thiết kế lại UI portal `/sx`

> **Cách dùng:** Stitch nhận **một prompt cho một màn hình**. Dán khối **§0 Design system**
> vào đầu *mỗi* lần, rồi nối tiếp một trong ba khối §1/§2/§3. Sau khi có bản đầu, dùng
> §4 để yêu cầu các trạng thái phụ và §5 cho các modal.
>
> **Prompt viết bằng tiếng Anh, chữ hiển thị giữ nguyên tiếng Việt trong ngoặc kép.**
> Stitch hiểu mô tả tiếng Anh chính xác hơn nhiều, còn text trong ngoặc kép nó chép
> nguyên văn nên nhãn tiếng Việt không bị dịch sai.

---

## §0 — Design system (dán vào đầu MỌI prompt)

```
CONTEXT
Internal production-floor web app for a Vietnamese food factory that makes mung bean
cakes ("bánh đậu xanh") and bean powder ("bột đậu"). It is a data-entry + monitoring
tool, not a consumer product. All visible text is Vietnamese with full diacritics.

USERS & ENVIRONMENT — this drives every decision
- 3 users only: two QC staff who record numbers, one manager who reviews and closes
  the day. Low computer literacy. Middle-aged.
- Used standing on a factory floor, often with gloves or damp hands, under bright
  fluorescent light, on a 10-inch Android tablet mounted or handheld. Must also work
  on a phone.
- Users are interrupted constantly. Every screen must be scannable in 2 seconds and
  every action recoverable.

HARD UI CONSTRAINTS (non-negotiable)
- Minimum tap target 56x56 px. Primary action buttons 64 px tall, full width.
- Base body text 16 px minimum. Numbers that matter (kg, quantities, lot codes)
  20-28 px, bold.
- NO free-text number typing anywhere. Numbers are always entered through a custom
  on-screen numpad with huge digit keys. Design that numpad as a reusable component.
- Never an icon-only button. Every button has a Vietnamese text label.
- High contrast, works under glare. Avoid thin fonts and low-contrast grey-on-grey.
- No decorative photography, no illustrations, no marketing hero sections.
- Support both light and dark theme.

APP CHROME (present on all three screens)
- Top: a sticky "day bar" — a "◀" button, a date input, a "▶" button, a "Hôm nay"
  button, and a status chip that reads either "🔒 đã chốt" or "✎ ngày cũ" or nothing.
  This bar sets which production day every screen below is showing.
- Bottom: a 3-tab bottom navigation — "📝 Ghi số", "📦 Vào hộp", "📊 Quản lý".
- A full-width red offline banner that appears above everything: "Mất mạng — đang thử
  kết nối lại…".
- Content between them is a single scrolling column of cards.

VISUAL DIRECTION
Clean industrial utility. Card-based, 12 px radius, generous padding, one strong
accent colour (suggest a deep blue) used only for primary actions and "active" state.
Semantic colours: amber for warnings, red for errors and negative stock, green for
completed. Neutral grey scale for everything else. Flat, minimal shadows. The design
should feel like a well-made instrument panel, not a dashboard template.
```

---

## §1 — Màn hình 1: "Ghi số" (QC ghi số liệu sản xuất)

```
SCREEN: "Ghi số" — the production recording screen. Page title "Ghi số — 2026-07-29",
with a green badge "Đã chốt" appended when the day is locked. It contains 4 cards
stacked vertically, in this order.

CARD 1 — "Luồng sản xuất tầng 1" (the most important card, give it the most space)
This is a per-batch process flow tracker for turning raw mung beans into bean flour.
- At the top, one full-width primary button: "🫘 XUẤT KHO ĐỖ".
- Below it, a list of active production lots. Each lot is its own bordered block:
  - Header row: the lot code in large bold monospace ("R-300726"), then muted
    secondary text "Đỗ xanh · xuất 500 kg · rang 2026-07-30", then pushed to the far
    right an amber bold tag "còn 500 kg ở xưởng" (or a muted grey tag "đã vào kho hết").
  - Below the header, a horizontal 4-step process flow with "→" arrows between steps.
    Each step is a box containing, stacked and centre-aligned:
      1. a small muted label,
      2. the current stock in that step as a large bold number ("500 kg"),
      3. optionally a full-width action button that starts the next process step.
    The four steps and their buttons:
      "Đỗ ở xưởng" → button "Luộc + rang"
      "Đỗ ủ"       → button "Tách vỏ"
      "Đỗ vỡ"      → button "Nghiền bột"
      "Bột nền"    → no button (end of the chain)
  - A step that currently holds 0 kg is dimmed to ~50% opacity and shows NO button.
    A step holding stock is fully opaque with an accent-coloured border.
  - The flow row scrolls horizontally on narrow screens; the page itself must never
    scroll sideways.
- Empty state text: "Không có lô nào đang chạy — lô đã nghiền xong và dùng hết bột thì
  tự rụng khỏi lưu đồ."

CARD 2 — "Báo mẻ 2026-07-29"
A responsive grid of large tappable chips, one per semi-finished product (about 19 of
them, Vietnamese names like "Bột bánh trà xanh", "Đường hoán cốm"). Each chip shows the
product name and, when a number has been entered, that number large and bold next to it.
Tapping a chip opens the numpad to enter "số mẻ" (batch count). Chips with a value get
the accent border. One full-width primary button at the bottom: "LƯU BÁO MẺ".

CARD 3 — "Báo cán (bột bánh)"
Visually identical to Card 2 but a shorter list (8 items). Button: "LƯU BÁO CÁN".

CARD 4 — "Sự cố hôm nay (2)"
A compact list of incidents already logged today; each row shows incident type, minutes
of line stoppage, and an optional note. Empty state: "Chưa có sự cố." Below the list, a
secondary (not primary) full-width button to open the incident form.

Show the card in both a filled state and an empty state.
```

---

## §2 — Màn hình 2: "Vào hộp" (chấm sản lượng khoán theo người)

```
SCREEN: "Vào hộp" — piece-rate output recording. Page title "Vào hộp — 2026-07-29".
Two cards.

CARD 1 — "Bảng vào hộp (bấm tên công nhân)"
The core interaction: a supervisor walks the line and taps a worker's name to record
how many boxes that person packed.
- Top section: a dense grid of worker-name chips (about 30 workers, short Vietnamese
  names like "Nga", "Nga Trương", "Hải T."). Chips are large, 2-4 per row on tablet.
  Tapping a chip starts the entry flow.
- Below: a results table grouped by worker, columns "Công nhân | Loại công việc |
  SL | Tiền". Rows of the same worker are visually grouped together, and when a worker
  has more than one row a subtotal row labelled "Cộng" appears under their group with a
  tinted background. Each quantity cell is itself tappable to correct the number in
  place. Money is formatted in Vietnamese đồng.
- A summary strip at the bottom of the card: total boxes and total money, large.
- Secondary actions as a row of smaller buttons: "Chấm ăn ca / ăn đêm" and
  "Copy sản lượng".
- Empty state: "Chưa có dòng nào."
- When the day is locked, the whole card becomes read-only: chips and quantity cells
  lose their affordance and the header reads "(đã chốt — chỉ xem)".

CARD 2 — "Sự cố hôm nay" — same component as on the "Ghi số" screen.

ALSO DESIGN THESE THREE BOTTOM SHEETS / MODALS FOR THIS SCREEN

A) "Nga — chọn loại công việc"
A search field with placeholder "Tìm loại công việc…" at the top. Then a section
"Dùng gần đây" showing 3-5 large chips. Then a section "Tất cả loại công việc" listing
job types; each row shows the job name in bold, and on the right the unit price and a
small muted count of how many product SKUs it covers, e.g. "Vào hộp 300 · 1.200 đ · 3 SKU".
Rows must be at least 64 px tall.

B) The numpad — a reusable full-screen-on-phone / centred-dialog-on-tablet component.
Title line describing what is being entered (e.g. "Nga — Vào hộp 300"), the current
value displayed very large with its unit, then a 3x4 grid of huge digit keys plus a
decimal point and a backspace, then two buttons "HUỶ" and "XONG".

C) "Chấm ăn ca / ăn đêm"
A list of workers, each row with the worker name and two independent toggle chips "Ca"
and "Đêm". At the top two bulk buttons: "Tất cả ăn ca" and "Bỏ hết". A primary "LƯU"
button pinned at the bottom.
```

---

## §3 — Màn hình 3: "Quản lý" (chốt sổ + theo dõi)

```
SCREEN: "Quản lý" — the manager's screen. Two action cards at the very top, then a
monitoring dashboard below. Never bury the closing action under the charts.

CARD 1 — "Chốt ngày" (day closing) — has two distinct states, design BOTH.
- Open state: explanatory line about what closing does, then one very prominent
  full-width primary button "CHỐT NGÀY". Tapping it opens a two-step confirmation
  dialog (a summary of what will be posted, then a final confirm) because the action
  writes inventory and payroll records.
- Closed state: a green success block "✅ Ngày đã chốt. Kho + lương khoán đã ghi nhận.",
  a muted explanation, a red destructive full-width button "HUỶ CHỐT NGÀY ĐỂ SỬA", and
  below it a collapsible section "Chứng từ đã tạo (14) — bấm để mở" listing generated
  documents as tappable rows, cancelled ones struck through with a grey "đã huỷ" tag.
- Also design a post-close dialog "✅ Đã chốt — có cảnh báo" that lists soft warnings as
  bullet points with one button "ĐÃ HIỂU".

CARD 2 — "Tồn bán thành phẩm theo luồng" (semi-finished stock, read-only)
Two production chains stacked vertically. Each chain is a bordered block:
- Header: chain name in bold ("Bánh đậu xanh" / "Bột đậu"), and at the far right an
  amber bold tag "26.692 kg bán thành phẩm".
- Below: a horizontal flow of stage boxes joined by "→" arrows. Each stage box contains,
  centre-aligned: a small muted stage label (with an optional tiny grey pill "chung"
  meaning the stage is shared between both chains), then the stage total as a large bold
  number, then a thin divider, then a left-aligned mini list of the individual products
  currently in stock — product name on the left (truncated with ellipsis), weight bold on
  the right, and for some stages an extra small muted suffix like "6 mẻ".
- Stage boxes with stock: full opacity, accent border. Empty stages: dimmed, showing the
  text "hết hàng". Any stage containing a negative stock figure gets a RED border and the
  offending line turns red — negative stock is an error that must be impossible to miss.
- Chain 1 stages: "Đỗ ở xưởng" → "Bột nền" → "Đường hoán" → "Bột bánh" → "Thành phẩm".
- Chain 2 stages: "Đỗ ở xưởng" → "Bột nền" → "Bột đậu" → "Thành phẩm".
- The "Thành phẩm" box is narrower and shows a large count plus "8/14 SKU còn hàng".

DASHBOARD SECTION BELOW (section heading "Theo dõi")
- Alert banners at the top when relevant, red: "⚠ Tồn BTP ÂM (quên báo mẻ?): …" and
  "⚠ Cán > Trộn: …".
- A search block "Truy xuất lô — nhập mã batch TP" with a text input (placeholder
  "VD: BB-TT-230726") and a "TRUY XUẤT" button. Its result is an indented recursive
  tree showing the traceability chain: finished product → semi-finished batches →
  roasting lot → supplier bean lot, each node with an emoji marker, the batch code bold,
  and the item name plus kg in muted text. Indentation must make depth obvious.
- A segmented control "7 ngày / 30 ngày".
- A row of 4 KPI tiles: "Sản lượng" (boxes), "Lương SP" (money), "Dừng sự cố" (minutes),
  "SKU đã đóng" (count). Big number, small label, optional muted sub-line.
- A line chart card "Sản lượng theo ngày".
- Three data table cards: "Sản lượng theo SKU", "Năng suất vào hộp theo người",
  "Mẻ trộn vs cán (bột bánh)" — the last one highlights warning rows with a tinted
  background.
- A final card of external links styled as a list of text links with a "↗" suffix.
```

---

## §4 — Trạng thái phụ (yêu cầu thêm sau khi có bản đầu)

```
Now produce the supporting states for the screens above, matching the same design system:
1. Loading state for a card — a skeleton, not a spinner, with the card title already visible.
2. Empty state for each card, using the Vietnamese copy given earlier.
3. Inline error state inside a card: a red-tinted block with the error message and a
   "Thử lại" button.
4. The read-only "đã chốt" variant of the "Ghi số" and "Vào hộp" screens, where all inputs
   are visibly disabled and a green "Đã chốt" badge sits next to the page title.
5. A toast notification component, bottom-centred, in success / warning / error variants.
6. A generic confirmation dialog and the two-step destructive confirmation dialog.
7. The offline banner state.
8. Dark theme versions of all three main screens.
```

---

## §5 — Modal đặc biệt: hiện mã lô để ghi tay ra thẻ

```
Design a full-screen result dialog shown right after a production lot is created.
Its single job: the operator must copy a code by hand onto a paper tag hanging on the
bean bin, standing on the factory floor.
- Title "Đã xuất kho — ghi mã lô ra thẻ".
- The lot code "R-300726" displayed ENORMOUS — as large as the screen allows, bold,
  monospace, high contrast, generous letter spacing, centred. This is the entire point
  of the screen; everything else is secondary.
- One line of supporting text below: "Rang ngày 2026-07-30. Đỗ đã chuyển sang kho Xưởng."
- One full-width primary button "XONG".
Design a second variant of the same dialog used after each process step completes:
title "✅ Tách vỏ", the resulting batch code large, a line "Đỗ xanh vỡ: 780 kg · hao hụt
20 kg", and the "XONG" button.
```

---

## Ghi chú khi làm việc với Stitch

- **Đưa từng màn một.** Nhồi cả 3 màn vào một prompt thì Stitch trộn lẫn các thành phần.
- **Ảnh chụp màn hình hiện tại là input mạnh hơn chữ.** Chụp 3 màn đang chạy, upload kèm
  prompt và ghi *"redesign this screen, keep the same information architecture and all
  Vietnamese labels, improve visual hierarchy, spacing and readability"* — kết quả bám
  nghiệp vụ sát hơn hẳn mô tả suông.
- **Đừng để Stitch tự nghĩ nội dung.** Mọi nhãn tiếng Việt đã cho sẵn trong ngoặc kép;
  nếu nó tự chế chữ mới thì nhắc *"use exactly the Vietnamese labels I provided"*.
- **Chốt hai ràng buộc trước khi tinh chỉnh màu mè:** tap target 56 px và không gõ số
  bằng bàn phím hệ thống. Hai thứ này quyết định app dùng được hay không trên sàn xưởng,
  đẹp mà mất chúng thì hỏng.
- Khi có bản ưng ý, xuất Figma rồi gửi tôi ảnh + mã màu/khoảng cách — tôi áp vào
  `sx/public/sx/shell.css` (toàn bộ giao diện dùng biến CSS và tiền tố `sx-`, đổi da
  không phải sửa logic).
