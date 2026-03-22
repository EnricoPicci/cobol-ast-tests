"""Tests for the CobolAstVisitor — all division visitors.

These tests validate the Visitor pipeline:
    COBOL source → Preprocessor → ANTLR4 Parser → Visitor → AST dataclasses

Covers:
- IDENTIFICATION DIVISION — PROGRAM-ID extraction
- ENVIRONMENT DIVISION — presence detection
- DATA DIVISION — WORKING-STORAGE and LINKAGE SECTION data items with PIC
  clauses, USAGE types, VALUE literals, REDEFINES, and level-number hierarchy
"""

from cobol_ast.ast_nodes import (
    EnvironmentDivisionNode,
    IdentificationDivisionNode,
    ProgramNode,
    UsageType,
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


# ---------------------------------------------------------------------------
# DATA DIVISION — WORKING-STORAGE and LINKAGE SECTION data items
# ---------------------------------------------------------------------------


class TestVisitorDataItems:
    """Tests for extracting data items from WORKING-STORAGE and LINKAGE sections.

    The DATA DIVISION declares all variables used by the program. Each data item
    has a level number, name, and optional clauses (PIC, USAGE, VALUE, REDEFINES).
    Level numbers define a hierarchy: level-01 items are top-level, and higher
    level numbers (02-49) nest under the preceding lower-level item.
    """

    def test_extracts_comp3_item_from_inline_cobol(self):
        """Parse and visit:
            01  WS-ORDER-ID  PIC S9(9) COMP-3 VALUE 12345.

        Must produce DataItemNode with:
        - level=1, name='WS-ORDER-ID'
        - pic.raw='S9(9)', pic.signed=True, pic.size=9
        - usage=UsageType.COMP_3
        - value='12345'
        """
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TEST1.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  WS-ORDER-ID  PIC S9(9) COMP-3 VALUE 12345.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        assert program.data is not None
        assert program.data.working_storage is not None
        items = program.data.working_storage.items
        assert len(items) == 1

        item = items[0]
        assert item.level == 1
        assert item.name == "WS-ORDER-ID"
        assert item.pic is not None
        assert item.pic.raw == "S9(9)"
        assert item.pic.signed is True
        assert item.pic.size == 9
        assert item.usage == UsageType.COMP_3
        assert item.value == "12345"

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
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TEST2.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  WS-ORDER-ID      PIC S9(9) COMP VALUE 12345.\n"
            "       01  WS-ORDER-BYTES   REDEFINES WS-ORDER-ID.\n"
            "           05  WS-BYTE-1    PIC X(1).\n"
            "           05  WS-BYTE-2    PIC X(1).\n"
            "           05  WS-BYTE-3    PIC X(1).\n"
            "           05  WS-BYTE-4    PIC X(1).\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        items = program.data.working_storage.items
        assert len(items) == 2  # Two level-01 items at the top

        # First item: WS-ORDER-ID with COMP and VALUE
        order_id = items[0]
        assert order_id.name == "WS-ORDER-ID"
        assert order_id.usage == UsageType.COMP
        assert order_id.value == "12345"
        assert order_id.redefines is None

        # Second item: WS-ORDER-BYTES, a group with REDEFINES
        order_bytes = items[1]
        assert order_bytes.name == "WS-ORDER-BYTES"
        assert order_bytes.redefines == "WS-ORDER-ID"
        assert order_bytes.pic is None  # Group items have no PIC
        assert len(order_bytes.children) == 4

        # Each child is a level-05 PIC X(1) item
        for i, child in enumerate(order_bytes.children, start=1):
            assert child.level == 5
            assert child.name == f"WS-BYTE-{i}"
            assert child.pic is not None
            assert child.pic.raw == "X(1)"
            assert child.pic.category == "alphanumeric"
            assert child.pic.size == 1

    def test_extracts_comp5_item(self):
        """Parse and visit:
            01  WS-ORA-ORDER-ID  PIC S9(9) COMP-5.

        usage must be UsageType.COMP_5. No VALUE clause → value=None.
        """
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TEST3.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  WS-ORA-ORDER-ID  PIC S9(9) COMP-5.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        items = program.data.working_storage.items
        assert len(items) == 1

        item = items[0]
        assert item.name == "WS-ORA-ORDER-ID"
        assert item.usage == UsageType.COMP_5
        assert item.value is None
        assert item.pic.signed is True
        assert item.pic.size == 9

    def test_extracts_display_numeric_item(self):
        """Parse and visit:
            01  WS-COUNTER  PIC 9(5) DISPLAY VALUE 98765.

        usage=UsageType.DISPLAY, pic.signed=False, pic.size=5
        """
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TEST4.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  WS-COUNTER  PIC 9(5) DISPLAY VALUE 98765.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        items = program.data.working_storage.items
        assert len(items) == 1

        item = items[0]
        assert item.name == "WS-COUNTER"
        assert item.usage == UsageType.DISPLAY
        assert item.pic.signed is False
        assert item.pic.size == 5
        assert item.value == "98765"

    def test_extracts_alphanumeric_item(self):
        """Parse and visit:
            01  WS-STATUS  PIC X(10) VALUE "ACTIVE".

        pic.category='alphanumeric', usage=None or DISPLAY
        """
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TEST5.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            '       01  WS-STATUS  PIC X(10) VALUE "ACTIVE".\n'
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        items = program.data.working_storage.items
        assert len(items) == 1

        item = items[0]
        assert item.name == "WS-STATUS"
        assert item.pic.category == "alphanumeric"
        assert item.pic.size == 10
        assert item.value == "ACTIVE"
        # No explicit USAGE clause → usage is None (defaults to DISPLAY in COBOL)
        assert item.usage is None

    def test_linkage_section_items(self, safe02_called_source: str):
        """Parse and visit SAFE02-CALLED's LINKAGE SECTION:
            01  LS-ORDER-ID     PIC S9(9) COMP.
            01  LS-QUANTITY      PIC S9(9) COMP.
            01  LS-RETURN-CODE   PIC S9(4) COMP.

        Three items, all COMP, in the linkage section.
        """
        program = _parse_and_visit(safe02_called_source)

        assert program.data is not None
        assert program.data.linkage is not None
        items = program.data.linkage.items
        assert len(items) == 3

        # All three are COMP with signed numeric PICs.
        assert items[0].name == "LS-ORDER-ID"
        assert items[0].usage == UsageType.COMP
        assert items[0].pic.raw == "S9(9)"

        assert items[1].name == "LS-QUANTITY"
        assert items[1].usage == UsageType.COMP
        assert items[1].pic.raw == "S9(9)"

        assert items[2].name == "LS-RETURN-CODE"
        assert items[2].usage == UsageType.COMP
        assert items[2].pic.raw == "S9(4)"

    def test_level_hierarchy_nests_children(self):
        """Level-05 items must appear as children of the preceding
        level-01 group item, not as siblings.

        01  GROUP-ITEM.
            05  CHILD-1  PIC X(1).
            05  CHILD-2  PIC X(1).

        GROUP-ITEM.children must have length 2.
        """
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. TEST6.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  GROUP-ITEM.\n"
            "           05  CHILD-1  PIC X(1).\n"
            "           05  CHILD-2  PIC X(1).\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           STOP RUN.\n"
        )
        program = _parse_and_visit(source)

        items = program.data.working_storage.items
        # Only one top-level item (the group)
        assert len(items) == 1

        group = items[0]
        assert group.name == "GROUP-ITEM"
        assert group.pic is None  # Group items have no PIC
        assert len(group.children) == 2
        assert group.children[0].name == "CHILD-1"
        assert group.children[1].name == "CHILD-2"

    def test_safe01_full_working_storage(self, safe01_source: str):
        """Integration: parse SAFE01.cob end-to-end and verify
        all five WORKING-STORAGE items are extracted with correct
        types: COMP-3, COMP-3, DISPLAY, DISPLAY, PIC X.

        SAFE01 declares:
            01  WS-ORDER-ID   PIC S9(9) COMP-3 VALUE 12345.
            01  WS-AMOUNT     PIC S9(9) COMP-3 VALUE 70000.
            01  WS-COUNTER    PIC 9(5) DISPLAY VALUE 98765.
            01  WS-BALANCE    PIC S9(7) DISPLAY VALUE -54321.
            01  WS-STATUS     PIC X(10) VALUE "ACTIVE".
        """
        program = _parse_and_visit(safe01_source)

        assert program.data is not None
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 5

        # Item 1: WS-ORDER-ID — COMP-3, signed, 9 digits
        assert ws.items[0].name == "WS-ORDER-ID"
        assert ws.items[0].usage == UsageType.COMP_3
        assert ws.items[0].pic.signed is True
        assert ws.items[0].pic.size == 9
        assert ws.items[0].value == "12345"

        # Item 2: WS-AMOUNT — COMP-3, signed, 9 digits
        assert ws.items[1].name == "WS-AMOUNT"
        assert ws.items[1].usage == UsageType.COMP_3
        assert ws.items[1].value == "70000"

        # Item 3: WS-COUNTER — DISPLAY, unsigned, 5 digits
        assert ws.items[2].name == "WS-COUNTER"
        assert ws.items[2].usage == UsageType.DISPLAY
        assert ws.items[2].pic.signed is False
        assert ws.items[2].pic.size == 5

        # Item 4: WS-BALANCE — DISPLAY, signed, 7 digits
        assert ws.items[3].name == "WS-BALANCE"
        assert ws.items[3].usage == UsageType.DISPLAY
        assert ws.items[3].pic.signed is True

        # Item 5: WS-STATUS — alphanumeric PIC X(10)
        assert ws.items[4].name == "WS-STATUS"
        assert ws.items[4].pic.category == "alphanumeric"
        assert ws.items[4].pic.size == 10
        assert ws.items[4].value == "ACTIVE"

    def test_endian01_full_working_storage(self, endian01_source: str):
        """Integration: parse ENDIAN01.cob and verify all data
        items including the three REDEFINES groups.

        ENDIAN01 declares (top-level items only):
            01  WS-ORDER-ID       PIC S9(9) COMP VALUE 12345.
            01  WS-ORDER-BYTES    REDEFINES WS-ORDER-ID.  (4 children)
            01  WS-COMP-VAL       PIC S9(9) COMP VALUE 70000.
            01  WS-COMP-BYTES     REDEFINES WS-COMP-VAL.  (4 children)
            01  WS-COMP5-VAL      PIC S9(9) COMP-5 VALUE 70000.
            01  WS-COMP5-BYTES    REDEFINES WS-COMP5-VAL. (4 children)
        """
        program = _parse_and_visit(endian01_source)

        assert program.data is not None
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 6  # Six level-01 items

        # WS-ORDER-ID: COMP with value
        assert ws.items[0].name == "WS-ORDER-ID"
        assert ws.items[0].usage == UsageType.COMP
        assert ws.items[0].value == "12345"

        # WS-ORDER-BYTES: REDEFINES group with 4 children
        assert ws.items[1].name == "WS-ORDER-BYTES"
        assert ws.items[1].redefines == "WS-ORDER-ID"
        assert len(ws.items[1].children) == 4

        # WS-COMP-VAL: COMP with value
        assert ws.items[2].name == "WS-COMP-VAL"
        assert ws.items[2].usage == UsageType.COMP

        # WS-COMP-BYTES: REDEFINES group
        assert ws.items[3].name == "WS-COMP-BYTES"
        assert ws.items[3].redefines == "WS-COMP-VAL"
        assert len(ws.items[3].children) == 4

        # WS-COMP5-VAL: COMP-5
        assert ws.items[4].name == "WS-COMP5-VAL"
        assert ws.items[4].usage == UsageType.COMP_5

        # WS-COMP5-BYTES: REDEFINES group
        assert ws.items[5].name == "WS-COMP5-BYTES"
        assert ws.items[5].redefines == "WS-COMP5-VAL"
        assert len(ws.items[5].children) == 4
