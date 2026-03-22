"""End-to-end integration tests for the COBOL AST parser public API.

These tests validate the complete pipeline — from raw COBOL source to typed
AST dataclasses — using both ``parse_cobol_file()`` and ``parse_cobol_source()``.

Each test in ``TestEndToEndSampleFiles`` parses a real sample file through:
    raw source → CobolPreprocessor → CobolParser (ANTLR4 CST) → CobolAstVisitor → AST

and verifies that the resulting AST structure matches the known content of
that file: program ID, data items, statements, and structural relationships.
"""

from pathlib import Path

import pytest

from cobol_ast import (
    AddNode,
    CallNode,
    CobolParseError,
    DisplayNode,
    ExecSqlNode,
    GobackNode,
    IfNode,
    MoveNode,
    ProgramNode,
    StopRunNode,
    UsageType,
    parse_cobol_file,
    parse_cobol_source,
)


class TestEndToEndSampleFiles:
    """Full pipeline integration tests against every sample .cob file.

    Each test parses a real sample file through the complete pipeline
    (preprocess → parse → visit → AST) and verifies the resulting
    AST structure matches the known content of that file.
    """

    def test_safe01_full_ast(self, samples_dir: Path) -> None:
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
        path = samples_dir / "endianness" / "without-issues" / "SAFE01.cob"
        program = parse_cobol_file(path)

        # Root structure
        assert isinstance(program, ProgramNode)
        assert program.program_id == "SAFE01"
        assert program.identification is not None
        assert program.environment is not None
        assert program.data is not None
        assert program.procedure is not None

        # WORKING-STORAGE: 5 top-level items, no linkage
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 5
        assert program.data.linkage is None

        # WS-ORDER-ID: PIC S9(9) COMP-3 VALUE 12345
        order_id = ws.items[0]
        assert order_id.name == "WS-ORDER-ID"
        assert order_id.level == 1
        assert order_id.pic is not None
        assert order_id.pic.category == "numeric"
        assert order_id.pic.size == 9
        assert order_id.pic.signed is True
        assert order_id.usage == UsageType.COMP_3
        assert order_id.value == "12345"

        # WS-AMOUNT: PIC S9(9) COMP-3 VALUE 70000
        amount = ws.items[1]
        assert amount.name == "WS-AMOUNT"
        assert amount.usage == UsageType.COMP_3
        assert amount.value == "70000"

        # WS-COUNTER: PIC 9(5) DISPLAY VALUE 98765
        counter = ws.items[2]
        assert counter.name == "WS-COUNTER"
        assert counter.usage == UsageType.DISPLAY
        assert counter.pic.signed is False
        assert counter.pic.size == 5
        assert counter.value == "98765"

        # WS-BALANCE: PIC S9(7) DISPLAY VALUE -54321
        balance = ws.items[3]
        assert balance.name == "WS-BALANCE"
        assert balance.usage == UsageType.DISPLAY
        assert balance.pic.signed is True
        assert balance.value == "-54321"

        # WS-STATUS: PIC X(10) VALUE "ACTIVE"
        status = ws.items[4]
        assert status.name == "WS-STATUS"
        assert status.pic.category == "alphanumeric"
        assert status.pic.size == 10
        assert status.value == "ACTIVE"

        # PROCEDURE DIVISION: one paragraph (MAIN-PARA)
        proc = program.procedure
        assert len(proc.paragraphs) == 1
        assert proc.paragraphs[0].name == "MAIN-PARA"
        assert len(proc.using_items) == 0

        # Statements: multiple DISPLAYs, one ADD, then STOP RUN
        stmts = proc.paragraphs[0].statements
        display_count = sum(1 for s in stmts if isinstance(s, DisplayNode))
        assert display_count > 0
        add_stmts = [s for s in stmts if isinstance(s, AddNode)]
        assert len(add_stmts) == 1
        assert add_stmts[0].value == "1000"
        assert add_stmts[0].target == "WS-AMOUNT"
        # Last statement is STOP RUN
        assert isinstance(stmts[-1], StopRunNode)

    def test_endian01_full_ast(self, samples_dir: Path) -> None:
        """ENDIAN01.cob — REDEFINES and mixed COMP/COMP-5.

        Expected AST:
        - program_id: 'ENDIAN01'
        - working_storage: 6 top-level items (3 REDEFINES groups)
          - WS-ORDER-ID (COMP) + WS-ORDER-BYTES (REDEFINES, 4 children)
          - WS-COMP-VAL (COMP) + WS-COMP-BYTES (REDEFINES, 4 children)
          - WS-COMP5-VAL (COMP-5) + WS-COMP5-BYTES (REDEFINES, 4 children)
        - procedure: DISPLAY statements, STOP RUN
        """
        path = samples_dir / "endianness" / "with-issues" / "ENDIAN01.cob"
        program = parse_cobol_file(path)

        assert program.program_id == "ENDIAN01"
        assert program.environment is not None
        assert program.data is not None
        assert program.data.linkage is None

        # WORKING-STORAGE: 6 top-level items
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 6

        # WS-ORDER-ID: PIC S9(9) COMP VALUE 12345
        assert ws.items[0].name == "WS-ORDER-ID"
        assert ws.items[0].usage == UsageType.COMP
        assert ws.items[0].value == "12345"

        # WS-ORDER-BYTES: REDEFINES WS-ORDER-ID, 4 children (PIC X(1) each)
        order_bytes = ws.items[1]
        assert order_bytes.name == "WS-ORDER-BYTES"
        assert order_bytes.redefines == "WS-ORDER-ID"
        assert len(order_bytes.children) == 4
        for child in order_bytes.children:
            assert child.level == 5
            assert child.pic.category == "alphanumeric"
            assert child.pic.size == 1

        # WS-COMP-VAL: PIC S9(9) COMP VALUE 70000
        assert ws.items[2].name == "WS-COMP-VAL"
        assert ws.items[2].usage == UsageType.COMP
        assert ws.items[2].value == "70000"

        # WS-COMP-BYTES: REDEFINES WS-COMP-VAL, 4 children
        comp_bytes = ws.items[3]
        assert comp_bytes.name == "WS-COMP-BYTES"
        assert comp_bytes.redefines == "WS-COMP-VAL"
        assert len(comp_bytes.children) == 4

        # WS-COMP5-VAL: PIC S9(9) COMP-5 VALUE 70000
        assert ws.items[4].name == "WS-COMP5-VAL"
        assert ws.items[4].usage == UsageType.COMP_5
        assert ws.items[4].value == "70000"

        # WS-COMP5-BYTES: REDEFINES WS-COMP5-VAL, 4 children
        comp5_bytes = ws.items[5]
        assert comp5_bytes.name == "WS-COMP5-BYTES"
        assert comp5_bytes.redefines == "WS-COMP5-VAL"
        assert len(comp5_bytes.children) == 4

        # PROCEDURE DIVISION: MAIN-PARA with DISPLAYs and STOP RUN
        proc = program.procedure
        assert len(proc.paragraphs) == 1
        assert proc.paragraphs[0].name == "MAIN-PARA"
        stmts = proc.paragraphs[0].statements
        assert all(isinstance(s, (DisplayNode, StopRunNode)) for s in stmts)
        assert isinstance(stmts[-1], StopRunNode)

    def test_endian02_caller_full_ast(self, samples_dir: Path) -> None:
        """ENDIAN02-CALLER.cob — CALL with USING.

        Expected AST:
        - program_id: 'ENDIAN02-CALLER'
        - working_storage: 3 COMP items
        - procedure: MOVE, DISPLAY, CALL, DISPLAY, STOP RUN
        - CallNode.program_name: 'ENDIAN02-CALLED'
        - CallNode.using_items: 3 parameters
        """
        path = samples_dir / "endianness" / "with-issues" / "ENDIAN02-CALLER.cob"
        program = parse_cobol_file(path)

        assert program.program_id == "ENDIAN02-CALLER"
        assert program.environment is not None

        # WORKING-STORAGE: 3 COMP items (WS-ORDER-ID, WS-QUANTITY, WS-RETURN-CODE)
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 3
        for item in ws.items:
            assert item.usage == UsageType.COMP

        assert ws.items[0].name == "WS-ORDER-ID"
        assert ws.items[1].name == "WS-QUANTITY"
        assert ws.items[2].name == "WS-RETURN-CODE"

        # No linkage section in the caller
        assert program.data.linkage is None

        # PROCEDURE: MAIN-PARA with MOVE, DISPLAY, CALL, DISPLAY, STOP RUN
        proc = program.procedure
        assert len(proc.paragraphs) == 1
        assert proc.paragraphs[0].name == "MAIN-PARA"
        assert len(proc.using_items) == 0

        stmts = proc.paragraphs[0].statements
        # Find the CALL statement
        call_stmts = [s for s in stmts if isinstance(s, CallNode)]
        assert len(call_stmts) == 1
        call = call_stmts[0]
        assert call.program_name == "ENDIAN02-CALLED"
        assert len(call.using_items) == 3
        assert call.using_items[0] == "WS-ORDER-ID"
        assert call.using_items[1] == "WS-QUANTITY"
        assert call.using_items[2] == "WS-RETURN-CODE"

        # MOVE statements (3 MOVEs: 12345, ZEROS, ZEROS)
        move_stmts = [s for s in stmts if isinstance(s, MoveNode)]
        assert len(move_stmts) == 3

        # Ends with STOP RUN
        assert isinstance(stmts[-1], StopRunNode)

    def test_endian02_called_full_ast(self, samples_dir: Path) -> None:
        """ENDIAN02-CALLED.cob — EXEC SQL, LINKAGE, IF/ELSE.

        Expected AST:
        - program_id: 'ENDIAN02-CALLED'
        - working_storage: WS-QUANTITY (COMP) + EXEC SQL INCLUDE SQLCA
        - linkage: 3 COMP items
        - procedure USING: 3 parameters
        - Statements: EXEC SQL SELECT, IF/ELSE, GOBACK
        """
        path = samples_dir / "endianness" / "with-issues" / "ENDIAN02-CALLED.cob"
        program = parse_cobol_file(path)

        assert program.program_id == "ENDIAN02-CALLED"
        assert program.environment is not None

        # WORKING-STORAGE: WS-QUANTITY (COMP)
        # The EXEC SQL INCLUDE SQLCA is not modelled as a data item —
        # only Format-1 entries are extracted.
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 1
        assert ws.items[0].name == "WS-QUANTITY"
        assert ws.items[0].usage == UsageType.COMP

        # LINKAGE SECTION: 3 COMP items
        linkage = program.data.linkage
        assert linkage is not None
        assert len(linkage.items) == 3
        assert linkage.items[0].name == "LS-ORDER-ID"
        assert linkage.items[1].name == "LS-QUANTITY"
        assert linkage.items[2].name == "LS-RETURN-CODE"
        for item in linkage.items:
            assert item.usage == UsageType.COMP

        # PROCEDURE DIVISION USING: 3 parameters
        proc = program.procedure
        assert len(proc.using_items) == 3
        assert proc.using_items[0] == "LS-ORDER-ID"
        assert proc.using_items[1] == "LS-QUANTITY"
        assert proc.using_items[2] == "LS-RETURN-CODE"

        # Statements: EXEC SQL, IF/ELSE, GOBACK
        stmts = proc.paragraphs[0].statements
        assert proc.paragraphs[0].name == "MAIN-PARA"

        # EXEC SQL SELECT
        exec_stmts = [s for s in stmts if isinstance(s, ExecSqlNode)]
        assert len(exec_stmts) == 1
        assert "SELECT" in exec_stmts[0].sql_text
        assert ":WS-QUANTITY" in exec_stmts[0].sql_text
        assert ":LS-ORDER-ID" in exec_stmts[0].sql_text

        # IF/ELSE with SQLCODE = 0
        if_stmts = [s for s in stmts if isinstance(s, IfNode)]
        assert len(if_stmts) == 1
        assert "SQLCODE" in if_stmts[0].condition
        assert len(if_stmts[0].then_statements) > 0
        assert len(if_stmts[0].else_statements) > 0

        # GOBACK
        assert isinstance(stmts[-1], GobackNode)

    def test_safe02_caller_full_ast(self, samples_dir: Path) -> None:
        """SAFE02-CALLER.cob — same structure as ENDIAN02-CALLER
        but calls SAFE02-CALLED.

        Expected AST mirrors ENDIAN02-CALLER with different names.
        """
        path = samples_dir / "endianness" / "without-issues" / "SAFE02-CALLER.cob"
        program = parse_cobol_file(path)

        assert program.program_id == "SAFE02-CALLER"
        assert program.environment is not None

        # WORKING-STORAGE: 3 COMP items
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 3
        for item in ws.items:
            assert item.usage == UsageType.COMP

        assert program.data.linkage is None

        # PROCEDURE: MAIN-PARA with MOVE, DISPLAY, CALL, STOP RUN
        proc = program.procedure
        assert len(proc.paragraphs) == 1
        assert proc.paragraphs[0].name == "MAIN-PARA"

        # CALL SAFE02-CALLED with 3 parameters
        stmts = proc.paragraphs[0].statements
        call_stmts = [s for s in stmts if isinstance(s, CallNode)]
        assert len(call_stmts) == 1
        assert call_stmts[0].program_name == "SAFE02-CALLED"
        assert len(call_stmts[0].using_items) == 3

        assert isinstance(stmts[-1], StopRunNode)

    def test_safe02_called_full_ast(self, samples_dir: Path) -> None:
        """SAFE02-CALLED.cob — correct endianness pattern.

        Expected AST:
        - program_id: 'SAFE02-CALLED'
        - working_storage: EXEC SQL INCLUDE SQLCA5 + 2 COMP-5 items
        - linkage: 3 COMP items
        - procedure USING: 3 parameters
        - Statements: MOVE, EXEC SQL SELECT, IF/ELSE, GOBACK
        """
        path = samples_dir / "endianness" / "without-issues" / "SAFE02-CALLED.cob"
        program = parse_cobol_file(path)

        assert program.program_id == "SAFE02-CALLED"
        assert program.environment is not None

        # WORKING-STORAGE: 2 COMP-5 items (EXEC SQL INCLUDE is not a data item)
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 2
        assert ws.items[0].name == "WS-ORA-ORDER-ID"
        assert ws.items[0].usage == UsageType.COMP_5
        assert ws.items[1].name == "WS-ORA-QUANTITY"
        assert ws.items[1].usage == UsageType.COMP_5

        # LINKAGE SECTION: 3 COMP items
        linkage = program.data.linkage
        assert linkage is not None
        assert len(linkage.items) == 3
        assert linkage.items[0].name == "LS-ORDER-ID"
        assert linkage.items[1].name == "LS-QUANTITY"
        assert linkage.items[2].name == "LS-RETURN-CODE"
        for item in linkage.items:
            assert item.usage == UsageType.COMP

        # PROCEDURE DIVISION USING: 3 parameters
        proc = program.procedure
        assert len(proc.using_items) == 3

        # Statements: MOVE, EXEC SQL, IF/ELSE, GOBACK
        stmts = proc.paragraphs[0].statements
        assert proc.paragraphs[0].name == "MAIN-PARA"

        # MOVE LS-ORDER-ID TO WS-ORA-ORDER-ID
        move_stmts = [s for s in stmts if isinstance(s, MoveNode)]
        assert len(move_stmts) == 1
        assert move_stmts[0].source == "LS-ORDER-ID"
        assert move_stmts[0].targets == ["WS-ORA-ORDER-ID"]

        # EXEC SQL SELECT
        exec_stmts = [s for s in stmts if isinstance(s, ExecSqlNode)]
        assert len(exec_stmts) == 1
        assert "SELECT" in exec_stmts[0].sql_text
        assert ":WS-ORA-QUANTITY" in exec_stmts[0].sql_text
        assert ":WS-ORA-ORDER-ID" in exec_stmts[0].sql_text

        # IF/ELSE with SQLCODE = 0
        if_stmts = [s for s in stmts if isinstance(s, IfNode)]
        assert len(if_stmts) == 1
        assert "SQLCODE" in if_stmts[0].condition
        # Then branch: MOVE WS-ORA-QUANTITY TO LS-QUANTITY, MOVE 0 TO LS-RETURN-CODE
        assert len(if_stmts[0].then_statements) == 2
        # Else branch: MOVE 0 TO LS-QUANTITY, MOVE SQLCODE TO LS-RETURN-CODE
        assert len(if_stmts[0].else_statements) == 2

        # GOBACK
        assert isinstance(stmts[-1], GobackNode)


class TestParseCobolSource:
    def test_parse_inline_cobol_snippet(self) -> None:
        """parse_cobol_source() accepts a string of COBOL source.

        This is the primary API for testing — tests provide inline
        COBOL snippets rather than reading files.

        The snippet uses fixed-format layout (7-char prefix) so the
        preprocessor strips it into free-form text for parsing.
        """
        # Fixed-format COBOL: 6-char sequence area + 1-char indicator + code area.
        source = (
            "       IDENTIFICATION DIVISION.\n"
            "       PROGRAM-ID. INLINE-TEST.\n"
            "       DATA DIVISION.\n"
            "       WORKING-STORAGE SECTION.\n"
            "       01  WS-VAR  PIC 9(5) VALUE 100.\n"
            "       PROCEDURE DIVISION.\n"
            "       MAIN-PARA.\n"
            "           DISPLAY WS-VAR.\n"
            "           STOP RUN.\n"
        )
        program = parse_cobol_source(source)

        assert isinstance(program, ProgramNode)
        assert program.program_id == "INLINE-TEST"

        # One data item in WORKING-STORAGE
        ws = program.data.working_storage
        assert ws is not None
        assert len(ws.items) == 1
        assert ws.items[0].name == "WS-VAR"
        assert ws.items[0].pic.size == 5
        assert ws.items[0].value == "100"

        # Two statements: DISPLAY and STOP RUN
        stmts = program.procedure.paragraphs[0].statements
        assert len(stmts) == 2
        assert isinstance(stmts[0], DisplayNode)
        assert isinstance(stmts[1], StopRunNode)

    def test_parse_error_raises_exception(self) -> None:
        """Completely invalid input raises CobolParseError."""
        with pytest.raises(CobolParseError) as exc_info:
            parse_cobol_source("THIS IS NOT VALID COBOL AT ALL")
        # The exception should contain at least one error message.
        assert len(exc_info.value.errors) > 0


class TestParseCobolFile:
    def test_parse_file_reads_and_parses(self, samples_dir: Path) -> None:
        """parse_cobol_file() takes a Path and returns a ProgramNode.
        Verify with SAFE01.cob.
        """
        path = samples_dir / "endianness" / "without-issues" / "SAFE01.cob"
        program = parse_cobol_file(path)

        assert isinstance(program, ProgramNode)
        assert program.program_id == "SAFE01"
        assert program.data is not None
        assert program.procedure is not None
