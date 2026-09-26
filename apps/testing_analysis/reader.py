import xml.etree.ElementTree as ET


def read_junit_xml(file_path):
    """
    Đọc file JUnit XML và trả về thống kê test.
    Không kết nối database.
    """

    tree = ET.parse(file_path)
    root = tree.getroot()

    # JUnit XML thường có root là testsuite hoặc testsuites
    if root.tag == "testsuites":
        suites = list(root.iter("testsuite"))
    elif root.tag == "testsuite":
        suites = [root]
    else:
        raise ValueError(f"Không nhận diện được định dạng JUnit XML: {root.tag}")

    results = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "failures": [],
    }

    for suite in suites:
        for testcase in suite.findall("testcase"):
            results["total"] += 1

            failure = testcase.find("failure")
            error = testcase.find("error")
            skipped = testcase.find("skipped")

            if failure is not None:
                results["failed"] += 1
                results["failures"].append({
                    "test": testcase.get("name", "Không rõ tên"),
                    "type": "failure",
                    "message": failure.get("message", ""),
                    "details": (failure.text or "").strip(),
                })
            elif error is not None:
                results["errors"] += 1
                results["failures"].append({
                    "test": testcase.get("name", "Không rõ tên"),
                    "type": "error",
                    "message": error.get("message", ""),
                    "details": (error.text or "").strip(),
                })
            elif skipped is not None:
                results["skipped"] += 1
            else:
                results["passed"] += 1

    executed = results["passed"] + results["failed"] + results["errors"]

    if executed == 0:
        results["pass_rate"] = 0.0
    else:
        results["pass_rate"] = round(
            results["passed"] / executed * 100,
            2,
        )

    return results