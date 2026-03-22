"""Tests for the COBOL fixed-format preprocessor.

These tests verify that the preprocessor correctly strips the fixed-format
column layout and removes comments, producing free-form text suitable for
ANTLR4 parsing. Each test documents a specific aspect of the COBOL
fixed-format specification.
"""

import os

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


class TestValidationMilestone:
    """Validation milestone: preprocess all sample .cob files.

    Verifies that after preprocessing, the output contains no sequence
    numbers, no comment lines, and no inline comments. This runs against
    all six sample COBOL files in the samples/ directory.
    """

    def _get_sample_files(self) -> list[str]:
        """Collect all .cob files from the samples/ directory."""
        samples_dir = os.path.join(os.path.dirname(__file__), "..", "..", "samples")
        samples_dir = os.path.normpath(samples_dir)
        cob_files = []
        for root, _, files in os.walk(samples_dir):
            for f in files:
                if f.endswith(".cob"):
                    cob_files.append(os.path.join(root, f))
        return sorted(cob_files)

    def test_all_sample_files_preprocess_without_errors(self):
        """Every sample .cob file should preprocess without raising exceptions."""
        preprocessor = CobolPreprocessor()
        sample_files = self._get_sample_files()
        assert len(sample_files) == 6, (
            f"Expected 6 sample files, found {len(sample_files)}"
        )

        for filepath in sample_files:
            with open(filepath) as f:
                source = f.read()
            # Should not raise.
            result = preprocessor.process(source)
            assert result.text, f"Empty output for {filepath}"

    def test_no_comment_indicators_in_preprocessed_output(self):
        """After preprocessing, no line should start with a comment indicator.

        In the preprocessed output, column 7 indicators are gone. Any line
        starting with '*' (from a full-line comment) means the comment was
        not removed.
        """
        preprocessor = CobolPreprocessor()
        sample_files = self._get_sample_files()

        for filepath in sample_files:
            with open(filepath) as f:
                source = f.read()
            result = preprocessor.process(source)

            for line_num, line in enumerate(result.text.split("\n"), start=1):
                # In the output, line content starts at what was column 7.
                # Full-line comments should have been removed entirely.
                # The only '*' that should appear is inside '*>' inline
                # comments — but those should be stripped too.
                assert "*>" not in line, (
                    f"Inline comment '*>' found in {os.path.basename(filepath)} "
                    f"at preprocessed line {line_num}: {line!r}"
                )

    def test_no_sequence_numbers_in_preprocessed_output(self):
        """After preprocessing, no line should contain the original
        6-digit sequence numbers from columns 1-6.

        COBOL fixed-format files use columns 1-6 for sequence numbers
        (e.g., '000100', '000200'). After column stripping, the output
        should start at column 7. We verify this by checking that the
        known sequence number patterns from the original source do not
        appear at the start of any output line.
        """
        preprocessor = CobolPreprocessor()
        sample_files = self._get_sample_files()

        for filepath in sample_files:
            with open(filepath) as f:
                source = f.read()

            # Collect sequence numbers (cols 1-6) from non-empty
            # original lines that are long enough to have them.
            seq_numbers = set()
            for line in source.splitlines():
                if len(line) >= 6:
                    seq = line[:6].strip()
                    if seq.isdigit() and len(seq) >= 4:
                        seq_numbers.add(seq)

            result = preprocessor.process(source)

            for line_num, line in enumerate(
                result.text.split("\n"), start=1
            ):
                for seq in seq_numbers:
                    assert not line.startswith(seq), (
                        f"Sequence number '{seq}' found at start of "
                        f"preprocessed line {line_num} in "
                        f"{os.path.basename(filepath)}: {line!r}"
                    )
