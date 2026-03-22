"""COBOL AST Parser — educational examples of AST-based COBOL analysis.

This package provides tools to parse COBOL source files into typed
Abstract Syntax Tree (AST) representations using ANTLR4.

Pipeline:
    COBOL source → Preprocessor → ANTLR4 Parser (CST) → Visitor → AST dataclasses

The two main entry points are:

- ``parse_cobol_file(path)`` — reads a ``.cob`` / ``.cbl`` file from disk
  and returns a ``ProgramNode``.
- ``parse_cobol_source(source)`` — accepts COBOL source as a string (useful
  for testing with inline snippets) and returns a ``ProgramNode``.

Both functions raise ``CobolParseError`` if the source contains syntax errors.

Example::

    from cobol_ast import parse_cobol_file, ProgramNode

    program = parse_cobol_file("samples/endianness/without-issues/SAFE01.cob")
    print(program.program_id)  # "SAFE01"
"""

from __future__ import annotations

from pathlib import Path

from cobol_ast.ast_nodes import (
    AddNode,
    CallNode,
    DataDivisionNode,
    DataItemNode,
    DisplayNode,
    EnvironmentDivisionNode,
    ExecSqlNode,
    GobackNode,
    IdentificationDivisionNode,
    IfNode,
    LinkageSectionNode,
    MoveNode,
    ParagraphNode,
    PicClause,
    ProcedureDivisionNode,
    ProgramNode,
    StatementNode,
    StopRunNode,
    UsageType,
    WorkingStorageSectionNode,
)
from cobol_ast.parser import CobolParser
from cobol_ast.preprocessor import CobolPreprocessor
from cobol_ast.visitor import CobolAstVisitor

# Re-export key AST node types so users can import directly from cobol_ast.
__all__ = [
    "parse_cobol_file",
    "parse_cobol_source",
    "CobolParseError",
    "AddNode",
    "CallNode",
    "DataDivisionNode",
    "DataItemNode",
    "DisplayNode",
    "EnvironmentDivisionNode",
    "ExecSqlNode",
    "GobackNode",
    "IdentificationDivisionNode",
    "IfNode",
    "LinkageSectionNode",
    "MoveNode",
    "ParagraphNode",
    "PicClause",
    "ProcedureDivisionNode",
    "ProgramNode",
    "StatementNode",
    "StopRunNode",
    "UsageType",
    "WorkingStorageSectionNode",
]


class CobolParseError(Exception):
    """Raised when COBOL source contains syntax errors.

    The ``errors`` attribute holds the list of individual error messages
    collected by the ANTLR4 error listener during parsing. Each message
    includes the line number and column where the error was detected.

    Example::

        try:
            program = parse_cobol_source("NOT VALID COBOL")
        except CobolParseError as e:
            for msg in e.errors:
                print(msg)
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"COBOL parse errors: {'; '.join(errors)}")


def parse_cobol_file(path: str | Path) -> ProgramNode:
    """Parse a COBOL source file and return its AST.

    This is the main entry point for file-based parsing. It reads the file,
    preprocesses the fixed-format source (stripping columns, removing
    comments, tagging EXEC SQL blocks), parses it with ANTLR4, and builds
    a typed AST using the Visitor.

    Args:
        path: Path to a ``.cob`` or ``.cbl`` file.

    Returns:
        ProgramNode representing the complete program structure.

    Raises:
        CobolParseError: If the source contains syntax errors.
    """
    source = Path(path).read_text()
    return parse_cobol_source(source)


def parse_cobol_source(source: str) -> ProgramNode:
    """Parse COBOL source text (as a string) and return its AST.

    Useful for testing with inline COBOL snippets. The source is
    preprocessed (fixed-format column stripping, comment removal,
    EXEC SQL tagging), parsed with ANTLR4, and transformed into
    typed AST dataclasses by the Visitor.

    Args:
        source: Raw COBOL source text (fixed-format or free-form).

    Returns:
        ProgramNode representing the complete program structure.

    Raises:
        CobolParseError: If the source contains syntax errors.
    """
    preprocessor = CobolPreprocessor()
    parser = CobolParser()
    visitor = CobolAstVisitor()

    preprocessed = preprocessor.process(source)
    result = parser.parse(preprocessed.text)

    if result.errors:
        raise CobolParseError(result.errors)

    return visitor.visit(result.tree)
