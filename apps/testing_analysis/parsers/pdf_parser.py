import pdfplumber
from typing import List
from apps.testing_analysis.parsers.base_parser import BaseParser
from apps.testing_analysis.schemas import TestCaseRecord

class PDFParser(BaseParser):
    def parse(self, file_path: str) -> List[TestCaseRecord]:
        records = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    for table in tables:
                        if not table:
                            continue
                            
                        header_row_idx = None
                        col_map = {}
                        
                        # Find header
                        for row_idx, row in enumerate(table):
                            if not row: continue
                            row_str = " ".join([str(cell).strip().lower() for cell in row if cell])
                            if "id" in row_str or "status" in row_str or "result" in row_str:
                                header_row_idx = row_idx
                                for col_idx, cell in enumerate(row):
                                    mapped_name = self._normalize_column_name(cell)
                                    if mapped_name and mapped_name not in col_map:
                                        col_map[mapped_name] = col_idx
                                break
                                
                        if header_row_idx is None or not col_map:
                            continue
                            
                        forward_fill_state = {field: None for field in col_map.keys()}
                        
                        for row_idx, row in enumerate(table):
                            if row_idx <= header_row_idx or not row:
                                continue
                                
                            record_data = {}
                            is_empty_row = True
                            
                            for field_name, col_idx in col_map.items():
                                if col_idx < len(row):
                                    cell_text = str(row[col_idx]).strip() if row[col_idx] else ""
                                    if cell_text:
                                        record_data[field_name] = cell_text
                                        forward_fill_state[field_name] = cell_text
                                        is_empty_row = False
                                    else:
                                        record_data[field_name] = forward_fill_state[field_name]
                                        
                            if not is_empty_row and (record_data.get("test_case_id") or record_data.get("description")):
                                records.append(TestCaseRecord(**record_data))
        except Exception:
            pass
            
        return records
