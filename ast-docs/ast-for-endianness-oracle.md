# Using AST Analysis to Detect and Remediate Oracle Endianness Issues

## 1. The Problem

When migrating COBOL applications from AIX (big-endian) to Linux x86 (little-endian) with the `BINARY(BE)` compiler option, Oracle embedded SQL becomes a source of **silent data corruption**.

The root cause is a byte-order mismatch between two systems that share raw memory:

- **COBOL compiled with `BINARY(BE)`** stores COMP/BINARY fields in big-endian format, preserving compatibility with AIX, MQ, and inter-module calls.
- **The Oracle client library on Linux x86** is a native C library. It reads and writes memory in little-endian byte order. It has no knowledge of the COBOL compiler's `BINARY(BE)` option.

When the COBOL program passes a COMP field to Oracle as a host variable (via EXEC SQL), Oracle interprets the big-endian bytes as little-endian and reads the wrong value. The same corruption occurs in reverse: Oracle writes little-endian values into COMP fields, and COBOL reads them as big-endian.

For example, a value of 12,345 stored as COMP under `BINARY(BE)` occupies bytes `00 00 30 39`. Oracle reads those bytes as little-endian and gets 959,447,040. No error is raised. The program runs to completion with wrong results.

**COMP-5 is the escape hatch.** COMP-5 fields always use the platform's native byte order, regardless of `BINARY(BE)`. When a host variable is COMP-5, both COBOL and Oracle agree on byte layout.

The corruption affects every numeric exchange with Oracle:

- Host variables sent TO Oracle (WHERE clauses, INSERT values)
- Host variables received FROM Oracle (SELECT INTO)
- SQLCODE, SQLERRD, and all SQLCA diagnostic fields
- Oracle-generated internal variables (cursor descriptors, indicators) — handled by the `COMP5=YES` precompiler option

There are no compiler errors, no runtime exceptions, and no crashes. Tests using symmetric values like 0 pass even when endianness handling is broken. This makes the problem particularly dangerous at scale.

The full set of rules for Oracle compatibility under `BINARY(BE)` is documented in `cobol-docs/COMP5_ORACLE_PROBLEM_EXPLAINED.md`. This document shows how AST-based analysis can automate the detection and remediation of these issues.

**Assumptions.** This document assumes:

- All modules are compiled with `BINARY(BE)` and `FLOAT(BE)`.
- All programs containing EXEC SQL target **Oracle** (not DB2 or another database).
- All Oracle-facing modules are precompiled with Pro\*COBOL using the `COMP5=YES` option, which makes Pro\*COBOL generate all Oracle-internal variables (cursor descriptors, indicator variables, etc.) as COMP-5.

With these in place, the remaining task is to ensure that all *manually declared* host variables and SQLCA/ORACA/SQLDA includes are also correct — and that is what AST analysis automates.

---

## 2. What the AST Gives You

The AST produced by `parse_cobol_file` and `parse_cobol_source` captures the information needed to evaluate every Oracle endianness rule. This section maps each rule to specific AST node fields from `ast_nodes.py`.

### Oracle Endianness Rules and Their AST Mappings

#### Rule 1: SQLCA must be replaced with SQLCA5

SQLCA declares SQLCODE and all numeric diagnostic fields as COMP. Under `BINARY(BE)`, Oracle writes these fields in little-endian, but COBOL reads them as big-endian. SQLCA5 declares all numeric fields as COMP-5, making them native byte order.

**AST mapping:** `ExecSqlNode.sql_text` contains the raw SQL text. An INCLUDE directive appears as `sql_text = "INCLUDE SQLCA"` or `sql_text = "INCLUDE SQLCA5"`. The check is a string match on `sql_text`.

The same rule applies to `ORACA` (replace with `ORACA5`) and `SQLDA` (replace with `SQLDA5`).

#### Rule 2: All numeric host variables in WORKING-STORAGE must be COMP-5

Every numeric variable used as a host variable in EXEC SQL must be COMP-5 so that Oracle and COBOL agree on byte order.

**AST mapping:** This check requires two pieces of information:

1. **Host variable names** — extracted from `ExecSqlNode.sql_text` by scanning for `:VARIABLE-NAME` tokens (a colon followed by a COBOL identifier).
2. **Variable declarations** — looked up in `WorkingStorageSectionNode.items` (and recursively in `DataItemNode.children` for group items). The relevant fields are `DataItemNode.name` and `DataItemNode.usage`.

A host variable is a problem if `DataItemNode.usage` is `UsageType.COMP`. Variables with `UsageType.COMP_5` are correct for Oracle. The check can skip variables that are not affected by endianness: `UsageType.COMP_3` (packed decimal — digit-by-digit encoding, no multi-byte integer), `UsageType.DISPLAY` (zoned decimal — one byte per digit), and alphanumeric fields (`DataItemNode.pic.category == "alphanumeric"`).

#### Rule 3: No LINKAGE SECTION parameter may be used directly as an Oracle host variable

When a module receives a COMP parameter from a caller (both compiled with `BINARY(BE)`), the parameter is big-endian. Using it directly in EXEC SQL passes big-endian bytes to Oracle, which reads them as little-endian.

The correct pattern is to MOVE from the COMP LINKAGE parameter to a COMP-5 WORKING-STORAGE variable before using it in SQL.

**AST mapping:** This requires combining three pieces:

1. **LINKAGE item names** — from `LinkageSectionNode.items`, collecting each `DataItemNode.name`.
2. **Host variable names in SQL** — from `ExecSqlNode.sql_text`, scanning for `:VARIABLE-NAME`.
3. **Cross-reference** — if a host variable name matches a LINKAGE item name, the parameter is used directly in SQL.

#### Rule 4: COMP-5 results from Oracle must be MOVE'd back to COMP LINKAGE parameters before returning

After a SELECT INTO writes a value into a COMP-5 working variable, the result must be MOVE'd to the COMP LINKAGE parameter before GOBACK. This ensures the caller receives the value in the byte order it expects (big-endian under `BINARY(BE)`).

**AST mapping:** This check requires verifying that:

1. For each COMP-5 host variable that receives data from Oracle (appears after `INTO` in `ExecSqlNode.sql_text`), a corresponding `MoveNode` exists where `MoveNode.source` is the COMP-5 variable name and one of `MoveNode.targets` is a LINKAGE item name.
2. The `MoveNode` appears after the `ExecSqlNode` in the paragraph's statement list.

The AST captures statement order within `ParagraphNode.statements`, so this temporal check is possible.

### Summary of AST Fields Used

| AST Node / Field | Role in Oracle Endianness Analysis |
|---|---|
| `ExecSqlNode.sql_text` | Contains INCLUDE directives and host variable references (`:VAR`) |
| `DataItemNode.usage` | Determines if a field is COMP (problem), COMP-5 (correct), or COMP-3/DISPLAY (safe) |
| `DataItemNode.pic.category` | Skips alphanumeric fields (`"alphanumeric"`) which are not affected by endianness |
| `DataItemNode.name` | Cross-references host variables to their declarations |
| `WorkingStorageSectionNode.items` | Where Oracle host variables should be declared |
| `LinkageSectionNode.items` | Parameters from callers — must not be used directly in SQL |
| `MoveNode.source` / `MoveNode.targets` | Verifies COMP-to-COMP-5 conversion pattern |
| `ParagraphNode.statements` | Preserves statement order for verifying MOVE placement |
| `ProcedureDivisionNode.using_items` | Lists which LINKAGE items the program receives |


---

## 3. Concrete Analysis Examples

Each example below uses the sample files under `samples/endianness/` to demonstrate how the AST checks work in practice. The pseudocode algorithms are followed by Python implementations using this project's `parse_cobol_file` API.

### Check 1: Detect SQLCA vs SQLCA5

**Goal:** Find programs that include SQLCA instead of SQLCA5.

**Algorithm:**

```
For each ExecSqlNode in the program:
    If sql_text matches "INCLUDE SQLCA" (but NOT "INCLUDE SQLCA5"):
        → Flag: "Uses SQLCA instead of SQLCA5 — SQLCODE and all
          numeric diagnostic fields will be corrupted under BINARY(BE)."
    Also check for "INCLUDE ORACA" (should be "INCLUDE ORACA5")
    and "INCLUDE SQLDA" (should be "INCLUDE SQLDA5").
```

**What this finds in the sample files:**

- `ENDIAN02-CALLED.cob`: contains `EXEC SQL INCLUDE SQLCA END-EXEC` — the AST produces an `ExecSqlNode` with `sql_text = "INCLUDE SQLCA"`. **Flagged.**
- `SAFE02-CALLED.cob`: contains `EXEC SQL INCLUDE SQLCA5 END-EXEC` — `sql_text = "INCLUDE SQLCA5"`. **OK.**

**Python implementation:**

```python
import re
from cobol_ast import parse_cobol_file, ExecSqlNode


def check_sqlca_include(file_path: str) -> list[str]:
    """Find EXEC SQL INCLUDE statements that use SQLCA instead of SQLCA5.

    Scans all ExecSqlNode entries in the program for INCLUDE directives
    that reference SQLCA, ORACA, or SQLDA without the "5" suffix. These
    copybooks declare numeric fields as COMP, which causes byte-order
    corruption when the Oracle client writes native little-endian values
    into fields that COBOL reads as big-endian under BINARY(BE).

    Args:
        file_path: Path to a COBOL source file.

    Returns:
        List of diagnostic messages, one per problematic INCLUDE.
    """
    program = parse_cobol_file(file_path)
    findings = []

    if not program.procedure:
        return findings

    # Patterns match "INCLUDE SQLCA" but not "INCLUDE SQLCA5"
    # (using a negative lookahead for the "5" suffix).
    include_patterns = [
        (r"\bINCLUDE\s+SQLCA\b(?!5)", "SQLCA", "SQLCA5"),
        (r"\bINCLUDE\s+ORACA\b(?!5)", "ORACA", "ORACA5"),
        (r"\bINCLUDE\s+SQLDA\b(?!5)", "SQLDA", "SQLDA5"),
    ]

    for paragraph in program.procedure.paragraphs:
        for stmt in paragraph.statements:
            if isinstance(stmt, ExecSqlNode):
                for pattern, old_name, new_name in include_patterns:
                    if re.search(pattern, stmt.sql_text, re.IGNORECASE):
                        findings.append(
                            f"Uses {old_name} instead of {new_name} — "
                            f"numeric diagnostic fields will be corrupted "
                            f"under BINARY(BE)."
                        )

    return findings
```

### Check 2: Audit Oracle Host Variables

**Goal:** Find all host variables in EXEC SQL statements and verify each numeric one is COMP-5.

**Algorithm:**

```
Step 1 — Build a name→DataItemNode lookup from WORKING-STORAGE and LINKAGE:
    For all data items (recursively including children):
        item_lookup[item.name] = item

Step 2 — Find all EXEC SQL nodes (excluding INCLUDE directives):
    For each ExecSqlNode where sql_text does NOT contain "INCLUDE":
        Extract host variable names by scanning for :VARIABLE-NAME tokens.
        (Pattern: colon followed by one or more word/hyphen characters.)

Step 3 — Check each host variable:
    For each host variable name:
        Look up the DataItemNode in item_lookup.
        If item.usage is COMP:
            → Flag: "Host variable {name} is COMP — must be COMP-5
              for Oracle under BINARY(BE)."
        If item.usage is COMP_5:
            → OK.
        If item.usage is COMP_3 or DISPLAY:
            → OK (not affected by endianness).
        If item.pic.category is "alphanumeric":
            → OK (not affected by endianness).
```

**What this finds in `ENDIAN02-CALLED.cob`:**

The SELECT statement is:
```sql
SELECT QUANTITY INTO :WS-QUANTITY FROM ORDERS WHERE ORDER_ID = :LS-ORDER-ID
```

Host variables extracted: `WS-QUANTITY`, `LS-ORDER-ID`.

- `WS-QUANTITY`: declared as `PIC S9(9) COMP` in WORKING-STORAGE. `usage = UsageType.COMP`. **Flagged: must be COMP-5.**
- `LS-ORDER-ID`: declared as `PIC S9(9) COMP` in LINKAGE. **Flagged: COMP host variable** (and also flagged by Check 3 as a LINKAGE parameter used directly in SQL).

**What this finds in `SAFE02-CALLED.cob`:**

Host variables: `WS-ORA-QUANTITY`, `WS-ORA-ORDER-ID`.

- `WS-ORA-QUANTITY`: `usage = UsageType.COMP_5`. **OK.**
- `WS-ORA-ORDER-ID`: `usage = UsageType.COMP_5`. **OK.**

**Python implementation:**

```python
import re
from cobol_ast import (
    parse_cobol_file,
    DataItemNode,
    ExecSqlNode,
    UsageType,
)


def _collect_items(items, lookup: dict[str, DataItemNode]) -> None:
    """Recursively collect all data items into a name→node lookup.

    Walks the data item hierarchy (group items contain children) and
    adds every item to the lookup dictionary keyed by its name.
    """
    for item in items:
        lookup[item.name] = item
        if item.children:
            _collect_items(item.children, lookup)


def _extract_host_variables(sql_text: str) -> list[str]:
    """Extract host variable names from EXEC SQL text.

    Oracle host variables appear as :VARIABLE-NAME in the SQL text.
    COBOL identifiers use hyphens, digits, and letters.

    Returns a list of variable names (without the leading colon).
    """
    return re.findall(r":([A-Za-z0-9][\w-]*)", sql_text)


def check_host_variable_usage(file_path: str) -> list[str]:
    """Find Oracle host variables that are COMP instead of COMP-5.

    Parses the COBOL file, extracts host variable references from all
    EXEC SQL statements, looks up each variable's declaration, and
    flags any numeric COMP variable that should be COMP-5.

    Args:
        file_path: Path to a COBOL source file.

    Returns:
        List of diagnostic messages, one per problematic host variable.
    """
    program = parse_cobol_file(file_path)
    findings = []

    if not program.procedure or not program.data:
        return findings

    # Build lookup of all declared data items.
    item_lookup: dict[str, DataItemNode] = {}
    if program.data.working_storage:
        _collect_items(program.data.working_storage.items, item_lookup)
    if program.data.linkage:
        _collect_items(program.data.linkage.items, item_lookup)

    # Walk all EXEC SQL statements.
    for paragraph in program.procedure.paragraphs:
        for stmt in paragraph.statements:
            if not isinstance(stmt, ExecSqlNode):
                continue
            # Skip INCLUDE directives — they don't contain host variables.
            if re.search(r"\bINCLUDE\b", stmt.sql_text, re.IGNORECASE):
                continue

            host_vars = _extract_host_variables(stmt.sql_text)
            for var_name in host_vars:
                item = item_lookup.get(var_name)
                if item is None:
                    findings.append(
                        f"Host variable {var_name} not found in "
                        f"WORKING-STORAGE or LINKAGE declarations."
                    )
                    continue

                # Alphanumeric and COMP-3 fields are endianness-safe.
                if item.pic and item.pic.category == "alphanumeric":
                    continue
                if item.usage == UsageType.COMP_3:
                    continue

                # COMP-5 is correct for Oracle.
                if item.usage == UsageType.COMP_5:
                    continue

                # COMP (or BINARY) is the problem.
                if item.usage == UsageType.COMP:
                    findings.append(
                        f"Host variable {var_name} is COMP — must be "
                        f"COMP-5 for Oracle under BINARY(BE)."
                    )

    return findings
```

### Check 3: Detect LINKAGE Parameters Used Directly as Oracle Host Variables

**Goal:** Find programs where a LINKAGE SECTION parameter appears directly as a host variable in EXEC SQL.

**Algorithm:**

```
Step 1 — Collect all LINKAGE item names:
    linkage_names = set()
    For each item in program.data.linkage.items (recursively):
        linkage_names.add(item.name)

Step 2 — Extract host variables from each EXEC SQL node:
    For each ExecSqlNode (excluding INCLUDE directives):
        host_vars = extract :VARIABLE-NAME tokens from sql_text

Step 3 — Cross-reference:
    For each host variable name:
        If name is in linkage_names:
            → Flag: "LINKAGE parameter {name} used directly as Oracle
              host variable — must MOVE to a COMP-5 WORKING-STORAGE
              variable first."
```

**What this finds in `ENDIAN02-CALLED.cob`:**

- LINKAGE items: `LS-ORDER-ID` (COMP), `LS-QUANTITY` (COMP), `LS-RETURN-CODE` (COMP).
- Host variables in the SELECT: `:LS-ORDER-ID`, `:WS-QUANTITY`.
- `LS-ORDER-ID` is in the LINKAGE set. **Flagged: LINKAGE parameter used directly in SQL.**

The caller (`ENDIAN02-CALLER.cob`) passed ORDER-ID = 12345 as COMP (big-endian bytes `00 00 30 39`). The inter-module CALL is fine — both sides agree on big-endian. But the callee hands those big-endian bytes directly to Oracle, which reads them as little-endian and gets 959,447,040.

**What this finds in `SAFE02-CALLED.cob`:**

- LINKAGE items: `LS-ORDER-ID`, `LS-QUANTITY`, `LS-RETURN-CODE`.
- Host variables: `:WS-ORA-ORDER-ID`, `:WS-ORA-QUANTITY`.
- Neither host variable is in the LINKAGE set. **OK.**

**Python implementation:**

```python
import re
from cobol_ast import parse_cobol_file, DataItemNode, ExecSqlNode


def _collect_names(items, names: set[str]) -> None:
    """Recursively collect data item names into a set."""
    for item in items:
        names.add(item.name)
        if item.children:
            _collect_names(item.children, names)


def check_linkage_in_sql(file_path: str) -> list[str]:
    """Find LINKAGE parameters used directly as Oracle host variables.

    A LINKAGE COMP parameter is big-endian under BINARY(BE). Using it
    directly in EXEC SQL passes big-endian bytes to Oracle, which reads
    them as little-endian. The correct pattern is to MOVE from the COMP
    LINKAGE parameter to a COMP-5 WORKING-STORAGE variable first.

    Args:
        file_path: Path to a COBOL source file.

    Returns:
        List of diagnostic messages, one per LINKAGE item found in SQL.
    """
    program = parse_cobol_file(file_path)
    findings = []

    if not program.procedure or not program.data:
        return findings
    if not program.data.linkage:
        return findings

    # Collect LINKAGE item names.
    linkage_names: set[str] = set()
    _collect_names(program.data.linkage.items, linkage_names)

    # Scan EXEC SQL statements for host variables that are LINKAGE items.
    for paragraph in program.procedure.paragraphs:
        for stmt in paragraph.statements:
            if not isinstance(stmt, ExecSqlNode):
                continue
            if re.search(r"\bINCLUDE\b", stmt.sql_text, re.IGNORECASE):
                continue

            host_vars = re.findall(r":([A-Za-z0-9][\w-]*)", stmt.sql_text)
            for var_name in host_vars:
                if var_name in linkage_names:
                    findings.append(
                        f"LINKAGE parameter {var_name} used directly as "
                        f"Oracle host variable — must MOVE to a COMP-5 "
                        f"WORKING-STORAGE variable first."
                    )

    return findings
```

### Check 4: Verify the COMP-to-COMP-5 MOVE Pattern

**Goal:** For programs that correctly use COMP-5 host variables, verify that the MOVE conversion pattern is complete — both the incoming MOVE (COMP → COMP-5 before SQL) and the outgoing MOVE (COMP-5 → COMP after SQL).

**Algorithm:**

```
Step 1 — Identify COMP-5 host variables that receive data from Oracle:
    For each ExecSqlNode, find variables after the INTO keyword.
    These are "output" host variables — Oracle writes values into them.

Step 2 — Check for outgoing MOVE:
    For each output host variable (COMP-5 in WORKING-STORAGE):
        Search the paragraph's statements (after the ExecSqlNode) for
        a MoveNode where:
            MoveNode.source == host_variable_name
            AND any of MoveNode.targets is a LINKAGE item name
        If no such MOVE exists:
            → Flag: "COMP-5 variable {name} receives data from Oracle
              but is never MOVE'd back to a COMP LINKAGE parameter."

Step 3 — Identify COMP-5 host variables used as input to Oracle:
    For each ExecSqlNode, find variables NOT after INTO — these are
    "input" host variables sent to Oracle (WHERE clause, INSERT values).

Step 4 — Check for incoming MOVE:
    For each input host variable (COMP-5 in WORKING-STORAGE):
        Search the paragraph's statements (before the ExecSqlNode) for
        a MoveNode where:
            any of MoveNode.targets == host_variable_name
            AND MoveNode.source is a LINKAGE item name
        If no such MOVE exists and the program has a LINKAGE SECTION:
            → Warning: "COMP-5 variable {name} is used as Oracle input
              but has no MOVE from a LINKAGE parameter. Verify the value
              source is correct."
```

**What this finds in `SAFE02-CALLED.cob`:**

The program has:
- `MOVE LS-ORDER-ID TO WS-ORA-ORDER-ID` — incoming MOVE, COMP to COMP-5. **OK.**
- `MOVE WS-ORA-QUANTITY TO LS-QUANTITY` — outgoing MOVE, COMP-5 to COMP. **OK.** (This MOVE is inside the `IF SQLCODE = 0` branch. The AST captures it in `IfNode.then_statements`.)

Both conversions are present. The pattern is complete.

**What this finds in `ENDIAN02-CALLED.cob`:**

No COMP-5 host variables exist (because the program uses COMP incorrectly), so this check produces no results. The problems in this file are caught by Checks 2 and 3 instead.

**Python implementation:**

```python
import re
from cobol_ast import (
    parse_cobol_file,
    DataItemNode,
    ExecSqlNode,
    IfNode,
    MoveNode,
    UsageType,
)


def _collect_items_lookup(items, lookup: dict[str, DataItemNode]) -> None:
    """Recursively build a name→DataItemNode dictionary."""
    for item in items:
        lookup[item.name] = item
        if item.children:
            _collect_items_lookup(item.children, lookup)


def _collect_moves(statements, moves: list[MoveNode]) -> None:
    """Recursively collect all MoveNode instances from a statement list.

    Walks into IfNode branches to find MOVEs inside conditionals, since
    the COMP-5 to COMP conversion often happens inside IF SQLCODE = 0.
    """
    for stmt in statements:
        if isinstance(stmt, MoveNode):
            moves.append(stmt)
        elif isinstance(stmt, IfNode):
            _collect_moves(stmt.then_statements, moves)
            _collect_moves(stmt.else_statements, moves)


def _extract_into_variables(sql_text: str) -> list[str]:
    """Extract host variable names that appear after INTO in SQL text.

    These are "output" variables — Oracle writes values into them.
    Pattern: INTO :VAR1, :VAR2, ...
    """
    # Find the INTO clause and extract variables from it.
    into_match = re.search(
        r"\bINTO\s+(:[A-Za-z0-9][\w-]*(?:\s*,\s*:[A-Za-z0-9][\w-]*)*)",
        sql_text,
        re.IGNORECASE,
    )
    if not into_match:
        return []
    into_clause = into_match.group(1)
    return re.findall(r":([A-Za-z0-9][\w-]*)", into_clause)


def _extract_non_into_variables(sql_text: str) -> list[str]:
    """Extract host variable names that appear outside INTO in SQL text.

    These are "input" variables — values sent to Oracle (WHERE, INSERT).
    """
    all_vars = re.findall(r":([A-Za-z0-9][\w-]*)", sql_text)
    into_vars = set(_extract_into_variables(sql_text))
    return [v for v in all_vars if v not in into_vars]


def check_move_pattern(file_path: str) -> list[str]:
    """Verify the COMP-to-COMP-5 MOVE conversion pattern.

    For Oracle-facing programs that correctly use COMP-5 host variables,
    checks that:
    - Input host variables have an incoming MOVE from a LINKAGE parameter
    - Output host variables have an outgoing MOVE to a LINKAGE parameter

    The MOVE between COMP and COMP-5 triggers the compiler's automatic
    byte-order conversion. Without it, values are either never converted
    (if COMP is used directly) or lost (if COMP-5 results aren't sent
    back to the caller).

    Args:
        file_path: Path to a COBOL source file.

    Returns:
        List of diagnostic messages for missing MOVE conversions.
    """
    program = parse_cobol_file(file_path)
    findings = []

    if not program.procedure or not program.data:
        return findings
    if not program.data.linkage:
        return findings

    # Build lookups.
    ws_lookup: dict[str, DataItemNode] = {}
    if program.data.working_storage:
        _collect_items_lookup(
            program.data.working_storage.items, ws_lookup
        )

    linkage_names: set[str] = set()
    linkage_items = program.data.linkage.items
    for item in linkage_items:
        linkage_names.add(item.name)

    # Collect all MOVEs in the program.
    all_moves: list[MoveNode] = []
    for paragraph in program.procedure.paragraphs:
        _collect_moves(paragraph.statements, all_moves)

    # Check each EXEC SQL statement.
    for paragraph in program.procedure.paragraphs:
        for stmt in paragraph.statements:
            if not isinstance(stmt, ExecSqlNode):
                continue
            if re.search(r"\bINCLUDE\b", stmt.sql_text, re.IGNORECASE):
                continue

            # Check output variables (after INTO).
            output_vars = _extract_into_variables(stmt.sql_text)
            for var_name in output_vars:
                item = ws_lookup.get(var_name)
                if not item or item.usage != UsageType.COMP_5:
                    continue
                # Look for a MOVE from this COMP-5 var to a LINKAGE item.
                has_outgoing = any(
                    m.source == var_name
                    and any(t in linkage_names for t in m.targets)
                    for m in all_moves
                )
                if not has_outgoing:
                    findings.append(
                        f"COMP-5 variable {var_name} receives data from "
                        f"Oracle but is never MOVE'd back to a COMP "
                        f"LINKAGE parameter."
                    )

            # Check input variables (outside INTO).
            input_vars = _extract_non_into_variables(stmt.sql_text)
            for var_name in input_vars:
                item = ws_lookup.get(var_name)
                if not item or item.usage != UsageType.COMP_5:
                    continue
                # Look for a MOVE from a LINKAGE item to this COMP-5 var.
                has_incoming = any(
                    m.source in linkage_names and var_name in m.targets
                    for m in all_moves
                )
                if not has_incoming:
                    findings.append(
                        f"COMP-5 variable {var_name} is used as Oracle "
                        f"input but has no MOVE from a LINKAGE parameter. "
                        f"Verify the value source is correct."
                    )

    return findings
```

### Running All Checks Together

The four checks above can be combined into a single audit function. Here is how the results look for the buggy and correct sample files:

**`ENDIAN02-CALLED.cob`** (buggy):

1. Check 1 (SQLCA): "Uses SQLCA instead of SQLCA5 — numeric diagnostic fields will be corrupted under BINARY(BE)."
2. Check 2 (host variables): "Host variable WS-QUANTITY is COMP — must be COMP-5 for Oracle under BINARY(BE)." and "Host variable LS-ORDER-ID is COMP — must be COMP-5 for Oracle under BINARY(BE)."
3. Check 3 (LINKAGE in SQL): "LINKAGE parameter LS-ORDER-ID used directly as Oracle host variable — must MOVE to a COMP-5 WORKING-STORAGE variable first."
4. Check 4 (MOVE pattern): No COMP-5 variables to check (all are incorrectly COMP).

**`SAFE02-CALLED.cob`** (correct):

1. Check 1 (SQLCA): No findings — uses SQLCA5.
2. Check 2 (host variables): No findings — both host variables are COMP-5.
3. Check 3 (LINKAGE in SQL): No findings — no LINKAGE items used in SQL.
4. Check 4 (MOVE pattern): No findings — both incoming and outgoing MOVEs are present.

---

## 4. What the AST Cannot Tell You (and What Else You Need)

### Things the AST cannot determine

**Cross-module data flow.** When the caller is in a different source file, the AST of the called program cannot trace where the LINKAGE parameter's value originated. The analysis can detect that a LINKAGE parameter is used directly in SQL (Check 3), but it cannot determine whether the caller populated that parameter from MQ, from a file, or from its own computation. **Alternative:** build a call graph across all programs and trace data flow. This requires parsing all programs in the application and linking `CallNode.using_items` to `ProcedureDivisionNode.using_items` in the called program.

**Dynamic SQL.** The AST captures `ExecSqlNode.sql_text` for static embedded SQL. If a program builds SQL strings dynamically (using string concatenation in WORKING-STORAGE and `EXEC SQL EXECUTE IMMEDIATE`), the host variable references are not visible in the static SQL text. **Alternative:** for dynamic SQL, trace the variables used to build the SQL string and apply the same checks to those variables.

### What a complete solution needs

| Layer | What it provides | How to implement |
|---|---|---|
| **AST analysis** (this document) | Detects SQLCA/SQLCA5, COMP vs COMP-5 host variables, LINKAGE-in-SQL, missing MOVEs | Parse each file, run the four checks |
| **Call graph** | Cross-module data flow, tracing parameters to external boundaries | Parse all programs, link CALLs to targets |

The AST provides the foundation — the structured, queryable representation of each program. The other layers provide context that the source code alone does not contain.

---

## 5. From Detection to Transformation

AST analysis is not limited to finding problems — it can also drive automated code transformations. For the Oracle endianness migration, three transformations cover the required changes.

### Transformation 1: Change COMP to COMP-5 on Oracle host variables

When Check 2 identifies a WORKING-STORAGE host variable declared as COMP, the transformation changes its USAGE to COMP-5.

**Before:**
```cobol
       01  WS-QUANTITY         PIC S9(9) COMP.
```

**After:**
```cobol
       01  WS-QUANTITY         PIC S9(9) COMP-5.
```

### Transformation 2: Insert MOVE statements for LINKAGE-to-SQL conversion

When Check 3 detects a LINKAGE parameter used directly in SQL, the transformation:

1. Adds a new COMP-5 item to WORKING-STORAGE (e.g., `WS-ORA-ORDER-ID`).
2. Inserts `MOVE LS-ORDER-ID TO WS-ORA-ORDER-ID` before the EXEC SQL block.
3. Replaces `:LS-ORDER-ID` with `:WS-ORA-ORDER-ID` in the SQL text.
4. If the variable receives data from Oracle (appears after INTO), inserts a reverse MOVE after the SQL block to copy the result back to the LINKAGE parameter.

**Before (`ENDIAN02-CALLED.cob` pattern):**
```cobol
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       01  WS-QUANTITY         PIC S9(9) COMP.

       LINKAGE SECTION.
       01  LS-ORDER-ID         PIC S9(9) COMP.
       01  LS-QUANTITY         PIC S9(9) COMP.

       PROCEDURE DIVISION USING LS-ORDER-ID LS-QUANTITY.
       MAIN-PARA.
           EXEC SQL
               SELECT QUANTITY INTO :WS-QUANTITY
               FROM ORDERS WHERE ORDER_ID = :LS-ORDER-ID
           END-EXEC
           IF SQLCODE = 0
               MOVE WS-QUANTITY TO LS-QUANTITY
           END-IF
```

**After (`SAFE02-CALLED.cob` pattern):**
```cobol
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA5 END-EXEC.
       01  WS-ORA-ORDER-ID    PIC S9(9) COMP-5.
       01  WS-ORA-QUANTITY    PIC S9(9) COMP-5.

       LINKAGE SECTION.
       01  LS-ORDER-ID         PIC S9(9) COMP.
       01  LS-QUANTITY         PIC S9(9) COMP.

       PROCEDURE DIVISION USING LS-ORDER-ID LS-QUANTITY.
       MAIN-PARA.
           MOVE LS-ORDER-ID TO WS-ORA-ORDER-ID.
           EXEC SQL
               SELECT QUANTITY INTO :WS-ORA-QUANTITY
               FROM ORDERS WHERE ORDER_ID = :WS-ORA-ORDER-ID
           END-EXEC
           IF SQLCODE = 0
               MOVE WS-ORA-QUANTITY TO LS-QUANTITY
           END-IF
```

### Transformation 3: Replace SQLCA with SQLCA5

When Check 1 finds `EXEC SQL INCLUDE SQLCA END-EXEC`, replace the SQL text with `INCLUDE SQLCA5`. The same applies to ORACA → ORACA5 and SQLDA → SQLDA5.

### Implementing transformations: the parse-analyze-transform-emit pipeline

A transformation pipeline works in four stages:

```
Parse → Analyze → Build modified AST → Emit COBOL source
```

1. **Parse** the original source into an AST using `parse_cobol_file` (already implemented).
2. **Analyze** the AST using the checks from Section 3 to identify what needs to change.
3. **Build a modified AST** — construct new node instances with corrected field values. Since the AST nodes are frozen dataclasses (`@dataclass(frozen=True)`), this means creating new copies with changed fields (using `dataclasses.replace()`), not mutating existing ones.
4. **Emit COBOL source** — generate syntactically valid COBOL text from the modified AST.

### The challenge of source emission (unparsing)

Step 4 is the hardest. COBOL uses a fixed-format layout with strict column rules:

| Columns | Name | Content |
|---|---|---|
| 1-6 | Sequence number area | Line numbers (often blank) |
| 7 | Indicator area | `*` for comments, `-` for continuation, space for code |
| 8-11 | Area A | Division/section/paragraph headers, level 01/77 items |
| 12-72 | Area B | Statements, level 02-49 items, continuation text |
| 73-80 | Identification area | Ignored by compiler (often blank) |

Generating COBOL from scratch while preserving this layout — plus existing comments, spacing, and continuation lines — is nontrivial.

**Two approaches to source emission:**

**Approach A — Full regeneration from AST.** Build a COBOL code generator that takes an AST and produces correctly formatted fixed-format source. This requires the AST to carry enough information to regenerate every detail (indentation, comments, continuation lines). The current AST does not preserve comments or original formatting, so this approach would produce correct but differently-formatted output. This may be acceptable for automated migration but can make code review harder.

How to implement:
- Write an emitter that walks the AST top-down (ProgramNode → divisions → sections → items/statements).
- For each node type, emit the corresponding COBOL syntax with correct column positioning.
- Data items: pad to column 8 for level 01/77, column 12 for subordinate levels. Emit level number, name, PIC clause, USAGE clause, VALUE clause, and period.
- Statements: emit in Area B (column 12+). Handle multi-line statements (EXEC SQL blocks, IF/ELSE/END-IF) with continuation.
- Enforce the 72-column limit: split long lines at word boundaries and use continuation in column 7.

**Approach B — Surgical text edits guided by AST analysis (recommended).** Use the AST to determine *what* to change, then apply targeted text replacements to the original source. This preserves all existing formatting, comments, and layout.

How to implement:
- Parse the source to get the AST and the list of findings.
- For each finding, compute the text edit:
  - SQLCA → SQLCA5: find the string `SQLCA` in the EXEC SQL INCLUDE line and replace with `SQLCA5`.
  - COMP → COMP-5: find the data item's declaration line (by matching the item name and `COMP` keyword) and replace `COMP` with `COMP-5`.
  - Insert MOVE: locate the EXEC SQL line, insert a new line before it with the MOVE statement formatted in Area B (columns 12-72).
  - Insert new data items: locate the last item in WORKING-STORAGE and insert a new line after it with the declaration formatted in Area A/B.
- Apply all edits to the original source text, adjusting line positions as insertions shift subsequent lines.

This approach requires tracking source positions (line numbers) for each AST node. The current AST stores source positions for each node.

**Approach B is recommended** for production use because it preserves the existing code style, comments, and formatting. Developers reviewing the changes see minimal diffs — only the specific lines that were modified or inserted. This makes the migration auditable and reduces review effort.
