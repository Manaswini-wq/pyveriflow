"""CI/CD integration: JUnit XML, Cobertura XML, notifications."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from pyveriflow.regression.result_parser import TestResult
from pyveriflow.utils.logger import get_logger

logger = get_logger("ci")


def generate_junit_xml(results: list[TestResult], output: Path) -> None:
    """Generate JUnit XML report for Jenkins test result plugin."""
    suite = ET.Element("testsuite")
    suite.set("name", "regression")
    suite.set("tests", str(len(results)))
    suite.set("failures", str(sum(1 for r in results if r.status == "FAIL")))
    suite.set("errors", str(sum(1 for r in results if r.status in ("ERROR", "TIMEOUT"))))

    for r in results:
        tc = ET.SubElement(suite, "testcase")
        tc.set("name", f"{r.test_name}_seed{r.seed}")
        tc.set("classname", r.test_name)
        tc.set("time", f"{r.sim_time_seconds:.2f}")

        if r.status == "FAIL":
            fail = ET.SubElement(tc, "failure")
            fail.set("message", r.error_message or "Test failed")
            fail.text = "\n".join(r.error_messages) if r.error_messages else r.error_message
        elif r.status in ("ERROR", "TIMEOUT"):
            err = ET.SubElement(tc, "error")
            err.set("message", r.error_message or r.status)

    tree = ET.ElementTree(suite)
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output), xml_declaration=True, encoding="utf-8")
    logger.info("JUnit XML written to %s", output)


def generate_cobertura_xml(
    coverage_data: dict[str, float], output: Path
) -> None:
    """Generate Cobertura-compatible XML for coverage plugins."""
    root = ET.Element("coverage")
    overall = sum(coverage_data.values()) / max(len(coverage_data), 1) / 100
    root.set("line-rate", f"{overall:.4f}")
    root.set("branch-rate", f"{overall:.4f}")
    root.set("version", "1.0")

    packages = ET.SubElement(root, "packages")
    pkg = ET.SubElement(packages, "package")
    pkg.set("name", "functional_coverage")
    pkg.set("line-rate", f"{overall:.4f}")

    classes = ET.SubElement(pkg, "classes")
    for name, pct in coverage_data.items():
        cls = ET.SubElement(classes, "class")
        cls.set("name", name)
        cls.set("filename", name)
        cls.set("line-rate", f"{pct / 100:.4f}")
        ET.SubElement(cls, "lines")

    tree = ET.ElementTree(root)
    output.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output), xml_declaration=True, encoding="utf-8")
    logger.info("Cobertura XML written to %s", output)


@dataclass
class BuildStatus:
    """CI build status determination."""
    passed: bool
    pass_rate: float
    coverage_met: bool
    message: str

    @staticmethod
    def evaluate(
        pass_rate: float, coverage_pct: float,
        min_pass_rate: float = 100.0, min_coverage: float = 90.0,
    ) -> BuildStatus:
        passed = pass_rate >= min_pass_rate and coverage_pct >= min_coverage
        msg = "PASS" if passed else (
            f"FAIL: pass_rate={pass_rate:.1f}% (min={min_pass_rate}%), "
            f"coverage={coverage_pct:.1f}% (min={min_coverage}%)"
        )
        return BuildStatus(
            passed=passed, pass_rate=pass_rate,
            coverage_met=coverage_pct >= min_coverage, message=msg,
        )
