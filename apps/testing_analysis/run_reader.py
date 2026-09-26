from pathlib import Path
from reader import read_junit_xml


sample_file = Path(__file__).parent / "samples" / "sample_junit.xml"
result = read_junit_xml(sample_file)

print("=== KẾT QUẢ PHÂN TÍCH TEST ===")
print(f"Tổng số test: {result['total']}")
print(f"PASS: {result['passed']}")
print(f"FAIL: {result['failed']}")
print(f"ERROR: {result['errors']}")
print(f"SKIP: {result['skipped']}")
print(f"Tỷ lệ PASS: {result['pass_rate']}%")

if result["failures"]:
    print("\n=== TEST CÓ LỖI ===")
    for item in result["failures"]:
        print(f"- Tên test: {item['test']}")
        print(f"  Loại lỗi: {item['type']}")
        print(f"  Thông báo: {item['message']}")
        if item["details"]:
            print(f"  Chi tiết: {item['details']}")