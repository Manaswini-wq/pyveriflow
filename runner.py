"""Regression runner with parallel execution and result tracking."""

from __future__ import annotations

import json
import signal
import subprocess
import time
from concurrent.futures import ProcessPoolExecutor, as_completed, Future
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from pyveriflow.utils.config import RegressionConfig, TestConfig
from pyveriflow.utils.logger import get_logger
from pyveriflow.regression.result_parser import TestResult, parse_sim_log
from pyveriflow.regression.scheduler import TestJob, schedule_tests

logger = get_logger("regression")


@dataclass
class RegressionResult:
    """Aggregate results for a regression run."""
    project_name: str = ""
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    wall_time_seconds: float = 0.0
    test_results: list[TestResult] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total_tests * 100) if self.total_tests > 0 else 0.0

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.errors == 0

    def summary(self) -> str:
        return (
            f"Regression: {self.project_name}\n"
            f"  Total: {self.total_tests}  Passed: {self.passed}  "
            f"Failed: {self.failed}  Errors: {self.errors}\n"
            f"  Pass Rate: {self.pass_rate:.1f}%  Wall Time: {self.wall_time_seconds:.1f}s"
        )


def _run_single_test(
    test: TestConfig,
    seed: int,
    sim_tool: str,
    sim_args: list[str],
    output_dir: str,
    coverage: bool,
) -> TestResult:
    """Execute a single simulation test (runs in subprocess)."""
    test_dir = Path(output_dir) / f"{test.name}_seed{seed}"
    test_dir.mkdir(parents=True, exist_ok=True)
    log_file = test_dir / "sim.log"

    cmd = _build_sim_command(test, seed, sim_tool, sim_args, coverage)
    start = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=test.timeout, cwd=str(test_dir),
        )
        elapsed = time.monotonic() - start
        log_file.write_text(proc.stdout + proc.stderr)
        result = parse_sim_log(log_file, test.name, seed)
        result.sim_time_seconds = elapsed
        if proc.returncode != 0 and result.status == "PASS":
            result.status = "FAIL"
            result.error_message = f"Non-zero exit code: {proc.returncode}"
    except subprocess.TimeoutExpired:
        elapsed = time.monotonic() - start
        result = TestResult(
            test_name=test.name, seed=seed, status="TIMEOUT",
            sim_time_seconds=elapsed,
            error_message=f"Timeout after {test.timeout}s",
        )
    except FileNotFoundError:
        result = TestResult(
            test_name=test.name, seed=seed, status="ERROR",
            error_message=f"Simulator not found: {sim_tool}",
        )
    return result


def _build_sim_command(
    test: TestConfig, seed: int, tool: str, extra_args: list[str], coverage: bool,
) -> list[str]:
    """Build simulator command line."""
    cmd: list[str] = []
    if tool == "vcs":
        cmd = ["./simv", f"+UVM_TESTNAME={test.name}", f"+seed={seed}"]
        if coverage:
            cmd.append("-cm line+cond+fsm+tgl+branch")
    elif tool == "questa":
        cmd = ["vsim", "-c", "-do", "run -all; quit",
               f"+UVM_TESTNAME={test.name}", f"-sv_seed {seed}"]
        if coverage:
            cmd.extend(["-coverage"])
    elif tool == "xcelium":
        cmd = ["xrun", f"+UVM_TESTNAME={test.name}", f"-svseed {seed}"]
        if coverage:
            cmd.append("-coverage all")
    cmd.extend(extra_args)
    cmd.extend([f"+{pa}" for pa in test.plusargs])
    return cmd


class RegressionRunner:
    """Main regression runner with parallel execution support."""

    def __init__(self, config: RegressionConfig) -> None:
        self.config = config
        self._results: list[TestResult] = []
        self._shutdown = False
        signal.signal(signal.SIGINT, self._handle_sigint)

    def _handle_sigint(self, signum: int, frame: Any) -> None:
        logger.warning("SIGINT received, shutting down gracefully...")
        self._shutdown = True

    def run(self) -> RegressionResult:
        """Execute the full regression suite."""
        jobs = schedule_tests(self.config.tests)
        total_jobs = sum(len(j.seeds) for j in jobs)
        logger.info("Starting regression: %s (%d tests, %d jobs)",
                     self.config.project_name, len(jobs), total_jobs)

        start_time = time.monotonic()
        self._results = []
        completed = 0

        with ProcessPoolExecutor(max_workers=self.config.max_parallel) as pool:
            futures: dict[Future[TestResult], tuple[str, int]] = {}

            for job in jobs:
                if self._shutdown:
                    break
                for seed in job.seeds:
                    fut = pool.submit(
                        _run_single_test, job.test, seed,
                        self.config.simulator.tool,
                        self.config.simulator.sim_args,
                        self.config.output_dir,
                        self.config.coverage_enable,
                    )
                    futures[fut] = (job.test.name, seed)

            for fut in as_completed(futures):
                name, seed = futures[fut]
                try:
                    result = fut.result()
                except Exception as e:
                    result = TestResult(test_name=name, seed=seed, status="ERROR",
                                        error_message=str(e))
                self._results.append(result)
                completed += 1
                status_sym = "PASS" if result.status == "PASS" else "FAIL"
                logger.info("[%d/%d] %s %s (seed=%d, %.1fs)",
                            completed, total_jobs, status_sym, name, seed,
                            result.sim_time_seconds)

                # Retry on failure
                if result.status != "PASS" and self._count_attempts(name, seed) < self.config.retry_count:
                    logger.info("Retrying %s seed=%d", name, seed)
                    test_cfg = next(t for t in self.config.tests if t.name == name)
                    retry_fut = pool.submit(
                        _run_single_test, test_cfg, seed,
                        self.config.simulator.tool,
                        self.config.simulator.sim_args,
                        self.config.output_dir,
                        self.config.coverage_enable,
                    )
                    futures[retry_fut] = (name, seed)

        wall_time = time.monotonic() - start_time
        return self._build_result(wall_time)

    def _count_attempts(self, name: str, seed: int) -> int:
        return sum(1 for r in self._results if r.test_name == name and r.seed == seed)

    def _build_result(self, wall_time: float) -> RegressionResult:
        # Use last result per (test, seed) pair
        latest: dict[tuple[str, int], TestResult] = {}
        for r in self._results:
            latest[(r.test_name, r.seed)] = r

        results = list(latest.values())
        return RegressionResult(
            project_name=self.config.project_name,
            total_tests=len(results),
            passed=sum(1 for r in results if r.status == "PASS"),
            failed=sum(1 for r in results if r.status == "FAIL"),
            errors=sum(1 for r in results if r.status in ("ERROR", "TIMEOUT")),
            wall_time_seconds=wall_time,
            test_results=results,
        )

    def save_results(self, path: Path) -> None:
        """Save regression results to JSON."""
        result = self._build_result(0)
        data = {
            "project_name": result.project_name,
            "total_tests": result.total_tests,
            "passed": result.passed,
            "failed": result.failed,
            "pass_rate": result.pass_rate,
            "wall_time": result.wall_time_seconds,
            "tests": [asdict(r) for r in result.test_results],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))
        logger.info("Results saved to %s", path)
