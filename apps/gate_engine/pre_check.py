import os
import re
import zipfile
import tempfile

class ArtifactPreChecker:
    SECRET_REGEX = re.compile(r'(?i)(api[_-]?key|secret|token|password|auth[_-]?token)\s*=\s*["\'][a-zA-Z0-9\-_]{16,}["\']')

    def run_check(self, file_path):
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
            total_size = 0
            file_count = 0
            MAX_TOTAL_SIZE = 2 * 1024 * 1024 * 1024 
            MAX_FILE_COUNT = 50000

            with zipfile.ZipFile(file_path, 'r') as z:
                for info in z.infolist():
                    file_count += 1
                    total_size += info.file_size
                    
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
                    
                    if info.filename.startswith('/') or '../' in info.filename or '..\\' in info.filename:
                        return {
                            "is_valid": False,
                            "error_code": "PATH_TRAVERSAL",
                            "error_message": f"Illegal path found in zip: {info.filename}"
                        }
                        
                from django.conf import settings
                project_tmp_dir = os.path.join(settings.BASE_DIR, 'tmp')
                os.makedirs(project_tmp_dir, exist_ok=True)
                temp_dir = tempfile.TemporaryDirectory(dir=project_tmp_dir)
                extract_path = temp_dir.name
                
                z.extractall(path=extract_path)

            for root, _, files in os.walk(extract_path):
                for file_name in files:
                    if '.venv' in root or file_name.endswith('.exe') or file_name.endswith('.dll') or file_name.endswith('.pyc'):
                        continue
                    current_file_path = os.path.join(root, file_name)
                    with open(current_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            if self.SECRET_REGEX.search(line):
                                relative_path = os.path.relpath(current_file_path, extract_path)
                                return {
                                    "is_valid": False,
                                    "error_code": "HARDCODED_SECRET",
                                    "error_message": f"Secret found in file: {relative_path}"
                                }

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
            if temp_dir is not None:
                temp_dir.cleanup()

