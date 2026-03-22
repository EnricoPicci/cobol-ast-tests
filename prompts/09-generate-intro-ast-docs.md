# Role

You are a senior technical writer with deep expertise in:
- **Compiler and parser technology**: Lexing, parsing, concrete syntax trees (CST), abstract syntax trees (AST), visitor/listener patterns, and tree transformations.
- **COBOL**: Program structure, fixed-format layout, divisions, data description, and the challenges COBOL presents to modern tooling.
- **Developer education**: Writing documentation that builds understanding progressively — from high-level concepts to concrete, working examples.

# Context

This project creates **educational examples** of using AST parsers to analyze and transform COBOL source code. Before writing anything, read these files to understand the project's conventions and current state:

1. **Root `CLAUDE.md`** — Project-wide guidelines and the educational-first philosophy.
2. **`python/CLAUDE.md`** — Python-specific conventions (the first language implementation).
3. **`python/ast-docs/parser-evaluation.md`** — The evaluation of parser approaches. It explains what options exist and why ANTLR4 was chosen.
4. **`python/ast-docs/implementation-plan.md`** — The implementation plan for the Python parser. It describes the end-to-end pipeline: COBOL source → preprocessing → ANTLR4 parsing → CST → Visitor → typed AST.
5. **Every `.cob` file under `samples/`** — Real COBOL source files that the parser handles. Use these as concrete examples in the documentation.

The project targets developers who:
- Know at least one modern programming language (Python, TypeScript, Java, Go) but may never have worked with parsers or COBOL.
- Want to understand *what* AST parsers are, *why* they are useful, and *how* they work — before diving into the implementation code.
- Need enough conceptual grounding to read the project's code and tests and understand what they are doing and why.

# Task

Write an introductory document that explains AST parsers to someone encountering them for the first time, using COBOL as the running example throughout. The document should bridge the gap between "I've never heard of AST parsers" and "I understand the code in this project."

## Document Structure

The document must have **two distinct parts** that serve different readers and reading modes:

### Part 1 — "AST Parsing in 5 Minutes" (the quick overview)

This is the "for dummies" section. A reader who stops here should walk away with a solid mental model of what AST parsers are and why this project exists. Write it so it works as a standalone piece.

Cover these concepts **briefly and visually** — favor diagrams, short examples, and plain language over technical depth:

1. **The problem** — Source code is text. To analyze or transform it programmatically, you need structure. One sentence on why regex isn't enough.

2. **The solution in one picture** — Show the end-to-end pipeline as a simple flow:
   ```
   COBOL source → Lexer → Tokens → Parser → Tree → Your analysis code
   ```
   One sentence per box explaining what it does. Use a small COBOL snippet (from `samples/`) as the running input.

3. **What's a syntax tree?** — Take that same snippet and show its tree representation (indented text). Keep it to one tree — don't distinguish CST/AST yet. Just show: "text becomes a tree, and trees are easy to walk programmatically."

4. **You already use AST parsers every day** — A short note (2-3 sentences) pointing out that AST parsers are the engine behind IDE features the reader uses without thinking about: "Rename Symbol" in VS Code or IntelliJ works by parsing the code into an AST, finding every node that references that symbol, and rewriting them. Same for "Go to Definition", syntax highlighting beyond keywords, and real-time error squiggles. The reader already trusts AST parsers — this project just makes the mechanism visible.

5. **What can you do with it?** — Three bullet points, each one sentence with a concrete COBOL example:
   - Analyze (e.g., list all data items and their types)
   - Transform (e.g., rename variables across a program)
   - Validate (e.g., check naming conventions)

6. **Why COBOL is interesting** — Two or three sentences on what makes COBOL different from languages the reader already knows (fixed-format layout, English-like verbosity, dialect variations). Don't go deep — just enough to set expectations.

7. **How this project works** — One paragraph: "This project uses ANTLR4 with a COBOL grammar to parse source files into a tree, then walks the tree with a Visitor to build a clean, typed AST. Read on for the details, or jump to the implementation plan."

**Tone**: Conversational, zero jargon without definition, heavy use of "you" and "we". A developer should be able to read this in 5 minutes and explain AST parsers to a colleague.

**Length**: 400-700 words maximum.

---

### Part 2 — "How It Actually Works" (the detailed explanation)

This is for the reader who wants to understand the mechanics before reading the code. It builds on Part 1 — it can reference concepts introduced there without re-explaining them.

Cover these topics in order, each building on the previous:

#### 2.1. Parsing: from text to structure
- Contrast regex/string-matching with grammar-based parsing. Show why regex breaks down for nested or context-dependent constructs.
- Use a COBOL snippet (from `samples/`) to illustrate: "Here's what a human sees, here's what a parser produces."

#### 2.2. Concrete Syntax Tree (CST) vs Abstract Syntax Tree (AST)
- Define CST — the full, lossless parse tree that mirrors the grammar. Every token, every whitespace rule, every period.
- Define AST — a simplified, semantically meaningful tree. Drops syntactic noise, keeps what matters for analysis.
- Show a side-by-side example: a small COBOL construct (e.g., a data item definition with PIC and USAGE clauses) as CST and as AST. Use indented-text trees that make the difference obvious.
- Explain why this project converts CST → AST: the grammar gives us a CST, but our analysis code works with the cleaner AST.

#### 2.3. How grammar-based parsing works
- The pipeline: source text → lexer (tokens) → parser (tree) → visitor/listener (AST).
- What a grammar is — a set of rules that describe the structure of valid programs. Show a tiny grammar fragment (a simplified version of a COBOL rule) and explain how it maps to the source code.
- What the lexer does (tokenization) — with a COBOL-specific example showing how fixed-format columns, keywords, and literals become tokens.
- What the parser does (tree construction) — how tokens are assembled into a tree according to the grammar rules.

#### 2.4. Walking the tree: Visitor and Listener patterns
- Once you have a CST, how do you extract information? Walk the tree.
- Visitor pattern: you choose which nodes to visit and what to return. Pull-based, selective.
- Listener pattern: you get notified for every node enter/exit. Push-based, exhaustive.
- Explain which pattern this project uses and why (refer to the implementation plan).
- A concrete example: "To extract the PROGRAM-ID from a COBOL program, the visitor visits the identificationDivision node, finds the programIdParagraph child, and returns the program name."

#### 2.5. What can you do with an AST? (expanded)
- Expand on the three bullet points from Part 1 with more detail and examples:
  - **Analysis**: Extract program metadata, find all CALL statements, list data items and their types, detect patterns.
  - **Transformation**: Rename variables, restructure code, convert between dialects.
  - **Validation**: Check coding standards, find potential bugs, enforce naming conventions.
- For each category, give a concrete COBOL example that connects to a real use case (e.g., analyzing data items to understand endianness differences during a platform migration).

#### 2.6. Why COBOL is special (and challenging) for parsing
- Fixed-format layout: columns 1-6 (sequence), column 7 (indicator), columns 8-72 (code), columns 73-80 (identification). Why this matters for the lexer.
- COBOL's verbose, English-like syntax and keyword-heavy grammar. How this affects grammar size and ambiguity.
- Dialect differences (Micro Focus vs IBM) and why the parser needs to handle both.
- Preprocessing concerns: COPY statements (copybook inclusion), REPLACE, comment handling.
- Briefly mention that these challenges are addressed in the implementation — link the reader to the implementation plan for details.

#### 2.7. How this project fits together (expanded)
- The end-to-end pipeline: source file → preprocessor → ANTLR4 parser → CST → Visitor → typed AST dataclasses.
- One sentence on each component explaining its role and where to find it in the codebase.
- Point the reader to the next steps: the implementation plan, the code in `python/src/`, and the tests in `python/tests/`.

**Tone**: Still accessible, but more technical. Jargon is allowed after it has been defined. Detailed examples and visual trees.

**Length**: 1200-2000 words.

## Writing Guidelines

- **Use concrete examples throughout.** Every concept should be illustrated with a COBOL snippet from the `samples/` directory. Do not explain concepts abstractly when a 5-line code example would make them clear.
- **Build concepts incrementally.** Each section should use only concepts introduced in previous sections. Do not forward-reference.
- **Keep it accessible.** Assume the reader knows programming but not parsing theory or COBOL. Define jargon the first time you use it.
- **Show, don't just tell.** When explaining CST vs AST, show both trees. When explaining tokenization, show the token stream. When explaining visitors, show the traversal.
- **Be honest about complexity.** Don't oversimplify to the point of inaccuracy. If something is genuinely complex (like COBOL's fixed-format handling), say so and explain why.
- **Keep the educational tone.** This is a learning resource, not a reference manual. Use "we" and direct address ("you") to keep the reader engaged.

## Output

Write the document to `docs/intro-to-ast-parsers.md`.

The document should be self-contained — a reader should be able to read it without any prior knowledge of parsers or COBOL and come away understanding both the concepts and how this project applies them.

Target length: **Part 1** — 400-700 words. **Part 2** — 1200-2000 words. Part 1 must work as a standalone read. Part 2 expands without repeating.

# Constraints

- All COBOL examples must come from the actual files in `samples/` — do not invent COBOL code. Quote the file name when using a snippet.
- Do not duplicate content from `parser-evaluation.md` or `implementation-plan.md` — reference them and point the reader there for details.
- Do not include any implementation code (Python, Java, etc.) — this document is language-agnostic. The concepts apply regardless of which language implementation the reader explores.
- Use Markdown formatting: headers, code blocks (with `cobol` language tag for COBOL snippets), and simple indented-text trees for AST visualizations. Avoid complex diagrams that cannot be rendered in plain Markdown.

# Review

After writing the document, critically review it by asking:

1. **Part 1 standalone test**: Could a developer read *only* Part 1 and explain AST parsers to a colleague? If not, Part 1 is missing something.
2. **No repetition test**: Does Part 2 expand on Part 1 without repeating the same explanations? It may reference Part 1 concepts, but should not restate them.
3. Could a developer with no parsing background read the full document start-to-finish and understand what the project does and why?
4. Does every section include at least one concrete example (not just abstract explanation)?
5. Are the CST/AST visual examples clear enough to show the difference without further explanation?
6. Does the document flow logically — does each section build on the previous one without forward-references?
7. Are all COBOL snippets taken from actual sample files (not invented)?
8. Does the "How this project fits together" section accurately reflect the current architecture in the implementation plan?
9. Is the document language-agnostic — does it avoid assuming the reader will use Python?

Fix any gaps found during review.
