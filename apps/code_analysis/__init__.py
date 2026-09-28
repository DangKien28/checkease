"""Luồng phân tích mã nguồn (Source Code Analysis Branch).

Ghi chú bảo mật: chỉ rule trong rules/custom/ (Checkease viết) mới được đọc
field `hard_gate`. Rule cộng đồng có field này bị bỏ qua — enforce trong
findings_parser.SemgrepParser (kiểm tra rule_id không chứa dấu chấm).
"""
