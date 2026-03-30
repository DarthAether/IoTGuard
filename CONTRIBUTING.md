# Contributing to IoTGuard

Thank you for your interest in contributing to IoTGuard. This document provides guidelines and instructions for contributing.

## Development Setup

1. Clone the repository and install dependencies:

```bash
git clone https://github.com/DarthAether/IoTGuard.git
cd IoTGuard
python -m venv .venv
source .venv/bin/activate    # Linux/macOS
pip install -e ".[dev,test]"
```

2. Install pre-commit hooks:

```bash
make pre-commit
```

3. Copy the environment file and configure:

```bash
cp .env.example .env
```

## Development Workflow

### Running the application

```bash
make run
```

### Running tests

```bash
make test          # quick run
make test-cov      # with coverage report
```

### Code quality

```bash
make lint          # check style
make format        # auto-format
make typecheck     # mypy
make security      # bandit + pip-audit
```

## Coding Standards

- **Python 3.11+** is required.
- Follow the existing code style enforced by **Ruff** (see `pyproject.toml`).
- All public functions and classes must have docstrings.
- Type annotations are mandatory -- the project uses `mypy --strict`.
- Tests are required for new features and bug fixes.

## Project Structure

```
src/iotguard/
  api/           # FastAPI routers, middleware, dependencies
  analysis/      # Command analysis pipeline (rules + LLM)
  core/          # Config, events, security, circuit breaker
  db/            # SQLAlchemy models, repositories, migrations
  devices/       # Device management service
  mqtt/          # MQTT client and service
  observability/ # Metrics, health checks, audit logging
tests/
  unit/          # Unit tests (no external dependencies)
  integration/   # Integration tests (use SQLite)
  load/          # Locust load tests
```

## Pull Request Process

1. Create a feature branch from `main` or `develop`.
2. Make your changes with clear, focused commits.
3. Ensure all checks pass: `make lint typecheck test`.
4. Fill out the pull request template.
5. Request a review from `@DarthAether`.

## Commit Messages

Use clear, imperative-mood commit messages:

- `Add circuit breaker to MQTT client`
- `Fix token expiration check in JWT decoder`
- `Update Gemini engine prompt template`

## Reporting Issues

Use the GitHub issue templates:

- **Bug reports**: Use the bug report template with reproduction steps.
- **Feature requests**: Use the feature request template with a clear problem statement.

## Security

If you discover a security vulnerability, please do **not** open a public issue.
Instead, email the maintainers directly.

## License

By contributing, you agree that your contributions will be licensed under the project's MIT License.
