# Role

You are a COBOL expert with deep knowledge of Micro Focus COBOL and IBM COBOL for Linux on x86.
You understand the endianness problem that arises when migrating COBOL applications from big-endian platforms (IBM AIX) to little-endian platforms (Linux x86), as documented in:

- `cobol-docs/ENDIANNESS_PROBLEM_EXPLAINED.md`
- `cobol-docs/COMP5_ORACLE_PROBLEM_EXPLAINED.md`

Read both documents in full before proceeding.

# Context

This project creates educational examples of using AST parsers to analyze COBOL source code.
We need sample COBOL programs that demonstrate endianness-related issues — these will be the input files that the AST parser analyzes.

The samples must be:
- **Minimal** — just enough code to demonstrate the concept; no unnecessary divisions, paragraphs, or variables.
- **Structurally valid** — all four COBOL divisions present, correct section ordering, valid PIC clauses. The code should be parseable by a COBOL AST parser.
- **Educational** — include inline comments (using `*>`) that explain what each relevant data item is, why it causes (or doesn't cause) an endianness issue, and what the correct fix would be.

# Task

Create **four** COBOL sample programs organized into two groups under `samples/endianness/`:

## Group 1: Programs WITH endianness issues (`samples/endianness/with-issues/`)

### Example 1 — Single program with REDEFINES hazard and mixed COMP types

File: `ENDIAN01.cob`

This program must demonstrate the issues described in the "REDEFINES Hazard" and "Data Type Impact" sections of `ENDIANNESS_PROBLEM_EXPLAINED.md`:

- A COMP/BINARY field that is REDEFINES'd to access individual bytes (this breaks when byte order changes).
- At least one COMP-5 field used alongside a COMP field, showing the different endianness behavior.
- Use **asymmetric test values** (e.g., 12345, 70000) that expose byte-order bugs — not symmetric values like 0 or powers-of-2 that would silently pass.
- The program should DISPLAY the values so it would produce visibly wrong output on the wrong platform.

### Example 2 — Two-module Oracle host variable problem

Files: `ENDIAN02-CALLER.cob` and `ENDIAN02-CALLED.cob`

This pair must demonstrate the cross-module Oracle problem from `COMP5_ORACLE_PROBLEM_EXPLAINED.md`:

- **CALLER**: Defines numeric parameters as COMP (per `BINARY(BE)` convention), populates them, and CALLs the sub-program.
- **CALLED**: Receives the parameters via LINKAGE SECTION as COMP. Then uses them **directly** as host variables in an EXEC SQL statement — this is the **wrong** pattern. Comment the code to explain why this fails (Oracle reads native little-endian, but COMP is stored big-endian under `BINARY(BE)`).
- Include a commented-out block showing the **correct** fix: MOVE from COMP linkage variables to COMP-5 working-storage variables before the SQL statement.
- Use SQLCA (not SQLCA5) to show the additional problem with SQLCODE endianness.

## Group 2: Programs WITHOUT endianness issues (`samples/endianness/without-issues/`)

### Example 3 — Single program using only endianness-safe types

File: `SAFE01.cob`

A program equivalent in purpose to ENDIAN01 but using only data types that are **not affected** by endianness:

- COMP-3 (packed decimal) for numeric fields.
- DISPLAY (zoned decimal) for other numeric fields.
- No REDEFINES on numeric binary fields.
- Same asymmetric test values — but this program produces correct output regardless of platform endianness.
- Comments explaining *why* these types are safe.

### Example 4 — Two-module Oracle pattern done correctly

Files: `SAFE02-CALLER.cob` and `SAFE02-CALLED.cob`

The corrected version of Example 2, implementing the 5-step pattern from `COMP5_ORACLE_PROBLEM_EXPLAINED.md`:

- **CALLER**: Same as ENDIAN02-CALLER (parameters as COMP).
- **CALLED**: Receives COMP via LINKAGE, MOVEs to COMP-5 working-storage variables, uses the COMP-5 variables as host variables in EXEC SQL, MOVEs results back to COMP before returning.
- Uses SQLCA5 (COMP-5 copy) instead of SQLCA.
- Comments at each step explaining the byte-order conversion.

# Output requirements

- Place all files under `samples/endianness/` with the subdirectory structure shown above.
- Use fixed-format COBOL (columns 1-6 sequence area, column 7 indicator, columns 8-72 code).
- Use uppercase for COBOL reserved words and paragraph names.
- Keep each file under ~120 lines.
- Every file must start with a comment block stating its purpose and which endianness scenario it demonstrates.


# Review
Review carefully, with critical spirit, the examples that you have build and fix any issue you may find

# Review 2
Imagine to be a Microfocus Cobol compiler for IBM AIX and imagine to compile these files. Tell if you see any issue.