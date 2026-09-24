# Cảnh báo về Thiết kế MinIO Deduplication

**Quyết định thiết kế:** Khuyên dùng việc **xóa ràng buộc `UNIQUE`** ở cột `storage_key` trong Database và Model, đồng thời **giữ lại logic Deduplication** (chống trùng lặp file).

## Lý do (Tại sao nên làm vậy?)
Hệ thống thường xuyên nhận các bản build hoặc source code không có sự thay đổi lớn giữa các phiên bản (`ProjectVersion`).
- **Tiết kiệm dung lượng lưu trữ (Storage Deduplication):** Nếu người dùng upload cùng một file mã nguồn 1GB lên 10 phiên bản dự án khác nhau, chúng ta chỉ tốn đúng 1GB trên MinIO thay vì 10GB.
- **Tiền đề cho tối ưu Băng thông:** Về sau, Client có thể gửi mã hash (`sha256`) lên server kiểm tra trước. Nếu server báo file đã tồn tại, Client có thể bỏ qua bước upload, giúp tiết kiệm rất nhiều băng thông và thời gian chờ.

## ⚠️ Cảnh báo quan trọng khi thực hiện tính năng XÓA (Delete)
Do chúng ta đang thiết kế theo cấu trúc **Nhiều bản ghi `Artifact` trong Database có thể trỏ chung vào 1 file vật lý trên MinIO (quan hệ n-1)**:

- Khi một bản ghi `Artifact` bị xóa khỏi Database, **TUYỆT ĐỐI KHÔNG** được gọi MinIO để xóa file vật lý (`storage_key`) ngay lập tức.
- **Cách xử lý đúng (Garbage Collection / Reference Counting):** 
  Trước khi gọi API xóa file trên MinIO, bạn phải truy vấn DB xem còn bất kỳ bản ghi `Artifact` nào khác đang tham chiếu đến cùng `storage_key` này hay không. 
  - Nếu `count > 0`: File này đang được sử dụng bởi các Artifact khác -> Chỉ xóa bản ghi hiện tại trong DB, giữ nguyên file trên MinIO.
  - Nếu `count == 0`: Không còn Artifact nào dùng chung file này -> Có thể an toàn xóa bản ghi trong DB VÀ gọi lệnh xóa file vật lý trên MinIO.
