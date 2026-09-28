import xml.etree.ElementTree as ET
from typing import List
from apps.testing_analysis.parsers.base_parser import BaseParser
from apps.testing_analysis.schemas import TestCaseRecord

class XMLParser(BaseParser):
    def parse(self, file_path: str) -> List[TestCaseRecord]:
        records = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
        except ET.ParseError:
            return records

        if root.tag == "testsuites":
            suites = list(root.iter("testsuite"))
        elif root.tag == "testsuite":
            suites = [root]
        else:
            return records

        for suite in suites:
            for testcase in suite.findall("testcase"):
                name = testcase.get("name", "Unknown TestCase")
                classname = testcase.get("classname", "")
                full_name = f"{classname}.{name}" if classname else name
                
                failure = testcase.find("failure")
                error = testcase.find("error")
                skipped = testcase.find("skipped")
                
                status = "PASS"
                reason = None
                
                if failure is not None:
                    status = "FAIL"
                    reason = failure.text or failure.get("message", "")
                elif error is not None:
                    status = "FAIL"
                    reason = error.text or error.get("message", "")
                elif skipped is not None:
                    status = "SKIP"
                    
                records.append(TestCaseRecord(
                    test_case_id=full_name,
                    description=name,
                    status=status,
                    reason=str(reason).strip() if reason else None
                ))
                
        return records
