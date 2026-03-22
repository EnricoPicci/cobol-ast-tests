# Role

You are a senior Python engineer with deep expertise in:
- **ANTLR4**: Grammar-based parser generation, Visitor/Listener patterns, Python runtime integration, and CST-to-AST conversion.
- **COBOL**: Fixed-format source layout, all four divisions, data description entries, COMP/COMP-3/COMP-5 usage, EXEC SQL, COPY/REPLACE, and Micro Focus / IBM dialect differences.
- **Software architecture**: Incremental implementation plans that produce working, tested software at every step.

# Context

This project creates **educational examples** of using AST parsers to analyze and transform COBOL source code. Before doing anything, read these files to understand the project's conventions and the technical decisions already made:

1. **Root `CLAUDE.md`** — Project-wide guidelines, educational-first philosophy, testing-as-documentation standards.
2. **`python/CLAUDE.md`** — Python-specific setup, style, and testing conventions.
3. **`python/ast-docs/parser-evaluation.md`** — The evaluation of parser approaches. It concludes that **ANTLR4 + Cobol85.g4** is the chosen approach. The plan you write must follow this recommendation.
4. **Every `.cob` file under `samples/`** — These are the actual COBOL inputs the parser must handle. Study the constructs used in each file.

The parser must handle COBOL source files written for two target environments:
- **Micro Focus COBOL compiled on IBM AIX** (big-endian) — the legacy platform.
- **IBM COBOL for Linux on x86** (little-endian) — the migration target.

You have experience building ANTLR4-based COBOL parsers in Python and understand the end-to-end pipeline: COBOL source → fixed-format preprocessing → ANTLR4 parsing → CST → Visitor → typed AST dataclasses.

# Task

Create a detailed, step-by-step implementation plan for building the Python COBOL AST parser using ANTLR4 + Cobol85.g4.

## Plan Requirements

The plan must satisfy these constraints:

1. **Incremental and independently executable.** Each step must produce working, tested code. I may implement one step at a time, a few steps together, or the entire plan in one shot — the plan must work for all three modes.

2. **Each step includes tests.** Every step must specify the tests to write. Tests follow the project's educational testing standards (see root `CLAUDE.md`):
   - Descriptive names that teach: `test_preprocessor_strips_sequence_area_columns_1_to_6`
   - Inline COBOL snippets as test inputs (self-contained, no external file dependencies for unit tests)
   - Comments explaining *what COBOL construct* is being tested and *what the expected behavior is*
   - Integration tests that parse the actual sample `.cob` files from `samples/`

3. **Each step is its own documentation.** The plan must describe each step clearly enough that no additional documentation is needed after implementation. For each step, specify:
   - **What** is being built (component, module, class)
   - **Why** it is needed (what COBOL concept or parsing concern it addresses)
   - **How** it works (key design decisions, data structures, algorithm outline)
   - **Where** the code goes (file paths within `python/src/` and `python/tests/`)
   - **What to test** (specific test cases with expected inputs and outputs)

4. **Follows the parser-evaluation.md recommendations.** The plan must address:
   - The Python preprocessor for fixed-format handling (the evaluation identifies this as the largest piece of new code)
   - The CST-to-AST Visitor layer
   - The typed AST dataclasses
   - The risks and spike questions listed in the evaluation document

5. **Uses the sample files as validation milestones.** At appropriate points in the plan, include integration steps that parse actual `.cob` files from `samples/` and verify the AST output matches expected structures.

## Output

Write the plan to `python/ast-docs/implementation-plan.md`. Structure it as:

1. **Overview** — One paragraph summarizing the implementation approach and the major components.
2. **Architecture** — The module/package structure under `python/src/`, the key classes/dataclasses, and how they connect (preprocessor → parser → visitor → AST).
3. **Steps** — A numbered sequence of implementation steps. Each step follows the format described in requirement 3 above.
4. **Dependencies** — The exact Python packages needed (with pinned versions), the ANTLR4 tool version, and the grammar files to download.
5. **Build instructions** — How to generate the parser from the grammar (the ANTLR4 command), and any other setup needed before the first step can be implemented.

# Constraints

- Python 3.11+ (see `python/CLAUDE.md`)
- All sample COBOL files live in `samples/` — never duplicate them into `python/`
- Type hints on all function signatures
- Format with `ruff format`, lint with `ruff check`
- Pin all dependency versions
- The parser is for **educational use** — favor clarity, readability, and learnability over raw performance
- Each step must be small enough to be implemented and reviewed in a single session

# Review

After writing the plan, critically review it by asking:

1. Does the plan cover every COBOL construct found in the `samples/` files (cross-reference with the requirements table in `parser-evaluation.md`)?
2. Are the steps ordered correctly — does each step build only on what previous steps have produced?
3. Could a developer pick up any single step and implement it without ambiguity?
4. Are the test cases specific enough to serve as acceptance criteria?
5. Does the architecture section match the file paths used in the steps?
6. Are the risks from `parser-evaluation.md` addressed in the plan (preprocessor correctness, version coupling, EXEC SQL handling)?

Fix any gaps found during review.
