# Introduction to AST Parsers — A COBOL Walkthrough

## Part 1 — AST Parsing in 5 Minutes

### The problem

Source code is text. If you want to programmatically answer questions about it — "What variables does this program declare?" or "Does this function call that one?" — you need to turn that text into a structure your code can navigate. Regular expressions can match simple patterns, but they break down the moment you need to understand nesting, scope, or context. You need a parser.

### The solution in one picture

Here is what a parser does, end to end:

```
COBOL source file
       │
       ▼
    ┌───────┐
    │ Lexer │  Breaks the text into tokens (keywords, names, symbols)
    └───┬───┘
        │
        ▼
   ┌────────┐
   │ Parser │  Arranges tokens into a tree according to the language's grammar
   └───┬────┘
       │
       ▼
  ┌────────┐
  │  Tree  │  A structured representation of the program
  └───┬────┘
      │
      ▼
  Your analysis code
```

Take this snippet from `SAFE01.cob`:

```cobol
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAFE01.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-ORDER-ID        PIC S9(9) COMP-3 VALUE 12345.
```

The lexer chops it into tokens: `IDENTIFICATION`, `DIVISION`, `.`, `PROGRAM-ID`, `.`, `SAFE01`, `.`, and so on. The parser takes those tokens and builds a tree that captures the program's structure.

### What's a syntax tree?

That same snippet becomes a tree like this:

```
program
├── identificationDivision
│   └── programId: "SAFE01"
├── dataDivision
│   └── workingStorageSection
│       └── dataItem
│           ├── level: 01
│           ├── name: "WS-ORDER-ID"
│           ├── picture: "S9(9)"
│           ├── usage: COMP-3
│           └── value: 12345
```

Text became a tree. And trees are easy to walk programmatically — you can visit each node, ask what type it is, read its children, and collect exactly the information you need.

### You already use AST parsers every day

If you use an IDE like VS Code or IntelliJ, you are already relying on AST parsers without realizing it. When you right-click a variable and choose "Rename Symbol," the IDE parses your code into an AST, finds every node that references that symbol — the declaration, every usage, even occurrences in different files — and rewrites them all. "Go to Definition" works by locating the declaration node in the AST. The red squiggly error underlines you see as you type come from the IDE continuously re-parsing your code and spotting structural problems in the tree. Even syntax highlighting beyond simple keyword coloring uses the AST to understand what each token *means* in context. This project makes that same mechanism visible and hands-on — instead of the IDE doing it silently, you build the parser and walk the tree yourself.

### What can you do with it?

- **Analyze**: Walk the tree to list every data item and its type — for example, find all `COMP` fields that might be affected by a platform migration.
- **Transform**: Rename a variable from `WS-ORDER-ID` to `WS-ORD-ID` across the entire program — the tree knows every place the name appears, not just the definition.
- **Validate**: Check that every data item name starts with a standard prefix (like `WS-` for working storage) by inspecting the `name` field of each data-item node.

### Why COBOL is interesting

COBOL is not like the languages you may be used to. Cobol usually has a fixed-format layout where specific column positions determine what the compiler sees — columns 1-6 are line numbers, column 7 marks comments, and only columns 8-72 contain actual code. Its syntax is verbose and English-like (`ADD 1000 TO WS-AMOUNT`), and decades of vendor extensions mean there are dialect differences between compilers. These quirks make COBOL a challenging and instructive language to parse.

### How this project works

This project uses ANTLR4, a widely-used parser generator, together with an existing COBOL grammar to parse source files into a syntax tree. A preprocessing step handles COBOL's fixed-format layout, stripping line numbers and comments so the parser sees clean input. A Visitor then walks the resulting tree and builds a clean, typed AST — a set of simple data structures that represent the COBOL program's meaning without the syntactic noise. The rest of this document explains each of these concepts in detail, or you can jump directly to the [implementation plan](../python/ast-docs/implementation-plan.md).

---

## Part 2 — How It Actually Works

### 2.1. Parsing: from text to structure

When you look at a COBOL program, you see structure immediately — divisions, sections, data items, statements. A computer sees a flat sequence of characters. Parsing is the process of recovering that structure.

You might think: "Why not use regular expressions?" For simple, flat patterns, you can. A regex can find every line that starts with `01` and extract a variable name. But consider this snippet from `ENDIAN01.cob`:

```cobol
       01  WS-ORDER-ID        PIC S9(9) COMP VALUE 12345.
       01  WS-ORDER-BYTES     REDEFINES WS-ORDER-ID.
           05  WS-BYTE-1      PIC X(1).
           05  WS-BYTE-2      PIC X(1).
           05  WS-BYTE-3      PIC X(1).
           05  WS-BYTE-4      PIC X(1).
```

`WS-ORDER-BYTES` is a group item that REDEFINES `WS-ORDER-ID`, and it contains four subordinate items at level 05. To understand that `WS-BYTE-1` belongs to `WS-ORDER-BYTES`, which in turn redefines `WS-ORDER-ID`, you need to track hierarchical relationships defined by level numbers. A regex cannot do this — it has no concept of nesting or parent-child relationships. A grammar-based parser can, because the grammar encodes these structural rules.

The parser takes the flat text above and produces a tree where `WS-ORDER-BYTES` is a parent node, its four `05`-level items are children, and the REDEFINES relationship to `WS-ORDER-ID` is an explicit attribute.

### 2.2. Concrete Syntax Tree (CST) vs Abstract Syntax Tree (AST)

When a parser processes source code, it first produces a **Concrete Syntax Tree (CST)** — also called a parse tree. The CST is a direct, lossless representation of the grammar rules that were matched. Every token appears in the tree, including periods, noise words, and syntactic scaffolding that carries no semantic meaning.

The **Abstract Syntax Tree (AST)** is a simplified version. It keeps only the semantically meaningful information and drops the syntactic noise.

Here is a data item from `SAFE01.cob` shown as both trees:

```cobol
       01  WS-COUNTER         PIC 9(5) DISPLAY VALUE 98765.
```

**CST** (mirrors the grammar — every token is present):

```
dataDescriptionEntry
├── LEVEL_NUMBER: "01"
├── dataName
│   └── IDENTIFIER: "WS-COUNTER"
├── dataPictureClause
│   ├── PIC
│   └── pictureString
│       └── PICTURE_STRING: "9(5)"
├── dataUsageClause
│   └── DISPLAY
├── dataValueClause
│   ├── VALUE
│   └── literal
│       └── NUMERIC_LITERAL: "98765"
└── DOT: "."
```

**AST** (only what matters for analysis):

```
DataItem
├── level: 1
├── name: "WS-COUNTER"
├── picture: "9(5)"
├── usage: DISPLAY
└── value: 98765
```

The CST preserves the `PIC` keyword, the `VALUE` keyword, the trailing period, and the grammar rule names (`dataPictureClause`, `dataValueClause`). The AST collapses all of that into a clean data structure with named fields. When your analysis code needs to know the picture clause of a data item, it reads `item.picture` — it does not navigate through `dataPictureClause → pictureString → PICTURE_STRING`.

This project converts CST to AST because the grammar gives us a CST (that is what ANTLR4 produces), but our analysis and transformation code is far easier to write against the cleaner AST.

### 2.3. How grammar-based parsing works

The pipeline has four stages: **source text → lexer → parser → visitor**.

**What is a grammar?** A grammar is a set of rules that describes the structure of valid programs. Each rule says: "This construct is made up of these parts, in this order." Here is a simplified version of what a COBOL data description rule looks like in a grammar:

```
dataDescriptionEntry
    : levelNumber dataName? pictureClause? usageClause? valueClause? '.'
    ;
```

This says: a data description entry starts with a level number, optionally followed by a name, an optional picture clause, an optional usage clause, an optional value clause, and ends with a period. The grammar for full COBOL has thousands of such rules — the one this project uses has roughly 5,600 lines.

**What the lexer does.** The lexer (also called a tokenizer) reads the raw character stream and groups characters into **tokens** — the smallest meaningful units. Consider this line from `ENDIAN01.cob`:

```cobol
       01  WS-ORDER-ID        PIC S9(9) COMP VALUE 12345.
```

After preprocessing strips the fixed-format columns, the lexer produces tokens like:

```
LEVEL_NUMBER("01")  IDENTIFIER("WS-ORDER-ID")  PIC  PICTURE_STRING("S9(9)")
COMP  VALUE  NUMERIC_LITERAL("12345")  DOT(".")
```

Each token has a type (e.g., `LEVEL_NUMBER`, `IDENTIFIER`) and a text value. Whitespace and layout are consumed — the parser never sees them.

**What the parser does.** The parser reads the token stream and matches it against the grammar rules, building a tree. It sees `LEVEL_NUMBER("01")` and recognizes the start of a `dataDescriptionEntry`. It then expects the optional parts defined in the rule — a data name, picture clause, usage clause, value clause — and wraps everything into a tree node. Each grammar rule becomes a node in the CST, and the tokens become leaves.

### 2.4. Walking the tree: Visitor and Listener patterns

Once you have a CST, you need to extract information from it. You do this by **walking the tree** — visiting nodes in a structured way.

There are two common patterns for tree walking:

**Visitor pattern**: You write a class with `visit` methods for the node types you care about. The visitor only processes nodes you explicitly handle — everything else is skipped. Each visit method returns a value, so you can build up results (like AST nodes) as you traverse. This is a *pull-based* approach: you choose what to visit and what to return.

**Listener pattern**: The tree walker calls `enter` and `exit` methods on your class for *every* node in the tree. You override the methods for the nodes you care about and ignore the rest. This is a *push-based* approach: you get notified about everything and decide what to act on.

This project uses the **Visitor pattern**. The Visitor is selective — it visits only the grammar nodes that correspond to meaningful COBOL constructs and builds typed AST dataclasses from them. The Listener pattern would also work, but the Visitor's ability to return values makes the CST-to-AST conversion more natural: `visitDataDescriptionEntry` returns a `DataItem`, `visitIdentificationDivision` returns program metadata, and so on.

A concrete example: to extract the program name from a COBOL source file, the Visitor visits the `identificationDivision` node in the CST, navigates to its `programIdParagraph` child, reads the program name token, and returns it as a string. The calling code gets back `"SAFE01"` — no tree navigation required on its end.

### 2.5. What can you do with an AST? (expanded)

The AST is where the real work begins. Once you have a clean, typed representation of a COBOL program, three broad categories of operations become straightforward.

**Analysis** — answering questions about the code. Walk the AST to extract metadata: list every data item and its type, find all `CALL` statements and the programs they invoke, identify which variables are passed as parameters to subprograms. For example, given the data items in `ENDIAN01.cob`, an analyzer could identify that `WS-ORDER-ID` is declared as `COMP` (a binary type affected by endianness) and `WS-ORDER-BYTES` redefines it as individual `PIC X` bytes — flagging this as a potential endianness hazard during a platform migration from big-endian AIX to little-endian Linux. This kind of structural analysis is exactly what motivates this project: the sample files demonstrate real endianness issues that AST-based tooling can detect automatically.

**Transformation** — modifying the code programmatically. Because the AST captures the program's structure, you can make targeted changes. Rename a data item everywhere it appears — the AST knows the declaration, every MOVE that references it, and every DISPLAY that prints it. Convert `COMP` fields to `COMP-5` where appropriate. Restructure a program's PROCEDURE DIVISION. Transformation operates on the tree, then generates modified source code from the result.

**Validation** — enforcing rules and standards. Walk the AST to check coding conventions: do all working-storage items start with `WS-`? Do all linkage-section items start with `LS-`? Are there any `COMP` fields used directly as host variables in `EXEC SQL` statements (a pattern that causes endianness bugs, as shown in `ENDIAN02-CALLED.cob`)? Validation rules are easy to express as AST queries — "find all nodes of type X where condition Y is true."

### 2.6. Why COBOL is special (and challenging) for parsing

COBOL presents several parsing challenges that most modern languages do not.

**Fixed-format layout.** Traditional COBOL uses a rigid column structure inherited from 80-column punch cards:

| Columns | Name | Purpose |
|---|---|---|
| 1-6 | Sequence area | Line numbers (ignored by compiler) |
| 7 | Indicator | `*` = comment, `-` = continuation, `D` = debug, space = code |
| 8-11 | Area A | Division/section/paragraph headers, level numbers |
| 12-72 | Area B | Statements, clauses, data descriptions |
| 73-80 | Identification area | Program ID (ignored by compiler) |

This matters for the lexer because the *meaning* of a character depends on its column position. An `*` in column 7 makes the entire line a comment; the same `*` in column 20 is a multiplication operator. The parser cannot handle this directly — a **preprocessing step** must strip the non-code columns and interpret the indicator column before the lexer ever sees the input. Every sample file in this project (e.g., `SAFE01.cob`, `ENDIAN01.cob`) uses this fixed format.

**Verbose, keyword-heavy syntax.** COBOL was designed to read like English: `ADD 1000 TO WS-AMOUNT`, `MOVE WS-ORDER-ID TO WS-ORA-ORDER-ID`, `CALL "ENDIAN02-CALLED" USING WS-ORDER-ID`. This verbosity means the grammar is large — many keywords, many optional clauses, many ways to express the same construct. The COBOL grammar used in this project is roughly 5,600 lines, compared to a few hundred for a language like JSON.

**Dialect differences.** There is no single "COBOL." IBM COBOL, Micro Focus COBOL, and GnuCOBOL each have extensions and variations. For instance, `COMP-5` (native-endian binary) is a Micro Focus and IBM extension not in the COBOL-85 standard. `EXEC SQL INCLUDE SQLCA5 END-EXEC` is an IBM-specific directive. A parser that handles real-world COBOL must accommodate these dialect differences. The grammar this project uses is IBM COBOL-centric but covers Micro Focus extensions like `COMP-5`.

**Preprocessing concerns.** Beyond fixed-format handling, COBOL has `COPY` statements that include external files (called copybooks) and `REPLACE` directives that perform text substitution before parsing. Comment handling (both full-line `*` comments and inline `*>` comments) must also happen before the parser runs. These preprocessing steps are addressed in this project's implementation — see the [implementation plan](../python/ast-docs/implementation-plan.md) for details.

### 2.7. How this project fits together (expanded)

The project implements an end-to-end pipeline that transforms a COBOL source file into a typed AST:

```
COBOL source (.cob file)
       │
       ▼
┌──────────────────┐
│   Preprocessor   │  Strips columns 1-6 and 73-80, removes comments,
│                  │  joins continuation lines, handles column 7 indicators
└────────┬─────────┘
         │  (normalized free-form text)
         ▼
┌──────────────────┐
│   ANTLR4 Lexer   │  Tokenizes the normalized source into keywords,
│   + Parser       │  identifiers, literals, etc. — then assembles
│                  │  tokens into a Concrete Syntax Tree (CST)
└────────┬─────────┘
         │  (CST)
         ▼
┌──────────────────┐
│     Visitor      │  Walks the CST, visits semantically meaningful
│                  │  nodes, and builds typed AST dataclasses
└────────┬─────────┘
         │  (AST)
         ▼
   Typed AST nodes     Clean data structures representing the COBOL
                       program: divisions, data items, statements
```

- **Preprocessor** — Transforms fixed-format COBOL into free-form text that the parser can consume. Handles the column-position rules described in section 2.6.
- **ANTLR4 Lexer + Parser** — Generated from the Cobol85 grammar (a ~5,600-line grammar file from the `antlr/grammars-v4` repository). Produces a CST that mirrors the grammar's rule structure.
- **Visitor** — A custom class that extends the ANTLR4-generated Visitor base. It selectively walks the CST and constructs typed AST nodes — one dataclass per COBOL concept (program, data item, paragraph, statement).
- **AST dataclasses** — Simple, typed data structures that represent the COBOL program's semantic content. These are what your analysis, transformation, and validation code works with.

The grammar file is language-agnostic — the same `.g4` grammar generates parsers for Python, TypeScript, Go, and Java. Each language implementation writes its own Visitor and AST layer, idiomatic to that language, but shares the grammar and the COBOL sample files.

To explore the implementation details — module structure, dependencies, build steps, and the step-by-step plan for building each component — see the [implementation plan](../python/ast-docs/implementation-plan.md). For the rationale behind choosing ANTLR4 over other parser approaches, see the [parser evaluation](../python/ast-docs/parser-evaluation.md). The sample COBOL files are in the [`samples/`](../samples/) directory.
