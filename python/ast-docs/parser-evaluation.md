# Python COBOL AST Parser — Evaluation of Approaches

## 1. Requirements Summary

The parser must handle COBOL source files written for two target environments:

- **Micro Focus COBOL compiled on IBM AIX** (big-endian) — the legacy platform
- **IBM COBOL for Linux on x86** (little-endian) — the migration target

The following COBOL constructs appear in the project's sample files (`samples/`) and must be parsed:

| Construct | Where it appears | What the parser must capture |
|---|---|---|
| **IDENTIFICATION DIVISION** | All six `.cob` files | `PROGRAM-ID` name |
| **ENVIRONMENT DIVISION** | All files (empty) | Division presence |
| **DATA DIVISION** | All files | Division structure |
| **WORKING-STORAGE SECTION** | All files | Section with data items |
| **LINKAGE SECTION** | ENDIAN02-CALLED, SAFE02-CALLED | Section with parameter items |
| **Level-01 data items** | All files | Level number, name, PIC clause, USAGE, VALUE |
| **Level-05 data items** | ENDIAN01, SAFE02-CALLED | Subordinate items within group structures |
| **PIC S9(n) COMP** | ENDIAN01, ENDIAN02-*, SAFE02-* | Binary integer, big-endian under BINARY(BE) |
| **PIC S9(n) COMP-3** | SAFE01 | Packed decimal |
| **PIC S9(n) COMP-5** | ENDIAN01, SAFE02-CALLED | Native-endian binary (Micro Focus / IBM extension) |
| **PIC 9(n) DISPLAY** | SAFE01 | Zoned decimal |
| **PIC S9(n) DISPLAY** | SAFE01 | Signed zoned decimal |
| **PIC X(n)** | ENDIAN01, SAFE01 | Alphanumeric |
| **REDEFINES** | ENDIAN01 (3 instances) | Source item redefining target item |
| **VALUE clause** | ENDIAN01, SAFE01 | Literal values (numeric, string, ZEROS) |
| **PROCEDURE DIVISION** | All files | Statement sequence |
| **PROCEDURE DIVISION USING** | ENDIAN02-CALLED, SAFE02-CALLED | Parameter list for called programs |
| **Paragraph names** | All files (MAIN-PARA) | Labels in PROCEDURE DIVISION |
| **DISPLAY statement** | All files | String/variable output |
| **MOVE statement** | ENDIAN02-CALLER, SAFE02-* | Data movement |
| **ADD statement** | SAFE01 | Arithmetic |
| **CALL ... USING** | ENDIAN02-CALLER, SAFE02-CALLER | Inter-program invocation with parameters |
| **IF / ELSE / END-IF** | ENDIAN02-CALLED, SAFE02-CALLED | Conditional logic |
| **STOP RUN** | ENDIAN01, SAFE01, callers | Program termination |
| **GOBACK** | ENDIAN02-CALLED, SAFE02-CALLED | Return to caller |
| **EXEC SQL ... END-EXEC** | ENDIAN02-CALLED, SAFE02-CALLED | Embedded SQL (SELECT INTO, INCLUDE SQLCA/SQLCA5) |
| **Figurative constants** | ENDIAN02-CALLER, SAFE02-CALLER | `ZEROS` in MOVE ZEROS TO ... |
| **Numeric literals** | ENDIAN01, SAFE01, SAFE02-CALLED | Integer literals (12345, 70000, 1000, 0) |
| **String literals** | All files (DISPLAY) | Quoted strings in DISPLAY statements |
| **Fixed-format layout** | All files | Columns 1-6 (sequence), 7 (indicator), 8-72 (code) |
| **Full-line comments** | All files (column 7 `*`) | Must be recognized and skipped |
| **Inline comments** | All files (`*>`) | Must be recognized and skipped |

### Constructs not yet in samples but expected in a real codebase

These are mentioned in the project's task description and would likely appear in future samples:

- **COPY statements** (copybook inclusion)
- **COPY ... REPLACING** (copybook inclusion with text substitution)
- **EVALUATE / WHEN** (switch-case equivalent)
- **PERFORM** (loop / paragraph invocation)
- **OCCURS** (arrays)
- **88-level condition names**

---

## 2. Options Evaluated

| # | Option | Type | Existing COBOL grammar? | License | Actively maintained? |
|---|---|---|---|---|---|
| 1 | **ANTLR4 + Cobol85.g4** | Grammar-based parser generator | Yes (comprehensive, NIST-tested) | MIT | Yes |
| 2 | **tree-sitter-cobol + py-tree-sitter** | Incremental parser with C runtime | Yes (partial, NIST-tested) | MIT | Moderate |
| 3 | **Lark + custom grammar** | Pure-Python Earley/LALR parser | No — write from scratch | MIT | Yes (Lark itself) |
| 4 | **pyparsing + custom grammar** | Pure-Python combinator parser | No — write from scratch | MIT | Yes |
| 5 | **Hand-rolled recursive descent** | Custom parser in Python | N/A | N/A | N/A |
| 6 | **Koopa** | Java COBOL parser generator | Yes (comprehensive) | BSD | Yes |
| 7 | **Existing pip packages** | Various copybook/extractor tools | N/A (none parse full programs) | Various | Various |

Options 6 and 7 are not viable as primary approaches (Koopa is Java-only; pip packages only parse copybooks, not full programs) and are excluded from detailed analysis below.

---

## 3. Detailed Analysis

### Option 1: ANTLR4 + Cobol85.g4

**What it is.** The `antlr/grammars-v4` repository contains a comprehensive COBOL-85 grammar (`Cobol85.g4`, ~5,600 lines) originally authored by Ulrich Wolffgang for the ProLeap COBOL Parser. A companion preprocessor grammar (`Cobol85Preprocessor.g4`) handles COPY, REPLACE, and EXEC blocks. The grammar passes the NIST COBOL-85 test suite and has been used in production on banking/insurance codebases. You generate a Python parser with `antlr4 -Dlanguage=Python3 Cobol85.g4` and walk the resulting parse tree using Visitor or Listener classes.

**Strengths:**
- Most comprehensive open-source COBOL grammar available — covers all four divisions, COMP through COMP-5, EXEC SQL/CICS, REDEFINES, LINKAGE SECTION, 88-levels, OCCURS, PERFORM, EVALUATE, and hundreds of other constructs.
- NIST COBOL-85 test suite validated. Used against real-world banking codebases.
- MIT license. No restrictions on educational use.
- ANTLR4's Python runtime (`antlr4-python3-runtime`) is mature and well-documented.
- Generated Visitor/Listener classes are strongly typed to grammar rules (e.g., `visitDataDescriptionEntry()`), giving clear extension points.
- The grammar is a readable artifact — students can study `Cobol85.g4` to understand COBOL syntax.

**Weaknesses:**
- **Preprocessing required.** Fixed-format column handling (sequence area, indicator column) is not in the main grammar — it is handled by Java preprocessing code in the grammars-v4 repo. This Java preprocessor must be **rewritten in Python**. It handles: stripping columns 1-6 and 73-80, interpreting column 7 indicators (`*`, `-`, `D`, `/`), line continuation, and COPY/REPLACE expansion.
- **Parse tree, not AST.** ANTLR4 produces a concrete syntax tree (CST) that preserves every token. To get a clean AST with typed Python dataclasses, you must write a Visitor layer that extracts semantic information and discards syntactic noise.
- **Version coupling.** The ANTLR4 tool version and `antlr4-python3-runtime` version must match exactly.
- **Grammar size.** At ~5,600 lines, the grammar is complex. Debugging parser issues requires understanding ANTLR4's grammar notation and the COBOL grammar's structure.
- **Not reusable across project languages.** The generated Python code is Python-specific. For TypeScript/Go/Java implementations in this project, separate parsers would need to be generated (though from the same `.g4` grammar).
- **Memory.** ANTLR4's Python runtime can be memory-hungry on large files (issue #2315 in grammars-v4).

**Dialect gaps:**
- COMP-5 is explicitly supported in the grammar.
- EXEC SQL is supported (both in main grammar and preprocessor).
- Micro Focus-specific extensions beyond COMP-5 are not explicitly documented but IBM COBOL compatibility is strong.

**Effort estimate:** Medium-high. Generating the parser is trivial (one command). Writing the Python preprocessor for fixed-format handling is the largest effort. Building the CST-to-AST Visitor layer is moderate.

---

### Option 2: tree-sitter-cobol + py-tree-sitter

**What it is.** A tree-sitter grammar for COBOL (`yutaro-sakamoto/tree-sitter-cobol`) that produces incremental, error-tolerant parse trees. Used from Python via the `tree_sitter` package (official bindings). The grammar is defined in `grammar.js` (JavaScript) and compiled to a C parser.

**Strengths:**
- **Multi-language reusability.** The same compiled grammar works from Python, Node.js, Go, Rust, and Java — a perfect match for this project's plan to add TypeScript, Go, and Java implementations. One grammar, four languages.
- **Error tolerance.** tree-sitter produces a valid tree even for syntactically incomplete or erroneous COBOL. Useful for educational examples and real-world messy code.
- **Performance.** The parser is written in C; parsing is extremely fast even for large files. Incremental re-parsing means edits are near-instant.
- **Ecosystem.** tree-sitter is used by GitHub (code navigation), Neovim, Helix, and other tools. Well-supported infrastructure.
- **MIT license.**
- NIST COBOL-85 test suite tested.

**Weaknesses:**
- **Grammar completeness is uncertain.** The grammar has 33 GitHub stars and 12 open issues. Coverage of vendor-specific extensions (COMP-5, EXEC SQL) is not documented — it needs empirical testing against the sample files.
- **Build step.** The grammar must be compiled into a shared library (`.so`/`.dylib`) for `py-tree-sitter`. This adds a build dependency (C compiler, Node.js for grammar generation).
- **Grammar.js authoring.** If the grammar needs extension, you must modify `grammar.js` (JavaScript, not Python), which is a different skill from the rest of the Python codebase.
- **CST output.** Like ANTLR4, tree-sitter produces a concrete syntax tree. You must walk the tree to build a semantic AST.
- **No preprocessor.** COPY expansion and fixed-format column stripping are not handled by tree-sitter itself — you need a preprocessing step.
- **Not in `tree-sitter-languages`.** The COBOL grammar is not in the pre-bundled `tree-sitter-languages` package, so you cannot `pip install` it — you must build from source.

**Dialect gaps:**
- COMP-5 support: unknown, needs testing.
- EXEC SQL support: unknown, needs testing.
- Fixed-format handling: unknown, needs testing.

**Effort estimate:** Medium. Compiling and integrating the grammar is moderate. The unknown dialect coverage is the main risk — if the grammar lacks critical constructs, extending `grammar.js` is more difficult than extending an ANTLR4 `.g4` file (JavaScript DSL vs. declarative EBNF).

---

### Option 3: Lark + Custom COBOL Grammar

**What it is.** Lark is a pure-Python parsing library that accepts grammars in an EBNF-like notation. You would write a COBOL grammar from scratch in Lark's format and use its `Transformer` to convert the parse tree into typed AST nodes.

**Strengths:**
- **Pure Python, zero C dependencies.** Easy to install (`pip install lark`), no build step.
- **Earley parser available.** Lark's Earley mode handles ambiguous grammars gracefully, which is useful for COBOL's context-sensitive keywords.
- **Transformer pattern.** Lark's `Transformer` class provides a clean, Pythonic way to convert the parse tree into custom AST dataclasses — well-suited for educational code.
- **Educational transparency.** Writing the grammar from scratch means students can see every rule and understand exactly what is being parsed. The grammar is a readable, self-contained `.lark` file.
- **Active maintenance.** Lark 1.x is actively maintained, well-documented, MIT licensed.

**Weaknesses:**
- **No existing COBOL grammar.** You must write the entire grammar from scratch. For the subset of COBOL in the samples, this is 200-500 lines. For broader coverage, it could grow to 1,000+.
- **No column awareness.** Lark has no concept of column position. Fixed-format handling requires a preprocessing step that strips/transforms column regions before Lark sees the input.
- **Performance.** Earley parsing in pure Python is slow for large files. LALR(1) is faster but may struggle with COBOL's ambiguities.
- **Not reusable across languages.** A Lark grammar is specific to Lark (Python). TypeScript/Go/Java implementations would need their own parser.
- **Risk of grammar bugs.** Writing a COBOL grammar from scratch is error-prone, especially for edge cases (continuation lines, inline EXEC SQL, nested conditionals).

**Dialect gaps:** None inherent — you write the grammar, so you control dialect coverage. The risk is in omitting constructs rather than the tool lacking support.

**Effort estimate:** Medium for the current sample subset. High for broader COBOL coverage. The grammar writing is the main effort, but it produces the most educationally transparent result.

---

### Option 4: pyparsing + Custom COBOL Grammar

**What it is.** pyparsing is a pure-Python combinator parsing library where you define the grammar in Python code using operator overloading (`+`, `|`, `~`). It has been actively maintained for 20+ years.

**Strengths:**
- **Column-aware helpers.** pyparsing provides `AtColumn()`, `LineStart()`, and `LineEnd()` constructs that can enforce column-position rules. This is a meaningful advantage for COBOL's fixed-format layout — you can match Area A vs. Area B placement directly in grammar rules.
- **Pure Python.** No build step, no C dependencies.
- **Mature.** 20+ years of development, extensive documentation and examples.
- **Parse actions.** You can attach Python functions to grammar rules that transform matched tokens on the fly, producing AST nodes directly.

**Weaknesses:**
- **No existing COBOL grammar.** Must write from scratch.
- **Combinator style does not scale.** For a language as large as COBOL, defining the grammar as chains of Python objects becomes unwieldy and hard to read. A 500-rule grammar in pyparsing is substantially less readable than the same grammar in EBNF notation (Lark or ANTLR4).
- **Performance.** Pure Python with backtracking. Can be slow on large inputs.
- **Not reusable across languages.**
- **Grammar is code, not data.** The grammar is embedded in Python source rather than being a standalone, portable artifact. This reduces educational transparency — the grammar structure is mixed with Python syntax.

**Dialect gaps:** Same as Lark — you write the grammar, you control coverage.

**Effort estimate:** Medium for the current subset. The column-aware helpers reduce preprocessing effort compared to Lark, but the combinator style makes the grammar harder to maintain as it grows.

---

### Option 5: Hand-Rolled Recursive Descent

**What it is.** A custom lexer and recursive-descent parser written entirely in Python, with no parser library dependency.

**Strengths:**
- **Maximum educational value.** Students learn how parsing works at every level — tokenization, lookahead, recursive descent, AST construction. No library abstractions to hide behind.
- **Full control over column handling.** The lexer can inspect column positions natively without a preprocessing step.
- **Full control over AST shape.** You produce exactly the AST node types you need — dataclasses with type hints, directly.
- **Zero dependencies.** Pure Python standard library.
- **Precise error messages.** You control every error path and can produce COBOL-specific diagnostics.

**Weaknesses:**
- **Highest effort.** You must write every parsing rule by hand. Even for the current sample subset, this is 500-1,000 lines of careful code.
- **Not reusable across languages.** The parser is Python-only.
- **Bug surface.** Hand-rolled parsers are prone to subtle bugs in edge cases (continuation lines, nested structures, ambiguous keywords).
- **No grammar artifact.** The parsing logic is spread across methods — there is no single, inspectable grammar file that defines what the parser accepts.
- **Maintenance burden.** Adding new COBOL constructs requires writing new parsing methods rather than adding grammar rules.

**Dialect gaps:** None inherent — full control.

**Effort estimate:** High. Produces the most educational parser code but requires the most development time.

---

## 4. Recommendation

### Primary: ANTLR4 + Cobol85.g4

**ANTLR4 with the existing Cobol85 grammar is the best fit for this project.**

**Justification:**

1. **The grammar already exists and is battle-tested.** The `Cobol85.g4` grammar (~5,600 lines) covers every COBOL construct in the sample files — COMP-5, EXEC SQL, REDEFINES, LINKAGE SECTION, all four divisions — plus hundreds of constructs the project will likely need as it grows (PERFORM VARYING, EVALUATE, STRING/UNSTRING, OCCURS DEPENDING ON, 88-levels, nested programs). Writing a grammar from scratch (as Lark, pyparsing, or hand-rolled approaches require) means re-inventing this coverage one rule at a time, with no guarantee of correctness. Starting from a NIST-validated grammar eliminates an entire class of bugs.

2. **The grammar itself is educational.** `Cobol85.g4` is a readable, standalone artifact that defines COBOL syntax in EBNF notation. Students can open the grammar file, find the rule for `dataDescriptionEntry` or `callStatement`, and see exactly what syntactic forms COBOL allows. This is the same kind of educational transparency that a Lark `.lark` file would provide — but with complete language coverage instead of a hand-maintained subset.

3. **Typed Visitor/Listener classes.** ANTLR4 generates Visitor and Listener base classes with methods named after grammar rules: `visitIdentificationDivision()`, `enterDataDescriptionEntry()`, `exitCallStatement()`. These provide clear, well-typed extension points for building an AST. Writing a Visitor that converts the parse tree into Python dataclasses is where the real educational value lives — it teaches students how to walk a concrete syntax tree, extract semantic information, and build a domain-specific AST.

4. **The real learning is in the AST layer, not the grammar.** The educational goals of this project are best served by focusing on: (a) the Python dataclass AST design, (b) the Visitor that builds it, (c) the analyzers that operate on it. These are the components students write and study. The grammar is a tool — having it pre-built lets students focus on the interesting parts rather than spending weeks debugging grammar rules for COBOL's many syntactic edge cases.

5. **Scales gracefully.** As the project adds more COBOL constructs or tackles more complex sample programs, the grammar already handles them. With Lark or a hand-rolled parser, each new construct requires writing and testing new grammar rules — a cost that grows linearly with coverage. With ANTLR4, the grammar is already done; only the Visitor needs extension.

6. **Cross-language grammar reuse.** The same `.g4` grammar files generate parsers for Python, TypeScript (via antlr4ts), Go, and Java — matching this project's plan for multi-language implementations. Each language writes its own Visitor/AST layer (idiomatic to that language), but the grammar is shared. This avoids maintaining four separate grammars that must stay in sync.

**Trade-offs acknowledged:**

- **Preprocessing must be written in Python.** The `grammars-v4` repo includes a Java preprocessor for fixed-format column handling, COPY expansion, and line continuation. This must be reimplemented in Python. This is a nontrivial but well-scoped task (format detection, column stripping, indicator interpretation, continuation joining, COPY/REPLACE resolution). It is also educational — the preprocessor teaches students about COBOL's fixed-format layout, which is fundamental to understanding COBOL source code.

- **CST, not AST.** ANTLR4 produces a verbose concrete syntax tree that preserves every token. You must write a Visitor to extract a clean AST. This is extra code, but it is the same work any grammar-based approach requires (Lark's Transformer, tree-sitter's tree walker, etc.). The Visitor pattern is well-documented and the generated base classes make it straightforward.

- **Toolchain complexity.** Using ANTLR4 requires: (a) the ANTLR4 tool (Java JAR) to generate the parser, (b) `antlr4-python3-runtime` with an exactly matching version. This is more setup than `pip install lark`, but it is a one-time cost, well-documented, and automatable via a build script.

- **Grammar size.** At ~5,600 lines, the full grammar is large. Students do not need to read it end-to-end — they look up specific rules as needed (e.g., "how does ANTLR4 parse a REDEFINES clause?"). The grammar is a reference, not a tutorial.

- **Memory on large files.** ANTLR4's Python runtime can be memory-hungry on very large COBOL programs (thousands of lines). For the educational sample files (50-110 lines), this is irrelevant.

### Fallback: Lark + Custom COBOL Grammar

If the ANTLR4 toolchain proves too burdensome (e.g., the version-coupling issues or the Java dependency create friction for contributors), Lark is the best pure-Python alternative. Its Earley parser handles COBOL's ambiguities, its `Transformer` pattern produces clean AST output, and `pip install lark` is trivially simple. The cost is writing and maintaining the grammar from scratch, which limits how far the project can grow before the grammar becomes a maintenance burden.

### Why not tree-sitter?

Tree-sitter's multi-language reusability is compelling. However:

- The `tree-sitter-cobol` grammar's coverage of COMP-5 and EXEC SQL is undocumented and needs empirical validation before committing.
- Extending the grammar requires JavaScript (`grammar.js`), adding a third language to a Python-focused project.
- The build step (compile grammar to a C shared library) adds more friction than ANTLR4's JAR-based generation.
- ANTLR4 provides the same cross-language benefit (one `.g4` grammar, multiple target languages) with a more mature COBOL grammar.

Tree-sitter should be reconsidered if the `tree-sitter-cobol` grammar matures and adds documented support for the needed dialect extensions. Its error tolerance and incremental parsing are genuine advantages that ANTLR4 lacks.

### Why not Lark, pyparsing, or hand-rolled as primary?

All three require writing a COBOL grammar from scratch. This is viable for the current small sample set, but it means:

- Every new COBOL construct requires grammar work before it can be parsed — development effort scales linearly with language coverage.
- Grammar correctness depends on the author's knowledge of COBOL syntax, not on a NIST-validated reference.
- The grammar is Python-only — other language implementations cannot reuse it.

The educational value of writing a grammar from scratch is real, but it comes at the cost of coverage, correctness, and cross-language reuse. Since the project's primary educational goal is AST analysis and transformation (not parser construction), using a proven grammar and focusing effort on the AST layer is the better trade-off.

---

## 5. Risks and Unknowns

### Risk 1: Python preprocessor for fixed-format handling

**What could go wrong:** The `grammars-v4` Java preprocessor handles column stripping, line continuation, comment removal, and COPY/REPLACE expansion. Reimplementing this in Python is the largest piece of new code. Subtle bugs (e.g., incorrect continuation-line joining, wrong column boundaries) silently corrupt the input before ANTLR4 sees it.

**Mitigation:** Write the preprocessor first, with dedicated tests for each concern: column stripping, comment lines (column 7 `*`), inline comments (`*>`), continuation lines (column 7 `-`), debug lines (column 7 `D`). Test against all six sample files before writing any Visitor code. The preprocessor is a well-scoped, independently testable component.

### Risk 2: ANTLR4 Python runtime version coupling

**What could go wrong:** The ANTLR4 tool version and `antlr4-python3-runtime` version must match exactly. If a contributor has a different ANTLR4 version installed, the generated parser may be incompatible with the pinned runtime.

**Mitigation:** Pin the exact versions in `requirements.txt` and the build script. Commit the generated parser files to the repository so that contributors do not need to install the ANTLR4 tool unless they modify the grammar. Document the version requirement clearly.

### Risk 3: CST-to-AST Visitor complexity

**What could go wrong:** The `Cobol85.g4` grammar produces a deeply nested parse tree with many intermediate nodes. Writing a Visitor that navigates this tree to extract clean AST nodes requires understanding the grammar's structure, which has a learning curve.

**Mitigation:** Start with a minimal Visitor that handles only the constructs in the sample files. Use ANTLR4's `toStringTree()` to inspect the parse tree for each sample file and understand its shape before writing Visitor methods. Build the Visitor incrementally — one COBOL construct at a time, with tests at each step.

### Risk 4: EXEC SQL blocks and the preprocessor grammar

**What could go wrong:** EXEC SQL blocks contain embedded SQL, not COBOL. The main `Cobol85.g4` grammar has rules for EXEC SQL statements, but the preprocessor grammar (`Cobol85Preprocessor.g4`) also processes EXEC blocks during preprocessing. The interaction between these two grammars for EXEC SQL handling needs to be understood — using the wrong approach could cause the SQL content to be mangled or lost.

**Mitigation:** Study how the Java ProLeap parser handles EXEC SQL. In the simplest approach, treat `EXEC SQL ... END-EXEC` as an opaque block during preprocessing (preserve the content as-is) and let the main grammar's `execSqlStatement` rule match the boundaries. The SQL content between the delimiters can be captured as raw text.

### Risk 5: Grammar dialect gaps for Micro Focus extensions

**What could go wrong:** The `Cobol85.g4` grammar is IBM COBOL-centric. While it handles COMP-5 (present in both IBM and Micro Focus), there may be Micro Focus-specific syntax in real production code that the grammar does not recognize (e.g., certain compiler directives, non-standard PERFORM syntax, proprietary EXEC blocks).

**Mitigation:** The current sample files use standard COBOL-85 constructs plus COMP-5 and EXEC SQL, all of which the grammar supports. If future samples include Micro Focus-specific syntax that the grammar rejects, the `.g4` file can be extended — ANTLR4 grammars are designed to be modified. Document any grammar extensions in a changelog so they do not diverge silently from the upstream `grammars-v4` version.

### Prototyping needed before committing

The following questions should be answered by a spike (a small proof-of-concept) before committing fully:

1. **Can a Python preprocessor correctly normalize all six sample files?** Write the fixed-format preprocessor and verify that ANTLR4 can parse its output without errors.
2. **What does the parse tree look like for a sample file?** Generate the Python parser, parse `SAFE01.cob` (the simplest sample), and inspect the tree structure with `toStringTree()`. Verify that the tree contains the expected nodes for data items, PIC clauses, and statements.
3. **Can a minimal Visitor extract PROGRAM-ID and data items?** Write a Visitor that visits `identificationDivision` and `dataDescriptionEntry` to produce typed Python dataclasses. Verify the pipeline end-to-end: COBOL source → preprocessor → ANTLR4 parser → Visitor → dataclass AST.
4. **How does EXEC SQL appear in the parse tree?** Parse `ENDIAN02-CALLED.cob` and inspect the EXEC SQL nodes. Confirm that the SQL content is accessible and not mangled.

If any of these spike questions reveals a fundamental blocker (e.g., the grammar rejects the preprocessed sample files, or the Python runtime crashes on the grammar size), fall back to Lark with a custom grammar.
