"""Tests for SourceLocation tracking on AST nodes.

These tests verify that every AST node records its source position
(start/end line and column) from the ANTLR4 parse tree context.

The line numbers refer to positions in the *preprocessed* source (after
the CobolPreprocessor strips fixed-format columns and comments). Since
the preprocessor preserves line count (one output line per input line),
these positions correspond to the original COBOL file line numbers.

Columns are 0-based (ANTLR4 convention). Lines are 1-based.
"""

from cobol_ast.ast_nodes import (
    AddNode,
    CallNode,
    DisplayNode,
    GobackNode,
    IfNode,
    MoveNode,
    ProgramNode,
    SourceLocation,
    StopRunNode,
)
from cobol_ast.parser import CobolParser
from cobol_ast.preprocessor import CobolPreprocessor
from cobol_ast.visitor import CobolAstVisitor


def _parse_and_visit(source: str) -> ProgramNode:
    """Preprocess, parse, and visit a raw COBOL source string.

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


# A minimal COBOL program with all four divisions. Fixed-format columns
# (1-6 sequence, 7 indicator, 8-72 content) are preserved so the
# preprocessor works correctly.
MINIMAL_SOURCE = """\
       IDENTIFICATION DIVISION.
       PROGRAM-ID. LOCTEST.
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COUNT       PIC 9(5) VALUE 100.
       PROCEDURE DIVISION.
       MAIN-PARA.
           DISPLAY "HELLO"
           STOP RUN.
"""


class TestSourceLocationPresence:
    """Every AST node produced by the visitor must have a non-None location."""

    def test_program_node_has_location(self):
        """The root ProgramNode should record the span of the entire program unit."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.location is not None
        assert isinstance(program.location, SourceLocation)

    def test_identification_division_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.identification.location is not None

    def test_environment_division_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.environment is not None
        assert program.environment.location is not None

    def test_data_division_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.data is not None
        assert program.data.location is not None

    def test_working_storage_section_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        ws = program.data.working_storage
        assert ws is not None
        assert ws.location is not None

    def test_data_item_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        item = program.data.working_storage.items[0]
        assert item.location is not None

    def test_pic_clause_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        item = program.data.working_storage.items[0]
        assert item.pic is not None
        assert item.pic.location is not None

    def test_procedure_division_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.procedure is not None
        assert program.procedure.location is not None

    def test_paragraph_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        para = program.procedure.paragraphs[0]
        assert para.location is not None

    def test_display_statement_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert isinstance(stmt, DisplayNode)
        assert stmt.location is not None

    def test_stop_run_has_location(self):
        program = _parse_and_visit(MINIMAL_SOURCE)
        stmt = program.procedure.paragraphs[0].statements[1]
        assert isinstance(stmt, StopRunNode)
        assert stmt.location is not None


class TestSourceLocationStartLine:
    """Verify that start_line values are correct for key nodes.

    The preprocessor preserves line numbers from the original source,
    so line N in the preprocessed text corresponds to line N of the
    fixed-format input.
    """

    def test_identification_division_starts_on_line_1(self):
        """IDENTIFICATION DIVISION is on line 1 of the source."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.identification.location.start_line == 1

    def test_environment_division_starts_on_line_3(self):
        """ENVIRONMENT DIVISION is on line 3 of the source."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.environment.location.start_line == 3

    def test_data_division_starts_on_line_4(self):
        """DATA DIVISION is on line 4 of the source."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.data.location.start_line == 4

    def test_working_storage_starts_on_line_5(self):
        """WORKING-STORAGE SECTION is on line 5."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.data.working_storage.location.start_line == 5

    def test_data_item_starts_on_line_6(self):
        """The 01-level data item WS-COUNT is declared on line 6."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        item = program.data.working_storage.items[0]
        assert item.location.start_line == 6

    def test_procedure_division_starts_on_line_7(self):
        """PROCEDURE DIVISION is on line 7."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.procedure.location.start_line == 7

    def test_paragraph_starts_on_line_8(self):
        """MAIN-PARA is on line 8."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        para = program.procedure.paragraphs[0]
        assert para.location.start_line == 8

    def test_display_starts_on_line_9(self):
        """DISPLAY statement is on line 9."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert stmt.location.start_line == 9

    def test_stop_run_starts_on_line_10(self):
        """STOP RUN is on line 10."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        stmt = program.procedure.paragraphs[0].statements[1]
        assert stmt.location.start_line == 10


class TestSourceLocationStatementTypes:
    """Verify location tracking for each statement type.

    Each test uses a self-contained COBOL snippet with the target
    statement and checks that it gets a valid SourceLocation.
    """

    def _make_program(self, proc_body: str) -> str:
        """Build a minimal COBOL program wrapping the given PROCEDURE DIVISION body."""
        return (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. STMTTEST.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  WS-A PIC 9(5) VALUE 1.\n"
            "       01  WS-B PIC 9(5) VALUE 2.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n" + proc_body + "           STOP RUN.\n"
        )

    def test_move_statement_location(self):
        source = self._make_program("           MOVE 1 TO WS-A\n")
        program = _parse_and_visit(source)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert isinstance(stmt, MoveNode)
        assert stmt.location is not None
        assert stmt.location.start_line == 9

    def test_add_statement_location(self):
        source = self._make_program("           ADD 1 TO WS-A\n")
        program = _parse_and_visit(source)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert isinstance(stmt, AddNode)
        assert stmt.location is not None
        assert stmt.location.start_line == 9

    def test_if_statement_location(self):
        source = self._make_program(
            '           IF WS-A = 1\n               DISPLAY "YES"\n           END-IF\n'
        )
        program = _parse_and_visit(source)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert isinstance(stmt, IfNode)
        assert stmt.location is not None
        assert stmt.location.start_line == 9

    def test_goback_statement_location(self):
        """GOBACK produces a GobackNode with a location."""
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. GOTEST.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           GOBACK.\n"
        )
        program = _parse_and_visit(source)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert isinstance(stmt, GobackNode)
        assert stmt.location is not None
        assert stmt.location.start_line == 5

    def test_call_statement_location(self):
        source = self._make_program('           CALL "SUBPROG" USING WS-A\n')
        program = _parse_and_visit(source)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert isinstance(stmt, CallNode)
        assert stmt.location is not None
        assert stmt.location.start_line == 9


class TestSourceLocationLineRange:
    """Verify that end_line is >= start_line for multi-line constructs."""

    def test_if_spans_multiple_lines(self):
        """An IF/ELSE/END-IF block should span from IF to END-IF."""
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. IFTEST.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  WS-X PIC 9 VALUE 1.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           IF WS-X = 1\n"  # line 8
            '               DISPLAY "ONE"\n'  # line 9
            "           ELSE\n"  # line 10
            '               DISPLAY "OTHER"\n'  # line 11
            "           END-IF\n"  # line 12
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)
        stmt = program.procedure.paragraphs[0].statements[0]
        assert isinstance(stmt, IfNode)
        assert stmt.location.start_line == 8
        assert stmt.location.end_line >= 12

    def test_program_node_spans_entire_source(self):
        """ProgramNode should span from the first to the last line."""
        program = _parse_and_visit(MINIMAL_SOURCE)
        assert program.location.start_line == 1
        assert program.location.end_line >= 10


class TestSourceLocationDataclass:
    """Unit tests for the SourceLocation dataclass itself."""

    def test_source_location_is_frozen(self):
        """SourceLocation should be immutable (frozen dataclass)."""
        loc = SourceLocation(start_line=1, start_column=0, end_line=1, end_column=10)
        try:
            loc.start_line = 5
            assert False, "SourceLocation should be frozen"
        except AttributeError:
            pass

    def test_source_location_equality(self):
        """Two SourceLocations with the same values should be equal."""
        a = SourceLocation(start_line=1, start_column=0, end_line=2, end_column=5)
        b = SourceLocation(start_line=1, start_column=0, end_line=2, end_column=5)
        assert a == b

    def test_source_location_fields(self):
        """Verify all four fields are accessible."""
        loc = SourceLocation(start_line=10, start_column=6, end_line=15, end_column=20)
        assert loc.start_line == 10
        assert loc.start_column == 6
        assert loc.end_line == 15
        assert loc.end_column == 20
