import docx
from typing import List
from apps.testing_analysis.parsers.base_parser import BaseParser
from apps.testing_analysis.schemas import TestCaseRecord

class WordParser(BaseParser):
    def parse(self, file_path: str) -> List[TestCaseRecord]:
        records = []
        try:
            doc = docx.Document(file_path)
        except Exception:
            return records
            
        for table in doc.tables:
            header_row_idx = None
            col_map = {}
            
            # Quét tìm header trong bảng
            for row_idx, row in enumerate(table.rows):
                row_str = " ".join([cell.text.strip().lower() for cell in row.cells if cell.text])
                if "id" in row_str or "status" in row_str or "result" in row_str:
                    header_row_idx = row_idx
                    for col_idx, cell in enumerate(row.cells):
                        mapped_name = self._normalize_column_name(cell.text)
                        if mapped_name and mapped_name not in col_map:
                            col_map[mapped_name] = col_idx
                    break
                    
            if header_row_idx is None or not col_map:
                continue
                
            # Biến cờ cho forward-fill (điền tiếp nối nếu gộp ô)
            forward_fill_state = {field: None for field in col_map.keys()}
            
            for row_idx, row in enumerate(table.rows):
                if row_idx <= header_row_idx:
                    continue
                    
                record_data = {}
                is_empty_row = True
                
                for field_name, col_idx in col_map.items():
                    if col_idx < len(row.cells):
                        cell_text = row.cells[col_idx].text.strip()
                        if cell_text:
                            record_data[field_name] = cell_text
                            forward_fill_state[field_name] = cell_text
                            is_empty_row = False
                        else:
                            # Nếu rỗng do gộp ô, lấy từ state cũ
                            record_data[field_name] = forward_fill_state[field_name]
                
                if not is_empty_row and (record_data.get("test_case_id") or record_data.get("description")):
                    records.append(TestCaseRecord(**record_data))
                    
        return records
