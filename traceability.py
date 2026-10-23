"""Traceability matrix linking specs, test plan, tests, and coverage."""

from __future__ import annotations

from dataclasses import dataclass, field

from pyveriflow.testplan.testplan_parser import TestPlan, TestPlanItem


@dataclass
class TraceLink:
    """Link from spec requirement to test plan to test to coverage."""
    spec_section: str = ""
    testplan_id: str = ""
    test_names: list[str] = field(default_factory=list)
    coverage_groups: list[str] = field(default_factory=list)
    status: str = "Not Started"


@dataclass
class GapAnalysis:
    """Result of traceability gap analysis."""
    untested_requirements: list[str] = field(default_factory=list)
    uncovered_features: list[str] = field(default_factory=list)
    orphan_tests: list[str] = field(default_factory=list)
    completeness_pct: float = 0.0


class TraceabilityMatrix:
    """Bidirectional traceability between spec, plan, tests, coverage."""

    def __init__(self, testplan: TestPlan) -> None:
        self.testplan = testplan
        self._links: list[TraceLink] = []
        self._build_links()

    def _build_links(self) -> None:
        for item in self.testplan.all_items():
            link = TraceLink(
                spec_section=item.spec_section,
                testplan_id=item.id,
                test_names=[item.test_link] if item.test_link else [],
                coverage_groups=[item.coverage_link] if item.coverage_link else [],
                status=item.status,
            )
            self._links.append(link)

    def forward_trace(self, spec_section: str) -> list[TraceLink]:
        """Spec -> test plan -> tests -> coverage."""
        return [l for l in self._links if l.spec_section == spec_section]

    def backward_trace(self, coverage_group: str) -> list[TraceLink]:
        """Coverage -> tests -> test plan -> spec."""
        return [l for l in self._links if coverage_group in l.coverage_groups]

    def gap_analysis(self, all_test_names: list[str] | None = None) -> GapAnalysis:
        """Find gaps in traceability."""
        gaps = GapAnalysis()

        for link in self._links:
            if not link.test_names:
                gaps.untested_requirements.append(link.testplan_id)
            if not link.coverage_groups:
                gaps.uncovered_features.append(link.testplan_id)

        if all_test_names:
            linked_tests = {t for l in self._links for t in l.test_names}
            gaps.orphan_tests = [t for t in all_test_names if t not in linked_tests]

        total = len(self._links)
        fully_traced = sum(
            1 for l in self._links if l.test_names and l.coverage_groups
        )
        gaps.completeness_pct = (fully_traced / total * 100) if total > 0 else 0.0

        return gaps

    def summary(self) -> dict[str, int | float]:
        """Return traceability summary metrics."""
        gaps = self.gap_analysis()
        return {
            "total_items": len(self._links),
            "fully_traced": sum(1 for l in self._links if l.test_names and l.coverage_groups),
            "untested": len(gaps.untested_requirements),
            "uncovered": len(gaps.uncovered_features),
            "completeness_pct": gaps.completeness_pct,
        }
