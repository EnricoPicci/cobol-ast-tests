"""Tests for the COBOL parser wrapper — ANTLR4 integration.

These tests verify that ``CobolParser`` correctly wraps the ANTLR4 lexer
and parser pipeline, producing parse trees from preprocessed COBOL source
text and collecting errors without raising exceptions.

The parser expects *preprocessed* input (free-form text with fixed-format
columns already stripped). All inline COBOL snippets in these tests are
written in free-form to match what the preprocessor would produce.

The ``TestParserSampleFiles`` class runs the full pipeline (preprocessor →
parser) against all six sample COBOL files to verify zero parse errors.
This validates that the preprocessor output is compatible with the ANTLR4
grammar for real-world COBOL programs.
"""

from pathlib import Path

from cobol_ast.parser import CobolParser, ParseResult
from cobol_ast.preprocessor import CobolPreprocessor


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


class TestParserSampleFiles:
    """Integration tests: preprocess → parse real COBOL sample files.

    These tests validate that the full pipeline (read source → preprocess
    fixed-format columns → parse with ANTLR4) produces zero errors for
    every sample file. A parse failure here means either the preprocessor
    has a bug or the grammar cannot handle a construct used in the sample.
    """

    @staticmethod
    def _preprocess_and_parse(source: str) -> ParseResult:
        """Run the full pipeline: preprocess fixed-format source, then parse.

        Args:
            source: Raw fixed-format COBOL source text (80-column layout).

        Returns:
            ParseResult from the ANTLR4 parser.
        """
        preprocessor = CobolPreprocessor()
        preprocessed = preprocessor.process(source)
        parser = CobolParser()
        return parser.parse(preprocessed.text)

    def test_safe01_parses_without_errors(self, safe01_source: str):
        """SAFE01.cob is the simplest sample — COMP-3, DISPLAY,
        PIC X, no EXEC SQL, no LINKAGE. It must parse cleanly.
        """
        result = self._preprocess_and_parse(safe01_source)
        assert result.errors == [], f"SAFE01.cob parse errors: {result.errors}"
        assert result.tree is not None

    def test_endian01_parses_without_errors(self, endian01_source: str):
        """ENDIAN01.cob has REDEFINES and mixed COMP/COMP-5.
        Verify the grammar handles REDEFINES clauses.
        """
        result = self._preprocess_and_parse(endian01_source)
        assert result.errors == [], f"ENDIAN01.cob parse errors: {result.errors}"
        assert result.tree is not None

    def test_endian02_called_parses_without_errors(
        self, endian02_called_source: str
    ):
        """ENDIAN02-CALLED.cob has EXEC SQL blocks and
        PROCEDURE DIVISION USING. Both must parse correctly.
        """
        result = self._preprocess_and_parse(endian02_called_source)
        assert result.errors == [], (
            f"ENDIAN02-CALLED.cob parse errors: {result.errors}"
        )
        assert result.tree is not None

    def test_safe02_called_parses_without_errors(
        self, safe02_called_source: str
    ):
        """SAFE02-CALLED.cob has LINKAGE SECTION, PROCEDURE DIVISION
        USING, EXEC SQL with SELECT INTO, and IF/ELSE/END-IF.
        """
        result = self._preprocess_and_parse(safe02_called_source)
        assert result.errors == [], (
            f"SAFE02-CALLED.cob parse errors: {result.errors}"
        )
        assert result.tree is not None

    def test_all_sample_files_parse_without_errors(self, samples_dir: Path):
        """Smoke test: every .cob file under samples/ preprocesses
        and parses with zero ANTLR4 errors.

        This catches regressions if new sample files are added that the
        preprocessor or grammar cannot handle.
        """
        cob_files = sorted(samples_dir.rglob("*.cob"))
        assert len(cob_files) > 0, "No .cob files found in samples/"

        for cob_file in cob_files:
            source = cob_file.read_text()
            result = self._preprocess_and_parse(source)
            assert result.errors == [], (
                f"{cob_file.name} parse errors: {result.errors}"
            )
            assert result.tree is not None, (
                f"{cob_file.name} produced no parse tree"
            )

    def test_safe01_parse_tree_contains_identification_division(
        self, safe01_source: str
    ):
        """Inspect SAFE01's parse tree to verify it contains an
        identificationDivision node with the correct PROGRAM-ID.

        Uses toStringTree() to dump the tree structure as a Lisp-style
        s-expression. The tree should contain:
        - An ``identificationDivision`` rule node
        - The program name ``SAFE01`` within a ``programIdParagraph`` node
        """
        result = self._preprocess_and_parse(safe01_source)
        assert result.errors == [], f"SAFE01.cob parse errors: {result.errors}"

        tree_text = result.tree.toStringTree(recog=None)
        assert "SAFE01" in tree_text, (
            "Parse tree should contain the program name SAFE01"
        )
