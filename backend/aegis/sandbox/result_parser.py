"""Parse a pytest JUnit-XML report into TestOutcome objects. See
docs/EXECUTION_MODEL.md Section 4 step 7 ("parse -> per-test results").
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from aegis.schemas.testing import TestOutcome


def parse_junit_xml(xml_path: Path) -> list[TestOutcome]:
    """Parse a pytest --junitxml report. Missing/unparseable input yields an
    empty list rather than raising -- the caller treats that as INFRA_ERROR."""
    if not xml_path.exists():
        return []
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError:
        return []

    outcomes: list[TestOutcome] = []
    for case in tree.getroot().iter("testcase"):
        file_attr = case.get("file")
        name = case.get("name", "")
        classname = case.get("classname", "")
        test_id = f"{file_attr}::{name}" if file_attr else f"{classname}::{name}"

        if case.find("failure") is not None or case.find("error") is not None:
            status = "FAIL" if case.find("failure") is not None else "ERROR"
        elif case.find("skipped") is not None:
            status = "SKIPPED"
        else:
            status = "PASS"
        outcomes.append(TestOutcome(test_id=test_id, outcome=status))
    return outcomes
