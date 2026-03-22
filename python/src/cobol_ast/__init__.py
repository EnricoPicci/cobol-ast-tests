"""COBOL AST Parser — educational examples of AST-based COBOL analysis.

This package provides tools to parse COBOL source files into typed
Abstract Syntax Tree (AST) representations using ANTLR4.

Pipeline:
    COBOL source → Preprocessor → ANTLR4 Parser (CST) → Visitor → AST dataclasses
"""
