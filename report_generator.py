"""Verification progress report generator."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pyveriflow.testplan.testplan_parser import TestPlan, parse_testplan
from pyveriflow.utils.logger import get_logger

logger = get_logger("report")


class ReportGenerator:
    """Generate markdown verification progress reports."""

    def generate(
        self,
        testplan_path: Path,
        regression_path: Path | None = None,
        coverage_path: Path | None = None,
        output_path: Path = Path("report.md"),
    ) -> None:
        """Generate a comprehensive verification report."""
        plan = parse_testplan(testplan_path)

        regression_data: dict[str, Any] = {}
        if regression_path and regression_path.exists():
            import json
            regression_data = json.loads(regression_path.read_text())

        sections: list[str] = []
        sections.append(self._header(plan))
        sections.append(self._executive_summary(plan, regression_data))
        sections.append(self._testplan_status(plan))
        if regression_data:
            sections.append(self._regression_results(regression_data))
        sections.append(self._risk_assessment(plan, regression_data))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n\n".join(sections))
        logger.info("Report generated: %s", output_path)

    def _header(self, plan: TestPlan) -> str:
        return (
            f"# Verification Report: {plan.project}\n\n"
            f"**Version:** {plan.version}  \n"
            f"**Date:** {datetime.now().strftime('%Y-%m-%d')}  \n"
            f"**Status:** {'Sign-off Ready' if plan.completion_pct >= 95 else 'In Progress'}\n"
        )

    def _executive_summary(self, plan: TestPlan, reg: dict[str, Any]) -> str:
        lines = [
            "## Executive Summary\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Test Plan Completion | {plan.completion_pct:.1f}% |",
            f"| Test Plan Items | {plan.total_items} |",
            f"| Completed Items | {plan.completed_items} |",
        ]
        if reg:
            lines.append(f"| Regression Pass Rate | {reg.get('pass_rate', 0):.1f}% |")
            lines.append(f"| Total Tests Run | {reg.get('total_tests', 0)} |")
        return "\n".join(lines)

    def _testplan_status(self, plan: TestPlan) -> str:
        lines = [
            "## Test Plan Status\n",
            "| Feature | Items | Completed | Progress |",
            "|---------|-------|-----------|----------|",
        ]
        for f in plan.features:
            pct = f.completion_pct
            bar = "█" * int(pct // 10) + "░" * (10 - int(pct // 10))
            lines.append(f"| {f.name} | {f.total_items} | {f.completed_items} | {bar} {pct:.0f}% |")
        return "\n".join(lines)

    def _regression_results(self, reg: dict[str, Any]) -> str:
        lines = [
            "## Regression Results\n",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total | {reg.get('total_tests', 0)} |",
            f"| Passed | {reg.get('passed', 0)} |",
            f"| Failed | {reg.get('failed', 0)} |",
            f"| Pass Rate | {reg.get('pass_rate', 0):.1f}% |",
        ]
        failed_tests = [t for t in reg.get("tests", []) if t.get("status") != "PASS"]
        if failed_tests:
            lines.append("\n### Failed Tests\n")
            lines.append("| Test | Seed | Error |")
            lines.append("|------|------|-------|")
            for t in failed_tests[:20]:
                lines.append(f"| {t.get('test_name','')} | {t.get('seed','')} | {t.get('error_message','')} |")
        return "\n".join(lines)

    def _risk_assessment(self, plan: TestPlan, reg: dict[str, Any]) -> str:
        risks: list[str] = []
        if plan.completion_pct < 80:
            risks.append("- **HIGH**: Test plan completion below 80%")
        if reg and reg.get("pass_rate", 100) < 95:
            risks.append("- **HIGH**: Regression pass rate below 95%")
        p0_items = [i for i in plan.all_items() if i.priority == "P0" and i.status != "Done"]
        if p0_items:
            risks.append(f"- **CRITICAL**: {len(p0_items)} P0 items not completed")

        if not risks:
            risks.append("- No significant risks identified")
        return "## Risk Assessment\n\n" + "\n".join(risks)
