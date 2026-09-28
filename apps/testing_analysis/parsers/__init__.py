import os
from apps.testing_analysis.parsers.excel_parser import ExcelParser
from apps.testing_analysis.parsers.word_parser import WordParser
from apps.testing_analysis.parsers.pdf_parser import PDFParser
from apps.testing_analysis.parsers.xml_parser import XMLParser

def get_parser(file_path: str):
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ['.xlsx', '.xls']:
        return ExcelParser()
    elif ext in ['.docx']:
        return WordParser()
    elif ext in ['.pdf']:
        return PDFParser()
    elif ext in ['.xml']:
        return XMLParser()
    else:
        raise ValueError(f"Không hỗ trợ định dạng file: {ext}")
