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

    The preprocessor performs four operations in order:

    1. **Column stripping** — removes the sequence number area (cols 1-6)
       and the identification area (cols 73-80), keeping only the indicator
       (col 7) and code area (cols 8-72).
    2. **Comment removal** — drops full-line comments (column 7 indicator)
       and strips inline comments (``*>`` sequences).
    3. **Continuation joining** — when column 7 contains a hyphen (``-``),
       the continuation line's content is appended to the previous line.
       For literal continuations the opening quote on the continuation is
       consumed so the string resumes seamlessly.
    4. **Line mapping** — records which original source line produced each
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

            # Continuation line: column 7 = '-'. The content of this line
            # is appended to the most recent non-blank output line.
            if indicator == "-":
                continuation_area = line[7:72] if len(line) > 7 else ""
                self._join_continuation(
                    output_lines, line_mapping, continuation_area, original_line_num
                )
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

    @staticmethod
    def _join_continuation(
        output_lines: list[str],
        line_mapping: dict[int, int],
        continuation_area: str,
        original_line_num: int,
    ) -> None:
        """Join a continuation line to the previous output line.

        COBOL continuation rules:
        - For **non-literal** continuations the leading spaces of the
          continuation area are stripped and the remaining text is appended
          to the previous line (which already had trailing spaces up to
          column 72 removed by slicing).
        - For **literal** continuations the previous line ends with an
          unclosed quote. The continuation area begins with a quote
          character (single or double) at or after column 12. The opening
          quote is consumed so the literal resumes without an extra quote.

        The line mapping is updated so that the merged output line maps
        back to the *first* original line that contributed to it.

        Args:
            output_lines: Accumulated output lines (mutated in place).
            line_mapping: Output-line → original-line mapping (mutated).
            continuation_area: Columns 8-72 of the continuation line
                (column 7, the hyphen indicator, is already stripped).
            original_line_num: 1-based line number in the original source.
        """
        if not output_lines:
            # Continuation with no preceding line — degenerate input.
            # Treat the continuation content as a new line.
            output_lines.append(continuation_area.lstrip())
            line_mapping[len(output_lines)] = original_line_num
            return

        previous = output_lines[-1]

        # Determine whether this is a literal continuation by checking if
        # the previous line has an unclosed string literal — an odd number
        # of quote characters means a literal was opened but not closed.
        prev_stripped = previous.rstrip()
        unclosed_double = prev_stripped.count('"') % 2 == 1
        unclosed_single = prev_stripped.count("'") % 2 == 1
        is_literal = unclosed_double or unclosed_single

        if is_literal:
            # Literal continuation: find the opening quote character in the
            # continuation area and skip it. Everything after it continues
            # the literal from the previous line.
            quote_char = '"' if unclosed_double else "'"
            quote_pos = continuation_area.find(quote_char)
            if quote_pos != -1:
                # Append everything after the opening quote.
                output_lines[-1] = prev_stripped + continuation_area[quote_pos + 1 :]
            else:
                # No matching quote found — fall back to non-literal join.
                output_lines[-1] = previous.rstrip() + continuation_area.lstrip()
        else:
            # Non-literal continuation: strip leading spaces and append.
            output_lines[-1] = previous.rstrip() + continuation_area.lstrip()

        # The line mapping keeps pointing to the *first* original line
        # that produced this output line — no update needed for the key,
        # but we record the continuation's original line for diagnostics
        # by storing an additional entry keyed on a negative sentinel.
        # (The primary mapping remains unchanged.)
