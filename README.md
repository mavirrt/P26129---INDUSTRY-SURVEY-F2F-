# P26129 – Industry Survey F2F – QC data

Dashboard kiểm tra chất lượng data phỏng vấn (QC), gồm:

- **Logic giữa các câu**: screen out, nhánh A4 → A5/A6, B1/B5, C1–C6, D2–D8, E1–E2, module H, so khớp B4 với A10…
- **So với thực tế**: thời lượng, giờ phỏng vấn, lương, số người tuyển so với quy mô công ty, câu mở chép y hệt hoặc quá ngắn, trùng SĐT, cùng PVV nhiều đáp viên cùng công ty hoặc cùng tên đường…
- **So sánh giữa các PVV**: số bài, thời lượng trung bình, bài dưới 25 phút, % bài lỗi Cao, lỗi/bài, số câu “Không rõ”.
- **Theo thành phố và quota**: tiến độ theo quota HCM/HN/ĐN và các quota trong QNR.
- **Danh sách lỗi chi tiết**: có bộ lọc theo PVV, thành phố, nhóm, mức độ, loại lỗi và mã bài.

Danh sách đầy đủ các check và ngưỡng nằm cuối trang dashboard, logic nằm trong `qc.py`.

## Xem dashboard

Bật GitHub Pages: Settings → Pages → Deploy from a branch → `main` / root. Hoặc chạy trên máy:

```bash
python -m http.server 8000   # rồi mở http://localhost:8000
```

(Mở trực tiếp file `index.html` sẽ không đọc được dữ liệu vì trình duyệt chặn.)

## Cập nhật dữ liệu

```bash
pip install google-auth requests
export GOOGLE_APPLICATION_CREDENTIALS=/duong/dan/service-account.json   # service account có quyền xem Sheet
python fetch_sheet.py          # tải tab Raw_Data của Sheet "RMIT_Industry Survey" -> data/raw.xml
python qc.py data/raw.xml      # chạy check -> data/interviews.json, data/flags.json
git add data && git commit -m "Cập nhật data QC" && git push
```

Nếu có sẵn file XML export từ SurveyToGo thì bỏ qua `fetch_sheet.py`, chạy thẳng `python qc.py duong/dan/file.xml`.

## Lưu ý

- **Mã PVV** lấy từ `SbjNam`, bỏ chữ số cuối (ví dụ 1271–1279 là PVV 127, 20051–20057 là PVV 2005). Nếu quy ước đặt SbjNam khác, sửa dòng `pvv = ...` trong `qc.py`.
- **Thời lượng** tính từ câu trả lời đầu tiên đến câu cuối cùng (theo `AnsweredTimeStamp`), không dùng cột Duration.
- **Không đưa dữ liệu cá nhân lên repo**: tên, SĐT, địa chỉ và tên công ty của đáp viên chỉ được dùng khi chạy `qc.py` để tìm trùng lặp, không ghi ra file JSON. `data/raw.xml` và file `.xlsx` đã nằm trong `.gitignore`.
