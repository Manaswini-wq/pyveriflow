"""HTML dashboard generator for coverage visualization."""

from __future__ import annotations

from pathlib import Path
from string import Template

from pyveriflow.coverage.coverage_db import CoverageDB
from pyveriflow.coverage.ucdb_parser import parse_ucdb_text, CoverageGroup
from pyveriflow.utils.logger import get_logger

logger = get_logger("dashboard")

DASHBOARD_TEMPLATE = Template("""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coverage Dashboard - $project</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f5f6fa; color: #2d3436; padding: 24px; }
  h1 { font-size: 24px; margin-bottom: 20px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
           gap: 16px; margin-bottom: 24px; }
  .card { background: white; border-radius: 8px; padding: 20px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
  .card h3 { font-size: 13px; color: #636e72; text-transform: uppercase; }
  .card .value { font-size: 32px; font-weight: 700; margin-top: 8px; }
  .card .value.pass { color: #00b894; }
  .card .value.warn { color: #fdcb6e; }
  .card .value.fail { color: #d63031; }
  table { width: 100%; border-collapse: collapse; background: white;
          border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
  th, td { padding: 12px 16px; text-align: left; border-bottom: 1px solid #dfe6e9; }
  th { background: #2d3436; color: white; font-size: 13px; text-transform: uppercase; }
  .bar { height: 20px; border-radius: 4px; background: #dfe6e9; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
  .bar-fill.high { background: #00b894; }
  .bar-fill.mid  { background: #fdcb6e; }
  .bar-fill.low  { background: #d63031; }
  .holes { margin-top: 24px; }
  .hole-item { background: #ffeaa7; padding: 8px 12px; margin: 4px 0;
               border-radius: 4px; font-family: monospace; font-size: 13px; }
  @media print { body { background: white; } .card { box-shadow: none; border: 1px solid #ddd; } }
</style>
</head>
<body>
<h1>Coverage Dashboard: $project</h1>
<div class="cards">
  <div class="card">
    <h3>Overall Coverage</h3>
    <div class="value $overall_class">$overall_pct%</div>
  </div>
  <div class="card">
    <h3>Coverage Groups</h3>
    <div class="value">$num_groups</div>
  </div>
  <div class="card">
    <h3>Coverage Holes</h3>
    <div class="value $holes_class">$num_holes</div>
  </div>
  <div class="card">
    <h3>Last Updated</h3>
    <div class="value" style="font-size:16px">$timestamp</div>
  </div>
</div>

<table>
<thead><tr><th>Group</th><th>Coverage</th><th>Progress</th></tr></thead>
<tbody>
$group_rows
</tbody>
</table>

<div class="holes">
<h2 style="margin:16px 0">Coverage Holes</h2>
$hole_items
</div>
</body>
</html>""")


def _bar_class(pct: float) -> str:
    if pct >= 90:
        return "high"
    if pct >= 70:
        return "mid"
    return "low"


def _value_class(pct: float) -> str:
    if pct >= 90:
        return "pass"
    if pct >= 70:
        return "warn"
    return "fail"


class DashboardGenerator:
    """Generate self-contained HTML coverage dashboard."""

    def generate(self, input_path: Path, output_path: Path, project: str = "DV Project") -> None:
        """Generate dashboard from coverage data directory or file."""
        groups: list[CoverageGroup] = []

        if input_path.is_file():
            groups = parse_ucdb_text(input_path)
        elif input_path.is_dir():
            for f in sorted(input_path.glob("*.txt")):
                groups.extend(parse_ucdb_text(f))

        overall = sum(g.coverage_pct for g in groups) / max(len(groups), 1)
        holes: list[str] = []
        for g in groups:
            for item in g.items:
                for b in item.uncovered_bins():
                    holes.append(f"{g.name}.{item.name}.{b.name}")

        group_rows = ""
        for g in groups:
            pct = g.coverage_pct
            bc = _bar_class(pct)
            group_rows += (
                f'<tr><td>{g.name}</td><td>{pct:.1f}%</td>'
                f'<td><div class="bar"><div class="bar-fill {bc}" '
                f'style="width:{pct:.1f}%"></div></div></td></tr>\n'
            )

        hole_items = ""
        for h in holes[:50]:
            hole_items += f'<div class="hole-item">{h}</div>\n'
        if not holes:
            hole_items = '<div style="padding:12px;color:#00b894">No coverage holes found</div>'

        from datetime import datetime
        html = DASHBOARD_TEMPLATE.substitute(
            project=project,
            overall_pct=f"{overall:.1f}",
            overall_class=_value_class(overall),
            num_groups=str(len(groups)),
            num_holes=str(len(holes)),
            holes_class="fail" if holes else "pass",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M"),
            group_rows=group_rows,
            hole_items=hole_items,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)
        logger.info("Dashboard written to %s", output_path)
