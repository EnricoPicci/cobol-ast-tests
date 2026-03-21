# The COMP-5 Oracle Problem: Why Oracle Host Variables Must Be COMP-5 on IBM COBOL for Linux with BINARY(BE)

## 1. Summary

When porting COBOL programs from Micro Focus on AIX to IBM COBOL for Linux x86, and compiling with `BINARY(BE)` (the recommended strategy for gradual migration), all numeric host variables used in Oracle embedded SQL must be declared as `COMP-5` — not `COMP` or `BINARY`. Failure to do so causes **silent data corruption** with no runtime error.

This document explains the problem, shows exactly what goes wrong, and covers the particularly tricky case where Oracle host variables receive their values from parameters passed by other modules.

---

## 2. The Root Cause

The problem arises from a fundamental mismatch between two systems that each have their own expectations about byte order:

| System | Expects | Why |
|--------|---------|-----|
| **COBOL program compiled with `BINARY(BE)`** | Big-endian COMP/BINARY fields | `BINARY(BE)` forces COMP/BINARY to store data in big-endian format, matching AIX and MQ expectations |
| **Oracle client library on Linux x86** | Native little-endian data | The Oracle client is a C library compiled for x86. It reads and writes memory in the platform's native little-endian byte order. It has no knowledge of the COBOL compiler's `BINARY(BE)` option. |

When the COBOL program passes a COMP field to Oracle (via embedded SQL), the Oracle client reads the raw bytes at that memory address. It interprets them as little-endian. If those bytes were stored in big-endian order by the COBOL program, Oracle reads the wrong value.

The same corruption occurs in reverse: when Oracle writes a value into a COMP field (e.g., a SELECT INTO), it writes little-endian bytes. The COBOL program then reads those bytes as big-endian and gets the wrong value.

**COMP-5 is the escape hatch.** COMP-5 fields are always stored in the platform's native byte order, regardless of the `BINARY(BE)` compiler option. When a host variable is declared as COMP-5, both the COBOL program and the Oracle client agree on the byte layout.

---

## 3. The Problem in Detail

### 3.1 The Original Code (AIX / Micro Focus — Works Correctly)

```cobol
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA END-EXEC.
       01  WS-ORDER-ID      PIC S9(9) COMP.
       01  WS-QUANTITY       PIC S9(9) COMP.
       01  WS-STATUS         PIC X(10).

       PROCEDURE DIVISION.
           MOVE 12345 TO WS-ORDER-ID.
           EXEC SQL
               SELECT QUANTITY, STATUS
               INTO :WS-QUANTITY, :WS-STATUS
               FROM ORDERS
               WHERE ORDER_ID = :WS-ORDER-ID
           END-EXEC.
           IF SQLCODE = 0
               DISPLAY "Quantity: " WS-QUANTITY
           END-IF.
```

On AIX, COMP is native big-endian. The Oracle client on AIX is also big-endian. Everything matches:

- `WS-ORDER-ID` = 12345 is stored as `00 00 30 39` (big-endian)
- Oracle client reads `00 00 30 39` as big-endian → 12345 → correct
- Oracle returns SQLCODE = 0, stored as `00 00 00 00` → COBOL reads 0 → correct

### 3.2 What Goes Wrong on Linux with BINARY(BE)

You compile the same code with `BINARY(BE)` on IBM COBOL for Linux x86. The program runs without errors but produces wrong results:

**Step 1 — Sending data to Oracle (WHERE clause):**

- `WS-ORDER-ID` = 12345 is stored as `00 00 30 39` (big-endian, because of `BINARY(BE)`)
- The Oracle client library receives the memory address of `WS-ORDER-ID`
- Oracle reads those bytes as **little-endian** (because it's a native x86 library): `00 00 30 39` → **959,447,040** (0x39300000)
- Oracle searches for ORDER_ID = 959,447,040 — **wrong order**

**Step 2 — Receiving data from Oracle (SQLCODE):**

- Oracle doesn't find order 959,447,040, so it sets SQLCODE = 100 (not found)
- SQLCODE is declared in `SQLCA.cob` as `PIC S9(9) COMP`
- Oracle writes 100 as little-endian bytes: `64 00 00 00`
- The COBOL program reads those bytes as big-endian (because of `BINARY(BE)`): `64 00 00 00` → **1,677,721,600**
- The test `IF SQLCODE = 0` fails, but SQLCODE is not 100 either — it's 1,677,721,600

**Step 3 — The cascade:**

Every numeric field exchanged with Oracle is corrupted in the same way:
- Host variables passed TO Oracle (WHERE clauses, INSERT values) → Oracle gets wrong values
- Host variables received FROM Oracle (SELECT INTO) → COBOL gets wrong values
- SQLCODE, SQLERRD, and all SQLCA diagnostic fields → all wrong
- No runtime error is raised — the program runs to completion with silently wrong results

### 3.3 Why This Is Particularly Dangerous

- **No compiler error** — the code compiles cleanly
- **No runtime error** — SQL executes, data flows, the program terminates normally
- **No obvious symptoms** — unless you compare output against expected results, you may never notice
- **Intermittent appearance** — values that happen to be symmetric in byte order (e.g., 0, or values where all 4 bytes are the same) will appear to work correctly, making testing unreliable unless you use values that are clearly asymmetric

---

## 4. The Fix

### 4.1 Use SQLCA5 Instead of SQLCA

Oracle provides `SQLCA5.cob` (or generates it when `COMP5=YES` is set) where all numeric fields use COMP-5 instead of COMP:

```cobol
      * Replace this:
           EXEC SQL INCLUDE SQLCA END-EXEC.
      * With this:
           EXEC SQL INCLUDE SQLCA5 END-EXEC.
```

Similarly, replace `ORACA` with `ORACA5` and `SQLDA` with `SQLDA5` if used.

### 4.2 Set COMP5=YES in Pro*COBOL Precompilation

```sh
procob MODE=ANSI FORMAT=IBM COMP5=YES INAME=ordproc.pco ONAME=ordproc.cbl
```

This makes Pro*COBOL generate all Oracle-internal variables (cursor descriptors, indicator variables, etc.) as COMP-5.

### 4.3 Declare All Host Variables as COMP-5

Every numeric host variable used in embedded SQL must be COMP-5:

```cobol
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA5 END-EXEC.
       01  WS-ORDER-ID      PIC S9(9) COMP-5.
       01  WS-QUANTITY       PIC S9(9) COMP-5.
       01  WS-STATUS         PIC X(10).
```

Now:
- `WS-ORDER-ID` = 12345 is stored as `39 30 00 00` (little-endian, because COMP-5 is always native)
- Oracle client reads it as little-endian → 12345 → **correct**
- Oracle returns SQLCODE = 0 as `00 00 00 00` (little-endian)
- COBOL reads SQLCODE as COMP-5 (native little-endian) → 0 → **correct**

Meanwhile, the rest of the program's COMP/BINARY fields (MQ structures, file records, inter-program parameters) remain big-endian because of `BINARY(BE)` — exactly what the MQ API and AIX-based consumers expect.

### 4.4 What Happens If You Forget Even One Field

If you convert SQLCA to SQLCA5 and set COMP5=YES, but forget to change one manually-declared host variable:

```cobol
       01  WS-ORDER-ID      PIC S9(9) COMP.    *> FORGOT TO CHANGE
       01  WS-QUANTITY       PIC S9(9) COMP-5.  *> Changed correctly
```

- SQLCODE works correctly (SQLCA5 uses COMP-5)
- WS-QUANTITY comes back correctly (COMP-5)
- But WS-ORDER-ID is passed to Oracle as big-endian, Oracle interprets it as little-endian → wrong order queried → wrong data returned → **silent corruption of just that one field**

**This is why the rule is absolute: ALL Oracle-facing numeric host variables must be COMP-5, with no exceptions.**

---

## 5. The Cross-Module Problem: Host Variables Received from a Caller

The problem becomes significantly more subtle when the Oracle-facing program does not own the data — it receives it as a parameter from another module via `CALL ... USING`.

### 5.1 The Call Chain

```
ORDMQ01 (MQ-facing, compiled with BINARY(BE))
    → extracts ORDER-ID from MQ message as COMP (big-endian)
    → CALL "ORDSQL01" USING WS-ORDER-ID

ORDSQL01 (Oracle-facing, compiled with BINARY(BE) + COMP5=YES)
    → receives ORDER-ID via LINKAGE SECTION
    → needs to use it as a host variable in SQL
```

### 5.2 The Naive (Wrong) Approach — Using the Parameter Directly

```cobol
      * ORDSQL01 — WRONG: using LINKAGE parameter directly as host variable
       LINKAGE SECTION.
       01  LS-ORDER-ID      PIC S9(9) COMP.

       PROCEDURE DIVISION USING LS-ORDER-ID.
           EXEC SQL
               SELECT QUANTITY INTO :WS-QUANTITY
               FROM ORDERS
               WHERE ORDER_ID = :LS-ORDER-ID
           END-EXEC.
```

What happens:
1. The caller stored ORDER-ID = 12345 as `00 00 30 39` (big-endian)
2. `LS-ORDER-ID` is COMP, compiled with `BINARY(BE)` → the COBOL program correctly reads it as 12345 in COBOL statements
3. But Oracle reads the raw bytes at the memory address of `LS-ORDER-ID` as little-endian → **959,447,040** → wrong order

The COBOL program sees the right value. Oracle sees the wrong value. Same problem as before.

### 5.3 The Tempting (Also Wrong) Approach — Changing LINKAGE to COMP-5

You might think: "Just declare the LINKAGE parameter as COMP-5 so Oracle can read it."

```cobol
      * ORDSQL01 — ALSO WRONG: changing LINKAGE to COMP-5
       LINKAGE SECTION.
       01  LS-ORDER-ID      PIC S9(9) COMP-5.
```

What happens:
1. The caller sent big-endian bytes `00 00 30 39`
2. `LS-ORDER-ID` is COMP-5, so the COBOL program interprets those same bytes as little-endian → **959,447,040**
3. Oracle also reads them as little-endian → **959,447,040**
4. Both COBOL and Oracle now agree — but they agree on the **wrong value**

You've moved the corruption from "Oracle reads wrong" to "everyone reads wrong."

### 5.4 The Correct Approach — MOVE to a COMP-5 Working Storage Variable

```cobol
      * ORDSQL01 — CORRECT: MOVE from COMP parameter to COMP-5 host variable
       LINKAGE SECTION.
       01  LS-ORDER-ID      PIC S9(9) COMP.

       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA5 END-EXEC.
       01  WS-ORDER-ID      PIC S9(9) COMP-5.
       01  WS-QUANTITY       PIC S9(9) COMP-5.

       PROCEDURE DIVISION USING LS-ORDER-ID.
      * MOVE converts from BE (COMP under BINARY(BE)) to native LE (COMP-5)
           MOVE LS-ORDER-ID TO WS-ORDER-ID.
           EXEC SQL
               SELECT QUANTITY INTO :WS-QUANTITY
               FROM ORDERS
               WHERE ORDER_ID = :WS-ORDER-ID
           END-EXEC.
```

What happens:
1. `LS-ORDER-ID` contains `00 00 30 39` (big-endian, from the caller)
2. The COBOL program reads `LS-ORDER-ID` as COMP with `BINARY(BE)` → value 12345 → **correct**
3. `MOVE LS-ORDER-ID TO WS-ORDER-ID` — the compiler knows the source is COMP (big-endian under `BINARY(BE)`) and the target is COMP-5 (always native little-endian). **The compiler automatically performs the byte-order conversion.** `WS-ORDER-ID` now contains `39 30 00 00` (little-endian, value 12345)
4. Oracle reads `WS-ORDER-ID` as native little-endian → 12345 → **correct**

**The MOVE statement is the critical step.** The COBOL compiler handles the BE-to-LE conversion transparently because it knows the data types on both sides. You never write byte-swap code — you just MOVE from COMP to COMP-5 and the compiler does the right thing.

### 5.5 The Reverse Direction — Returning Data to the Caller

If the Oracle-facing module needs to return numeric data to the caller (e.g., the quantity retrieved from the database), the reverse MOVE is needed:

```cobol
       LINKAGE SECTION.
       01  LS-ORDER-ID      PIC S9(9) COMP.
       01  LS-QUANTITY       PIC S9(9) COMP.

       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA5 END-EXEC.
       01  WS-ORDER-ID      PIC S9(9) COMP-5.
       01  WS-QUANTITY       PIC S9(9) COMP-5.

       PROCEDURE DIVISION USING LS-ORDER-ID LS-QUANTITY.
      * Incoming: COMP (BE) → COMP-5 (native LE) for Oracle
           MOVE LS-ORDER-ID TO WS-ORDER-ID.
           EXEC SQL
               SELECT QUANTITY INTO :WS-QUANTITY
               FROM ORDERS
               WHERE ORDER_ID = :WS-ORDER-ID
           END-EXEC.
      * Outgoing: COMP-5 (native LE) → COMP (BE) for caller
           MOVE WS-QUANTITY TO LS-QUANTITY.
```

The MOVE from COMP-5 to COMP automatically converts from little-endian back to big-endian, so the caller receives the value in the byte order it expects.

---

## 6. The General Rule

**Never use a LINKAGE SECTION parameter directly as an Oracle host variable** when compiled with `BINARY(BE)`. Always follow this pattern:

1. **Receive** the parameter as COMP in the LINKAGE SECTION (matching the caller's byte layout under `BINARY(BE)`)
2. **MOVE** it to a COMP-5 WORKING-STORAGE variable (the compiler converts BE → native LE automatically)
3. **Use** the COMP-5 variable as the Oracle host variable in embedded SQL
4. **MOVE** any Oracle output from COMP-5 back to the COMP LINKAGE parameter before returning (the compiler converts native LE → BE automatically)

This pattern applies to every numeric parameter received from an external caller that needs to be used in any embedded SQL statement — SELECT, INSERT, UPDATE, DELETE, or dynamic SQL.

---

## 7. Checklist for Auditing Oracle-Facing Modules

When reviewing a COBOL program that contains embedded SQL for Oracle compatibility with `BINARY(BE)`:

- [ ] `SQLCA` replaced with `SQLCA5`
- [ ] `ORACA` replaced with `ORACA5` (if used)
- [ ] `SQLDA` replaced with `SQLDA5` (if used)
- [ ] `COMP5=YES` set in Pro*COBOL precompiler options
- [ ] All numeric host variables in WORKING-STORAGE declared as COMP-5
- [ ] No LINKAGE SECTION parameters used directly as host variables in SQL
- [ ] All incoming COMP parameters MOVE'd to COMP-5 working variables before SQL use
- [ ] All outgoing COMP-5 results MOVE'd back to COMP linkage parameters before return
- [ ] PIC X / alphanumeric host variables left as-is (not affected by endianness)
- [ ] COMP-3 host variables left as-is (packed decimal is endian-independent)
