"""COBOL fixed-format preprocessor — normalizes source for ANTLR4 parsing.

COBOL source written in fixed format (the traditional card-based layout)
divides each line into columns with specific meanings:

    Columns 1-6:   Sequence number area (line identifiers, ignored by compiler)
    Column 7:      Indicator area (* = comment, / = page break, - = continuation,
                   D/d = debug line, space = normal code)
    Columns 8-72:  Code area (Area A: 8-11, Area B: 12-72)
    Columns 73-80: Identification area (ignored by compiler)

The ANTLR4 Cobol85 grammar expects free-form input — it does not handle
column positions. This module strips the fixed-format layout and produces
clean text suitable for parsing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PreprocessedSource:
    """Result of preprocessing a COBOL source file.

    Attributes:
        text: The normalized free-form text with columns stripped and
            comments removed. Ready for ANTLR4 parsing.
        line_mapping: Maps each line number in ``text`` (1-based) to the
            corresponding line number in the original source. This allows
            error messages to reference the original file positions even
            after comment lines have been removed.
    """

    text: str
    line_mapping: dict[int, int] = field(default_factory=dict)


# Column 7 indicators that mark a line as a comment.
# '*' = comment, '/' = page-break comment, 'D'/'d' = debug line (treated
# as comment for non-debug compilation).
_COMMENT_INDICATORS = {"*", "/", "D", "d"}


class CobolPreprocessor:
    """Transforms fixed-format COBOL source into free-form text.

    The preprocessor performs three operations in order:

    1. **Column stripping** — removes the sequence number area (cols 1-6)
       and the identification area (cols 73-80), keeping only the indicator
       (col 7) and code area (cols 8-72).
    2. **Comment removal** — drops full-line comments (column 7 indicator)
       and strips inline comments (``*>`` sequences).
    3. **Line mapping** — records which original source line produced each
       output line, so downstream error messages stay accurate.

    Example::

        preprocessor = CobolPreprocessor()
        result = preprocessor.process(cobol_source)
        print(result.text)  # free-form text ready for ANTLR4
        # result.line_mapping[5] → original line number for output line 5
    """

    def process(self, source: str) -> PreprocessedSource:
        """Preprocess fixed-format COBOL source into free-form text.

        Args:
            source: Raw COBOL source text in fixed format (80-column layout).

        Returns:
            A ``PreprocessedSource`` containing the normalized text and a
            mapping from output line numbers to original source line numbers.
        """
        lines = source.splitlines()
        output_lines: list[str] = []
        line_mapping: dict[int, int] = {}

        for original_line_num, line in enumerate(lines, start=1):
            # Lines shorter than 7 characters have no indicator column
            # and no code area — treat as blank.
            if len(line) < 7:
                output_lines.append("")
                line_mapping[len(output_lines)] = original_line_num
                continue

            indicator = line[6]

            # Check column 7 indicator for full-line comments.
            # '*' and '/' are standard comment indicators; 'D'/'d' mark
            # debug lines which we treat as comments for non-debug builds.
            if indicator in _COMMENT_INDICATORS:
                continue

            # Extract the code area: columns 7-72 (0-indexed: characters 6-71).
            # Column 7 (the indicator, index 6) is included because for normal
            # lines it's a space and is part of the Area A indentation.
            code_area = line[6:72]

            # Strip inline comments: '*>' starts an inline comment that
            # extends to the end of the line.
            inline_comment_pos = code_area.find("*>")
            if inline_comment_pos != -1:
                code_area = code_area[:inline_comment_pos]

            output_lines.append(code_area)
            line_mapping[len(output_lines)] = original_line_num

        text = "\n".join(output_lines)
        return PreprocessedSource(text=text, line_mapping=line_mapping)
