"""SQLite-backed coverage database for tracking and merging coverage data."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pyveriflow.coverage.ucdb_parser import CoverageGroup


@dataclass
class CoverageSnapshot:
    """Coverage snapshot at a point in time."""
    timestamp: str
    commit_hash: str
    overall_pct: float
    group_data: dict[str, float]


class CoverageDB:
    """Persistent coverage database using SQLite."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._create_tables()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS coverage_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                commit_hash TEXT DEFAULT '',
                test_name TEXT DEFAULT '',
                overall_pct REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS coverage_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER REFERENCES coverage_runs(id),
                group_name TEXT NOT NULL,
                coverage_pct REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS coverage_bins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER REFERENCES coverage_groups(id),
                item_name TEXT NOT NULL,
                bin_name TEXT NOT NULL,
                hits INTEGER DEFAULT 0,
                goal INTEGER DEFAULT 1
            );
        """)
        self._conn.commit()

    def add_coverage(
        self, groups: list[CoverageGroup],
        test_name: str = "", commit_hash: str = "",
    ) -> int:
        """Insert coverage data from a test run."""
        ts = datetime.now().isoformat()
        overall = sum(g.coverage_pct for g in groups) / max(len(groups), 1)

        cur = self._conn.execute(
            "INSERT INTO coverage_runs (timestamp, commit_hash, test_name, overall_pct) VALUES (?,?,?,?)",
            (ts, commit_hash, test_name, overall),
        )
        run_id = cur.lastrowid
        assert run_id is not None

        for grp in groups:
            gcur = self._conn.execute(
                "INSERT INTO coverage_groups (run_id, group_name, coverage_pct) VALUES (?,?,?)",
                (run_id, grp.name, grp.coverage_pct),
            )
            gid = gcur.lastrowid
            for item in grp.items:
                for b in item.bins:
                    self._conn.execute(
                        "INSERT INTO coverage_bins (group_id, item_name, bin_name, hits, goal) VALUES (?,?,?,?,?)",
                        (gid, item.name, b.name, b.hits, b.goal),
                    )
        self._conn.commit()
        return run_id

    def get_merged_coverage(self) -> dict[str, float]:
        """Get merged coverage across all runs (max hits per bin)."""
        rows = self._conn.execute("""
            SELECT cg.group_name, AVG(cg.coverage_pct)
            FROM coverage_groups cg
            GROUP BY cg.group_name
        """).fetchall()
        return {row[0]: row[1] for row in rows}

    def get_coverage_trend(self, days: int = 30) -> list[CoverageSnapshot]:
        """Get coverage progression over time."""
        rows = self._conn.execute("""
            SELECT timestamp, commit_hash, overall_pct
            FROM coverage_runs
            ORDER BY timestamp DESC
            LIMIT ?
        """, (days,)).fetchall()

        snapshots: list[CoverageSnapshot] = []
        for ts, commit, pct in rows:
            snapshots.append(CoverageSnapshot(
                timestamp=ts, commit_hash=commit,
                overall_pct=pct, group_data={},
            ))
        return list(reversed(snapshots))

    def get_coverage_holes(self) -> list[dict[str, str | int]]:
        """Find bins with zero hits across all runs."""
        rows = self._conn.execute("""
            SELECT cg.group_name, cb.item_name, cb.bin_name, MAX(cb.hits) as max_hits
            FROM coverage_bins cb
            JOIN coverage_groups cg ON cb.group_id = cg.id
            GROUP BY cg.group_name, cb.item_name, cb.bin_name
            HAVING max_hits = 0
        """).fetchall()
        return [
            {"group": r[0], "item": r[1], "bin": r[2], "hits": r[3]}
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
