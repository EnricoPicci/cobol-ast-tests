"""Tests for AST node dataclasses — core program structure.

These tests verify the typed dataclass hierarchy that represents a COBOL
program's high-level structure: ProgramNode → divisions → sections.

Each test documents a COBOL structural concept alongside the Python
dataclass that models it.
"""

from cobol_ast.ast_nodes import (
    DataDivisionNode,
    EnvironmentDivisionNode,
    IdentificationDivisionNode,
    LinkageSectionNode,
    ProcedureDivisionNode,
    ProgramNode,
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
        """A freshly created WORKING-STORAGE SECTION has no items.
        Items (DataItemNode) are added in Step 6.
        """
        ws = WorkingStorageSectionNode()
        assert ws.items == ()

    def test_linkage_section_items_default_empty(self):
        """A freshly created LINKAGE SECTION has no items.
        Items (DataItemNode) are added in Step 6.
        """
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
        """Paragraphs (ParagraphNode) are added in Step 7.
        Until then, the list defaults to empty.
        """
        proc = ProcedureDivisionNode()
        assert proc.paragraphs == ()
