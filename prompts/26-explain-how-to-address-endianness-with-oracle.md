# Role

You are a COBOL migration expert and AST (Abstract Syntax Tree) practitioner. You understand both the endianness problem in COBOL platform migrations and how AST-based analysis can automate the detection and remediation of endianness issues at scale.

Read these documents in full before proceeding:

- `cobol-docs/COMP5_ORACLE_PROBLEM_EXPLAINED.md` — the COMP-5/Oracle sub-problem
- `python/src/cobol_ast/ast_nodes.py` — the AST node types this project already captures
- `python/src/cobol_ast/__init__.py` — the public API (`parse_cobol_file`, `parse_cobol_source`)

Also parse and inspect the sample COBOL files under `samples/endianness/` to ground your explanation in concrete examples from this project.

# Context

This is an educational project that builds AST parsers for COBOL code. The Python implementation can already parse COBOL source files into a typed AST that captures:

- Data items with their **level numbers**, **PIC clauses**, **USAGE types** (COMP, COMP-3, COMP-5, DISPLAY), **VALUE clauses**, **REDEFINES** targets, and **parent–child hierarchy**
- PROCEDURE DIVISION statements including **MOVE**, **CALL** (with USING items), **EXEC SQL** (with raw SQL text), **DISPLAY**, **ADD**, **IF/ELSE**, **STOP RUN**, **GOBACK**
- The distinction between **WORKING-STORAGE** and **LINKAGE SECTION** items
- **PROCEDURE DIVISION USING** clause for called subprograms

The endianness documents describe a real-world migration problem (AIX big-endian → Linux x86 little-endian) with specific rules about which data items need to change and how. These rules are deterministic and can be expressed as AST queries.

The project has to explain how to migrate from Cobol on AIX to Cobol on Linux. Therefore you must assume that:
- the source code you see is using bigendian and you need to find algorithms to migrate this code to a littlendian environment
- the target code will be compiled with the `BINARY(BE)` and `FLOAT(BE)` options.

# Task

Write a clear, educational document (saved as `ast-docs/ast-for-endianness-oracle.md`) that explains how AST-based analysis can help solve the endianness problem with Oracle described in the cobol-docs. The document should make the connection concrete by referencing the AST node types and sample files from this project.

Structure the document as follows:

## 1. The Problem

Briefly restate why endianness is dangerous in COBOL migrations (silent data corruption, no compiler errors). Focus only on the Oracle problem.

## 2. What the AST Gives You

Explain what information the AST captures that makes automated analysis possible. Map each endianness with Oracle rule from the documents to the specific AST node fields that are needed to evaluate it. Use the actual field names from `ast_nodes.py` (e.g., `DataItemNode.usage`, `DataItemNode.redefines`, `ExecSqlNode.sql_text`, `CallNode.using_items`). Show which checks can be implemented using the AST and highlight checks that can not be performed using the AST, suggesting alternative solutions.

## 3. Concrete Analysis Examples

For each of the endianness checks relevant with Oracle, show how it can be implemented as an AST query. Use the sample files under `samples/endianness/` as concrete examples — parse them with `parse_cobol_file`, walk the resulting AST, and describe what the analysis would find. Write the examples as pseudocode or plain-English algorithms, not full Python implementations.

## 4. What the AST Cannot Tell You (and What Else You Need)

Be honest about the limits. If there are things that it is not possible to do with the AST analysis only, state them clearly and suggest an alternative approach.

## 5. From Detection to Transformation

Briefly explain that AST is not just for detection — it can also drive automated code transformation. For example:
- Changing `COMP` to `COMP-5` on Oracle host variables
- Inserting MOVE statements to convert LINKAGE COMP parameters to WORKING-STORAGE COMP-5 variables before SQL
- Replacing `SQLCA` with `SQLCA5` in EXEC SQL INCLUDE statements

Note that this project's AST is currently read-only (frozen dataclasses). Describe at a high level how a transformation pipeline would work: parse → analyze → build modified AST → emit COBOL source. Explain how to implement thw source emission (unparsing) considering that the COBOL's fixed-format layout must be preserved.

# Output requirements

- Save the document as `ast-docs/ast-for-endianness-oracle.md`.
- Use clear headings and short paragraphs. This is an educational document — make sure that clarity goes together with completeness.
- Reference specific file names from `samples/endianness/` and specific field names from `ast_nodes.py` to keep the explanation grounded in this project.
- First describe the solution with pseudocode and plain-English then add Python implementation. 
- Keep the document concise and to the point. It must be clear and explain how to solve this problem.

# Review

After writing the document, review it against these criteria:
1. Does every endianness for Oracle rule from the cobol-docs map to a concrete AST query?
2. Are the AST field names accurate (check against `ast_nodes.py`)?
3. Are the sample file references accurate (check the files actually exist and contain what the document claims)?
4. Is the "limitations" section honest — does it avoid overselling what AST alone can do?
