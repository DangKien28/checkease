import os
import re
import zipfile
import tempfile

class ArtifactPreChecker:
    # Compile regex pattern ở mức class để tái sử dụng, tăng tốc độ quét
    SECRET_REGEX = re.compile(r'(?i)(api[_-]?key|secret|token|password|auth[_-]?token)\s*=\s*["\'][a-zA-Z0-9\-_]{16,}["\']')

    def run_check(self, file_path):
        # Bước 1: Kiểm tra Magic Bytes
        try:
            with open(file_path, 'rb') as f:
                magic = f.read(4)
                if magic != b'PK\x03\x04':
                    return {
                        "is_valid": False,
                        "error_code": "INVALID_FORMAT",
                        "error_message": "The file is not a valid ZIP format."
                    }
        except Exception as e:
            return {
                "is_valid": False,
                "error_code": "FILE_READ_ERROR",
                "error_message": f"Could not read file: {str(e)}"
            }

        temp_dir = None
        try:
            # Bước 2 & 3: ZIP Bomb & Path Traversal
            total_size = 0
            file_count = 0
            MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
            MAX_FILE_COUNT = 50000

            with zipfile.ZipFile(file_path, 'r') as z:
                for info in z.infolist():
                    file_count += 1
                    total_size += info.file_size
                    
                    # Bước 2: ZIP Bomb
                    if file_count > MAX_FILE_COUNT:
                        return {
                            "is_valid": False,
                            "error_code": "ZIP_BOMB_DETECTED",
                            "error_message": "Exceeded maximum allowed number of files (>50,000)."
                        }

                    if total_size > MAX_TOTAL_SIZE:
                        return {
                            "is_valid": False,
                            "error_code": "ZIP_BOMB_DETECTED",
                            "error_message": "Exceeded maximum allowed uncompressed size (>2GB)."
                        }
                        
                    if info.compress_size > 0:
                        if (info.file_size / info.compress_size) > 100:
                            return {
                                "is_valid": False,
                                "error_code": "ZIP_BOMB_DETECTED",
                                "error_message": "Highly compressed file detected (ratio > 100)."
                            }
                    
                    # Bước 3: Path Traversal
                    if info.filename.startswith('/') or '../' in info.filename or '..\\' in info.filename:
                        return {
                            "is_valid": False,
                            "error_code": "PATH_TRAVERSAL",
                            "error_message": f"Illegal path found in zip: {info.filename}"
                        }
                        
                # Bước 4: Quét Hardcoded Secret
                temp_dir = tempfile.TemporaryDirectory()
                extract_path = temp_dir.name
                
                # Giải nén toàn bộ
                z.extractall(path=extract_path)

            for root, _, files in os.walk(extract_path):
                for file_name in files:
                    current_file_path = os.path.join(root, file_name)
                    # Dùng errors='ignore' để bỏ qua lỗi encoding khi đọc nhầm file nhị phân
                    with open(current_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if self.SECRET_REGEX.search(line):
                                relative_path = os.path.relpath(current_file_path, extract_path)
                                return {
                                    "is_valid": False,
                                    "error_code": "HARDCODED_SECRET",
                                    "error_message": f"Secret found in file: {relative_path}"
                                }

            # Bước 5: Tất cả các bài kiểm tra đều vượt qua
            return {"is_valid": True}

        except zipfile.BadZipFile:
            return {
                "is_valid": False,
                "error_code": "INVALID_FORMAT",
                "error_message": "Corrupted zip file."
            }
        except Exception as e:
            return {
                "is_valid": False,
                "error_code": "UNEXPECTED_ERROR",
                "error_message": str(e)
            }
        finally:
            # Bước 5 (tiếp): Đảm bảo xóa thư mục tạm
            if temp_dir is not None:
                temp_dir.cleanup()
