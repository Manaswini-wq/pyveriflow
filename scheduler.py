"""Test scheduler with priority-based ordering and dependency resolution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pyveriflow.utils.config import TestConfig


@dataclass
class TestJob:
    """A scheduled test job."""
    test: TestConfig
    seeds: list[int] = field(default_factory=list)
    priority: int = 5
    estimated_time: int = 300

    @property
    def name(self) -> str:
        return self.test.name


def _resolve_dependencies(tests: list[TestConfig]) -> list[TestConfig]:
    """Topological sort based on test dependencies."""
    name_map = {t.name: t for t in tests}
    visited: set[str] = set()
    ordered: list[TestConfig] = []

    def visit(t: TestConfig) -> None:
        if t.name in visited:
            return
        visited.add(t.name)
        for dep_name in t.dependencies:
            if dep_name in name_map:
                visit(name_map[dep_name])
        ordered.append(t)

    for t in tests:
        visit(t)
    return ordered


def schedule_tests(tests: list[TestConfig]) -> list[TestJob]:
    """Schedule tests by priority and dependencies.

    Priority ordering:
      - P0 (smoke): run first
      - P1-P3: normal priority order
      - Lower priority number = higher priority
    """
    ordered = _resolve_dependencies(tests)

    category_priority = {"smoke": 0, "sanity": 1, "directed": 2, "random": 3}
    jobs: list[TestJob] = []

    for t in ordered:
        cat_pri = category_priority.get(t.category, 5)
        effective_priority = cat_pri * 10 + t.priority
        jobs.append(TestJob(
            test=t,
            seeds=t.seeds if t.seeds else [1],
            priority=effective_priority,
            estimated_time=t.timeout // 2,
        ))

    jobs.sort(key=lambda j: j.priority)
    return jobs
