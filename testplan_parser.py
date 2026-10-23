"""Test plan parser for YAML-based verification plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class TestPlanItem:
    """Single verification item in the test plan."""
    id: str
    description: str
    priority: str = "P2"  # P0-P3
    category: str = ""
    coverage_link: str = ""
    test_link: str = ""
    status: str = "Not Started"  # Not Started, In Progress, Done, Blocked
    spec_section: str = ""


@dataclass
class TestPlanFeature:
    """Feature grouping in the test plan."""
    name: str
    description: str = ""
    items: list[TestPlanItem] = field(default_factory=list)
    sub_features: list[TestPlanFeature] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        count = len(self.items)
        for sf in self.sub_features:
            count += sf.total_items
        return count

    @property
    def completed_items(self) -> int:
        count = sum(1 for i in self.items if i.status == "Done")
        for sf in self.sub_features:
            count += sf.completed_items
        return count

    @property
    def completion_pct(self) -> float:
        total = self.total_items
        return (self.completed_items / total * 100) if total > 0 else 0.0


@dataclass
class TestPlan:
    """Top-level test plan."""
    project: str = ""
    version: str = "1.0"
    features: list[TestPlanFeature] = field(default_factory=list)

    @property
    def total_items(self) -> int:
        return sum(f.total_items for f in self.features)

    @property
    def completed_items(self) -> int:
        return sum(f.completed_items for f in self.features)

    @property
    def completion_pct(self) -> float:
        total = self.total_items
        return (self.completed_items / total * 100) if total > 0 else 0.0

    def get_item(self, item_id: str) -> TestPlanItem | None:
        for feature in self.features:
            for item in feature.items:
                if item.id == item_id:
                    return item
            for sf in feature.sub_features:
                for item in sf.items:
                    if item.id == item_id:
                        return item
        return None

    def all_items(self) -> list[TestPlanItem]:
        items: list[TestPlanItem] = []
        for f in self.features:
            items.extend(f.items)
            for sf in f.sub_features:
                items.extend(sf.items)
        return items


def _parse_items(raw_items: list[dict]) -> list[TestPlanItem]:
    return [
        TestPlanItem(
            id=item.get("id", ""),
            description=item.get("description", ""),
            priority=item.get("priority", "P2"),
            category=item.get("category", ""),
            coverage_link=item.get("coverage_link", ""),
            test_link=item.get("test_link", ""),
            status=item.get("status", "Not Started"),
            spec_section=item.get("spec_section", ""),
        )
        for item in raw_items
    ]


def _parse_feature(raw: dict) -> TestPlanFeature:
    feature = TestPlanFeature(
        name=raw.get("name", ""),
        description=raw.get("description", ""),
        items=_parse_items(raw.get("items", [])),
    )
    for sf_raw in raw.get("sub_features", []):
        feature.sub_features.append(_parse_feature(sf_raw))
    return feature


def parse_testplan(path: Path) -> TestPlan:
    """Parse a YAML test plan file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    plan = TestPlan(
        project=raw.get("project", ""),
        version=raw.get("version", "1.0"),
    )
    for feat_raw in raw.get("features", []):
        plan.features.append(_parse_feature(feat_raw))

    # Validate unique IDs
    all_ids = [item.id for item in plan.all_items()]
    dupes = [id_ for id_ in all_ids if all_ids.count(id_) > 1]
    if dupes:
        raise ValueError(f"Duplicate test plan IDs: {set(dupes)}")

    return plan
