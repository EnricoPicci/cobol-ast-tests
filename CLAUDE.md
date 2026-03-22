# CLAUDE.md — COBOL AST Parser Examples

## Project Overview

This project builds educational examples of using AST (Abstract Syntax Tree) parsers to analyze and transform COBOL code. It is a multi-language project — starting with Python, with plans to add TypeScript (Node.js), Go, and Java implementations.

## Project Structure

```
cobol-ast-tests/
├── python/           # Python implementations
│   ├── src/          # Source modules
│   ├── tests/        # pytest test suite
│   └── CLAUDE.md     # Python-specific guidelines
├── samples/          # COBOL source files shared across ALL languages (language-invariant)
├── ast-docs/         # Documentation about AST parsing concepts
├── cobol-docs/       # Documentation about COBOL-specific topics
├── prompts/          # Prompt files for Claude Code (numbered sequentially)
├── README.md         # Project README for newcomers
└── CLAUDE.md         # Project-wide guidelines (this file)
```

### Shared Samples Directory

The `samples/` directory contains COBOL source files (`.cob`, `.cbl`) that are **language-invariant** — they are the same examples used by every language implementation. Never duplicate sample files into language-specific directories. All languages read from this single shared location.

### Adding a New Language

Create a top-level directory for the new language (e.g., `typescript/`, `go/`, `java/`) following the same `src/` + `tests/` convention. Then update this project to account for the new language — see the checklist in the "Language-Specific Guidelines" section below.

## Code Style & Documentation

### Educational-First Approach

All code in this project serves an educational purpose. Write it so a developer unfamiliar with COBOL AST parsing can learn from it.

- **Docstrings/comments**: Explain *why* and *how*, not just *what*. Describe the COBOL concepts being parsed and the AST structures involved.
- **Function/method docs**: Include a brief description, parameter explanations, and a short example or reference to the relevant COBOL construct.
- **Inline comments**: Use them at key decision points — e.g., why a particular AST node type is handled a certain way.

### Tests as Documentation

Tests are a primary form of documentation. Each test should teach the reader something.

- Name tests descriptively: `test_parse_identification_division_extracts_program_id` not `test_parse_1`.
- Add comments inside tests explaining what COBOL construct is being tested and what the expected AST structure looks like.
- Include small inline COBOL snippets as test inputs so tests are self-contained and readable.
- Group related tests in clearly named classes or files.

## Mandatory Post-Change Review

After every code change, verify that the following are still accurate and update them if needed:

1. **Docstrings and comments** — Do they still describe what the code does?
2. **Tests** — Do existing tests still pass? Do new behaviors need new tests? Do test comments still match the test logic?
3. **README.md** — Does it reflect the current state of the project? The README is the front door for newcomers. It **must** be updated whenever:
   - A key document is added or removed — any document that a newcomer to the project should know about.
   - A new language implementation is added (add it to the Languages section and update the project structure).
   - The project structure changes materially (new top-level directories, renamed directories).
   When in doubt, re-run the README generation prompt (`prompts/11-generate-readme.md`) to regenerate it from scratch.
4. **This file (CLAUDE.md)** — Does the project structure or workflow section need updating?

Do not skip this step. Treat outdated documentation as a bug.

## Periodic CLAUDE.md Review

Tools, best practices, and conventions evolve fast. Periodically review **all** `CLAUDE.md` files in the project (root and per-language) to ensure they still reflect current best practices — for Claude Code itself, for the languages and frameworks in use, and for the project's own conventions. Remove outdated guidance, update tool recommendations, and add any new practices that have emerged. A stale `CLAUDE.md` is worse than none — it silently steers work in the wrong direction.

## Language-Specific Guidelines

Each language has its own `CLAUDE.md` file inside its directory. Claude Code automatically picks up `CLAUDE.md` files in subdirectories.

Current languages:
- **Python** — see `python/CLAUDE.md`

> **IMPORTANT**: When adding a new language, you MUST:
> 1. Create a `<lang>/CLAUDE.md` file with setup, style, testing, and command guidelines. Follow the same structure as `python/CLAUDE.md`.
> 2. Update the Project Structure diagram at the top of this file.
> 3. Add the language to the "Current languages" list above.
> 4. Update any other sections that reference the set of supported languages.

## Best Practices

- **Small, focused commits** — each commit should do one thing.
- **No dead code** — remove unused code rather than commenting it out.
- **Fail fast** — validate inputs at boundaries; use assertions in tests.
- **Reproducibility** — pin dependency versions. Document any system-level prerequisites (e.g., a specific COBOL parser library).
- **COBOL samples** — store `.cob`/`.cbl` files in `samples/` so they are reusable across languages. Keep samples minimal — just enough to demonstrate the concept.
