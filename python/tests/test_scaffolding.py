"""Tests that verify the ANTLR4 toolchain and generated parser are set up correctly.

These tests confirm that all dependencies are installed and the generated
COBOL parser code is importable. They act as a smoke test for the project
scaffolding — if these fail, nothing else will work.
"""


def test_antlr4_runtime_imports():
    """Verify that the ANTLR4 Python runtime is installed and importable.

    The antlr4-python3-runtime package provides the base classes
    (CommonTokenStream, ParseTreeVisitor, etc.) that the generated
    parser depends on.
    """
    import antlr4

    assert hasattr(antlr4, "CommonTokenStream")


def test_generated_parser_imports():
    """Verify that the ANTLR4-generated COBOL parser is importable.

    The generated code lives in src/cobol_ast/generated/grammar/ and
    includes the Lexer (tokenizer), Parser (grammar rules), and Visitor
    (tree walker base class). All three must import without errors for
    the rest of the pipeline to work.
    """
    from cobol_ast.generated.grammar import (
        Cobol85Lexer,  # noqa: F401
        Cobol85Parser,  # noqa: F401
        Cobol85Visitor,  # noqa: F401
    )
