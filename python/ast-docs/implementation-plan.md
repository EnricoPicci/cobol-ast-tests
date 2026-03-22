# Python COBOL AST Parser — Implementation Plan

## Overview

This plan builds a Python COBOL AST parser using ANTLR4 and the existing Cobol85.g4 grammar from `antlr/grammars-v4`. The implementation has four major components: (1) a **Python preprocessor** that normalizes fixed-format COBOL source into free-form text suitable for ANTLR4, (2) the **ANTLR4-generated parser** from the Cobol85 grammar, (3) a **CST-to-AST Visitor** that walks the ANTLR4 parse tree and extracts semantic information, and (4) **typed AST dataclasses** that represent COBOL program structure in a clean, Pythonic form. Each step produces working, tested code and can be implemented independently.

## How to Use This Plan

The steps in this plan are designed to be implemented **one at a time**, **in blocks of related steps**, or **all at once**. Each mode works because every step produces working, tested code and clearly states its dependencies.

Use one of the following prompts with Claude Code depending on how you want to proceed.

### Implement a single step

```
Read the implementation plan at python/ast-docs/implementation-plan.md.
Implement Step N. Follow the plan exactly — create the files listed in the
"Where" section, implement the code described in "How", and write all the
tests listed in "Tests". Run the tests and make sure they pass.
After implementation, verify that docstrings and comments match the code
as required by the root CLAUDE.md post-change review checklist.
```

### Implement a block of steps

```
Read the implementation plan at python/ast-docs/implementation-plan.md.
Implement Steps N through M together. Follow the plan exactly for each
step — create the files, implement the code, and write all the tests.
Run the full test suite after implementing the block and make sure
everything passes. After implementation, verify that docstrings and
comments match the code as required by the root CLAUDE.md post-change
review checklist.
```

### Implement the entire plan

```
Read the implementation plan at python/ast-docs/implementation-plan.md.
Implement all steps (1 through 13) in order. Follow the plan exactly for
each step — create the files, implement the code, and write all the tests.
Run the full test suite at the end and make sure everything passes.
After implementation, verify that docstrings and comments match the code
as required by the root CLAUDE.md post-change review checklist.
```

## Architecture

### Module / Package Structure

```
python/
├── src/
│   └── cobol_ast/
│       ├── __init__.py              # Package root, public API
│       ├── preprocessor.py          # Fixed-format COBOL → free-form text
│       ├── parser.py                # ANTLR4 parser wrapper (parse text → CST)
│       ├── visitor.py               # CST-to-AST Visitor
│       ├── ast_nodes.py             # Typed AST dataclasses
│       └── generated/               # ANTLR4-generated code (committed to repo)
│           ├── Cobol85Lexer.py
│           ├── Cobol85Parser.py
│           ├── Cobol85Visitor.py
│           ├── Cobol85Listener.py
│           └── *.interp, *.tokens
├── tests/
│   ├── conftest.py                  # Shared fixtures (sample file paths, helpers)
│   ├── test_scaffolding.py          # Verify ANTLR4 imports and generated code
│   ├── test_preprocessor.py         # Preprocessor unit tests
│   ├── test_parser.py               # Parser integration tests (ANTLR4 parse)
│   ├── test_visitor.py              # Visitor unit tests
│   ├── test_ast_nodes.py            # AST dataclass tests
│   └── test_integration.py          # End-to-end: .cob file → AST
├── grammar/
│   ├── Cobol85.g4                   # Main grammar (from grammars-v4)
│   ├── Cobol85Lexer.g4              # Lexer grammar (if split grammar is used)
│   └── README.md                    # Grammar version, source URL, modifications
├── requirements.txt                 # Runtime dependencies
├── requirements-dev.txt             # Dev tools (pytest, ruff)
├── requirements-build.txt           # Parser generation only (antlr4-tools)
├── pyproject.toml                   # Project metadata, ruff config
└── CLAUDE.md
```

### Data Flow

```
COBOL source (.cob file)
    │
    ▼
┌──────────────┐
│ preprocessor │  Strips columns 1-6 and 73-80, handles column 7 indicators,
│              │  removes comments, joins continuation lines
└──────┬───────┘
       │  (normalized free-form text)
       ▼
┌──────────────┐
│ ANTLR4 Lexer │  Tokenizes the normalized source
│ + Parser     │  Produces a Concrete Syntax Tree (CST)
└──────┬───────┘
       │  (ParseTree / CST)
       ▼
┌──────────────┐
│   Visitor    │  Walks the CST, extracts semantic information,
│              │  builds typed AST nodes
└──────┬───────┘
       │  (AST dataclasses)
       ▼
  Program AST    Clean, typed representation of the COBOL program
```

### Key Classes

| Class / Module | Responsibility |
|---|---|
| `PreprocessedSource` (dataclass) | Holds the normalized text plus metadata (original line mapping, source format detected) |
| `CobolPreprocessor` | Transforms fixed-format COBOL source into free-form text for ANTLR4 |
| `CobolParser` | Wraps ANTLR4 lexer + parser; accepts preprocessed text, returns a CST |
| `CobolAstVisitor` | ANTLR4 Visitor subclass; walks CST nodes, returns AST dataclasses |
| `ProgramNode`, `DataItemNode`, `ParagraphNode`, etc. | Typed AST dataclasses representing COBOL program elements |

---

## Dependencies

### Runtime Dependencies (`requirements.txt`)

```
antlr4-python3-runtime==4.13.2
```

### Dev Dependencies (`requirements-dev.txt`)

```
pytest==8.3.4
ruff==0.9.7
```

These are needed by everyone working on the code — running tests, linting, and formatting.

### Build Dependencies (`requirements-build.txt`)

```
antlr4-tools==0.2.1
```

`antlr4-tools` is a pip-installable wrapper around the ANTLR4 code generator maintained by the ANTLR4 team. It provides the `antlr4` CLI command and **automatically downloads a JRE if Java is not installed on the machine**, eliminating the need to manually install Java or download the ANTLR4 JAR.

- The `antlr4-tools` version must be compatible with the `antlr4-python3-runtime` version. Both must target the same ANTLR4 release (4.13.2).
- Only needed when regenerating the parser from the grammar. Most developers never need this — the generated files are committed to the repository.

### Grammar Files

From the `antlr/grammars-v4` repository (`cobol85/` directory):

- `Cobol85.g4` — the main combined grammar (~5,600 lines)
- If the grammar is split into lexer + parser (some versions have `Cobol85Lexer.g4` + `Cobol85Parser.g4`), download both

Source: `https://github.com/antlr/grammars-v4/tree/master/cobol85`

---

## Build Instructions

### One-time setup

```bash
cd python/

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install runtime + dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

This is all that most developers need. The generated parser files are already committed to the repository.

### Generating the parser from the grammar

```bash
# Only needed when the grammar changes — most developers can skip this.
# Install antlr4-tools first (auto-downloads a JRE if Java is not installed):
pip install -r requirements-build.txt

# Generate the parser:
antlr4 \
    -Dlanguage=Python3 \
    -visitor \
    -listener \
    -o src/cobol_ast/generated \
    -package cobol_ast.generated \
    grammar/Cobol85.g4
```

The generated files are committed to the repository so contributors do not need `antlr4-tools` for normal development. Only install `requirements-build.txt` if you need to regenerate the parser after modifying the grammar.

### Running tests

```bash
cd python/
pytest -v
```

### Linting and formatting

```bash
cd python/
ruff check .
ruff format .
```

---

## Steps

### Step 1: Project Scaffolding and Grammar Setup

**What:** Create the Python package structure, `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `requirements-build.txt`, download the Cobol85 grammar, and generate the ANTLR4 parser.

**Why:** Everything else depends on the package structure existing and the ANTLR4-generated code being available. This step also validates that the ANTLR4 toolchain works end-to-end (grammar → generated Python code → importable module).

**How:**

1. Create directory structure: `src/cobol_ast/`, `src/cobol_ast/generated/`, `tests/`, `grammar/`.
2. Create `__init__.py` files for the package.
3. Create `pyproject.toml` with project metadata, ruff configuration, and pytest settings.
4. Create `requirements.txt` with the runtime dependency (`antlr4-python3-runtime==4.13.2`).
5. Create `requirements-dev.txt` with dev tools (`pytest==8.3.4`, `ruff==0.9.7`).
6. Create `requirements-build.txt` with the parser generation tool (`antlr4-tools==0.2.1`).
7. Download `Cobol85.g4` (and `Cobol85Lexer.g4` if the grammar is split) from `grammars-v4`.
8. Install `requirements-build.txt` and run `antlr4` to generate the Python lexer, parser, visitor, and listener. On first run, `antlr4-tools` will automatically download a JRE if Java is not installed.
9. Verify the generated code imports without errors.
10. Create `grammar/README.md` documenting the grammar version, source URL, and any local modifications.

**Where:**
- `python/pyproject.toml`
- `python/requirements.txt`
- `python/requirements-dev.txt`
- `python/requirements-build.txt`
- `python/src/cobol_ast/__init__.py`
- `python/src/cobol_ast/generated/` (generated files)
- `python/grammar/Cobol85.g4`
- `python/grammar/README.md`

**Tests:**

```python
# tests/test_scaffolding.py

def test_antlr4_runtime_imports():
    """Verify that the ANTLR4 Python runtime is installed and importable.

    The antlr4-python3-runtime package provides the base classes
    (CommonTokenStream, ParseTreeVisitor, etc.) that the generated
    parser depends on.
    """
    import antlr4
    assert hasattr(antlr4, "CommonTokenStream")

def test_generated_parser_imports():
    """Verify that the ANTLR4-generated COBOL parser is importable.

    The generated code lives in src/cobol_ast/generated/ and includes
    the Lexer (tokenizer), Parser (grammar rules), and Visitor (tree
    walker base class). All three must import without errors for the
    rest of the pipeline to work.
    """
    from cobol_ast.generated import Cobol85Lexer
    from cobol_ast.generated import Cobol85Parser
    from cobol_ast.generated import Cobol85Visitor
```

---

### Step 2: Preprocessor — Column Stripping and Comment Removal

**What:** Build the first part of `CobolPreprocessor`: stripping the sequence number area (columns 1–6), the identification area (columns 73–80), and removing full-line comments (column 7 = `*`) and inline comments (`*>`).

**Why:** COBOL's fixed-format layout is fundamental to reading COBOL source. The ANTLR4 Cobol85 grammar expects free-form input — it does not handle column positions. The preprocessor transforms fixed-format COBOL into a form the grammar can parse. Column stripping and comment removal are the simplest preprocessing concerns and must be correct before anything else works.

**How:**

- `CobolPreprocessor` class with a `process(source: str) -> PreprocessedSource` method.
- `PreprocessedSource` is a dataclass holding the normalized text and a line-number mapping (original → preprocessed) for error reporting.
- Processing steps:
  1. Split input into lines.
  2. For each line, if length >= 7 and column 7 is `*`, skip the line (full-line comment).
  3. For each line, extract columns 7–72 (the code area, 0-indexed: characters 6–71). If the line is shorter than 7 characters, treat it as blank.
  4. Strip inline comments: find `*>` in the code area and truncate at that position.
  5. Record the mapping from output line numbers to original source line numbers.
- Column 7 indicator `*` means comment. Indicator `/` also means comment (page break). Indicator `D` or `d` means debug line — treat as comment for now (configurable later). Blank or space means normal code line. Hyphen `-` means continuation — handled in Step 3.

**Where:**
- `python/src/cobol_ast/preprocessor.py`
- `python/tests/test_preprocessor.py`

**Tests:**

```python
# tests/test_preprocessor.py

class TestColumnStripping:

    def test_strips_sequence_area_columns_1_to_6(self):
        """Columns 1-6 are the sequence number area in fixed-format COBOL.

        These contain line numbers or other identifiers used by old
        card-based systems. They are not part of the COBOL code and
        must be removed before parsing.

        Input:  '000100 IDENTIFICATION DIVISION.'
        Cols:    123456|7-72...
        Output: ' IDENTIFICATION DIVISION.'
        """

    def test_strips_identification_area_columns_73_to_80(self):
        """Columns 73-80 are the identification area.

        Like the sequence area, this is a legacy card-format artifact.
        Any text in columns 73-80 is not COBOL code.
        """

    def test_short_lines_padded_correctly(self):
        """Lines shorter than 72 characters are valid in COBOL.

        The preprocessor must handle them without index errors.
        """

    def test_blank_lines_preserved_for_line_mapping(self):
        """Blank lines should map through the preprocessor so that
        error messages can reference the original line numbers.
        """

class TestCommentRemoval:

    def test_full_line_comment_asterisk_in_column_7(self):
        """Column 7 = '*' marks the entire line as a comment.

        COBOL comment lines:
            '      * This is a comment'
        Column 7 is the asterisk. The entire line is removed.
        """

    def test_full_line_comment_slash_in_column_7(self):
        """Column 7 = '/' is a page-break comment — also treated as
        a comment line and removed.
        """

    def test_inline_comment_star_greater_than(self):
        """The sequence '*>' anywhere in the code area starts an
        inline comment. Everything from '*>' to end of line is removed.

        Input code area: '       MOVE A TO B  *> transfer value'
        Output:          '       MOVE A TO B  '
        """

    def test_debug_line_indicator_d_treated_as_comment(self):
        """Column 7 = 'D' or 'd' marks a debug line. For non-debug
        compilation, these are treated as comments and removed.
        """

class TestLineMapping:

    def test_line_mapping_tracks_original_line_numbers(self):
        """After comment lines are removed, the preprocessed output
        has fewer lines than the original. The line mapping lets us
        translate preprocessed line numbers back to original source
        line numbers for error messages.
        """
```

**Validation milestone:** After this step, preprocess all six sample `.cob` files and verify the output contains no sequence numbers, no comment lines, and no inline comments.

---

### Step 3: Preprocessor — Continuation Lines

**What:** Add continuation-line handling to `CobolPreprocessor`. When column 7 contains a hyphen (`-`), the line is a continuation of the previous line.

**Why:** COBOL allows long literals and identifiers to span multiple lines using continuation. The continuation line's content (starting from column 12 for non-literals, or from the first quote for string literals) is appended to the previous line. Incorrect joining silently corrupts the input. None of the current sample files use continuation lines, but this is essential for real-world COBOL.

**How:**

- When column 7 is `-`, join the continuation line's code area to the previous non-blank line.
- For non-literal continuations: strip leading spaces from the continuation and append to the previous line (which has trailing spaces stripped to column 72).
- For literal continuations: the continuation line starts with a quote at or after column 12; the quote on the previous line's last character before column 72 is unclosed and the continuation picks up after the opening quote.
- Update the line mapping to account for merged lines.

**Where:**
- `python/src/cobol_ast/preprocessor.py` (extend existing class)
- `python/tests/test_preprocessor.py` (new test class)

**Tests:**

```python
class TestContinuationLines:

    def test_hyphen_in_column_7_joins_to_previous_line(self):
        """Column 7 = '-' means continuation. The content of the
        continuation line is appended to the previous line.

        Line 1: '      ' + ' ' + '       MOVE "HELLO'
        Line 2: '      ' + '-' + '           WORLD" TO WS-VAR'
        Result: '        MOVE "HELLOWORLD" TO WS-VAR'

        The hyphen indicator, sequence area, and leading spaces of
        the continuation are stripped; the content is appended.
        """

    def test_literal_continuation_preserves_quote_content(self):
        """When continuing a string literal, the continuation line
        starts with a quote character. The preprocessor must join
        the strings without inserting extra spaces or losing characters.
        """

    def test_multiple_consecutive_continuations(self):
        """A single statement can span three or more lines with
        multiple continuation lines. All must be joined correctly.
        """

    def test_continuation_updates_line_mapping(self):
        """The line mapping must reflect that continuation lines
        are merged into their predecessor, so error messages point
        to the original source lines.
        """
```

---

### Step 4: Preprocessor — Sample File Validation (Integration)

**What:** Integration tests that run the full preprocessor against every sample `.cob` file in `samples/` and verify the output is well-formed.

**Why:** This is the first validation milestone from the parser-evaluation.md spike questions: "Can a Python preprocessor correctly normalize all six sample files?" The preprocessor is the most risk-prone component — subtle bugs here silently corrupt input for all downstream components.

**How:**

- For each of the six sample files, run `CobolPreprocessor.process()` on the raw file content.
- Assert that:
  - No line in the output starts with 6 characters of sequence numbers (columns 1–6 stripped).
  - No line contains `*>` (inline comments removed).
  - No line has column 7 = `*` (full-line comments removed).
  - The output is non-empty and contains expected keywords (`IDENTIFICATION`, `PROGRAM-ID`, `PROCEDURE`).
- Spot-check specific output lines for each file to verify content preservation.

**Where:**
- `python/tests/test_preprocessor.py` (new integration test class)
- `python/tests/conftest.py` (shared fixture for sample file paths)

**Tests:**

```python
# tests/conftest.py
import pytest
from pathlib import Path

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"

@pytest.fixture
def samples_dir() -> Path:
    return SAMPLES_DIR

@pytest.fixture
def safe01_source(samples_dir) -> str:
    return (samples_dir / "endianness" / "without-issues" / "SAFE01.cob").read_text()

# ... similar fixtures for all six files

# tests/test_preprocessor.py

class TestPreprocessorSampleFiles:

    def test_preprocess_safe01_preserves_all_data_items(self, safe01_source):
        """SAFE01.cob defines five WORKING-STORAGE items:
        WS-ORDER-ID (COMP-3), WS-AMOUNT (COMP-3), WS-COUNTER (DISPLAY),
        WS-BALANCE (DISPLAY), WS-STATUS (PIC X).

        After preprocessing, all five data item names must appear
        in the output, and no sequence numbers or comments remain.
        """

    def test_preprocess_endian01_preserves_redefines_structure(self, endian01_source):
        """ENDIAN01.cob uses REDEFINES three times to overlay byte-level
        access on COMP and COMP-5 fields. The preprocessor must
        preserve the REDEFINES clauses and the subordinate level-05
        items exactly.
        """

    def test_preprocess_endian02_called_preserves_exec_sql(self, endian02_called_source):
        """ENDIAN02-CALLED.cob contains two EXEC SQL blocks:
        1. EXEC SQL INCLUDE SQLCA END-EXEC
        2. EXEC SQL SELECT ... END-EXEC

        The preprocessor must pass EXEC SQL content through unchanged.
        The SQL text between EXEC SQL and END-EXEC must not be altered.
        """

    def test_preprocess_safe02_called_preserves_linkage_section(self, safe02_called_source):
        """SAFE02-CALLED.cob has a LINKAGE SECTION with three parameters.
        The preprocessor must preserve the LINKAGE SECTION keyword and
        all three data item definitions.
        """

    def test_all_sample_files_preprocess_without_errors(self, samples_dir):
        """Smoke test: every .cob file under samples/ preprocesses
        without raising any exceptions.
        """
```

---

### Step 5: AST Node Dataclasses — Core Structure

**What:** Define the typed AST dataclasses that represent the high-level structure of a COBOL program: the program itself, divisions, and sections.

**Why:** The AST node types must exist before the Visitor can build them. Starting with the coarse-grained structure (program → divisions → sections) provides a skeleton that later steps fill in with finer-grained nodes (data items, statements). Defining these as dataclasses with type hints makes the AST introspectable and self-documenting.

**How:**

- All dataclasses in `ast_nodes.py`, frozen where possible for immutability.
- Core hierarchy:

```python
@dataclass
class ProgramNode:
    """Root AST node representing a complete COBOL program.

    A COBOL program has four divisions, each optional except
    IDENTIFICATION DIVISION (which provides the PROGRAM-ID).
    """
    program_id: str
    identification: IdentificationDivisionNode
    environment: EnvironmentDivisionNode | None
    data: DataDivisionNode | None
    procedure: ProcedureDivisionNode | None

@dataclass
class IdentificationDivisionNode:
    """IDENTIFICATION DIVISION — names the program.

    Every COBOL program begins with this division. The only
    required entry is PROGRAM-ID.
    """
    program_id: str

@dataclass
class EnvironmentDivisionNode:
    """ENVIRONMENT DIVISION — describes the computing environment.

    In the sample files, this division is always present but empty.
    """
    pass  # Extended in future steps if needed

@dataclass
class DataDivisionNode:
    """DATA DIVISION — declares all variables used by the program.

    Contains sections: WORKING-STORAGE, LINKAGE, FILE, etc.
    """
    working_storage: WorkingStorageSectionNode | None
    linkage: LinkageSectionNode | None

@dataclass
class WorkingStorageSectionNode:
    """WORKING-STORAGE SECTION — local variables.

    Items declared here are allocated when the program starts and
    persist for its lifetime.
    """
    items: list[DataItemNode]

@dataclass
class LinkageSectionNode:
    """LINKAGE SECTION — parameters passed from a calling program.

    Items declared here describe the layout of data passed via
    CALL ... USING. The memory is owned by the caller.
    """
    items: list[DataItemNode]

@dataclass
class ProcedureDivisionNode:
    """PROCEDURE DIVISION — the executable code.

    May include a USING clause listing parameters (matching the
    LINKAGE SECTION items) for called programs.
    """
    using_items: list[str]  # Parameter names from USING clause
    paragraphs: list[ParagraphNode]
```

**Where:**
- `python/src/cobol_ast/ast_nodes.py`
- `python/tests/test_ast_nodes.py`

**Tests:**

```python
# tests/test_ast_nodes.py

class TestProgramNodeStructure:

    def test_program_node_requires_program_id(self):
        """Every COBOL program has a PROGRAM-ID. The ProgramNode
        dataclass requires it as a mandatory field.
        """

    def test_program_node_optional_divisions(self):
        """ENVIRONMENT, DATA, and PROCEDURE divisions are optional
        in the AST (some minimal COBOL programs omit them).
        """

    def test_data_division_contains_sections(self):
        """The DATA DIVISION groups items into sections.
        WORKING-STORAGE and LINKAGE are the two sections used
        in the sample files.
        """

    def test_procedure_division_using_clause(self):
        """Called programs (like SAFE02-CALLED) receive parameters
        via PROCEDURE DIVISION USING. The AST captures the parameter
        names.
        """
```

---

### Step 6: AST Node Dataclasses — Data Items and PIC Clauses

**What:** Define `DataItemNode` and its associated types for representing COBOL data description entries — level numbers, PIC clauses, USAGE types (COMP, COMP-3, COMP-5, DISPLAY), VALUE clauses, and REDEFINES.

**Why:** Data items are the richest part of the COBOL samples. The AST must capture: level number (01, 05, etc.), data name, PIC string, USAGE type, VALUE literal, and REDEFINES target. These are the fields that downstream analyzers (e.g., endianness checkers) will inspect.

**How:**

```python
from enum import Enum

class UsageType(Enum):
    """COBOL USAGE clause values.

    USAGE determines how a data item is stored in memory:
    - DISPLAY: one character per digit (zoned decimal / alphanumeric)
    - COMP/BINARY: binary integer (big-endian under BINARY(BE))
    - COMP_3: packed decimal (BCD), endianness-safe
    - COMP_5: native binary (always machine byte order)
    """
    DISPLAY = "DISPLAY"
    COMP = "COMP"
    COMP_3 = "COMP-3"
    COMP_5 = "COMP-5"

@dataclass
class PicClause:
    """Represents a COBOL PIC (PICTURE) clause.

    The PIC clause defines the data type and size of a data item.
    Examples:
    - PIC S9(9)   → signed numeric, 9 digits
    - PIC X(10)   → alphanumeric, 10 characters
    - PIC 9(5)    → unsigned numeric, 5 digits
    """
    raw: str        # Original PIC string, e.g., "S9(9)"
    category: str   # "numeric", "alphanumeric", "alphabetic"
    size: int       # Total size in character positions
    signed: bool    # True if PIC contains 'S'

@dataclass
class DataItemNode:
    """A COBOL data description entry (a variable declaration).

    COBOL data items are hierarchical. Level 01 items are top-level;
    level 02-49 items are subordinates within a group. Level 77 items
    are standalone (non-group) items.

    Example COBOL:
        01  WS-ORDER-ID  PIC S9(9) COMP VALUE 12345.
    Produces:
        DataItemNode(level=1, name="WS-ORDER-ID",
                     pic=PicClause(raw="S9(9)", ...),
                     usage=UsageType.COMP,
                     value="12345", redefines=None, children=[])
    """
    level: int
    name: str
    pic: PicClause | None           # None for group items (no PIC)
    usage: UsageType | None         # None defaults to DISPLAY
    value: str | None               # VALUE clause literal
    redefines: str | None           # Name of redefined item
    children: list['DataItemNode']  # Subordinate items (level > parent)
```

**Where:**
- `python/src/cobol_ast/ast_nodes.py` (extend)
- `python/tests/test_ast_nodes.py` (extend)

**Tests:**

```python
class TestDataItemNode:

    def test_comp_data_item_from_endian01(self):
        """ENDIAN01.cob line: 01  WS-ORDER-ID  PIC S9(9) COMP VALUE 12345.

        This is a level-01 binary integer. COMP under BINARY(BE) stores
        the value in big-endian byte order. The AST must capture:
        level=1, name='WS-ORDER-ID', pic.raw='S9(9)',
        usage=COMP, value='12345'.
        """

    def test_comp3_data_item_from_safe01(self):
        """SAFE01.cob line: 01  WS-ORDER-ID  PIC S9(9) COMP-3 VALUE 12345.

        COMP-3 is packed decimal — each nibble stores a digit. It is
        endianness-safe because there is no multi-byte integer to reverse.
        """

    def test_comp5_data_item_from_safe02_called(self):
        """SAFE02-CALLED.cob line: 01  WS-ORA-ORDER-ID  PIC S9(9) COMP-5.

        COMP-5 uses native byte order (little-endian on x86).
        This is the correct type for Oracle host variables.
        """

    def test_display_numeric_from_safe01(self):
        """SAFE01.cob line: 01  WS-COUNTER  PIC 9(5) DISPLAY VALUE 98765.

        DISPLAY stores each digit as a separate character byte.
        Unsigned (no S in PIC), 5 digits.
        """

    def test_alphanumeric_from_safe01(self):
        """SAFE01.cob line: 01  WS-STATUS  PIC X(10) VALUE "ACTIVE".

        PIC X = alphanumeric. 10 characters. VALUE is a string literal.
        """

    def test_redefines_from_endian01(self):
        """ENDIAN01.cob:
            01  WS-ORDER-ID      PIC S9(9) COMP VALUE 12345.
            01  WS-ORDER-BYTES   REDEFINES WS-ORDER-ID.
                05  WS-BYTE-1    PIC X(1).
                ...

        REDEFINES overlays one data item on another's memory.
        WS-ORDER-BYTES redefines WS-ORDER-ID — same memory, different
        interpretation. The AST must capture the redefines target name
        and the subordinate level-05 items as children.
        """

    def test_group_item_has_children(self):
        """A group item (level-01 with no PIC) contains subordinate
        items. ENDIAN01's WS-ORDER-BYTES is a group with four
        level-05 children.
        """

class TestPicClause:

    def test_signed_numeric_pic(self):
        """PIC S9(9) → signed=True, category='numeric', size=9"""

    def test_unsigned_numeric_pic(self):
        """PIC 9(5) → signed=False, category='numeric', size=5"""

    def test_alphanumeric_pic(self):
        """PIC X(10) → signed=False, category='alphanumeric', size=10"""
```

---

### Step 7: AST Node Dataclasses — Statements

**What:** Define AST nodes for the PROCEDURE DIVISION statements found in the sample files: `DisplayNode`, `MoveNode`, `AddNode`, `CallNode`, `IfNode`, `StopRunNode`, `GobackNode`, `ExecSqlNode`, `ParagraphNode`.

**Why:** The PROCEDURE DIVISION is where executable logic lives. Each statement type has different semantics — MOVE transfers data, CALL invokes a subprogram, IF branches conditionally, EXEC SQL embeds database operations. The AST must represent each distinctly.

**How:**

```python
@dataclass
class ParagraphNode:
    """A named paragraph in the PROCEDURE DIVISION.

    Paragraphs are labeled blocks of statements. All sample files
    use MAIN-PARA as their primary paragraph.
    """
    name: str
    statements: list[StatementNode]

# StatementNode is a Union type or base class:
StatementNode = (DisplayNode | MoveNode | AddNode | CallNode
                 | IfNode | StopRunNode | GobackNode | ExecSqlNode)

@dataclass
class DisplayNode:
    """DISPLAY statement — outputs values to the console.

    DISPLAY can take a mix of string literals and variable names.
    Example: DISPLAY "ORDER-ID: " WS-ORDER-ID
    """
    operands: list[str]  # String literals and/or data names

@dataclass
class MoveNode:
    """MOVE statement — copies a value from source to target(s).

    MOVE is COBOL's assignment statement.
    Example: MOVE 12345 TO WS-ORDER-ID
    Example: MOVE ZEROS TO WS-QUANTITY
    """
    source: str          # Source value (literal, name, or figurative constant)
    targets: list[str]   # One or more target data names

@dataclass
class AddNode:
    """ADD statement — adds a value to a variable.

    Example: ADD 1000 TO WS-AMOUNT
    """
    value: str
    target: str

@dataclass
class CallNode:
    """CALL statement — invokes a subprogram.

    Example: CALL "SAFE02-CALLED" USING WS-ORDER-ID WS-QUANTITY WS-RETURN-CODE
    """
    program_name: str
    using_items: list[str]

@dataclass
class IfNode:
    """IF / ELSE / END-IF conditional statement.

    Example:
        IF SQLCODE = 0
            MOVE WS-ORA-QUANTITY TO LS-QUANTITY
        ELSE
            MOVE 0 TO LS-QUANTITY
        END-IF
    """
    condition: str                      # Raw condition text
    then_statements: list[StatementNode]
    else_statements: list[StatementNode]

@dataclass
class StopRunNode:
    """STOP RUN — terminates the program.

    Used by main programs to end execution.
    """
    pass

@dataclass
class GobackNode:
    """GOBACK — returns control to the calling program.

    Used by called subprograms instead of STOP RUN.
    """
    pass

@dataclass
class ExecSqlNode:
    """EXEC SQL ... END-EXEC — embedded SQL statement.

    The SQL content is captured as raw text. The parser does not
    parse SQL itself — it treats the content between EXEC SQL and
    END-EXEC as an opaque block.

    Examples from the samples:
    - EXEC SQL INCLUDE SQLCA END-EXEC
    - EXEC SQL SELECT QUANTITY INTO :WS-ORA-QUANTITY FROM ORDERS
          WHERE ORDER_ID = :WS-ORA-ORDER-ID END-EXEC
    """
    sql_text: str  # Raw SQL between EXEC SQL and END-EXEC
```

**Where:**
- `python/src/cobol_ast/ast_nodes.py` (extend)
- `python/tests/test_ast_nodes.py` (extend)

**Tests:**

```python
class TestStatementNodes:

    def test_display_with_mixed_operands(self):
        """DISPLAY "ORDER-ID: " WS-ORDER-ID has two operands:
        a string literal and a variable reference.
        """

    def test_move_with_figurative_constant(self):
        """MOVE ZEROS TO WS-QUANTITY — ZEROS is a COBOL figurative
        constant that fills the target with zero values.
        """

    def test_call_with_using_parameters(self):
        """CALL "SAFE02-CALLED" USING WS-ORDER-ID WS-QUANTITY WS-RETURN-CODE
        — three parameters passed by reference (default).
        """

    def test_if_with_else_branch(self):
        """IF SQLCODE = 0 ... ELSE ... END-IF — both branches
        must be captured in the AST.
        """

    def test_exec_sql_preserves_raw_sql_text(self):
        """EXEC SQL SELECT QUANTITY INTO :WS-ORA-QUANTITY ... END-EXEC
        — the SQL text between the delimiters is stored as-is,
        including host variable references (:WS-ORA-QUANTITY).
        """

    def test_exec_sql_include(self):
        """EXEC SQL INCLUDE SQLCA END-EXEC — this is a preprocessor
        directive to include the SQLCA copybook. It appears as an
        ExecSqlNode with sql_text='INCLUDE SQLCA'.
        """
```

---

### Step 8: Parser Wrapper — ANTLR4 Integration

**What:** Build `CobolParser`, a wrapper that feeds preprocessed text into the ANTLR4-generated lexer and parser and returns the CST (parse tree). Include error handling for lexer/parser errors.

**Why:** The ANTLR4 API requires several setup steps (create InputStream, Lexer, TokenStream, Parser, then invoke the start rule). Wrapping this in a clean class provides a simple interface for the rest of the pipeline and a single place to handle parse errors.

**How:**

```python
class CobolParser:
    """Wraps the ANTLR4 COBOL lexer and parser.

    Accepts preprocessed COBOL source text and produces an ANTLR4
    parse tree (CST). Collects any lexer/parser errors for reporting.
    """

    def parse(self, source: str) -> ParseResult:
        """Parse preprocessed COBOL source into a CST.

        Args:
            source: Preprocessed (free-form) COBOL source text.

        Returns:
            ParseResult containing the parse tree and any errors.
        """
```

- `ParseResult` dataclass with `tree` (the ANTLR4 ParseTree) and `errors` (list of error messages).
- Custom `ErrorListener` that collects syntax errors instead of printing to stderr.
- The start rule is `startRule` (or `compilationUnit` — depends on the grammar; must verify).

**Where:**
- `python/src/cobol_ast/parser.py`
- `python/tests/test_parser.py`

**Tests:**

```python
# tests/test_parser.py

class TestCobolParser:

    def test_parse_minimal_cobol_program(self):
        """Parse the smallest valid COBOL program:

            IDENTIFICATION DIVISION.
            PROGRAM-ID. MINIMAL.
            PROCEDURE DIVISION.
            MAIN-PARA.
                STOP RUN.

        The parser must produce a non-null parse tree with zero errors.
        """

    def test_parse_error_collected_not_raised(self):
        """Invalid COBOL input should produce errors in the ParseResult,
        not raise an exception. This allows callers to inspect errors
        and decide how to handle them.
        """

    def test_parse_data_division_with_pic_clauses(self):
        """Parse a program with WORKING-STORAGE data items:

            DATA DIVISION.
            WORKING-STORAGE SECTION.
            01  WS-FIELD  PIC S9(9) COMP VALUE 12345.

        The parse tree must contain a dataDescriptionEntry node.
        """

    def test_parse_exec_sql_block(self):
        """Parse a program containing EXEC SQL ... END-EXEC.

        The ANTLR4 grammar has rules for EXEC SQL statements.
        The parser must handle them without errors.
        """
```

---

### Step 9: Parser — Sample File Parse Validation (Integration)

**What:** Integration tests that run the full pipeline (preprocessor → parser) against all six sample files and verify zero parse errors.

**Why:** This is the second spike question from parser-evaluation.md: "What does the parse tree look like for a sample file?" and validates that the preprocessor output is compatible with the ANTLR4 grammar. If any sample file fails to parse, we know the preprocessor has a bug or the grammar needs adjustment.

**How:**

- For each sample file: read source → preprocess → parse → assert zero errors.
- For SAFE01.cob (the simplest file): inspect the parse tree with `toStringTree()` and verify key nodes exist.
- For ENDIAN02-CALLED.cob: verify that EXEC SQL nodes are present in the tree.

**Where:**
- `python/tests/test_parser.py` (new integration test class)

**Tests:**

```python
class TestParserSampleFiles:

    def test_safe01_parses_without_errors(self, safe01_source):
        """SAFE01.cob is the simplest sample — COMP-3, DISPLAY,
        PIC X, no EXEC SQL, no LINKAGE. It must parse cleanly.
        """

    def test_endian01_parses_without_errors(self, endian01_source):
        """ENDIAN01.cob has REDEFINES and mixed COMP/COMP-5.
        Verify the grammar handles REDEFINES clauses.
        """

    def test_endian02_called_parses_without_errors(self, endian02_called_source):
        """ENDIAN02-CALLED.cob has EXEC SQL blocks and
        PROCEDURE DIVISION USING. Both must parse correctly.
        """

    def test_safe02_called_parses_without_errors(self, safe02_called_source):
        """SAFE02-CALLED.cob has LINKAGE SECTION, PROCEDURE DIVISION
        USING, EXEC SQL with SELECT INTO, and IF/ELSE/END-IF.
        """

    def test_all_sample_files_parse_without_errors(self, samples_dir):
        """Smoke test: every .cob file under samples/ preprocesses
        and parses with zero ANTLR4 errors.
        """

    def test_safe01_parse_tree_contains_identification_division(self, safe01_source):
        """Inspect SAFE01's parse tree to verify it contains an
        identificationDivision node with the correct PROGRAM-ID.
        Uses toStringTree() to dump the tree structure.
        """
```

---

### Step 10: Visitor — Identification and Environment Divisions

**What:** Build the first part of `CobolAstVisitor`: extract `PROGRAM-ID` from the IDENTIFICATION DIVISION and detect the ENVIRONMENT DIVISION.

**Why:** The IDENTIFICATION DIVISION is mandatory in every COBOL program and contains the `PROGRAM-ID`, which names the program. Starting the Visitor with this division validates the end-to-end pipeline (COBOL → preprocessor → parser → Visitor → AST dataclass) with the simplest possible output.

**How:**

- `CobolAstVisitor` extends the ANTLR4-generated `Cobol85Visitor`.
- Override `visitStartRule()` (or the grammar's top-level rule) to return a `ProgramNode`.
- Override `visitIdentificationDivision()` to extract `PROGRAM-ID`.
- Override `visitEnvironmentDivision()` to return an `EnvironmentDivisionNode`.
- Inspect the parse tree (using `toStringTree()` on SAFE01) to identify the exact rule names and tree structure for these divisions.

**Where:**
- `python/src/cobol_ast/visitor.py`
- `python/tests/test_visitor.py`

**Tests:**

```python
# tests/test_visitor.py

class TestVisitorIdentificationDivision:

    def test_extracts_program_id_from_minimal_program(self):
        """Parse and visit:
            IDENTIFICATION DIVISION.
            PROGRAM-ID. TESTPROG.
            PROCEDURE DIVISION.
            MAIN-PARA.
                STOP RUN.

        The Visitor must produce ProgramNode(program_id='TESTPROG', ...).
        """

    def test_extracts_program_id_from_safe01(self, safe01_source):
        """SAFE01.cob → ProgramNode.program_id == 'SAFE01'"""

    def test_extracts_program_id_from_endian02_caller(self, endian02_caller_source):
        """ENDIAN02-CALLER.cob → ProgramNode.program_id == 'ENDIAN02-CALLER'"""

class TestVisitorEnvironmentDivision:

    def test_empty_environment_division_produces_node(self):
        """All sample files have an empty ENVIRONMENT DIVISION.
        The Visitor should produce an EnvironmentDivisionNode
        (not None) to indicate the division is present.
        """
```

---

### Step 11: Visitor — Working-Storage and Linkage Section Data Items

**What:** Extend the Visitor to extract data items from WORKING-STORAGE SECTION and LINKAGE SECTION: level numbers, names, PIC clauses, USAGE, VALUE, and REDEFINES.

**Why:** This is the most complex Visitor work. The grammar's `dataDescriptionEntry` rule produces deeply nested CST nodes. The Visitor must extract each clause (PIC, USAGE, VALUE, REDEFINES) from the CST and assemble a `DataItemNode`. It must also build the parent-child hierarchy based on level numbers (e.g., level-05 items are children of the preceding level-01 item).

**How:**

- Override `visitDataDivision()` to return a `DataDivisionNode`.
- Override `visitWorkingStorageSection()` to return a `WorkingStorageSectionNode`.
- Override `visitLinkageSection()` to return a `LinkageSectionNode`.
- Override `visitDataDescriptionEntry()` (or equivalent rule) to return a `DataItemNode`.
- Within `visitDataDescriptionEntry()`:
  - Extract level number from the first token.
  - Extract data name.
  - Find and parse the PIC clause → `PicClause`.
  - Find the USAGE clause → `UsageType` enum.
  - Find the VALUE clause → literal string.
  - Find REDEFINES → target name.
- Build the hierarchy: collect all `DataItemNode`s in order, then nest them based on level numbers. Level-01 items are top-level; any subsequent item with a higher level number is a child of the preceding lower-level item.

**Where:**
- `python/src/cobol_ast/visitor.py` (extend)
- `python/tests/test_visitor.py` (extend)

**Tests:**

```python
class TestVisitorDataItems:

    def test_extracts_comp3_item_from_inline_cobol(self):
        """Parse and visit:
            01  WS-ORDER-ID  PIC S9(9) COMP-3 VALUE 12345.

        Must produce DataItemNode with:
        - level=1, name='WS-ORDER-ID'
        - pic.raw='S9(9)', pic.signed=True, pic.size=9
        - usage=UsageType.COMP_3
        - value='12345'
        """

    def test_extracts_comp_item_with_redefines(self):
        """Parse and visit ENDIAN01's REDEFINES structure:
            01  WS-ORDER-ID      PIC S9(9) COMP VALUE 12345.
            01  WS-ORDER-BYTES   REDEFINES WS-ORDER-ID.
                05  WS-BYTE-1    PIC X(1).
                05  WS-BYTE-2    PIC X(1).
                05  WS-BYTE-3    PIC X(1).
                05  WS-BYTE-4    PIC X(1).

        WS-ORDER-BYTES must have:
        - redefines='WS-ORDER-ID'
        - 4 children (level-05 items)
        - No PIC (group item)
        """

    def test_extracts_comp5_item(self):
        """Parse and visit:
            01  WS-ORA-ORDER-ID  PIC S9(9) COMP-5.

        usage must be UsageType.COMP_5. No VALUE clause → value=None.
        """

    def test_extracts_display_numeric_item(self):
        """Parse and visit:
            01  WS-COUNTER  PIC 9(5) DISPLAY VALUE 98765.

        usage=UsageType.DISPLAY, pic.signed=False, pic.size=5
        """

    def test_extracts_alphanumeric_item(self):
        """Parse and visit:
            01  WS-STATUS  PIC X(10) VALUE "ACTIVE".

        pic.category='alphanumeric', usage=None or DISPLAY
        """

    def test_linkage_section_items(self):
        """Parse and visit SAFE02-CALLED's LINKAGE SECTION:
            01  LS-ORDER-ID     PIC S9(9) COMP.
            01  LS-QUANTITY      PIC S9(9) COMP.
            01  LS-RETURN-CODE   PIC S9(4) COMP.

        Three items, all COMP, in the linkage section.
        """

    def test_level_hierarchy_nests_children(self):
        """Level-05 items must appear as children of the preceding
        level-01 group item, not as siblings.

        01  GROUP-ITEM.
            05  CHILD-1  PIC X(1).
            05  CHILD-2  PIC X(1).

        GROUP-ITEM.children must have length 2.
        """

    def test_safe01_full_working_storage(self, safe01_source):
        """Integration: parse SAFE01.cob end-to-end and verify
        all five WORKING-STORAGE items are extracted with correct
        types: COMP-3, COMP-3, DISPLAY, DISPLAY, PIC X.
        """

    def test_endian01_full_working_storage(self, endian01_source):
        """Integration: parse ENDIAN01.cob and verify all data
        items including the three REDEFINES groups.
        """
```

---

### Step 12: Visitor — Procedure Division Statements

**What:** Extend the Visitor to extract PROCEDURE DIVISION statements: DISPLAY, MOVE, ADD, CALL, IF/ELSE/END-IF, STOP RUN, GOBACK, and EXEC SQL.

**Why:** The PROCEDURE DIVISION contains all executable logic. Extracting statements completes the AST for every construct in the sample files.

**How:**

- Override `visitProcedureDivision()` to return a `ProcedureDivisionNode` with the USING clause (if present) and paragraphs.
- Override `visitParagraph()` to return a `ParagraphNode` with its name and statements.
- Override visit methods for each statement type:
  - `visitDisplayStatement()` → `DisplayNode`
  - `visitMoveStatement()` → `MoveNode`
  - `visitAddStatement()` → `AddNode`
  - `visitCallStatement()` → `CallNode`
  - `visitIfStatement()` → `IfNode` (with recursive visit of then/else branches)
  - `visitStopRunStatement()` → `StopRunNode`
  - `visitGobackStatement()` → `GobackNode`
  - `visitExecSqlStatement()` → `ExecSqlNode`
- For EXEC SQL: capture the raw text between `EXEC SQL` and `END-EXEC` as the `sql_text`. Do not attempt to parse SQL.
- For IF statements: recursively visit the then-branch and else-branch to collect their statement lists.
- The exact rule names in the grammar must be verified by inspecting the parse tree (done in Step 9).

**Where:**
- `python/src/cobol_ast/visitor.py` (extend)
- `python/tests/test_visitor.py` (extend)

**Tests:**

```python
class TestVisitorStatements:

    def test_display_with_string_literal(self):
        """Parse and visit:
            DISPLAY "Hello World".

        DisplayNode.operands == ['"Hello World"']
        """

    def test_display_with_variable_reference(self):
        """Parse and visit:
            DISPLAY "Value: " WS-FIELD.

        DisplayNode.operands == ['"Value: "', 'WS-FIELD']
        """

    def test_move_numeric_literal(self):
        """Parse and visit:
            MOVE 12345 TO WS-ORDER-ID.

        MoveNode.source == '12345', MoveNode.targets == ['WS-ORDER-ID']
        """

    def test_move_figurative_constant_zeros(self):
        """Parse and visit:
            MOVE ZEROS TO WS-QUANTITY.

        MoveNode.source == 'ZEROS'
        ZEROS is a COBOL figurative constant that fills the target
        with zero values.
        """

    def test_add_numeric_literal(self):
        """Parse and visit:
            ADD 1000 TO WS-AMOUNT.

        AddNode.value == '1000', AddNode.target == 'WS-AMOUNT'
        """

    def test_call_with_using(self):
        """Parse and visit:
            CALL "SAFE02-CALLED" USING WS-ORDER-ID WS-QUANTITY WS-RETURN-CODE.

        CallNode.program_name == 'SAFE02-CALLED'
        CallNode.using_items == ['WS-ORDER-ID', 'WS-QUANTITY', 'WS-RETURN-CODE']
        """

    def test_if_else_endif(self):
        """Parse and visit:
            IF SQLCODE = 0
                MOVE WS-ORA-QUANTITY TO LS-QUANTITY
                MOVE 0 TO LS-RETURN-CODE
            ELSE
                MOVE 0 TO LS-QUANTITY
                MOVE SQLCODE TO LS-RETURN-CODE
            END-IF.

        IfNode.condition contains 'SQLCODE = 0'
        IfNode.then_statements has 2 MoveNodes
        IfNode.else_statements has 2 MoveNodes
        """

    def test_stop_run(self):
        """STOP RUN produces a StopRunNode with no fields."""

    def test_goback(self):
        """GOBACK produces a GobackNode with no fields."""

    def test_exec_sql_include(self):
        """Parse and visit:
            EXEC SQL INCLUDE SQLCA END-EXEC.

        ExecSqlNode.sql_text == 'INCLUDE SQLCA'
        """

    def test_exec_sql_select_into(self):
        """Parse and visit:
            EXEC SQL
                SELECT QUANTITY INTO :WS-ORA-QUANTITY
                FROM ORDERS WHERE ORDER_ID = :WS-ORA-ORDER-ID
            END-EXEC.

        ExecSqlNode.sql_text must contain the SELECT statement
        with host variable references preserved.
        """

class TestVisitorProcedureDivisionUsing:

    def test_procedure_division_without_using(self):
        """Programs like SAFE01 have no USING clause.
        ProcedureDivisionNode.using_items == []
        """

    def test_procedure_division_with_using(self):
        """SAFE02-CALLED has PROCEDURE DIVISION USING LS-ORDER-ID
        LS-QUANTITY LS-RETURN-CODE.

        ProcedureDivisionNode.using_items ==
            ['LS-ORDER-ID', 'LS-QUANTITY', 'LS-RETURN-CODE']
        """
```

---

### Step 13: Public API and End-to-End Pipeline

**What:** Create the public API in `__init__.py` that ties the entire pipeline together: `parse_cobol_file(path) -> ProgramNode` and `parse_cobol_source(source) -> ProgramNode`.

**Why:** Users of the library should not need to know about the preprocessor, parser, or visitor individually. A single function that goes from COBOL source to AST is the expected interface.

**How:**

```python
# src/cobol_ast/__init__.py

def parse_cobol_file(path: str | Path) -> ProgramNode:
    """Parse a COBOL source file and return its AST.

    This is the main entry point. It reads the file, preprocesses
    the fixed-format source, parses it with ANTLR4, and builds
    a typed AST using the Visitor.

    Args:
        path: Path to a .cob or .cbl file.

    Returns:
        ProgramNode representing the complete program structure.

    Raises:
        CobolParseError: If the source contains syntax errors.
    """

def parse_cobol_source(source: str) -> ProgramNode:
    """Parse COBOL source text (as a string) and return its AST.

    Useful for testing with inline COBOL snippets.
    """
```

- Define `CobolParseError` exception for syntax errors.
- Re-export key AST node types from `__init__.py` for convenience.

**Where:**
- `python/src/cobol_ast/__init__.py`
- `python/tests/test_integration.py`

**Tests:**

```python
# tests/test_integration.py

class TestEndToEndSampleFiles:
    """Full pipeline integration tests against every sample .cob file.

    Each test parses a real sample file through the complete pipeline
    (preprocess → parse → visit → AST) and verifies the resulting
    AST structure matches the known content of that file.
    """

    def test_safe01_full_ast(self, samples_dir):
        """SAFE01.cob — the simplest sample.

        Expected AST:
        - program_id: 'SAFE01'
        - working_storage: 5 items
          - WS-ORDER-ID: COMP-3, VALUE 12345
          - WS-AMOUNT: COMP-3, VALUE 70000
          - WS-COUNTER: DISPLAY, VALUE 98765
          - WS-BALANCE: DISPLAY, VALUE -54321
          - WS-STATUS: PIC X, VALUE "ACTIVE"
        - No linkage section
        - procedure: MAIN-PARA with DISPLAY and ADD statements
        - Ends with STOP RUN
        """

    def test_endian01_full_ast(self, samples_dir):
        """ENDIAN01.cob — REDEFINES and mixed COMP/COMP-5.

        Expected AST:
        - program_id: 'ENDIAN01'
        - working_storage: 6 top-level items (3 REDEFINES groups)
          - WS-ORDER-ID (COMP) + WS-ORDER-BYTES (REDEFINES, 4 children)
          - WS-COMP-VAL (COMP) + WS-COMP-BYTES (REDEFINES, 4 children)
          - WS-COMP5-VAL (COMP-5) + WS-COMP5-BYTES (REDEFINES, 4 children)
        - procedure: DISPLAY statements, STOP RUN
        """

    def test_endian02_caller_full_ast(self, samples_dir):
        """ENDIAN02-CALLER.cob — CALL with USING.

        Expected AST:
        - program_id: 'ENDIAN02-CALLER'
        - working_storage: 3 COMP items
        - procedure: MOVE, DISPLAY, CALL, DISPLAY, STOP RUN
        - CallNode.program_name: 'ENDIAN02-CALLED'
        - CallNode.using_items: 3 parameters
        """

    def test_endian02_called_full_ast(self, samples_dir):
        """ENDIAN02-CALLED.cob — EXEC SQL, LINKAGE, IF/ELSE.

        Expected AST:
        - program_id: 'ENDIAN02-CALLED'
        - working_storage: WS-QUANTITY (COMP) + EXEC SQL INCLUDE SQLCA
        - linkage: 3 COMP items
        - procedure USING: 3 parameters
        - Statements: EXEC SQL SELECT, IF/ELSE, GOBACK
        """

    def test_safe02_caller_full_ast(self, samples_dir):
        """SAFE02-CALLER.cob — same structure as ENDIAN02-CALLER
        but calls SAFE02-CALLED.

        Expected AST mirrors ENDIAN02-CALLER with different names.
        """

    def test_safe02_called_full_ast(self, samples_dir):
        """SAFE02-CALLED.cob — correct endianness pattern.

        Expected AST:
        - program_id: 'SAFE02-CALLED'
        - working_storage: EXEC SQL INCLUDE SQLCA5 + 2 COMP-5 items
        - linkage: 3 COMP items
        - procedure USING: 3 parameters
        - Statements: MOVE, EXEC SQL SELECT, IF/ELSE, GOBACK
        """

class TestParseCobolSource:

    def test_parse_inline_cobol_snippet(self):
        """parse_cobol_source() accepts a string of COBOL source.

        This is the primary API for testing — tests provide inline
        COBOL snippets rather than reading files.

        Input (already in free-form format for simplicity):
            IDENTIFICATION DIVISION.
            PROGRAM-ID. INLINE-TEST.
            DATA DIVISION.
            WORKING-STORAGE SECTION.
            01  WS-VAR  PIC 9(5) VALUE 100.
            PROCEDURE DIVISION.
            MAIN-PARA.
                DISPLAY WS-VAR.
                STOP RUN.

        Expected: ProgramNode with program_id='INLINE-TEST',
        one data item, two statements.
        """

    def test_parse_error_raises_exception(self):
        """Completely invalid input raises CobolParseError."""

class TestParseCobolFile:

    def test_parse_file_reads_and_parses(self, samples_dir):
        """parse_cobol_file() takes a Path and returns a ProgramNode.
        Verify with SAFE01.cob.
        """
```

---

## Review Checklist

### 1. Coverage of sample file constructs

Cross-referenced against parser-evaluation.md requirements table:

| Construct | Covered in Step |
|---|---|
| IDENTIFICATION DIVISION / PROGRAM-ID | Step 10 |
| ENVIRONMENT DIVISION | Step 10 |
| DATA DIVISION / WORKING-STORAGE / LINKAGE | Step 11 |
| Level-01 and level-05 data items | Step 11 |
| PIC S9(n) COMP, COMP-3, COMP-5, DISPLAY | Steps 6, 11 |
| PIC X(n) | Steps 6, 11 |
| REDEFINES | Steps 6, 11 |
| VALUE clause | Steps 6, 11 |
| PROCEDURE DIVISION / PROCEDURE DIVISION USING | Step 12 |
| Paragraph names (MAIN-PARA) | Step 12 |
| DISPLAY, MOVE, ADD, CALL...USING | Step 12 |
| IF / ELSE / END-IF | Step 12 |
| STOP RUN, GOBACK | Step 12 |
| EXEC SQL ... END-EXEC | Step 12 |
| Figurative constants (ZEROS) | Step 12 |
| Numeric and string literals | Steps 11, 12 |
| Fixed-format layout (columns) | Steps 2, 3 |
| Full-line comments, inline comments | Step 2 |

All constructs from the requirements table are covered.

### 2. Step ordering

Each step builds only on what previous steps produced:

- Steps 1 (scaffolding) → standalone
- Steps 2–4 (preprocessor) → depend only on Step 1
- Steps 5–7 (AST nodes) → depend only on Step 1 (pure dataclasses)
- Step 8 (parser wrapper) → depends on Steps 1 (generated code)
- Step 9 (parser integration) → depends on Steps 2–4 (preprocessor) + Step 8
- Steps 10–12 (Visitor) → depend on Steps 5–7 (AST nodes) + Step 8 (parser)
- Step 13 (public API) → depends on all previous steps

Note: Steps 2–4 and Steps 5–7 can be implemented in parallel since they are independent.

### 3. Implementability of individual steps

Each step specifies: what is built, why, how, where (file paths), and what to test. Test cases include inline COBOL snippets and expected outputs. A developer can pick up any step and implement it without consulting other documents.

### 4. Test specificity

Every test includes:
- A descriptive name explaining the COBOL construct being tested
- The inline COBOL input or sample file reference
- The expected AST output or assertion
- A comment explaining why this test matters

### 5. Architecture consistency

All file paths in the steps match the Architecture section. The data flow (preprocessor → parser → visitor → AST) is consistent throughout.

### 6. Risks addressed

| Risk (from parser-evaluation.md) | Addressed in |
|---|---|
| Preprocessor correctness | Steps 2–4 (dedicated tests, sample file validation) |
| Version coupling | Step 1 (pinned versions in requirements.txt + requirements-dev.txt + requirements-build.txt, committed generated code, antlr4-tools handles JRE automatically) |
| CST-to-AST complexity | Steps 10–12 (incremental, one construct at a time) |
| EXEC SQL handling | Steps 7, 8, 12 (opaque block approach, dedicated tests) |
| Micro Focus dialect gaps | Step 1 (grammar covers COMP-5; sample files validated in Step 9) |
