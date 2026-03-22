"""COBOL parser wrapper — feeds preprocessed text into the ANTLR4 pipeline.

The ANTLR4 API requires several setup steps to parse source text:
create an InputStream, instantiate the Lexer, build a CommonTokenStream,
create the Parser, and invoke the start rule. This module wraps all of
that into a single ``CobolParser.parse()`` call that returns a
``ParseResult`` containing the parse tree (CST) and any collected errors.

By default, ANTLR4 prints syntax errors to stderr. This module replaces
that behavior with a custom ``_ErrorListener`` that collects errors into
a list, giving callers full control over error reporting.

Typical usage::

    from cobol_ast.parser import CobolParser

    parser = CobolParser()
    result = parser.parse(preprocessed_text)

    if result.errors:
        for err in result.errors:
            print(err)
    else:
        print(result.tree.toStringTree(recog=parser))
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from antlr4 import CommonTokenStream, InputStream
from antlr4.error.ErrorListener import ErrorListener

from cobol_ast.generated.grammar.Cobol85Lexer import Cobol85Lexer
from cobol_ast.generated.grammar.Cobol85Parser import (
    Cobol85Parser as _Cobol85Parser,
)


@dataclass
class ParseResult:
    """Result of parsing preprocessed COBOL source text.

    Attributes:
        tree: The ANTLR4 parse tree (CST) rooted at the ``startRule``
            rule. ``None`` only if a catastrophic parser failure occurs
            (in practice this should not happen — even invalid input
            produces a partial tree).
        errors: List of syntax error messages collected during parsing.
            An empty list means the input was parsed without errors.
    """

    tree: Optional[object] = None
    errors: list[str] = field(default_factory=list)


class _ErrorListener(ErrorListener):
    """Collects ANTLR4 syntax errors instead of printing to stderr.

    ANTLR4's default ``ConsoleErrorListener`` writes errors to stderr,
    which is unhelpful for programmatic use. This listener stores each
    error as a formatted string so callers can inspect them after parsing.
    """

    def __init__(self) -> None:
        super().__init__()
        self.errors: list[str] = []

    def syntaxError(
        self,
        recognizer: object,
        offendingSymbol: object,
        line: int,
        column: int,
        msg: str,
        e: object,
    ) -> None:
        """Record a syntax error with its location.

        Args:
            recognizer: The lexer or parser that detected the error.
            offendingSymbol: The token that caused the error (may be None
                for lexer errors).
            line: Line number where the error occurred (1-based).
            column: Column position within the line (0-based).
            msg: Human-readable error description from ANTLR4.
            e: The underlying RecognitionException, if any.
        """
        self.errors.append(f"line {line}:{column} {msg}")


class CobolParser:
    """Wraps the ANTLR4 COBOL lexer and parser.

    Accepts preprocessed COBOL source text and produces an ANTLR4
    parse tree (CST). Collects any lexer/parser errors for reporting.

    The ANTLR4 parsing pipeline works as follows:

    1. **InputStream** — wraps the source text into a character stream.
    2. **Cobol85Lexer** — tokenizes the character stream into a sequence
       of tokens (keywords, identifiers, literals, etc.).
    3. **CommonTokenStream** — buffers the token sequence for the parser.
    4. **Cobol85Parser** — applies the grammar rules to the token stream
       and builds a parse tree (concrete syntax tree / CST).

    Both the lexer and parser have their default error listeners removed
    and replaced with a custom listener that collects errors into a list.
    """

    def parse(self, source: str) -> ParseResult:
        """Parse preprocessed COBOL source into a CST.

        Args:
            source: Preprocessed (free-form) COBOL source text. This
                should already have fixed-format columns stripped by the
                preprocessor — the ANTLR4 grammar does not handle
                column positions.

        Returns:
            ParseResult containing the parse tree and any errors.
            The tree is rooted at the grammar's ``startRule`` rule,
            which expects a ``compilationUnit`` followed by EOF.
        """
        # Step 1: Create a character stream from the source text
        input_stream = InputStream(source)

        # Step 2: Tokenize — the lexer splits the source into tokens
        lexer = Cobol85Lexer(input_stream)
        lexer.removeErrorListeners()
        error_listener = _ErrorListener()
        lexer.addErrorListener(error_listener)

        # Step 3: Buffer tokens for the parser
        token_stream = CommonTokenStream(lexer)

        # Step 4: Parse — apply grammar rules to build the CST
        parser = _Cobol85Parser(token_stream)
        parser.removeErrorListeners()
        parser.addErrorListener(error_listener)

        # Invoke the top-level grammar rule. startRule expects
        # a compilationUnit followed by EOF.
        tree = parser.startRule()

        return ParseResult(tree=tree, errors=error_listener.errors)
