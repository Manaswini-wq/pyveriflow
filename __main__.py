"""CLI entry point for PyVeriFlow."""

import argparse
import sys
from pathlib import Path

from pyveriflow.regression.runner import RegressionRunner
from pyveriflow.coverage.dashboard import DashboardGenerator
from pyveriflow.testplan.report_generator import ReportGenerator
from pyveriflow.utils.config import load_config
from pyveriflow.utils.logger import get_logger

logger = get_logger("pyveriflow")


def cmd_regression(args: argparse.Namespace) -> int:
    """Run regression."""
    config = load_config(Path(args.config))
    runner = RegressionRunner(config)
    result = runner.run()
    runner.save_results(Path(args.output))
    return 0 if result.passed else 1


def cmd_coverage(args: argparse.Namespace) -> int:
    """Generate coverage dashboard."""
    gen = DashboardGenerator()
    gen.generate(Path(args.input), Path(args.output))
    logger.info("Dashboard generated: %s", args.output)
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate verification report."""
    rgen = ReportGenerator()
    rgen.generate(
        testplan_path=Path(args.testplan),
        regression_path=Path(args.regression) if args.regression else None,
        coverage_path=Path(args.coverage) if args.coverage else None,
        output_path=Path(args.output),
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="pyveriflow", description="DV Automation Framework")
    sub = parser.add_subparsers(dest="command")

    p_reg = sub.add_parser("regression", help="Run regression suite")
    p_reg.add_argument("-c", "--config", required=True, help="Regression config YAML")
    p_reg.add_argument("-o", "--output", default="regression_results.json", help="Output file")

    p_cov = sub.add_parser("coverage", help="Generate coverage dashboard")
    p_cov.add_argument("-i", "--input", required=True, help="Coverage data dir")
    p_cov.add_argument("-o", "--output", default="coverage_dashboard.html", help="Output HTML")

    p_rpt = sub.add_parser("report", help="Generate verification report")
    p_rpt.add_argument("--testplan", required=True, help="Test plan YAML")
    p_rpt.add_argument("--regression", help="Regression results JSON")
    p_rpt.add_argument("--coverage", help="Coverage data path")
    p_rpt.add_argument("-o", "--output", default="verification_report.md")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 1

    handlers = {"regression": cmd_regression, "coverage": cmd_coverage, "report": cmd_report}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
