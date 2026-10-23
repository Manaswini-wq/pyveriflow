# PyVeriFlow: ASIC Verification Automation Framework

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![License MIT](https://img.shields.io/badge/license-MIT-green.svg)
![CI Passing](https://img.shields.io/badge/CI-passing-brightgreen.svg)

A production-grade Python framework for automating ASIC design verification workflows. PyVeriFlow streamlines regression management, coverage tracking, test plan traceability, and CI/CD integration across industry-standard EDA simulators.

---

## Feature Highlights

- **Parallel Regression Runner** - Priority-scheduled, dependency-aware test execution with automatic retry on failure
- **Coverage Dashboard** - Self-contained HTML dashboard with per-group breakdown and coverage hole detection
- **Test Plan Traceability** - Bidirectional linking from spec requirements through test plan to tests and coverage
- **CI/CD Integration** - JUnit XML and Cobertura XML generation for Jenkins, GitHub Actions, and GitLab CI
- **Multi-Simulator Support** - VCS, Questa (ModelSim), and Xcelium command generation and log parsing
- **UVM Log Parsing** - Automatic extraction of UVM_ERROR, UVM_FATAL, pass/fail status from simulation logs
- **SQLite Coverage DB** - Persistent coverage tracking with merge, trend analysis, and hole identification

---

## Architecture

```
                          +------------------+
                          |   pyveriflow CLI |
                          +--------+---------+
                                   |
              +--------------------+--------------------+
              |                    |                    |
     +--------v--------+  +-------v--------+  +-------v--------+
     |   Regression     |  |   Coverage      |  |   Test Plan    |
     |   Runner         |  |   Module        |  |   Module       |
     +--------+---------+  +-------+---------+  +-------+--------+
              |                    |                    |
  +-----------+-------+    +-------+-------+    +------+--------+
  |           |       |    |       |       |    |      |        |
  v           v       v    v       v       v    v      v        v
Scheduler  Result   Sim  UCDB   Coverage  HTML  YAML Trace-  Report
           Parser  Cmds  Parser    DB    Dash  Parser ability  Gen
              |                    |
              v                    v
         Simulators           SQLite DB
       (VCS/Questa/           coverage.db
        Xcelium)
              |
              v
         JUnit XML / Cobertura XML
         (CI/CD Integration)
```

---

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/pyveriflow.git
cd pyveriflow

# Install in development mode
pip install -e ".[dev]"

# Verify installation
pyveriflow --help
```

### Run a Regression

```bash
# Using a YAML configuration file
pyveriflow regression -c templates/regression_config.yaml -o results.json
```

### Generate Coverage Dashboard

```bash
# From coverage data directory (UCDB/URG text exports)
pyveriflow coverage -i coverage_data/ -o dashboard.html
```

### Generate Verification Report

```bash
# Combine test plan, regression results, and coverage
pyveriflow report \
    --testplan templates/testplan_template.yaml \
    --regression results.json \
    -o verification_report.md
```

---

## Configuration Reference

### Regression Configuration (`regression_config.yaml`)

```yaml
project_name: "my_design"
max_parallel: 8              # Maximum parallel simulation jobs
retry_count: 2               # Retry failed tests up to N times
coverage_enable: true        # Enable coverage collection

simulator:
  tool: "vcs"                # vcs | questa | xcelium
  compile_args:
    - "-sverilog"
    - "-ntb_opts uvm-1.2"
  sim_args:
    - "+UVM_VERBOSITY=UVM_MEDIUM"
  uvm_home: "${UVM_HOME}"   # Environment variable substitution
  license_wait: true

tests:
  - name: "my_test"
    top_module: "tb_top"
    plusargs: ["NUM_TXN=1000"]
    timeout: 3600            # Seconds
    seeds: [1, 42, 100]     # Multiple seeds per test
    priority: 3              # Lower = higher priority
    category: "random"       # smoke | sanity | directed | random
    dependencies:            # Run after these tests pass
      - "smoke_test"
```

### Test Plan (`testplan.yaml`)

```yaml
project: "My Design"
version: "1.0"
features:
  - name: "Feature Name"
    description: "What this feature covers"
    items:
      - id: "TP_FEAT_001"
        description: "Verification item description"
        priority: "P0"          # P0 (critical) through P3 (low)
        coverage_link: "cg_name.cp_name.bin_name"
        test_link: "test_name"
        status: "Done"          # Not Started | In Progress | Done | Blocked
        spec_section: "3.1"
    sub_features:
      - name: "Sub-feature"
        items: [...]
```

---

## Coverage Dashboard

The generated HTML dashboard (`pyveriflow coverage -o dashboard.html`) provides:

- **Summary Cards** - Overall coverage percentage, group count, coverage holes, timestamp
- **Group Table** - Per-group coverage with color-coded progress bars (green >= 90%, yellow >= 70%, red < 70%)
- **Coverage Holes** - List of uncovered bins across all groups, sorted for quick triage
- **Responsive Layout** - Works on desktop and mobile, with print-friendly styles

The dashboard is fully self-contained (no external dependencies) and can be served statically or attached to CI artifacts.

---

## CI/CD Integration

### GitHub Actions

A workflow is included at `.github/workflows/ci.yml` that runs linting and tests across Python 3.10-3.12.

### Jenkins Integration

```python
from pyveriflow.ci.jenkins_integration import generate_junit_xml, generate_cobertura_xml

# Generate JUnit XML for test results plugin
generate_junit_xml(test_results, Path("junit_results.xml"))

# Generate Cobertura XML for coverage plugin
generate_cobertura_xml(coverage_data, Path("cobertura.xml"))
```

### Build Gate

```python
from pyveriflow.ci.jenkins_integration import BuildStatus

status = BuildStatus.evaluate(
    pass_rate=99.5,
    coverage_pct=92.3,
    min_pass_rate=100.0,
    min_coverage=90.0,
)
print(status.message)  # "FAIL: pass_rate=99.5% (min=100.0%), ..."
```

---

## Project Structure

```
pyveriflow/
  pyveriflow/
    __init__.py              # Package exports
    __main__.py              # CLI entry point
    regression/
      runner.py              # Parallel regression runner
      scheduler.py           # Priority/dependency scheduler
      result_parser.py       # UVM log parser
    coverage/
      ucdb_parser.py         # UCDB/URG text parser
      coverage_db.py         # SQLite coverage database
      dashboard.py           # HTML dashboard generator
    testplan/
      testplan_parser.py     # YAML test plan parser
      traceability.py        # Spec-plan-test-coverage tracing
      report_generator.py    # Markdown report generator
    ci/
      jenkins_integration.py # JUnit/Cobertura XML, build gates
    utils/
      config.py              # YAML config with env var support
      logger.py              # Color-coded logging
  templates/                 # Configuration templates
  examples/                  # Working example configs
  tests/                     # Pytest test suite
  .github/workflows/ci.yml  # GitHub Actions CI
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run linter
ruff check pyveriflow/

# Type checking
mypy pyveriflow/
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.
