"""Parser for coverage report text exports (UCDB/URG formats)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CoverageBin:
    """Single coverage bin."""
    name: str
    hits: int = 0
    goal: int = 1
    excluded: bool = False

    @property
    def covered(self) -> bool:
        return self.hits >= self.goal


@dataclass
class CoverageItem:
    """Coverage point (coverpoint or cross)."""
    name: str
    bins: list[CoverageBin] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        if not self.bins:
            return 0.0
        active = [b for b in self.bins if not b.excluded]
        if not active:
            return 100.0
        covered = sum(1 for b in active if b.covered)
        return covered / len(active) * 100.0

    @property
    def total_bins(self) -> int:
        return len([b for b in self.bins if not b.excluded])

    @property
    def covered_bins(self) -> int:
        return sum(1 for b in self.bins if b.covered and not b.excluded)

    def uncovered_bins(self) -> list[CoverageBin]:
        return [b for b in self.bins if not b.covered and not b.excluded]


@dataclass
class CoverageGroup:
    """Coverage group containing multiple coverpoints."""
    name: str
    items: list[CoverageItem] = field(default_factory=list)

    @property
    def coverage_pct(self) -> float:
        if not self.items:
            return 0.0
        return sum(i.coverage_pct for i in self.items) / len(self.items)


def parse_ucdb_text(path: Path) -> list[CoverageGroup]:
    """Parse Questa UCDB text export format."""
    groups: list[CoverageGroup] = []
    current_group: CoverageGroup | None = None
    current_item: CoverageItem | None = None

    content = path.read_text(errors="replace")
    for line in content.splitlines():
        line = line.strip()

        # Group header: "COVERGROUP: <name>"
        grp_m = re.match(r"COVERGROUP:\s+(\S+)", line)
        if grp_m:
            current_group = CoverageGroup(name=grp_m.group(1))
            groups.append(current_group)
            continue

        # Coverpoint: "COVERPOINT: <name>"
        cp_m = re.match(r"COVERPOINT:\s+(\S+)", line)
        if cp_m and current_group:
            current_item = CoverageItem(name=cp_m.group(1))
            current_group.items.append(current_item)
            continue

        # Bin: "bin <name> hits=<n> goal=<g>"
        bin_m = re.match(r"bin\s+(\S+)\s+hits=(\d+)\s+goal=(\d+)", line)
        if bin_m and current_item:
            current_item.bins.append(CoverageBin(
                name=bin_m.group(1),
                hits=int(bin_m.group(2)),
                goal=int(bin_m.group(3)),
            ))
            continue

        # URG format: "<name>  <hits>/<goal>  <pct>%"
        urg_m = re.match(r"(\S+)\s+(\d+)/(\d+)\s+([\d.]+)%", line)
        if urg_m and current_item:
            current_item.bins.append(CoverageBin(
                name=urg_m.group(1),
                hits=int(urg_m.group(2)),
                goal=int(urg_m.group(3)),
            ))

    return groups


def parse_urg_report(path: Path) -> list[CoverageGroup]:
    """Parse VCS URG text report format."""
    return parse_ucdb_text(path)  # Unified parsing handles both
