## ADDED Requirements

### Requirement: Project structure and tooling
The repository SHALL follow the src-layout described in `design.md`, with `pyproject.toml` defining dependencies, entry point `pongwars`, and dev tools (pytest, pytest-cov, hypothesis, ruff, mypy).

#### Scenario: Install and run
- **WHEN** a developer runs `pip install -e .[dev]`
- **THEN** `pytest`, `ruff check` and `mypy` run without configuration errors

### Requirement: Automated tests
Every capability requirement SHALL be covered by automated tests (unit, integration or property), and the suite MUST run headless (SDL dummy drivers) without display, audio or network devices.

#### Scenario: Headless CI
- **WHEN** `pytest` runs on a machine without display
- **THEN** all tests pass

### Requirement: Coverage threshold
The `domain`, `ai` and `net` packages SHALL maintain at least 90% line coverage.

#### Scenario: Coverage gate
- **WHEN** coverage falls below the threshold
- **THEN** the check script fails

### Requirement: Static quality
The code SHALL pass `ruff` and `mypy --strict` for `domain`, `ai` and `net`.

#### Scenario: Type gate
- **WHEN** a public function lacks type annotations in a strict package
- **THEN** mypy reports an error

### Requirement: Doxygen documentation
All public modules, classes, functions and constants SHALL carry Doxygen-style comments, and `docs/Doxyfile` SHALL generate the HTML documentation without warnings.

#### Scenario: Docs build
- **WHEN** `scripts/docs.ps1` runs
- **THEN** Doxygen finishes with zero warnings

### Requirement: Layer dependency rules
Import dependencies between packages SHALL follow `app -> ui/render/input/audio/net -> domain <- ai`, enforced by an automated test.

#### Scenario: Forbidden import
- **WHEN** `domain` imports from `render`
- **THEN** the architecture test fails

### Requirement: Single check command
A script `scripts/check.ps1` SHALL run lint, types, tests with coverage and (optionally) docs in one command.

#### Scenario: Green run
- **WHEN** the script is run on a clean checkout
- **THEN** it exits with code 0
