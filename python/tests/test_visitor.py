"""Tests for the CobolAstVisitor — IDENTIFICATION and ENVIRONMENT divisions.

These tests validate the first stage of the Visitor: extracting the PROGRAM-ID
from the IDENTIFICATION DIVISION and detecting the ENVIRONMENT DIVISION.
Together they confirm the end-to-end pipeline works:
    COBOL source → Preprocessor → ANTLR4 Parser → Visitor → AST dataclasses

Each test parses a small COBOL snippet (inline or from a sample file), visits
the resulting CST, and asserts that the correct AST nodes are produced.
"""

from cobol_ast.ast_nodes import (
    EnvironmentDivisionNode,
    IdentificationDivisionNode,
    ProgramNode,
)
from cobol_ast.parser import CobolParser
from cobol_ast.preprocessor import CobolPreprocessor
from cobol_ast.visitor import CobolAstVisitor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_and_visit(source: str) -> ProgramNode:
    """Preprocess, parse, and visit a raw COBOL source string.

    This helper runs the full pipeline so each test can focus on asserting
    the AST output rather than repeating boilerplate setup.

    Args:
        source: Raw fixed-format COBOL source text.

    Returns:
        The ``ProgramNode`` produced by the visitor.
    """
    preprocessor = CobolPreprocessor()
    parser = CobolParser()
    visitor = CobolAstVisitor()

    preprocessed = preprocessor.process(source)
    result = parser.parse(preprocessed.text)
    assert not result.errors, f"Parse errors: {result.errors}"
    return visitor.visit(result.tree)


# ---------------------------------------------------------------------------
# IDENTIFICATION DIVISION tests
# ---------------------------------------------------------------------------


class TestVisitorIdentificationDivision:
    """Tests for extracting PROGRAM-ID from the IDENTIFICATION DIVISION.

    Every COBOL program must have an IDENTIFICATION DIVISION with a
    PROGRAM-ID paragraph. The Visitor extracts this name and stores it
    in both ``ProgramNode.program_id`` and
    ``ProgramNode.identification.program_id``.
    """

    def test_extracts_program_id_from_minimal_program(self):
        """Parse and visit a minimal COBOL program with just an
        IDENTIFICATION DIVISION and a PROCEDURE DIVISION containing
        STOP RUN.

        The Visitor must produce ProgramNode(program_id='TESTPROG', ...).

        COBOL input (fixed format — 7-char prefix for column 7 indicator):
            IDENTIFICATION DIVISION.
            PROGRAM-ID. TESTPROG.
            PROCEDURE DIVISION.
            MAIN-PARA.
                STOP RUN.
        """
        # Fixed-format COBOL: 6-char sequence area + 1-char indicator + code.
        # We use spaces for the sequence area and indicator (normal line).
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TESTPROG.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        assert isinstance(program, ProgramNode)
        assert program.program_id == "TESTPROG"
        assert isinstance(program.identification, IdentificationDivisionNode)
        assert program.identification.program_id == "TESTPROG"

    def test_extracts_program_id_from_safe01(self, safe01_source: str):
        """SAFE01.cob uses COMP-3 and DISPLAY types — the simplest
        endianness-safe sample. Its PROGRAM-ID is 'SAFE01'.

        This is an integration test: it reads the actual sample file,
        preprocesses it, parses it, and visits the CST to produce an AST.
        """
        program = _parse_and_visit(safe01_source)

        assert program.program_id == "SAFE01"
        assert program.identification.program_id == "SAFE01"

    def test_extracts_program_id_from_endian02_caller(
        self, endian02_caller_source: str
    ):
        """ENDIAN02-CALLER.cob is the caller module for the Oracle
        endianness problem. Its PROGRAM-ID contains a hyphen, which
        is valid in COBOL identifiers.

        PROGRAM-ID: 'ENDIAN02-CALLER'
        """
        program = _parse_and_visit(endian02_caller_source)

        assert program.program_id == "ENDIAN02-CALLER"
        assert program.identification.program_id == "ENDIAN02-CALLER"


# ---------------------------------------------------------------------------
# ENVIRONMENT DIVISION tests
# ---------------------------------------------------------------------------


class TestVisitorEnvironmentDivision:
    """Tests for detecting the ENVIRONMENT DIVISION.

    All sample files have an ENVIRONMENT DIVISION (even if empty).
    The Visitor should produce an ``EnvironmentDivisionNode`` to indicate
    the division is present, distinguishing it from being absent.
    """

    def test_empty_environment_division_produces_node(self):
        """All sample files have an empty ENVIRONMENT DIVISION.
        The Visitor should produce an EnvironmentDivisionNode (not None)
        to indicate the division is present.

        COBOL input:
            IDENTIFICATION DIVISION.
            PROGRAM-ID. ENVTEST.
            ENVIRONMENT DIVISION.
            PROCEDURE DIVISION.
            MAIN-PARA.
                STOP RUN.
        """
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. ENVTEST.\n"
            "       ENVIRONMENT DIVISION.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        # The ENVIRONMENT DIVISION is present but empty — we should still
        # get an EnvironmentDivisionNode, not None.
        assert program.environment is not None
        assert isinstance(program.environment, EnvironmentDivisionNode)

    def test_missing_environment_division_produces_none(self):
        """When the ENVIRONMENT DIVISION is omitted entirely, the Visitor
        should set ``ProgramNode.environment`` to ``None``.

        COBOL input (no ENVIRONMENT DIVISION):
            IDENTIFICATION DIVISION.
            PROGRAM-ID. NOENV.
            PROCEDURE DIVISION.
            MAIN-PARA.
                STOP RUN.
        """
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. NOENV.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        assert program.environment is None

    def test_environment_division_present_in_safe01(self, safe01_source: str):
        """SAFE01.cob has an ENVIRONMENT DIVISION — confirm it is detected."""
        program = _parse_and_visit(safe01_source)

        assert program.environment is not None
        assert isinstance(program.environment, EnvironmentDivisionNode)
