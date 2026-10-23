"""Configuration management with YAML loading and validation."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SimulatorConfig:
    """Simulator settings."""
    tool: str = "vcs"
    compile_args: list[str] = field(default_factory=list)
    sim_args: list[str] = field(default_factory=list)
    uvm_home: str = ""
    license_wait: bool = True


@dataclass
class TestConfig:
    """Single test configuration."""
    name: str = ""
    top_module: str = "tb_top"
    plusargs: list[str] = field(default_factory=list)
    timeout: int = 3600
    seeds: list[int] = field(default_factory=lambda: [1])
    priority: int = 5
    category: str = "sanity"
    dependencies: list[str] = field(default_factory=list)


@dataclass
class RegressionConfig:
    """Full regression configuration."""
    project_name: str = "unnamed"
    simulator: SimulatorConfig = field(default_factory=SimulatorConfig)
    tests: list[TestConfig] = field(default_factory=list)
    max_parallel: int = 4
    retry_count: int = 1
    coverage_enable: bool = True
    output_dir: str = "regression_results"
    notification: dict[str, Any] = field(default_factory=dict)


def _env_override(data: dict[str, Any]) -> dict[str, Any]:
    """Replace ${ENV_VAR} patterns with environment variable values."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            result[key] = os.environ.get(env_var, value)
        elif isinstance(value, dict):
            result[key] = _env_override(value)
        else:
            result[key] = value
    return result


def load_config(path: Path) -> RegressionConfig:
    """Load and validate regression configuration from YAML file."""
    with open(path) as f:
        raw = yaml.safe_load(f)

    raw = _env_override(raw)
    cfg = RegressionConfig()
    cfg.project_name = raw.get("project_name", cfg.project_name)
    cfg.max_parallel = raw.get("max_parallel", cfg.max_parallel)
    cfg.retry_count = raw.get("retry_count", cfg.retry_count)
    cfg.coverage_enable = raw.get("coverage_enable", cfg.coverage_enable)
    cfg.output_dir = raw.get("output_dir", cfg.output_dir)

    sim = raw.get("simulator", {})
    cfg.simulator = SimulatorConfig(
        tool=sim.get("tool", "vcs"),
        compile_args=sim.get("compile_args", []),
        sim_args=sim.get("sim_args", []),
        uvm_home=sim.get("uvm_home", ""),
        license_wait=sim.get("license_wait", True),
    )

    for t in raw.get("tests", []):
        cfg.tests.append(TestConfig(
            name=t.get("name", ""),
            top_module=t.get("top_module", "tb_top"),
            plusargs=t.get("plusargs", []),
            timeout=t.get("timeout", 3600),
            seeds=t.get("seeds", [1]),
            priority=t.get("priority", 5),
            category=t.get("category", "sanity"),
            dependencies=t.get("dependencies", []),
        ))

    return cfg
