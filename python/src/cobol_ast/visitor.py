"""COBOL AST Visitor — transforms the ANTLR4 parse tree (CST) into typed AST nodes.

The ANTLR4 parser produces a Concrete Syntax Tree (CST) that mirrors the grammar
rules exactly. While faithful to the syntax, the CST is verbose and grammar-specific.
The Visitor walks the CST and constructs a cleaner Abstract Syntax Tree (AST) using
the dataclasses defined in ``ast_nodes``.

This module implements the Visitor for:
- IDENTIFICATION DIVISION → extracts PROGRAM-ID
- ENVIRONMENT DIVISION → detects presence
- DATA DIVISION → extracts WORKING-STORAGE and LINKAGE SECTION data items,
  including PIC clauses, USAGE types, VALUE literals, REDEFINES, and the
  level-number hierarchy (e.g., level-05 items nested under level-01 groups).
- PROCEDURE DIVISION → extracts paragraphs and statements (DISPLAY, MOVE, ADD,
  CALL, IF/ELSE/END-IF, STOP RUN, GOBACK, EXEC SQL), plus the optional
  USING clause for called subprograms.

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
    # program is a ProgramNode with program_id, identification, environment, data, etc.
"""

from __future__ import annotations

import re

from cobol_ast.ast_nodes import (
    AddNode,
    CallNode,
    DataDivisionNode,
    DataItemNode,
    DisplayNode,
    EnvironmentDivisionNode,
    ExecSqlNode,
    GobackNode,
    IdentificationDivisionNode,
    IfNode,
    LinkageSectionNode,
    MoveNode,
    ParagraphNode,
    PicClause,
    ProcedureDivisionNode,
    ProgramNode,
    StatementNode,
    StopRunNode,
    UsageType,
    WorkingStorageSectionNode,
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
    - DATA DIVISION → extracts WORKING-STORAGE and LINKAGE SECTION data items
      with PIC clauses, USAGE types, VALUE literals, REDEFINES, and hierarchy
    - PROCEDURE DIVISION → extracts paragraphs and statements (DISPLAY, MOVE,
      ADD, CALL, IF/ELSE/END-IF, STOP RUN, GOBACK, EXEC SQL), plus the
      optional USING clause for called subprograms
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
        - ``dataDivision`` (optional) — variable declarations
        - ``procedureDivision`` (optional) — executable statements

        Returns:
            A ``ProgramNode`` with the extracted program ID and division nodes.
        """
        # IDENTIFICATION DIVISION is mandatory — it provides the program name.
        id_node = self.visitIdentificationDivision(ctx.identificationDivision())

        # ENVIRONMENT DIVISION is optional — check if present in the parse tree.
        env_ctx = ctx.environmentDivision()
        env_node = self.visitEnvironmentDivision(env_ctx) if env_ctx else None

        # DATA DIVISION is optional — contains WORKING-STORAGE and LINKAGE sections.
        data_ctx = ctx.dataDivision()
        data_node = self.visitDataDivision(data_ctx) if data_ctx else None

        # PROCEDURE DIVISION is optional — contains executable statements.
        proc_ctx = ctx.procedureDivision()
        proc_node = self.visitProcedureDivision(proc_ctx) if proc_ctx else None

        return ProgramNode(
            program_id=id_node.program_id,
            identification=id_node,
            environment=env_node,
            data=data_node,
            procedure=proc_node,
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

    # -------------------------------------------------------------------
    # DATA DIVISION
    # -------------------------------------------------------------------

    def visitDataDivision(
        self, ctx: Cobol85Parser.DataDivisionContext
    ) -> DataDivisionNode:
        """Visit the DATA DIVISION to extract WORKING-STORAGE and LINKAGE sections.

        The grammar structure is:
            dataDivision → DATA DIVISION DOT_FS dataDivisionSection*

        Each ``dataDivisionSection`` wraps exactly one section (WORKING-STORAGE,
        LINKAGE, FILE, etc.). We iterate through them, visiting only the section
        types we model.

        Returns:
            A ``DataDivisionNode`` with the extracted sections.
        """
        working_storage: WorkingStorageSectionNode | None = None
        linkage: LinkageSectionNode | None = None

        for section_ctx in ctx.dataDivisionSection():
            # Each dataDivisionSection contains exactly one child section.
            ws_ctx = section_ctx.workingStorageSection()
            if ws_ctx:
                working_storage = self.visitWorkingStorageSection(ws_ctx)

            ls_ctx = section_ctx.linkageSection()
            if ls_ctx:
                linkage = self.visitLinkageSection(ls_ctx)

        return DataDivisionNode(
            working_storage=working_storage,
            linkage=linkage,
        )

    def visitWorkingStorageSection(
        self, ctx: Cobol85Parser.WorkingStorageSectionContext
    ) -> WorkingStorageSectionNode:
        """Visit WORKING-STORAGE SECTION to extract data item declarations.

        The grammar structure is:
            workingStorageSection → WORKING_STORAGE SECTION DOT_FS dataDescriptionEntry*

        We collect all Format-1 data description entries (the standard level-number
        entries), then build the parent-child hierarchy based on level numbers.

        Returns:
            A ``WorkingStorageSectionNode`` with hierarchically nested data items.
        """
        flat_items = self._collect_data_items(ctx.dataDescriptionEntry())
        nested_items = _build_hierarchy(flat_items)
        return WorkingStorageSectionNode(items=tuple(nested_items))

    def visitLinkageSection(
        self, ctx: Cobol85Parser.LinkageSectionContext
    ) -> LinkageSectionNode:
        """Visit LINKAGE SECTION to extract parameter data items.

        The grammar structure mirrors WORKING-STORAGE:
            linkageSection → LINKAGE SECTION DOT_FS dataDescriptionEntry*

        LINKAGE SECTION items describe the layout of data passed via
        ``CALL ... USING`` from a calling program.

        Returns:
            A ``LinkageSectionNode`` with hierarchically nested data items.
        """
        flat_items = self._collect_data_items(ctx.dataDescriptionEntry())
        nested_items = _build_hierarchy(flat_items)
        return LinkageSectionNode(items=tuple(nested_items))

    def _collect_data_items(
        self,
        entries: list[Cobol85Parser.DataDescriptionEntryContext],
    ) -> list[DataItemNode]:
        """Extract ``DataItemNode`` instances from a list of data description entries.

        Only Format-1 entries (standard level-number declarations) are processed.
        Format-2 (RENAMES / level 66), Format-3 (condition names / level 88), and
        EXEC SQL entries are skipped — they are not modelled in the AST.

        Args:
            entries: List of ``dataDescriptionEntry`` contexts from the parser.

        Returns:
            A flat list of ``DataItemNode`` instances (not yet hierarchically nested).
        """
        items: list[DataItemNode] = []
        for entry_ctx in entries:
            fmt1 = entry_ctx.dataDescriptionEntryFormat1()
            if fmt1:
                item = self._visit_format1_entry(fmt1)
                if item is not None:
                    items.append(item)
        return items

    def _visit_format1_entry(
        self, ctx: Cobol85Parser.DataDescriptionEntryFormat1Context
    ) -> DataItemNode | None:
        """Extract a single data item from a Format-1 data description entry.

        The grammar structure is:
            dataDescriptionEntryFormat1
              → (INTEGERLITERAL | LEVEL_NUMBER_77) (FILLER | dataName)?
                (clause)* DOT_FS

        Clauses we extract: PIC, USAGE, VALUE, REDEFINES.
        Items named FILLER or with no name are skipped (not modelled).

        Args:
            ctx: A ``DataDescriptionEntryFormat1Context`` from the parser.

        Returns:
            A ``DataItemNode``, or ``None`` for FILLER / unnamed entries.
        """
        # --- Level number ---
        level_token = ctx.INTEGERLITERAL()
        if level_token:
            level = int(level_token.getText())
        elif ctx.LEVEL_NUMBER_77():
            level = 77
        else:
            return None

        # --- Data name ---
        # FILLER entries have no semantic name — skip them.
        if ctx.FILLER():
            return None
        name_ctx = ctx.dataName()
        if not name_ctx:
            return None
        name = name_ctx.getText()

        # --- PIC clause ---
        pic: PicClause | None = None
        pic_clauses = ctx.dataPictureClause()
        if pic_clauses:
            pic = self._extract_pic(pic_clauses[0])

        # --- USAGE clause ---
        usage: UsageType | None = None
        usage_clauses = ctx.dataUsageClause()
        if usage_clauses:
            usage = self._extract_usage(usage_clauses[0])

        # --- VALUE clause ---
        value: str | None = None
        value_clauses = ctx.dataValueClause()
        if value_clauses:
            value = self._extract_value(value_clauses[0])

        # --- REDEFINES clause ---
        redefines: str | None = None
        redefines_clauses = ctx.dataRedefinesClause()
        if redefines_clauses:
            redefines = redefines_clauses[0].dataName().getText()

        return DataItemNode(
            level=level,
            name=name,
            pic=pic,
            usage=usage,
            value=value,
            redefines=redefines,
        )

    # -------------------------------------------------------------------
    # Clause extraction helpers
    # -------------------------------------------------------------------

    def _extract_pic(self, ctx: Cobol85Parser.DataPictureClauseContext) -> PicClause:
        """Parse a PIC clause into a ``PicClause`` dataclass.

        The grammar structure is:
            dataPictureClause → (PICTURE | PIC) IS? pictureString

        ``pictureString`` is a sequence of picture characters and optional
        cardinalities (e.g., ``S9(9)``, ``X(10)``). We get the raw text and
        parse it to determine category, size, and signedness.

        Args:
            ctx: A ``DataPictureClauseContext`` from the parser.

        Returns:
            A ``PicClause`` with the parsed attributes.
        """
        raw = ctx.pictureString().getText()
        return _parse_pic_string(raw)

    def _extract_usage(
        self, ctx: Cobol85Parser.DataUsageClauseContext
    ) -> UsageType | None:
        """Map the USAGE clause to a ``UsageType`` enum value.

        The grammar supports many USAGE types (BINARY, COMP, COMP-1 through
        COMP-5, DISPLAY, etc.). We map only the types present in the sample
        files to ``UsageType``; unsupported types return ``None``.

        Args:
            ctx: A ``DataUsageClauseContext`` from the parser.

        Returns:
            The corresponding ``UsageType``, or ``None`` for unmapped types.
        """
        # Check each token type the grammar can produce.
        if ctx.COMP() or ctx.COMPUTATIONAL():
            return UsageType.COMP
        if ctx.COMP_3() or ctx.COMPUTATIONAL_3():
            return UsageType.COMP_3
        if ctx.COMP_5() or ctx.COMPUTATIONAL_5():
            return UsageType.COMP_5
        if ctx.DISPLAY():
            return UsageType.DISPLAY
        # BINARY and COMP-4 map to COMP in standard COBOL.
        if ctx.BINARY() or ctx.COMP_4() or ctx.COMPUTATIONAL_4():
            return UsageType.COMP
        return None

    def _extract_value(self, ctx: Cobol85Parser.DataValueClauseContext) -> str:
        """Extract the literal value from a VALUE clause.

        The grammar structure is:
            dataValueClause → (VALUE IS? | VALUES ARE?)? dataValueInterval ...
            dataValueInterval → dataValueIntervalFrom dataValueIntervalTo?
            dataValueIntervalFrom → literal | cobolWord

        We take the first interval's ``from`` value. For numeric literals the
        text is the number (e.g., ``"12345"``). For non-numeric literals (quoted
        strings), we strip the surrounding quotes.

        Args:
            ctx: A ``DataValueClauseContext`` from the parser.

        Returns:
            The value as a string (quotes stripped for string literals).
        """
        interval = ctx.dataValueInterval(0)
        from_ctx = interval.dataValueIntervalFrom()
        raw = from_ctx.getText()
        # Strip quotes from non-numeric literals (e.g., "ACTIVE" → ACTIVE).
        if raw.startswith('"') and raw.endswith('"'):
            return raw[1:-1]
        if raw.startswith("'") and raw.endswith("'"):
            return raw[1:-1]
        return raw

    # -------------------------------------------------------------------
    # PROCEDURE DIVISION
    # -------------------------------------------------------------------

    def visitProcedureDivision(
        self, ctx: Cobol85Parser.ProcedureDivisionContext
    ) -> ProcedureDivisionNode:
        """Visit the PROCEDURE DIVISION to extract paragraphs and the USING clause.

        The grammar structure is:
            procedureDivision
              → PROCEDURE DIVISION procedureDivisionUsingClause?
                procedureDivisionGivingClause? DOT_FS
                procedureDeclaratives? procedureDivisionBody

        The USING clause lists parameters for called subprograms (matching
        LINKAGE SECTION items). The body contains paragraphs with statements.

        Returns:
            A ``ProcedureDivisionNode`` with USING items and paragraphs.
        """
        # Extract USING clause parameters (if present).
        using_items: list[str] = []
        using_ctx = ctx.procedureDivisionUsingClause()
        if using_ctx:
            using_items = self._extract_proc_using_items(using_ctx)

        # Extract paragraphs from the division body.
        paragraphs: list[ParagraphNode] = []
        body_ctx = ctx.procedureDivisionBody()
        if body_ctx:
            paragraphs_ctx = body_ctx.paragraphs()
            if paragraphs_ctx:
                for para_ctx in paragraphs_ctx.paragraph():
                    para = self._visit_paragraph(para_ctx)
                    paragraphs.append(para)

        return ProcedureDivisionNode(
            using_items=tuple(using_items),
            paragraphs=tuple(paragraphs),
        )

    def _extract_proc_using_items(
        self, ctx: Cobol85Parser.ProcedureDivisionUsingClauseContext
    ) -> list[str]:
        """Extract parameter names from the PROCEDURE DIVISION USING clause.

        The grammar structure is:
            procedureDivisionUsingClause
              → (USING | CHAINING) procedureDivisionUsingParameter+

        Each parameter is passed BY REFERENCE (default) or BY VALUE.
        We extract the identifier name from each parameter.

        Args:
            ctx: The USING clause context.

        Returns:
            A list of parameter names (e.g., ``['LS-ORDER-ID', 'LS-QUANTITY']``).
        """
        items: list[str] = []
        for param in ctx.procedureDivisionUsingParameter():
            # Parameters passed by reference (the default in COBOL).
            by_ref = param.procedureDivisionByReferencePhrase()
            if by_ref:
                for ref in by_ref.procedureDivisionByReference():
                    ident = ref.identifier()
                    if ident:
                        items.append(ident.getText())
            # Parameters passed by value (uncommon, but supported).
            by_val = param.procedureDivisionByValuePhrase()
            if by_val:
                for val in by_val.procedureDivisionByValue():
                    ident = val.identifier()
                    if ident:
                        items.append(ident.getText())
        return items

    def _visit_paragraph(self, ctx: Cobol85Parser.ParagraphContext) -> ParagraphNode:
        """Visit a named paragraph and collect its statements.

        The grammar structure is:
            paragraph → paragraphName DOT_FS (alteredGoTo | sentence*)

        A paragraph is a labeled block of statements. Sentences within the
        paragraph contain one or more statements terminated by a period.

        Args:
            ctx: A ``ParagraphContext`` from the parser.

        Returns:
            A ``ParagraphNode`` with the paragraph name and its statements.
        """
        name = ctx.paragraphName().getText()
        statements: list[StatementNode] = []
        for sentence_ctx in ctx.sentence():
            for stmt_ctx in sentence_ctx.statement():
                stmt = self._visit_statement(stmt_ctx)
                if stmt is not None:
                    statements.append(stmt)
        return ParagraphNode(name=name, statements=statements)

    def _visit_statement(
        self, ctx: Cobol85Parser.StatementContext
    ) -> StatementNode | None:
        """Dispatch a statement context to the appropriate handler.

        The grammar's ``statement`` rule is a union of all statement types.
        We check which alternative matched and delegate to the corresponding
        visitor method. Unhandled statement types return ``None``.

        Args:
            ctx: A ``StatementContext`` from the parser.

        Returns:
            A typed statement AST node, or ``None`` for unhandled types.
        """
        if ctx.displayStatement():
            return self._visit_display(ctx.displayStatement())
        if ctx.moveStatement():
            return self._visit_move(ctx.moveStatement())
        if ctx.addStatement():
            return self._visit_add(ctx.addStatement())
        if ctx.callStatement():
            return self._visit_call(ctx.callStatement())
        if ctx.ifStatement():
            return self._visit_if(ctx.ifStatement())
        if ctx.stopStatement():
            return self._visit_stop(ctx.stopStatement())
        if ctx.gobackStatement():
            return GobackNode()
        if ctx.execSqlStatement():
            return self._visit_exec_sql(ctx.execSqlStatement())
        return None

    def _visit_display(self, ctx: Cobol85Parser.DisplayStatementContext) -> DisplayNode:
        """Extract operands from a DISPLAY statement.

        DISPLAY outputs one or more operands to the console. Each operand
        can be a string literal (``"Hello"``) or a data name (``WS-FIELD``).

        The grammar structure is:
            displayStatement → DISPLAY displayOperand+ displayAt? displayUpon?
                               displayWith?

        Args:
            ctx: A ``DisplayStatementContext`` from the parser.

        Returns:
            A ``DisplayNode`` with the list of operand texts.
        """
        operands: list[str] = []
        for op_ctx in ctx.displayOperand():
            operands.append(op_ctx.getText())
        return DisplayNode(operands=operands)

    def _visit_move(self, ctx: Cobol85Parser.MoveStatementContext) -> MoveNode:
        """Extract source and targets from a MOVE statement.

        MOVE is COBOL's assignment: ``MOVE source TO target1 target2 ...``
        The source can be a literal, data name, or figurative constant
        (e.g., ZEROS, SPACES).

        The grammar structure is:
            moveStatement → MOVE ALL? (moveToStatement |
                            moveCorrespondingToStatement)
            moveToStatement → moveToSendingArea TO identifier+

        Args:
            ctx: A ``MoveStatementContext`` from the parser.

        Returns:
            A ``MoveNode`` with the source value and target names.
        """
        move_to = ctx.moveToStatement()
        if move_to:
            source = move_to.moveToSendingArea().getText()
            targets = [ident.getText() for ident in move_to.identifier()]
            return MoveNode(source=source, targets=targets)
        # MOVE CORRESPONDING is not used in the sample files.
        return MoveNode(source=ctx.getText(), targets=[])

    def _visit_add(self, ctx: Cobol85Parser.AddStatementContext) -> AddNode:
        """Extract value and target from an ADD statement.

        The grammar structure is:
            addStatement → ADD (addToStatement | addToGivingStatement |
                           addCorrespondingStatement) ...
            addToStatement → addFrom+ TO addTo+

        Args:
            ctx: An ``AddStatementContext`` from the parser.

        Returns:
            An ``AddNode`` with the value being added and the target variable.
        """
        add_to = ctx.addToStatement()
        if add_to:
            # addFrom is the value being added (a literal or identifier).
            value = add_to.addFrom(0).getText()
            # addTo is the target variable receiving the sum.
            target = add_to.addTo(0).identifier().getText()
            return AddNode(value=value, target=target)
        # ADD GIVING and ADD CORRESPONDING are not used in the samples.
        return AddNode(value=ctx.getText(), target="")

    def _visit_call(self, ctx: Cobol85Parser.CallStatementContext) -> CallNode:
        """Extract program name and USING items from a CALL statement.

        CALL invokes a subprogram: ``CALL "PROG" USING param1 param2 ...``

        The grammar structure is:
            callStatement → CALL (identifier | literal) callUsingPhrase? ...
            callUsingPhrase → USING callUsingParameter+

        Args:
            ctx: A ``CallStatementContext`` from the parser.

        Returns:
            A ``CallNode`` with the called program name and parameter list.
        """
        # The program name is a literal (quoted string) or an identifier.
        literal_ctx = ctx.literal()
        if literal_ctx:
            raw = literal_ctx.getText()
            # Strip surrounding quotes from the program name.
            if (raw.startswith('"') and raw.endswith('"')) or (
                raw.startswith("'") and raw.endswith("'")
            ):
                program_name = raw[1:-1]
            else:
                program_name = raw
        else:
            program_name = ctx.identifier().getText()

        # Extract USING parameters — typically passed by reference.
        using_items: list[str] = []
        using_ctx = ctx.callUsingPhrase()
        if using_ctx:
            for param in using_ctx.callUsingParameter():
                by_ref = param.callByReferencePhrase()
                if by_ref:
                    for ref in by_ref.callByReference():
                        ident = ref.identifier()
                        if ident:
                            using_items.append(ident.getText())

        return CallNode(program_name=program_name, using_items=using_items)

    def _visit_if(self, ctx: Cobol85Parser.IfStatementContext) -> IfNode:
        """Extract condition and branches from an IF/ELSE/END-IF statement.

        The grammar structure is:
            ifStatement → IF condition ifThen ifElse? END_IF?
            ifThen → THEN? (NEXT SENTENCE | statement*)
            ifElse → ELSE (NEXT SENTENCE | statement*)

        The condition text is extracted from the original source with whitespace
        preserved, rather than using ``getText()`` which concatenates tokens
        without spaces (e.g., ``SQLCODE=0`` instead of ``SQLCODE = 0``).

        The then- and else-branches are visited recursively to collect nested
        statements (which may themselves be IF statements).

        Args:
            ctx: An ``IfStatementContext`` from the parser.

        Returns:
            An ``IfNode`` with the condition text and both branch statement lists.
        """
        condition = _get_original_text(ctx.condition())

        then_stmts: list[StatementNode] = []
        then_ctx = ctx.ifThen()
        if then_ctx:
            for stmt_ctx in then_ctx.statement():
                stmt = self._visit_statement(stmt_ctx)
                if stmt is not None:
                    then_stmts.append(stmt)

        else_stmts: list[StatementNode] = []
        else_ctx = ctx.ifElse()
        if else_ctx:
            for stmt_ctx in else_ctx.statement():
                stmt = self._visit_statement(stmt_ctx)
                if stmt is not None:
                    else_stmts.append(stmt)

        return IfNode(
            condition=condition,
            then_statements=then_stmts,
            else_statements=else_stmts,
        )

    def _visit_stop(
        self, ctx: Cobol85Parser.StopStatementContext
    ) -> StopRunNode | None:
        """Handle a STOP statement.

        The grammar structure is:
            stopStatement → STOP (RUN | literal)

        Only ``STOP RUN`` produces a ``StopRunNode``. ``STOP literal``
        (which pauses execution with a message) is not modelled.

        Args:
            ctx: A ``StopStatementContext`` from the parser.

        Returns:
            A ``StopRunNode`` for STOP RUN, or ``None`` for other forms.
        """
        if ctx.RUN():
            return StopRunNode()
        return None

    def _visit_exec_sql(
        self, ctx: Cobol85Parser.ExecSqlStatementContext
    ) -> ExecSqlNode:
        """Extract the SQL text from an EXEC SQL ... END-EXEC block.

        The preprocessor tags each line of an EXEC SQL block with the
        ``*>EXECSQL`` prefix, and the grammar matches these tagged lines
        as ``EXECSQLLINE`` tokens:
            execSqlStatement → EXECSQLLINE+

        We strip the tags, remove the ``EXEC SQL`` and ``END-EXEC``
        markers, and return the inner SQL content as raw text.
        The SQL is not parsed — it is preserved verbatim.

        Args:
            ctx: An ``ExecSqlStatementContext`` from the parser.

        Returns:
            An ``ExecSqlNode`` containing the raw SQL text.
        """
        lines: list[str] = []
        for token in ctx.EXECSQLLINE():
            text = token.getText()
            # Strip the *>EXECSQL tag that the preprocessor added.
            text = text.replace("*>EXECSQL", "", 1)
            text = text.strip()
            if text:
                lines.append(text)
        full_text = " ".join(lines)
        # Remove the EXEC SQL opening marker.
        full_text = re.sub(r"^EXEC\s+SQL\s*", "", full_text, flags=re.IGNORECASE)
        # Remove the END-EXEC closing marker (with optional trailing period).
        full_text = re.sub(r"\s*END-EXEC\.?\s*$", "", full_text, flags=re.IGNORECASE)
        return ExecSqlNode(sql_text=full_text.strip())


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _get_original_text(ctx) -> str:
    """Get the original text of a parse tree context with whitespace preserved.

    ``ParserRuleContext.getText()`` concatenates all token texts without
    spaces, producing output like ``SQLCODE=0`` instead of ``SQLCODE = 0``.
    This function reads directly from the character input stream to preserve
    the original whitespace between tokens.

    Args:
        ctx: An ANTLR4 ``ParserRuleContext`` with ``start`` and ``stop`` tokens.

    Returns:
        The original source text spanning the context, with whitespace intact.
    """
    # Token.source is a tuple (TokenSource, InputStream).  source[1] is the
    # CharStream (InputStream) that the Lexer read from — i.e. the preprocessed
    # COBOL text.  Token.start / Token.stop are character-position indices into
    # that stream.
    input_stream = ctx.start.source[1]
    return input_stream.getText(ctx.start.start, ctx.stop.stop)


def _parse_pic_string(raw: str) -> PicClause:
    """Parse a raw PIC string into a ``PicClause``.

    Examples:
    - ``"S9(9)"``  → category="numeric", size=9, signed=True
    - ``"9(5)"``   → category="numeric", size=5, signed=False
    - ``"X(10)"``  → category="alphanumeric", size=10, signed=False
    - ``"X(1)"``   → category="alphanumeric", size=1, signed=False
    - ``"S9(7)"``  → category="numeric", size=7, signed=True

    The function expands repeat counts (e.g., ``9(5)`` → 5 positions) and
    sums all character positions to determine the total size.

    Args:
        raw: The raw PIC string text (without the ``PIC`` keyword).

    Returns:
        A ``PicClause`` with category, size, and sign information.
    """
    signed = raw.upper().startswith("S")

    # Determine category from the character types present.
    upper = raw.upper().lstrip("S")
    if "X" in upper or "A" in upper:
        category = "alphanumeric"
    else:
        category = "numeric"

    # Calculate total size by expanding repeat counts.
    # Pattern: a character class like 9, X, A optionally followed by (n).
    size = 0
    for match in re.finditer(r"[9XA](?:\((\d+)\))?", raw, re.IGNORECASE):
        count = int(match.group(1)) if match.group(1) else 1
        size += count

    return PicClause(raw=raw, category=category, size=size, signed=signed)


def _build_hierarchy(flat_items: list[DataItemNode]) -> list[DataItemNode]:
    """Nest data items based on COBOL level numbers.

    COBOL uses level numbers to express a hierarchy:
    - Level-01 items are top-level (or level-77 standalone items).
    - Items with higher level numbers (02-49) are children of the preceding
      item with a lower level number.

    Example::

        01  GROUP-ITEM.          → top-level, no PIC (group)
            05  CHILD-1  PIC X.  → child of GROUP-ITEM
            05  CHILD-2  PIC X.  → child of GROUP-ITEM

    The algorithm uses a stack to track the current nesting path. When a new
    item has a level number higher than the current item, it becomes a child.
    When the level number is equal or lower, we pop back up the stack to find
    the correct parent.

    Args:
        flat_items: Data items in declaration order (not yet nested).

    Returns:
        A list of top-level ``DataItemNode`` instances with children populated.
    """
    if not flat_items:
        return []

    top_level: list[DataItemNode] = []
    # Stack of (level_number, DataItemNode) tracking the nesting path.
    stack: list[tuple[int, DataItemNode]] = []

    for item in flat_items:
        # Pop items from the stack that are at the same or deeper level,
        # because the new item is a sibling or belongs to a higher ancestor.
        while stack and stack[-1][0] >= item.level:
            stack.pop()

        if stack:
            # The item is a child of the current top of stack.
            parent = stack[-1][1]
            parent.children.append(item)
        else:
            # No parent on the stack — this is a top-level item.
            top_level.append(item)

        # Push this item onto the stack so subsequent deeper items
        # can become its children.
        stack.append((item.level, item))

    return top_level
