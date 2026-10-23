"""Simulation result parser for VCS, Questa, and Xcelium log formats."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TestResult:
    """Result of a single simulation test."""
    test_name: str = ""
    seed: int = 0
    status: str = "UNKNOWN"  # PASS, FAIL, ERROR, TIMEOUT
    sim_time_seconds: float = 0.0
    uvm_errors: int = 0
    uvm_warnings: int = 0
    uvm_fatals: int = 0
    error_message: str = ""
    error_messages: list[str] = field(default_factory=list)
    coverage_pct: float = 0.0
    log_file: str = ""


_UVM_SUMMARY_RE = re.compile(
    r"UVM_(?P<sev>INFO|WARNING|ERROR|FATAL)\s*:\s*(?P<count>\d+)"
)
_UVM_ERROR_RE = re.compile(r"UVM_ERROR\s+.*?:\s*(.*)")
_UVM_FATAL_RE = re.compile(r"UVM_FATAL\s+.*?:\s*(.*)")
_PASS_RE = re.compile(r"\*\*\* TEST PASSED \*\*\*|UVM_ERROR\s*:\s*0.*UVM_FATAL\s*:\s*0")
_FAIL_RE = re.compile(r"\*\*\* TEST FAILED \*\*\*")
_COVERAGE_RE = re.compile(r"Total Coverage\s*=\s*([\d.]+)%")


def parse_sim_log(log_path: Path, test_name: str = "", seed: int = 0) -> TestResult:
    """Parse a simulation log file and extract results."""
    result = TestResult(test_name=test_name, seed=seed, log_file=str(log_path))

    if not log_path.exists():
        result.status = "ERROR"
        result.error_message = f"Log file not found: {log_path}"
        return result

    content = log_path.read_text(errors="replace")

    # Extract UVM summary counts
    for match in _UVM_SUMMARY_RE.finditer(content):
        sev = match.group("sev")
        count = int(match.group("count"))
        if sev == "ERROR":
            result.uvm_errors = count
        elif sev == "FATAL":
            result.uvm_fatals = count
        elif sev == "WARNING":
            result.uvm_warnings = count

    # Collect error messages
    for match in _UVM_ERROR_RE.finditer(content):
        result.error_messages.append(match.group(1).strip())
    for match in _UVM_FATAL_RE.finditer(content):
        result.error_messages.append(f"FATAL: {match.group(1).strip()}")

    # Coverage
    cov_match = _COVERAGE_RE.search(content)
    if cov_match:
        result.coverage_pct = float(cov_match.group(1))

    # Determine pass/fail
    if _PASS_RE.search(content) and result.uvm_errors == 0 and result.uvm_fatals == 0:
        result.status = "PASS"
    elif _FAIL_RE.search(content) or result.uvm_errors > 0 or result.uvm_fatals > 0:
        result.status = "FAIL"
        if result.error_messages:
            result.error_message = result.error_messages[0]
    elif "Segmentation fault" in content or "core dumped" in content:
        result.status = "ERROR"
        result.error_message = "Simulation crashed (segfault)"
    else:
        result.status = "UNKNOWN"

    return result
