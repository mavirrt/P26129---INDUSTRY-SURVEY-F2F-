# P26129 – Industry Survey F2F – QC data

Dashboard kiểm tra chất lượng data phỏng vấn (QC), gồm:

- **Logic giữa các câu**: screen out, nhánh A4 → A5/A6, B1/B5, C1–C6, D2–D8, E1–E2, module H, so khớp B4 với A10…
- **So với thực tế**: thời lượng, giờ phỏng vấn, lương, số người tuyển so với quy mô công ty, câu mở chép y hệt hoặc quá ngắn, trùng SĐT, cùng PVV nhiều đáp viên cùng công ty hoặc cùng tên đường…
- **So sánh giữa các PVV**: số bài, thời lượng trung bình, bài dưới 25 phút, % bài lỗi Cao, lỗi/bài, số câu “Không rõ”.
- **Theo thành phố và quota**: tiến độ theo quota HCM/HN/ĐN và các quota trong QNR.
- **Danh sách lỗi chi tiết**: có bộ lọc theo PVV, thành phố, nhóm, mức độ, loại lỗi và mã bài.

Danh sách đầy đủ các check và ngưỡng nằm cuối trang dashboard, logic nằm trong `qc.py`.

## Cách chạy

Trang `index.html` đọc thẳng tab Raw_Data (XML SurveyToGo) và Sync_Log của Google Sheet “RMIT_Industry Survey” qua link export CSV, chạy toàn bộ các check trong `qc.js` ngay trên trình duyệt, rồi tự làm mới mỗi 5 phút. Không cần chạy script hay push data.

- Sheet phải để chế độ “Bất kỳ ai có đường liên kết – Người xem”. Nếu đổi về “Bị hạn chế”, dashboard sẽ không đọc được.
- Xem online: bật GitHub Pages (Settings → Pages → Deploy from a branch → `main` / root). Hoặc chạy trên máy: `python -m http.server 8000` rồi mở http://localhost:8000.
- Muốn thêm/sửa check hoặc ngưỡng: sửa `qc.js`. Muốn sửa quota: sửa mảng `QUOTA` và `CITYQ` trong `index.html`.

## Lưu ý

- **Mã PVV** lấy từ `SbjNam`, bỏ chữ số cuối (ví dụ 1271–1279 là PVV 127, 20051–20057 là PVV 2005). Nếu quy ước đặt SbjNam khác, sửa dòng `const pvv = ...` trong `qc.js`.
- **Thời lượng** tính từ câu trả lời đầu tiên đến câu cuối cùng (theo `AnsweredTimeStamp`), không dùng cột Duration.
- **Dữ liệu cá nhân**: trang không hiện tên, SĐT, địa chỉ, tên công ty của đáp viên (chỉ dùng để tìm trùng lặp). Tuy vậy ID Sheet nằm trong code và Sheet mở quyền xem cho ai có link, nên ai tìm ra repo này đều mở được raw data.
