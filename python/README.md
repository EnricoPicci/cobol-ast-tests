# Python COBOL AST Parser

Python implementation of an educational COBOL AST parser using ANTLR4.

## Quick Start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```

## Project Layout

| Path | Purpose |
|---|---|
| `src/cobol_ast/` | Main package — preprocessor, parser wrapper, visitor, AST nodes |
| `src/cobol_ast/generated/grammar/` | ANTLR4-generated lexer/parser/visitor (committed, do not edit by hand) |
| `tests/` | pytest test suite |
| `grammar/` | Cobol85.g4 grammar file — see [`grammar/README.md`](grammar/README.md) for provenance and regeneration instructions |
| `ast-docs/` | Design documents including the [`implementation-plan.md`](ast-docs/implementation-plan.md) that drives the build |

## Configuration

- **`pyproject.toml`** — project metadata, pytest settings (`pythonpath = ["src"]` so tests can import `cobol_ast`), and ruff config. The generated code and `.venv` are excluded from linting.
- **`requirements.txt`** — runtime dependency (`antlr4-python3-runtime`).
- **`requirements-dev.txt`** — dev tools (`pytest`, `ruff`). Install these to run tests and lint.
- **`requirements-build.txt`** — parser generation only (`antlr4-tools`). Most developers do not need this — the generated files are already committed.

## Implementation Plan

The parser is built incrementally following [`ast-docs/implementation-plan.md`](ast-docs/implementation-plan.md). Each step produces working, tested code. See that document for architecture, data flow, and step-by-step instructions.
