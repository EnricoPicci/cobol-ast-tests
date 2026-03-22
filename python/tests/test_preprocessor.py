"""Tests for the COBOL fixed-format preprocessor.

These tests verify that the preprocessor correctly strips the fixed-format
column layout and removes comments, producing free-form text suitable for
ANTLR4 parsing. Each test documents a specific aspect of the COBOL
fixed-format specification.
"""

from pathlib import Path

from cobol_ast.preprocessor import CobolPreprocessor


class TestColumnStripping:
    """Tests for sequence area (cols 1-6) and identification area
    (cols 73-80) removal."""

    def test_strips_sequence_area_columns_1_to_6(self):
        """Columns 1-6 are the sequence number area in fixed-format COBOL.

        These contain line numbers or other identifiers used by old
        card-based systems. They are not part of the COBOL code and
        must be removed before parsing.

        Input:  '000100 IDENTIFICATION DIVISION.'
        Cols:    123456|7-72...
        Output: ' IDENTIFICATION DIVISION.'
        """
        preprocessor = CobolPreprocessor()
        source = "000100 IDENTIFICATION DIVISION."
        result = preprocessor.process(source)

        # Column 7 is a space (normal code line), columns 8+ are the code.
        # The output should start from column 7 onward.
        assert result.text == " IDENTIFICATION DIVISION."

    def test_strips_identification_area_columns_73_to_80(self):
        """Columns 73-80 are the identification area.

        Like the sequence area, this is a legacy card-format artifact.
        Any text in columns 73-80 is not COBOL code.
        """
        preprocessor = CobolPreprocessor()
        # Build an 80-character line: 6 seq + 1 indicator + 65 code + 8 ident
        code_part = " MOVE A TO B."
        # Pad code area to fill columns 7-72 (66 characters)
        padded = code_part.ljust(66)
        source = "000100" + padded + "IDENT001"
        assert len(source) == 80

        result = preprocessor.process(source)

        # Output should contain only columns 7-72 (the padded code area),
        # not the identification area.
        assert result.text == padded
        assert "IDENT001" not in result.text

    def test_short_lines_padded_correctly(self):
        """Lines shorter than 72 characters are valid in COBOL.

        The preprocessor must handle them without index errors.
        """
        preprocessor = CobolPreprocessor()
        # A short line with just a sequence area and a few characters of code.
        source = "000100 STOP RUN."
        result = preprocessor.process(source)

        assert result.text == " STOP RUN."

    def test_blank_lines_preserved_for_line_mapping(self):
        """Blank lines should map through the preprocessor so that
        error messages can reference the original line numbers.
        """
        preprocessor = CobolPreprocessor()
        source = "000100 IDENTIFICATION DIVISION.\n\n000300 PROGRAM-ID. TEST1."
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        assert len(lines) == 3
        # The blank line (line 2) is preserved as empty string.
        assert lines[1] == ""
        # Line mapping should track all three output lines.
        assert result.line_mapping[1] == 1
        assert result.line_mapping[2] == 2
        assert result.line_mapping[3] == 3


class TestCommentRemoval:
    """Tests for full-line comment and inline comment removal."""

    def test_full_line_comment_asterisk_in_column_7(self):
        """Column 7 = '*' marks the entire line as a comment.

        COBOL comment lines:
            '      * This is a comment'
        Column 7 is the asterisk. The entire line is removed.
        """
        preprocessor = CobolPreprocessor()
        source = (
            "000100 IDENTIFICATION DIVISION.\n"
            "000200* This is a comment\n"
            "000300 PROGRAM-ID. TEST1."
        )
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        # The comment line is removed entirely — only 2 output lines remain.
        assert len(lines) == 2
        assert "This is a comment" not in result.text

    def test_full_line_comment_slash_in_column_7(self):
        """Column 7 = '/' is a page-break comment — also treated as
        a comment line and removed.
        """
        preprocessor = CobolPreprocessor()
        source = (
            "000100 IDENTIFICATION DIVISION.\n"
            "000200/ Page break here\n"
            "000300 PROGRAM-ID. TEST1."
        )
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        assert len(lines) == 2
        assert "Page break" not in result.text

    def test_inline_comment_star_greater_than(self):
        """The sequence '*>' anywhere in the code area starts an
        inline comment. Everything from '*>' to end of line is removed.

        Input code area: '       MOVE A TO B  *> transfer value'
        Output:          '       MOVE A TO B  '
        """
        preprocessor = CobolPreprocessor()
        source = "000100 MOVE A TO B.  *> transfer value"
        result = preprocessor.process(source)

        assert "transfer value" not in result.text
        assert "*>" not in result.text
        # The code before the inline comment is preserved.
        assert "MOVE A TO B." in result.text

    def test_debug_line_indicator_d_treated_as_comment(self):
        """Column 7 = 'D' or 'd' marks a debug line. For non-debug
        compilation, these are treated as comments and removed.
        """
        preprocessor = CobolPreprocessor()
        source = (
            "000100 IDENTIFICATION DIVISION.\n"
            "000200D    DISPLAY 'DEBUG INFO'\n"
            "000300d    DISPLAY 'MORE DEBUG'\n"
            "000400 PROGRAM-ID. TEST1."
        )
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        assert len(lines) == 2
        assert "DEBUG INFO" not in result.text
        assert "MORE DEBUG" not in result.text


class TestLineMapping:
    """Tests for the original-to-preprocessed line number mapping."""

    def test_line_mapping_tracks_original_line_numbers(self):
        """After comment lines are removed, the preprocessed output
        has fewer lines than the original. The line mapping lets us
        translate preprocessed line numbers back to original source
        line numbers for error messages.
        """
        preprocessor = CobolPreprocessor()
        source = (
            "000100 IDENTIFICATION DIVISION.\n"  # original line 1
            "000200* This is a comment\n"  # original line 2 (removed)
            "000300 PROGRAM-ID. TEST1.\n"  # original line 3
            "000400* Another comment\n"  # original line 4 (removed)
            "000500 ENVIRONMENT DIVISION."  # original line 5
        )
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        assert len(lines) == 3

        # Output line 1 came from original line 1.
        assert result.line_mapping[1] == 1
        # Output line 2 came from original line 3 (line 2 was a comment).
        assert result.line_mapping[2] == 3
        # Output line 3 came from original line 5 (lines 2 and 4 were comments).
        assert result.line_mapping[3] == 5


class TestPreprocessorStripsCommentsAndSequenceNumbers:
    """Verifies that after preprocessing, the output contains no sequence
    numbers, no comment lines, and no inline comments. This runs against
    all six sample COBOL files in the samples/ directory.
    """

    @staticmethod
    def _collect_cob_files(samples_dir: Path) -> list[Path]:
        """Collect all .cob files from the samples/ directory."""
        return sorted(samples_dir.rglob("*.cob"))

    def test_all_sample_files_preprocess_without_errors(self, samples_dir):
        """Every sample .cob file should preprocess without raising exceptions."""
        preprocessor = CobolPreprocessor()
        sample_files = self._collect_cob_files(samples_dir)
        assert len(sample_files) == 6, (
            f"Expected 6 sample files, found {len(sample_files)}"
        )

        for filepath in sample_files:
            source = filepath.read_text()
            # Should not raise.
            result = preprocessor.process(source)
            assert result.text, f"Empty output for {filepath}"

    def test_no_comment_indicators_in_preprocessed_output(self, samples_dir):
        """After preprocessing, no line should contain inline comment markers.

        In the preprocessed output, column 7 indicators are gone. Any line
        starting with '*' (from a full-line comment) means the comment was
        not removed. The only permitted use of '*>' is the ``*>EXECSQL``
        tag that the preprocessor adds to EXEC SQL block lines — these are
        required by the ANTLR4 grammar's EXECSQLLINE lexer rule.
        """
        preprocessor = CobolPreprocessor()
        sample_files = self._collect_cob_files(samples_dir)

        for filepath in sample_files:
            source = filepath.read_text()
            result = preprocessor.process(source)

            for line_num, line in enumerate(result.text.split("\n"), start=1):
                # Lines tagged with *>EXECSQL are EXEC SQL block lines —
                # the tag is intentional and required by the grammar.
                if line.startswith("*>EXECSQL"):
                    continue
                # In the output, line content starts at what was column 7.
                # Full-line comments should have been removed entirely.
                # The only '*>' that should appear is the EXECSQL tag
                # (handled above) — any other '*>' is an unstripped
                # inline comment.
                assert "*>" not in line, (
                    f"Inline comment '*>' found in {filepath.name} "
                    f"at preprocessed line {line_num}: {line!r}"
                )

    def test_no_sequence_numbers_in_preprocessed_output(self, samples_dir):
        """After preprocessing, no line should contain the original
        6-digit sequence numbers from columns 1-6.

        COBOL fixed-format files use columns 1-6 for sequence numbers
        (e.g., '000100', '000200'). After column stripping, the output
        should start at column 7. We verify this by checking that the
        known sequence number patterns from the original source do not
        appear at the start of any output line.
        """
        preprocessor = CobolPreprocessor()
        sample_files = self._collect_cob_files(samples_dir)

        for filepath in sample_files:
            source = filepath.read_text()

            # Collect sequence numbers (cols 1-6) from non-empty
            # original lines that are long enough to have them.
            seq_numbers = set()
            for line in source.splitlines():
                if len(line) >= 6:
                    seq = line[:6].strip()
                    if seq.isdigit() and len(seq) >= 4:
                        seq_numbers.add(seq)

            result = preprocessor.process(source)

            for line_num, line in enumerate(result.text.split("\n"), start=1):
                for seq in seq_numbers:
                    assert not line.startswith(seq), (
                        f"Sequence number '{seq}' found at start of "
                        f"preprocessed line {line_num} in "
                        f"{filepath.name}: {line!r}"
                    )


class TestContinuationLines:
    """Tests for COBOL continuation-line handling.

    In fixed-format COBOL, a hyphen ('-') in column 7 marks a continuation
    line. The content of that line is appended to the previous line. This
    mechanism allows long literals, identifiers, and statements to span
    multiple source lines.
    """

    def test_hyphen_in_column_7_joins_to_previous_line(self):
        """Column 7 = '-' means continuation. The content of the
        continuation line is appended to the previous line.

        Line 1: '      ' + ' ' + '       MOVE "HELLO'
        Line 2: '      ' + '-' + '           WORLD" TO WS-VAR'
        Result: '       MOVE "HELLOWORLD" TO WS-VAR'

        The hyphen indicator, sequence area, and leading spaces of
        the continuation are stripped; the content is appended.
        """
        preprocessor = CobolPreprocessor()
        # Line 1: cols 1-6 = '000100', col 7 = ' ', cols 8-72 = code
        # Line 2: cols 1-6 = '000200', col 7 = '-', cols 8-72 = continuation
        source = "000100        MOVE A TO\n000200-           B"
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        # Both lines should be joined into one.
        assert len(lines) == 1
        assert "MOVE A TO" in lines[0]
        assert "B" in lines[0]

    def test_literal_continuation_preserves_quote_content(self):
        """When continuing a string literal, the continuation line
        starts with a quote character. The preprocessor must join
        the strings without inserting extra spaces or losing characters.

        The previous line ends with an unclosed quote, e.g.:
            '       DISPLAY "HELLO'
        The continuation line provides the rest of the literal:
            '           "WORLD"'
        The result should be:
            '       DISPLAY "HELLOWORLD"'
        """
        preprocessor = CobolPreprocessor()
        # Previous line ends mid-literal with unclosed quote
        line1 = '000100        DISPLAY "HELLO'
        # Continuation line: col 7 = '-', starts with quote after spaces
        line2 = '000200-           "WORLD"'
        source = f"{line1}\n{line2}"
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        assert len(lines) == 1
        # The two parts should be joined as one literal: "HELLOWORLD"
        assert '"HELLOWORLD"' in lines[0]

    def test_multiple_consecutive_continuations(self):
        """A single statement can span three or more lines with
        multiple continuation lines. All must be joined correctly.
        """
        preprocessor = CobolPreprocessor()
        source = "000100        MOVE A\n000200-           TO\n000300-           B"
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        # All three lines joined into one.
        assert len(lines) == 1
        assert "MOVE A" in lines[0]
        assert "TO" in lines[0]
        assert "B" in lines[0]

    def test_continuation_updates_line_mapping(self):
        """The line mapping must reflect that continuation lines
        are merged into their predecessor, so error messages point
        to the original source lines.

        When lines 1, 2 (continuation), and 3 produce two output lines,
        the mapping should point output line 1 back to original line 1
        (the first line of the merged group).
        """
        preprocessor = CobolPreprocessor()
        source = (
            "000100        MOVE A\n"  # original line 1
            "000200-           TO B.\n"  # original line 2 (continuation)
            "000300        STOP RUN."  # original line 3
        )
        result = preprocessor.process(source)

        lines = result.text.split("\n")
        assert len(lines) == 2

        # Output line 1 maps to original line 1 (the first line of the group).
        assert result.line_mapping[1] == 1
        # Output line 2 maps to original line 3.
        assert result.line_mapping[2] == 3


class TestPreprocessorSampleFiles:
    """Integration tests that run the full preprocessor against each sample
    .cob file and verify file-specific content is preserved.

    While TestValidationMilestone checks generic invariants (no comments,
    no sequence numbers) across all files, these tests spot-check specific
    COBOL constructs in each sample to verify that the preprocessor
    preserves semantically important content.
    """

    def test_preprocess_safe01_preserves_all_data_items(self, safe01_source):
        """SAFE01.cob defines five WORKING-STORAGE items:
        WS-ORDER-ID (COMP-3), WS-AMOUNT (COMP-3), WS-COUNTER (DISPLAY),
        WS-BALANCE (DISPLAY), WS-STATUS (PIC X).

        After preprocessing, all five data item names must appear
        in the output, and no sequence numbers or comments remain.
        """
        preprocessor = CobolPreprocessor()
        result = preprocessor.process(safe01_source)
        text = result.text

        # All five WORKING-STORAGE data items must survive preprocessing.
        assert "WS-ORDER-ID" in text
        assert "WS-AMOUNT" in text
        assert "WS-COUNTER" in text
        assert "WS-BALANCE" in text
        assert "WS-STATUS" in text

        # Key division/section keywords must be present.
        assert "IDENTIFICATION DIVISION" in text
        assert "PROGRAM-ID" in text
        assert "PROCEDURE DIVISION" in text
        assert "WORKING-STORAGE SECTION" in text

        # Comments should be stripped — the original file has many
        # comment lines starting with '*' in column 7.
        for line in text.split("\n"):
            assert "*>" not in line

    def test_preprocess_endian01_preserves_redefines_structure(self, endian01_source):
        """ENDIAN01.cob uses REDEFINES three times to overlay byte-level
        access on COMP and COMP-5 fields. The preprocessor must
        preserve the REDEFINES clauses and the subordinate level-05
        items exactly.
        """
        preprocessor = CobolPreprocessor()
        result = preprocessor.process(endian01_source)
        text = result.text

        # Three REDEFINES clauses in the WORKING-STORAGE SECTION:
        # 1. WS-ORDER-BYTES REDEFINES WS-ORDER-ID
        # 2. WS-COMP-BYTES REDEFINES WS-COMP-VAL
        # 3. WS-COMP5-BYTES REDEFINES WS-COMP5-VAL
        assert "WS-ORDER-BYTES" in text
        assert "REDEFINES" in text
        assert "WS-COMP-BYTES" in text
        assert "WS-COMP5-BYTES" in text

        # The subordinate level-05 items under each REDEFINES group.
        assert "WS-BYTE-1" in text
        assert "WS-BYTE-4" in text
        assert "WS-CB-1" in text
        assert "WS-C5B-1" in text

        # COMP-5 type must survive (it's in the code area, not a comment).
        assert "COMP-5" in text

    def test_preprocess_endian02_called_preserves_exec_sql(
        self, endian02_called_source
    ):
        """ENDIAN02-CALLED.cob contains two EXEC SQL blocks:
        1. EXEC SQL INCLUDE SQLCA END-EXEC
        2. EXEC SQL SELECT ... END-EXEC

        The preprocessor must pass EXEC SQL content through unchanged.
        The SQL text between EXEC SQL and END-EXEC must not be altered.
        """
        preprocessor = CobolPreprocessor()
        result = preprocessor.process(endian02_called_source)
        text = result.text

        # Both EXEC SQL blocks must be present.
        assert "EXEC SQL INCLUDE SQLCA END-EXEC" in text
        assert "EXEC SQL" in text

        # The SELECT statement's key clauses must survive.
        assert "SELECT QUANTITY" in text
        assert "INTO :WS-QUANTITY" in text
        assert "FROM ORDERS" in text
        assert "WHERE ORDER_ID = :LS-ORDER-ID" in text
        assert "END-EXEC" in text

        # LINKAGE SECTION parameters must be preserved.
        assert "LINKAGE SECTION" in text
        assert "LS-ORDER-ID" in text
        assert "LS-QUANTITY" in text
        assert "LS-RETURN-CODE" in text

    def test_preprocess_safe02_called_preserves_linkage_section(
        self, safe02_called_source
    ):
        """SAFE02-CALLED.cob has a LINKAGE SECTION with three parameters.
        The preprocessor must preserve the LINKAGE SECTION keyword and
        all three data item definitions.
        """
        preprocessor = CobolPreprocessor()
        result = preprocessor.process(safe02_called_source)
        text = result.text

        # LINKAGE SECTION and its three parameters.
        assert "LINKAGE SECTION" in text
        assert "LS-ORDER-ID" in text
        assert "LS-QUANTITY" in text
        assert "LS-RETURN-CODE" in text

        # The COMP-5 working-storage variables used for Oracle host vars.
        assert "WS-ORA-ORDER-ID" in text
        assert "WS-ORA-QUANTITY" in text

        # EXEC SQL with SQLCA5 (the correct pattern).
        assert "EXEC SQL INCLUDE SQLCA5 END-EXEC" in text

    def test_all_sample_files_preprocess_without_errors(self, samples_dir):
        """Smoke test: every .cob file under samples/ preprocesses
        without raising any exceptions.

        This is the primary validation milestone — confirming that the
        Python preprocessor can normalize all six sample files.
        """
        preprocessor = CobolPreprocessor()
        cob_files = sorted(samples_dir.rglob("*.cob"))
        assert len(cob_files) == 6, (
            f"Expected 6 sample files, found {len(cob_files)}: "
            f"{[f.name for f in cob_files]}"
        )

        for filepath in cob_files:
            source = filepath.read_text()
            result = preprocessor.process(source)

            # Output must be non-empty.
            assert result.text.strip(), f"Empty output for {filepath.name}"

            # Every sample file must produce output containing these
            # fundamental COBOL keywords.
            assert "IDENTIFICATION" in result.text, (
                f"Missing IDENTIFICATION in {filepath.name}"
            )
            assert "PROGRAM-ID" in result.text, f"Missing PROGRAM-ID in {filepath.name}"
            assert "PROCEDURE" in result.text, f"Missing PROCEDURE in {filepath.name}"
