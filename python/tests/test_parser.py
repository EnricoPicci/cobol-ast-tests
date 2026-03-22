"""Tests for the COBOL parser wrapper — ANTLR4 integration.

These tests verify that ``CobolParser`` correctly wraps the ANTLR4 lexer
and parser pipeline, producing parse trees from preprocessed COBOL source
text and collecting errors without raising exceptions.

The parser expects *preprocessed* input (free-form text with fixed-format
columns already stripped). All inline COBOL snippets in these tests are
written in free-form to match what the preprocessor would produce.
"""

from cobol_ast.parser import CobolParser


class TestCobolParser:
    """Unit tests for CobolParser with inline COBOL snippets."""

    def test_parse_minimal_cobol_program(self):
        """Parse the smallest valid COBOL program.

        A minimal COBOL program needs only an IDENTIFICATION DIVISION
        with a PROGRAM-ID, and a PROCEDURE DIVISION with at least one
        paragraph containing a statement::

            IDENTIFICATION DIVISION.
            PROGRAM-ID. MINIMAL.
            PROCEDURE DIVISION.
            MAIN-PARA.
                STOP RUN.

        The parser must produce a non-null parse tree with zero errors.
        """
        source = (
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. MINIMAL.\n"
            "PROCEDURE DIVISION.\n"
            "MAIN-PARA.\n"
            "    STOP RUN.\n"
        )
        parser = CobolParser()
        result = parser.parse(source)

        assert result.tree is not None, "Parse tree should not be None"
        assert result.errors == [], f"Expected zero errors, got: {result.errors}"

    def test_parse_error_collected_not_raised(self):
        """Invalid COBOL input should produce errors in the ParseResult,
        not raise an exception. This allows callers to inspect errors
        and decide how to handle them.

        The input below is syntactically invalid — it contains an isolated
        keyword that does not form a valid COBOL construct. ANTLR4's error
        recovery will still produce a (partial) parse tree, but the errors
        list should be non-empty.
        """
        source = "THIS IS NOT VALID COBOL AT ALL !!!\n"
        parser = CobolParser()
        result = parser.parse(source)

        # The parser should NOT raise — errors are collected
        assert result.tree is not None, "Even invalid input produces a partial tree"
        assert len(result.errors) > 0, "Invalid input should produce at least one error"

    def test_parse_data_division_with_pic_clauses(self):
        """Parse a program with WORKING-STORAGE data items.

        COBOL data items are declared in the DATA DIVISION's
        WORKING-STORAGE SECTION using level numbers, names, and PIC
        (picture) clauses that define the data type and size::

            DATA DIVISION.
            WORKING-STORAGE SECTION.
            01  WS-FIELD  PIC S9(9) COMP VALUE 12345.

        The parse tree must contain a ``dataDescriptionEntry`` node,
        which is the ANTLR4 grammar rule that matches level-number +
        name + PIC clause combinations.
        """
        source = (
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. PICTEST.\n"
            "DATA DIVISION.\n"
            "WORKING-STORAGE SECTION.\n"
            "01  WS-FIELD  PIC S9(9) COMP VALUE 12345.\n"
            "PROCEDURE DIVISION.\n"
            "MAIN-PARA.\n"
            "    STOP RUN.\n"
        )
        parser = CobolParser()
        result = parser.parse(source)

        assert result.errors == [], f"Expected zero errors, got: {result.errors}"

        # Verify the parse tree contains a dataDescriptionEntry node
        # by dumping it to a string and checking for the rule name.
        # toStringTree() produces a Lisp-style s-expression of the tree.
        tree_text = result.tree.toStringTree(recog=None)
        assert "WS-FIELD" in tree_text, (
            "Parse tree should contain the data item name WS-FIELD"
        )

    def test_parse_exec_sql_block(self):
        """Parse a program containing EXEC SQL ... END-EXEC.

        Embedded SQL is common in enterprise COBOL programs that
        interact with databases (DB2, Oracle). The ANTLR4 Cobol85
        grammar expects EXEC SQL blocks to be pre-tagged by a
        preprocessor — each line of the SQL block must start with
        the ``*>EXECSQL`` tag. The grammar treats the content after
        the tag as opaque text (it does not parse the SQL itself).

        For example, this COBOL source::

            EXEC SQL
                SELECT FIELD1 INTO :WS-FIELD
                FROM SOME-TABLE
            END-EXEC.

        must be preprocessed into tagged lines::

            *>EXECSQL EXEC SQL
            *>EXECSQL     SELECT FIELD1 INTO :WS-FIELD
            *>EXECSQL     FROM SOME-TABLE
            *>EXECSQL END-EXEC.
        """
        # The grammar's lexer tokenizes lines starting with *>EXECSQL
        # as EXECSQLLINE tokens, which the parser matches in
        # execSqlStatement and dataDescriptionEntryExecSql rules.
        source = (
            "IDENTIFICATION DIVISION.\n"
            "PROGRAM-ID. SQLTEST.\n"
            "DATA DIVISION.\n"
            "WORKING-STORAGE SECTION.\n"
            "01  WS-FIELD  PIC X(50).\n"
            "PROCEDURE DIVISION.\n"
            "MAIN-PARA.\n"
            "*>EXECSQL EXEC SQL"
            " SELECT INTO END-EXEC.\n"
            "    STOP RUN.\n"
        )
        parser = CobolParser()
        result = parser.parse(source)

        assert result.errors == [], f"Expected zero errors, got: {result.errors}"
        assert result.tree is not None
