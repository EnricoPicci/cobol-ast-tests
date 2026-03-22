"""COBOL AST Visitor — transforms the ANTLR4 parse tree (CST) into typed AST nodes.

The ANTLR4 parser produces a Concrete Syntax Tree (CST) that mirrors the grammar
rules exactly. While faithful to the syntax, the CST is verbose and grammar-specific.
The Visitor walks the CST and constructs a cleaner Abstract Syntax Tree (AST) using
the dataclasses defined in ``ast_nodes``.

This module implements the first part of the Visitor: extracting the PROGRAM-ID from
the IDENTIFICATION DIVISION and detecting the ENVIRONMENT DIVISION. These two
divisions validate the end-to-end pipeline (COBOL → preprocessor → parser → Visitor
→ AST) with the simplest possible output.

The Visitor pattern works by overriding ``visit*`` methods from the generated
``Cobol85Visitor`` base class. Each override receives the corresponding CST context
node and returns an AST dataclass (or a primitive value used by the parent visitor
method).

Typical usage::

    from cobol_ast.preprocessor import CobolPreprocessor
    from cobol_ast.parser import CobolParser
    from cobol_ast.visitor import CobolAstVisitor

    preprocessor = CobolPreprocessor()
    parser = CobolParser()
    visitor = CobolAstVisitor()

    result = parser.parse(preprocessor.process(source).text)
    program = visitor.visit(result.tree)
    # program is a ProgramNode with program_id, identification, environment, etc.
"""

from __future__ import annotations

from cobol_ast.ast_nodes import (
    EnvironmentDivisionNode,
    IdentificationDivisionNode,
    ProgramNode,
)
from cobol_ast.generated.grammar.Cobol85Parser import Cobol85Parser
from cobol_ast.generated.grammar.Cobol85Visitor import Cobol85Visitor


class CobolAstVisitor(Cobol85Visitor):
    """Transforms an ANTLR4 COBOL parse tree into typed AST dataclasses.

    The visitor overrides specific ``visit*`` methods to extract meaningful
    information from the CST and construct AST nodes. Methods that are not
    overridden fall through to ``visitChildren()``, which recursively visits
    child nodes without producing AST output.

    Currently handles:
    - IDENTIFICATION DIVISION → extracts PROGRAM-ID
    - ENVIRONMENT DIVISION → produces an EnvironmentDivisionNode marker
    """

    def visitStartRule(self, ctx: Cobol85Parser.StartRuleContext) -> ProgramNode | None:
        """Visit the grammar's top-level rule.

        ``startRule`` contains a ``compilationUnit`` followed by EOF.
        We explicitly visit the ``compilationUnit`` child rather than using
        ``visitChildren()``, because ``visitChildren`` returns the result of
        the *last* child — which would be the EOF terminal node (``None``),
        discarding the ``ProgramNode`` we need.

        Returns:
            The ``ProgramNode`` produced by visiting the compilation unit,
            or ``None`` if the tree is empty.
        """
        return self.visitCompilationUnit(ctx.compilationUnit())

    def visitCompilationUnit(
        self, ctx: Cobol85Parser.CompilationUnitContext
    ) -> ProgramNode | None:
        """Visit the compilation unit — the container for program units.

        A compilation unit may contain multiple program units (nested programs),
        but for our educational examples we only process the first one.

        Returns:
            The ``ProgramNode`` from the first ``programUnit``, or ``None``.
        """
        program_unit_ctx = ctx.programUnit(0)
        if program_unit_ctx is not None:
            return self.visitProgramUnit(program_unit_ctx)
        return None

    def visitProgramUnit(self, ctx: Cobol85Parser.ProgramUnitContext) -> ProgramNode:
        """Visit a single program unit and assemble the root ProgramNode.

        The grammar's ``programUnit`` rule contains:
        - ``identificationDivision`` (mandatory) — provides PROGRAM-ID
        - ``environmentDivision`` (optional)
        - ``dataDivision`` (optional, handled in later steps)
        - ``procedureDivision`` (optional, handled in later steps)

        Returns:
            A ``ProgramNode`` with the extracted program ID and division nodes.
        """
        # IDENTIFICATION DIVISION is mandatory — it provides the program name.
        id_node = self.visitIdentificationDivision(ctx.identificationDivision())

        # ENVIRONMENT DIVISION is optional — check if present in the parse tree.
        env_ctx = ctx.environmentDivision()
        env_node = self.visitEnvironmentDivision(env_ctx) if env_ctx else None

        return ProgramNode(
            program_id=id_node.program_id,
            identification=id_node,
            environment=env_node,
        )

    def visitIdentificationDivision(
        self, ctx: Cobol85Parser.IdentificationDivisionContext
    ) -> IdentificationDivisionNode:
        """Visit the IDENTIFICATION DIVISION to extract the PROGRAM-ID.

        The grammar structure is:
            identificationDivision
              → (IDENTIFICATION | ID) DIVISION DOT_FS
                programIdParagraph
                identificationDivisionBody*

        We delegate to ``visitProgramIdParagraph`` to get the program name.

        Returns:
            An ``IdentificationDivisionNode`` containing the PROGRAM-ID.
        """
        program_id = self.visitProgramIdParagraph(ctx.programIdParagraph())
        return IdentificationDivisionNode(program_id=program_id)

    def visitProgramIdParagraph(
        self, ctx: Cobol85Parser.ProgramIdParagraphContext
    ) -> str:
        """Extract the program name from the PROGRAM-ID paragraph.

        The grammar structure is:
            programIdParagraph
              → PROGRAM_ID DOT_FS programName ...

        ``programName`` is either a ``NONNUMERICLITERAL`` (a quoted string)
        or a ``cobolWord`` (an identifier like ``SAFE01`` or ``ENDIAN02-CALLER``).
        We extract the text of the ``programName`` node, which gives us the
        raw program name.

        Returns:
            The program name as a string (e.g., ``'SAFE01'``).
        """
        # programName() returns either a NONNUMERICLITERAL or a cobolWord.
        # getText() on the context gives us the raw text of the matched rule.
        program_name_ctx = ctx.programName()
        return program_name_ctx.getText()

    def visitEnvironmentDivision(
        self, ctx: Cobol85Parser.EnvironmentDivisionContext
    ) -> EnvironmentDivisionNode:
        """Visit the ENVIRONMENT DIVISION.

        In the sample files, the ENVIRONMENT DIVISION is always present but
        empty (no CONFIGURATION SECTION or INPUT-OUTPUT SECTION). We return
        an ``EnvironmentDivisionNode`` marker to indicate the division exists
        in the source — this distinguishes "present but empty" from "absent".

        Returns:
            An ``EnvironmentDivisionNode`` instance.
        """
        return EnvironmentDivisionNode()
