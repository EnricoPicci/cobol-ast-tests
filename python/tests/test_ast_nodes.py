"""Tests for AST node dataclasses — program structure and data items.

These tests verify the typed dataclass hierarchy that represents a COBOL
program's high-level structure (ProgramNode → divisions → sections) and
data description entries (DataItemNode, PicClause, UsageType).

Each test documents a COBOL structural concept alongside the Python
dataclass that models it.
"""

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
    StopRunNode,
    UsageType,
    WorkingStorageSectionNode,
)


class TestProgramNodeStructure:
    """Tests for the root ProgramNode and its required/optional fields."""

    def test_program_node_requires_program_id(self):
        """Every COBOL program has a PROGRAM-ID. The ProgramNode
        dataclass requires it as a mandatory field.

        In COBOL, PROGRAM-ID is specified in the IDENTIFICATION DIVISION:
            IDENTIFICATION DIVISION.
            PROGRAM-ID. HELLO.
        """
        ident = IdentificationDivisionNode(program_id="HELLO")
        node = ProgramNode(program_id="HELLO", identification=ident)

        assert node.program_id == "HELLO"
        assert node.identification.program_id == "HELLO"

    def test_program_node_optional_divisions(self):
        """ENVIRONMENT, DATA, and PROCEDURE divisions are optional
        in the AST (some minimal COBOL programs omit them).

        A minimal COBOL program only requires IDENTIFICATION DIVISION:
            IDENTIFICATION DIVISION.
            PROGRAM-ID. MINIMAL.
        """
        ident = IdentificationDivisionNode(program_id="MINIMAL")
        node = ProgramNode(program_id="MINIMAL", identification=ident)

        # All optional divisions default to None
        assert node.environment is None
        assert node.data is None
        assert node.procedure is None

    def test_program_node_with_all_divisions(self):
        """A full COBOL program has all four divisions. The AST captures
        each one as a typed child node.

        Structure mirrors a typical COBOL program:
            IDENTIFICATION DIVISION.
            ENVIRONMENT DIVISION.
            DATA DIVISION.
            PROCEDURE DIVISION.
        """
        ident = IdentificationDivisionNode(program_id="FULL")
        env = EnvironmentDivisionNode()
        data = DataDivisionNode()
        proc = ProcedureDivisionNode()

        node = ProgramNode(
            program_id="FULL",
            identification=ident,
            environment=env,
            data=data,
            procedure=proc,
        )

        assert node.environment is not None
        assert node.data is not None
        assert node.procedure is not None

    def test_program_node_is_frozen(self):
        """AST nodes are immutable (frozen dataclasses). This prevents
        accidental mutation during analysis passes.
        """
        import pytest

        ident = IdentificationDivisionNode(program_id="IMMUT")
        node = ProgramNode(program_id="IMMUT", identification=ident)

        with pytest.raises(AttributeError):
            node.program_id = "CHANGED"  # type: ignore[misc]


class TestDataDivisionSections:
    """Tests for DataDivisionNode and its child sections."""

    def test_data_division_contains_sections(self):
        """The DATA DIVISION groups items into sections.
        WORKING-STORAGE and LINKAGE are the two sections used
        in the sample files.

        COBOL structure:
            DATA DIVISION.
            WORKING-STORAGE SECTION.
              01 WS-VAR PIC X(10).
            LINKAGE SECTION.
              01 LS-PARAM PIC 9(5).
        """
        ws = WorkingStorageSectionNode()
        ls = LinkageSectionNode()
        data = DataDivisionNode(working_storage=ws, linkage=ls)

        assert data.working_storage is ws
        assert data.linkage is ls

    def test_data_division_optional_sections(self):
        """Both sections are optional — a DATA DIVISION might have
        only WORKING-STORAGE (common) or only LINKAGE (rare), or
        neither (unusual but valid).
        """
        # Only working-storage
        data_ws = DataDivisionNode(working_storage=WorkingStorageSectionNode())
        assert data_ws.working_storage is not None
        assert data_ws.linkage is None

        # Only linkage
        data_ls = DataDivisionNode(linkage=LinkageSectionNode())
        assert data_ls.working_storage is None
        assert data_ls.linkage is not None

    def test_working_storage_items_default_empty(self):
        """A freshly created WORKING-STORAGE SECTION has no items."""
        ws = WorkingStorageSectionNode()
        assert ws.items == ()

    def test_linkage_section_items_default_empty(self):
        """A freshly created LINKAGE SECTION has no items."""
        ls = LinkageSectionNode()
        assert ls.items == ()


class TestProcedureDivision:
    """Tests for ProcedureDivisionNode and its USING clause."""

    def test_procedure_division_using_clause(self):
        """Called programs (like SAFE02-CALLED) receive parameters
        via PROCEDURE DIVISION USING. The AST captures the parameter
        names.

        COBOL example:
            PROCEDURE DIVISION USING LS-PARAM-1 LS-PARAM-2.

        The USING clause lists the LINKAGE SECTION items that the
        calling program passes. This is how COBOL implements
        parameter passing for subprograms.
        """
        proc = ProcedureDivisionNode(
            using_items=("LS-PARAM-1", "LS-PARAM-2"),
        )

        assert proc.using_items == ("LS-PARAM-1", "LS-PARAM-2")

    def test_procedure_division_no_using_clause(self):
        """Main programs (not called by others) have no USING clause.
        The using_items list defaults to empty.

        COBOL example:
            PROCEDURE DIVISION.
            MAIN-PARA.
                DISPLAY "HELLO".
        """
        proc = ProcedureDivisionNode()
        assert proc.using_items == ()

    def test_procedure_division_paragraphs_default_empty(self):
        """A PROCEDURE DIVISION with no paragraphs has an empty tuple."""
        proc = ProcedureDivisionNode()
        assert proc.paragraphs == ()

    def test_procedure_division_with_paragraph(self):
        """A PROCEDURE DIVISION containing a named paragraph with statements.

        COBOL example:
            PROCEDURE DIVISION.
            MAIN-PARA.
                DISPLAY "HELLO".
                STOP RUN.
        """
        para = ParagraphNode(
            name="MAIN-PARA",
            statements=[DisplayNode(operands=["HELLO"]), StopRunNode()],
        )
        proc = ProcedureDivisionNode(paragraphs=(para,))

        assert len(proc.paragraphs) == 1
        assert proc.paragraphs[0].name == "MAIN-PARA"
        assert len(proc.paragraphs[0].statements) == 2


class TestPicClause:
    """Tests for PicClause — the COBOL PIC (PICTURE) clause representation."""

    def test_signed_numeric_pic(self):
        """PIC S9(9) → signed=True, category='numeric', size=9

        The 'S' prefix indicates a signed numeric field. The 9(9)
        means 9 digits. This is the most common PIC for integer fields
        used with COMP or COMP-3.
        """
        pic = PicClause(raw="S9(9)", category="numeric", size=9, signed=True)

        assert pic.raw == "S9(9)"
        assert pic.category == "numeric"
        assert pic.size == 9
        assert pic.signed is True

    def test_unsigned_numeric_pic(self):
        """PIC 9(5) → signed=False, category='numeric', size=5

        No 'S' prefix means unsigned. Used for counters and other
        non-negative values like WS-COUNTER in SAFE01.cob.
        """
        pic = PicClause(raw="9(5)", category="numeric", size=5, signed=False)

        assert pic.raw == "9(5)"
        assert pic.category == "numeric"
        assert pic.size == 5
        assert pic.signed is False

    def test_alphanumeric_pic(self):
        """PIC X(10) → signed=False, category='alphanumeric', size=10

        PIC X defines an alphanumeric field — it can hold letters,
        digits, or special characters. Used for string data like
        WS-STATUS in SAFE01.cob.
        """
        pic = PicClause(raw="X(10)", category="alphanumeric", size=10, signed=False)

        assert pic.raw == "X(10)"
        assert pic.category == "alphanumeric"
        assert pic.size == 10
        assert pic.signed is False


class TestDataItemNode:
    """Tests for DataItemNode — COBOL data description entries.

    Each test corresponds to a real data item from the sample COBOL files,
    documenting both the COBOL semantics and the AST representation.
    """

    def test_comp_data_item_from_endian01(self):
        """ENDIAN01.cob line: 01  WS-ORDER-ID  PIC S9(9) COMP VALUE 12345.

        This is a level-01 binary integer. COMP under BINARY(BE) stores
        the value in big-endian byte order. The AST must capture:
        level=1, name='WS-ORDER-ID', pic.raw='S9(9)',
        usage=COMP, value='12345'.
        """
        pic = PicClause(raw="S9(9)", category="numeric", size=9, signed=True)
        node = DataItemNode(
            level=1,
            name="WS-ORDER-ID",
            pic=pic,
            usage=UsageType.COMP,
            value="12345",
            redefines=None,
        )

        assert node.level == 1
        assert node.name == "WS-ORDER-ID"
        assert node.pic is not None
        assert node.pic.raw == "S9(9)"
        assert node.usage == UsageType.COMP
        assert node.value == "12345"
        assert node.redefines is None
        assert node.children == []

    def test_comp3_data_item_from_safe01(self):
        """SAFE01.cob line: 01  WS-ORDER-ID  PIC S9(9) COMP-3 VALUE 12345.

        COMP-3 is packed decimal — each nibble stores a digit. It is
        endianness-safe because there is no multi-byte integer to reverse.
        """
        pic = PicClause(raw="S9(9)", category="numeric", size=9, signed=True)
        node = DataItemNode(
            level=1,
            name="WS-ORDER-ID",
            pic=pic,
            usage=UsageType.COMP_3,
            value="12345",
            redefines=None,
        )

        assert node.usage == UsageType.COMP_3
        assert node.usage.value == "COMP-3"

    def test_comp5_data_item_from_safe02_called(self):
        """SAFE02-CALLED.cob line: 01  WS-ORA-ORDER-ID  PIC S9(9) COMP-5.

        COMP-5 uses native byte order (little-endian on x86).
        This is the correct type for Oracle host variables.
        """
        pic = PicClause(raw="S9(9)", category="numeric", size=9, signed=True)
        node = DataItemNode(
            level=1,
            name="WS-ORA-ORDER-ID",
            pic=pic,
            usage=UsageType.COMP_5,
            value=None,
            redefines=None,
        )

        assert node.usage == UsageType.COMP_5
        assert node.usage.value == "COMP-5"
        assert node.value is None

    def test_display_numeric_from_safe01(self):
        """SAFE01.cob line: 01  WS-COUNTER  PIC 9(5) DISPLAY VALUE 98765.

        DISPLAY stores each digit as a separate character byte.
        Unsigned (no S in PIC), 5 digits.
        """
        pic = PicClause(raw="9(5)", category="numeric", size=5, signed=False)
        node = DataItemNode(
            level=1,
            name="WS-COUNTER",
            pic=pic,
            usage=UsageType.DISPLAY,
            value="98765",
            redefines=None,
        )

        assert node.usage == UsageType.DISPLAY
        assert node.pic is not None
        assert node.pic.signed is False
        assert node.value == "98765"

    def test_alphanumeric_from_safe01(self):
        """SAFE01.cob line: 01  WS-STATUS  PIC X(10) VALUE "ACTIVE".

        PIC X = alphanumeric. 10 characters. VALUE is a string literal.
        """
        pic = PicClause(raw="X(10)", category="alphanumeric", size=10, signed=False)
        node = DataItemNode(
            level=1,
            name="WS-STATUS",
            pic=pic,
            usage=None,
            value="ACTIVE",
            redefines=None,
        )

        assert node.pic is not None
        assert node.pic.category == "alphanumeric"
        assert node.value == "ACTIVE"
        # No explicit USAGE means implicit DISPLAY
        assert node.usage is None

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
        # Build the four level-05 children
        byte_children = [
            DataItemNode(
                level=5,
                name=f"WS-BYTE-{i}",
                pic=PicClause(raw="X(1)", category="alphanumeric", size=1, signed=False),
                usage=None,
                value=None,
                redefines=None,
            )
            for i in range(1, 5)
        ]

        # The group item that redefines WS-ORDER-ID
        node = DataItemNode(
            level=1,
            name="WS-ORDER-BYTES",
            pic=None,  # Group items have no PIC
            usage=None,
            value=None,
            redefines="WS-ORDER-ID",
            children=byte_children,
        )

        assert node.redefines == "WS-ORDER-ID"
        assert node.pic is None  # Group item
        assert len(node.children) == 4
        assert node.children[0].name == "WS-BYTE-1"
        assert node.children[3].name == "WS-BYTE-4"

    def test_group_item_has_children(self):
        """A group item (level-01 with no PIC) contains subordinate
        items. ENDIAN01's WS-ORDER-BYTES is a group with four
        level-05 children.
        """
        child = DataItemNode(
            level=5,
            name="WS-BYTE-1",
            pic=PicClause(raw="X(1)", category="alphanumeric", size=1, signed=False),
            usage=None,
            value=None,
            redefines=None,
        )
        group = DataItemNode(
            level=1,
            name="WS-ORDER-BYTES",
            pic=None,
            usage=None,
            value=None,
            redefines="WS-ORDER-ID",
            children=[child],
        )

        # Group items have no PIC — their structure is defined by children
        assert group.pic is None
        assert len(group.children) == 1
        assert group.children[0].level == 5


class TestStatementNodes:
    """Tests for PROCEDURE DIVISION statement AST nodes.

    Each test constructs a statement node matching a real COBOL pattern
    from the sample files, verifying both structure and semantics.
    """

    def test_display_with_mixed_operands(self):
        """DISPLAY "ORDER-ID: " WS-ORDER-ID has two operands:
        a string literal and a variable reference.
        """
        node = DisplayNode(operands=['"ORDER-ID: "', "WS-ORDER-ID"])

        assert len(node.operands) == 2
        assert node.operands[0] == '"ORDER-ID: "'
        assert node.operands[1] == "WS-ORDER-ID"

    def test_move_with_figurative_constant(self):
        """MOVE ZEROS TO WS-QUANTITY — ZEROS is a COBOL figurative
        constant that fills the target with zero values.
        """
        node = MoveNode(source="ZEROS", targets=["WS-QUANTITY"])

        assert node.source == "ZEROS"
        assert node.targets == ["WS-QUANTITY"]

    def test_move_with_multiple_targets(self):
        """MOVE 0 TO WS-A WS-B — MOVE can assign to multiple targets."""
        node = MoveNode(source="0", targets=["WS-A", "WS-B"])

        assert node.source == "0"
        assert len(node.targets) == 2

    def test_add_node(self):
        """ADD 1000 TO WS-AMOUNT — adds a numeric value to a variable."""
        node = AddNode(value="1000", target="WS-AMOUNT")

        assert node.value == "1000"
        assert node.target == "WS-AMOUNT"

    def test_call_with_using_parameters(self):
        """CALL "SAFE02-CALLED" USING WS-ORDER-ID WS-QUANTITY WS-RETURN-CODE
        — three parameters passed by reference (default).
        """
        node = CallNode(
            program_name="SAFE02-CALLED",
            using_items=["WS-ORDER-ID", "WS-QUANTITY", "WS-RETURN-CODE"],
        )

        assert node.program_name == "SAFE02-CALLED"
        assert len(node.using_items) == 3
        assert node.using_items[0] == "WS-ORDER-ID"

    def test_if_with_else_branch(self):
        """IF SQLCODE = 0 ... ELSE ... END-IF — both branches
        must be captured in the AST.
        """
        then_stmts = [MoveNode(source="WS-ORA-QUANTITY", targets=["LS-QUANTITY"])]
        else_stmts = [MoveNode(source="0", targets=["LS-QUANTITY"])]

        node = IfNode(
            condition="SQLCODE = 0",
            then_statements=then_stmts,
            else_statements=else_stmts,
        )

        assert node.condition == "SQLCODE = 0"
        assert len(node.then_statements) == 1
        assert len(node.else_statements) == 1
        # Verify nested statement types
        assert isinstance(node.then_statements[0], MoveNode)
        assert isinstance(node.else_statements[0], MoveNode)

    def test_if_without_else(self):
        """IF with no ELSE branch — else_statements is an empty list."""
        node = IfNode(
            condition="WS-STATUS = 'ACTIVE'",
            then_statements=[DisplayNode(operands=["ACTIVE"])],
            else_statements=[],
        )

        assert node.else_statements == []
        assert len(node.then_statements) == 1

    def test_stop_run_node(self):
        """STOP RUN has no fields — it simply terminates the program."""
        node = StopRunNode()
        assert isinstance(node, StopRunNode)

    def test_goback_node(self):
        """GOBACK has no fields — it returns control to the caller."""
        node = GobackNode()
        assert isinstance(node, GobackNode)

    def test_exec_sql_preserves_raw_sql_text(self):
        """EXEC SQL SELECT QUANTITY INTO :WS-ORA-QUANTITY ... END-EXEC
        — the SQL text between the delimiters is stored as-is,
        including host variable references (:WS-ORA-QUANTITY).
        """
        sql = (
            "SELECT QUANTITY INTO :WS-ORA-QUANTITY"
            " FROM ORDERS WHERE ORDER_ID = :WS-ORA-ORDER-ID"
        )
        node = ExecSqlNode(sql_text=sql)

        assert ":WS-ORA-QUANTITY" in node.sql_text
        assert ":WS-ORA-ORDER-ID" in node.sql_text

    def test_exec_sql_include(self):
        """EXEC SQL INCLUDE SQLCA END-EXEC — this is a preprocessor
        directive to include the SQLCA copybook. It appears as an
        ExecSqlNode with sql_text='INCLUDE SQLCA'.
        """
        node = ExecSqlNode(sql_text="INCLUDE SQLCA")

        assert node.sql_text == "INCLUDE SQLCA"


class TestParagraphNode:
    """Tests for ParagraphNode — named blocks of statements."""

    def test_paragraph_with_statements(self):
        """MAIN-PARA contains a sequence of statements.

        COBOL example:
            MAIN-PARA.
                DISPLAY "ORDER-ID: " WS-ORDER-ID.
                ADD 1000 TO WS-AMOUNT.
                STOP RUN.
        """
        stmts = [
            DisplayNode(operands=['"ORDER-ID: "', "WS-ORDER-ID"]),
            AddNode(value="1000", target="WS-AMOUNT"),
            StopRunNode(),
        ]
        para = ParagraphNode(name="MAIN-PARA", statements=stmts)

        assert para.name == "MAIN-PARA"
        assert len(para.statements) == 3
        assert isinstance(para.statements[0], DisplayNode)
        assert isinstance(para.statements[1], AddNode)
        assert isinstance(para.statements[2], StopRunNode)

    def test_empty_paragraph(self):
        """A paragraph with no statements (edge case)."""
        para = ParagraphNode(name="EMPTY-PARA", statements=[])

        assert para.name == "EMPTY-PARA"
        assert para.statements == []
