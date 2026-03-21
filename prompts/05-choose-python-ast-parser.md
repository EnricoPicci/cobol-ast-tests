# Role

You are a senior Python engineer with deep expertise in:
- **Language parsing**: Grammar-based parsers (ANTLR, PEG, combinators), tree-sitter, and hand-rolled recursive-descent approaches.
- **COBOL dialects**: Micro Focus COBOL (as used on IBM AIX) and IBM COBOL for Linux on x86 — including dialect-specific extensions like COMP-5, EXEC SQL, and COPY REPLACING.
- **Python ecosystem**: You know the landscape of parsing libraries available on PyPI and GitHub.

# Context

This project creates **educational examples** of using AST parsers to analyze and transform COBOL source code. Read the project's root `CLAUDE.md` and `python/CLAUDE.md` to understand the conventions and educational-first philosophy.

The parser must handle COBOL source files written for two target environments:
- **Micro Focus COBOL compiled on IBM AIX** (big-endian) — the legacy platform.
- **IBM COBOL for Linux on x86** (little-endian) — the migration target.

Real sample programs already exist in `samples/`. **Read every `.cob` file** under `samples/` before proceeding — these are some of the actual inputs the parser must handle. Pay close attention to the COBOL constructs used:
- All four divisions (IDENTIFICATION, ENVIRONMENT, DATA, PROCEDURE)
- WORKING-STORAGE and LINKAGE SECTION data definitions
- PIC clauses with COMP, COMP-3, COMP-5, and DISPLAY usage
- REDEFINES on group and elementary items
- CALL / STOP RUN control flow
- EXEC SQL blocks (embedded SQL)
- COPY statements (copybook inclusion)
- Fixed-format source layout (columns 1-6 sequence, column 7 indicator, 8-72 code)
- Inline comments (`*>`) and full-line comments (column 7 `*`)

# Task

Evaluate available approaches for building a Python-based COBOL AST parser and recommend the best option. This is a **research and evaluation task only** — do not write implementation code.

## Step 1 — Research available options

Search the web, PyPI, and GitHub for existing Python COBOL parsers or COBOL grammars. Investigate at least these categories:

| Category | What to look for |
|---|---|
| **Existing Python COBOL parsers** | Any PyPI package or GitHub repo that parses COBOL into an AST (e.g., `pycobol`, `cobol-parser`, similar) |
| **ANTLR4 COBOL grammars** | The `antlr/grammars-v4` repository has COBOL grammars — check dialect coverage and Python target support |
| **PEG / combinator parsers** | Libraries like `lark`, `pyparsing`, or `parsimonious` with a custom COBOL grammar |
| **Tree-sitter grammars** | Is there a `tree-sitter-cobol` grammar? How complete is it? Does `py-tree-sitter` make it usable from Python? |
| **Hand-rolled parser** | What would a custom recursive-descent parser look like for the subset of COBOL we need? |

For **each option found**, evaluate against these criteria:

1. **Dialect coverage** — Does it support Micro Focus and IBM COBOL extensions (COMP-5, EXEC SQL, COPY REPLACING)?
2. **AST completeness** — Does it produce a full AST with typed nodes for divisions, sections, data items, and statements? Or just a partial/flat parse?
3. **Maintenance status** — Last commit date, number of contributors, open issues, release cadence.
4. **License compatibility** — Must be compatible with educational/open-source use.
5. **Extensibility** — How hard is it to add support for COBOL constructs that are missing?
6. **Python integration** — Does it produce a Pythonic AST (dataclasses, type hints) or require manual tree conversion?
7. **Educational suitability** — Is the approach transparent enough that someone can learn from it? A black-box parser that "just works" is less useful here than one where the grammar and tree structure are visible and understandable.

## Step 2 — Recommend one approach

Based on the research, recommend **one primary approach** and optionally a fallback. Justify the choice against the evaluation criteria above. If no single existing parser covers enough of the dialect, recommend a hybrid approach (e.g., start from an ANTLR grammar and extend it, or use lark with a custom grammar).

Be explicit about trade-offs: what does the recommended approach do well, and where will it require extra work?

## Output

Write a single evaluation document to `python/ast-docs/parser-evaluation.md` containing:

1. **Requirements summary** — The COBOL constructs that must be parsed (derived from the sample files you read).
2. **Options evaluated** — A table of each option with a short description and scores/notes against the seven criteria above.
3. **Detailed analysis** — For each viable option (skip obviously unfit ones), a paragraph covering strengths, weaknesses, and dialect gaps.
4. **Recommendation** — The chosen approach with a clear justification.
5. **Risks and unknowns** — What might go wrong with the recommended approach? What needs prototyping or spiking before committing?

# Constraints

- Python 3.11+ (see `python/CLAUDE.md`)
- All sample COBOL files live in `samples/` — never duplicate them into `python/`
- The parser is for **educational use** — favor clarity, readability, and learnability over raw performance
- Pin all dependency versions in requirements
- The document must be self-contained: a reader should be able to understand the recommendation without prior context

# Review

After writing the document, critically review it by asking:
1. Does the requirements summary cover every COBOL construct found in the `samples/` files?
2. Are there COBOL features in the samples that **none** of the evaluated options handle?
3. Is the recommendation justified — would a reader understand *why* this option was chosen over the others?
4. Are the risks realistic and actionable — or are they generic hand-waving?

Fix any gaps found during review.

# Clarification
In the repo https://github.com/EnricoPicci/cobol-ast-parser I am using an AANTLR4 Python runtime for parsing.
Explain why you suggest something different.