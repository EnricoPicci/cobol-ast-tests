# Python Guidelines

## Setup

- Use Python 3.11+.
- Use virtual environments: `python -m venv .venv && source .venv/bin/activate`.
- Manage dependencies in `requirements.txt` (or `pyproject.toml` if the project grows).

## Code Style

- Use type hints on all function signatures.
- Format with `ruff format`. Lint with `ruff check`.

## Testing

- Use `pytest` for testing.
- Follow the educational testing standards defined in the root `CLAUDE.md`.

## Commands

All commands below assume your working directory is `python/`.

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest -v

# Run a single test
pytest tests/test_parser.py::test_name -v

# Lint & format
ruff check .
ruff format .
```
