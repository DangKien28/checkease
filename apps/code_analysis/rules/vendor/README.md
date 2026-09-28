# Rules đã vendor (pinned)

Thư mục này chứa bộ rule Semgrep **đã vendor** (copy vào repo, có pin phiên bản).

## Quy tắc

- **Không dùng `--config=auto`** (ADR-05/ADR-12): kết quả phải tái lập được, không
  phụ thuộc registry thay đổi theo thời gian.
- Rule vendored phải ghi rõ nguồn + giấy phép + phiên bản/commit gốc vào file YAML
  hoặc kèm file `VENDORED.md` trong cùng thư mục.
- `ruleset_sha256` trong `scan_meta` băm **toàn bộ** file `.yaml/.yml` trong
  `apps/code_analysis/rules/` (gồm cả `custom/` và `vendor/`), nên mọi thay đổi
  rule đều làm đổi hash — đúng mục đích kiểm tra tính tái lập.

## Cấu trúc

```
rules/
├── custom/     # rule do Checkease viết — CHỈ rule ở đây được đọc `metadata.hard_gate`
└── vendor/     # rule copy từ nguồn ngoài (mặc định bị bỏ qua `hard_gate`)
```

## Trạng thái hiện tại

- `custom/checkease_custom.yaml`: 5 rule đầu tiên (hardcoded secret, SQL injection,
  eval/exec, assert, so sánh None).
- `vendor/`: **chưa có rule nào được vendor** — đã ghi vào Backlog (mục 14 checklist).
  Khi vendor, chạy lại bộ thực nghiệm mục 13 để đo Recall/Precision trước và sau.
