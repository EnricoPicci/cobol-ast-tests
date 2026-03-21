# The Endianness Problem: Big-Endian to Little-Endian in COBOL Migration from AIX to Linux

## 1. Summary

When porting a COBOL application from Micro Focus on IBM AIX (POWER, big-endian) to IBM COBOL for Linux x86 (little-endian), the most pervasive and dangerous class of bugs comes from **endianness differences** — the way multi-byte binary numbers are stored in memory. Every binary numeric field (COMP, BINARY, COMP-4, COMP-5, COMP-1, COMP-2) is affected. If not handled correctly, the result is **silent data corruption**: values appear to work but are numerically wrong, with no compiler error and no runtime error.

This document explains what endianness is, why it causes problems in this specific migration, how each COBOL data type is affected, and the concrete strategies to resolve each case — with byte-level examples.

---

## 2. What Is Endianness?

Endianness defines the order in which bytes of a multi-byte value are stored in memory.

### 2.1 Big-Endian (AIX on POWER)

The **most significant byte** is stored at the lowest memory address. This is the "natural" reading order — the leftmost byte has the highest place value, just like writing a number on paper.

**Example:** The integer value **12,345** (hexadecimal `0x00003039`) stored as a 4-byte field:

```
Memory address:   +0    +1    +2    +3
                ┌─────┬─────┬─────┬─────┐
Big-endian:     │ 00  │ 00  │ 30  │ 39  │
                └─────┴─────┴─────┴─────┘
                  MSB                 LSB
```

### 2.2 Little-Endian (Linux on x86)

The **least significant byte** is stored at the lowest memory address. The byte order is reversed compared to big-endian.

**Example:** The same integer value **12,345** (`0x00003039`):

```
Memory address:   +0    +1    +2    +3
                ┌─────┬─────┬─────┬─────┐
Little-endian:  │ 39  │ 30  │ 00  │ 00  │
                └─────┴─────┴─────┴─────┘
                  LSB                 MSB
```

### 2.3 What Happens When You Read the Wrong Way

If a program on Linux reads the big-endian bytes `00 00 30 39` as if they were little-endian, it interprets:

```
Bytes:          00   00   30   39
Little-endian
interpretation: 39 × 2²⁴ + 30 × 2¹⁶ + 00 × 2⁸ + 00 × 2⁰
              = 959,447,040
```

The value **12,345** becomes **959,447,040**. There is no error message — the program simply operates on the wrong number.

### 2.4 The Core Danger: No Error, No Warning, No Crash

This is the fundamental reason endianness bugs are so dangerous:

- The CPU does not know whether bytes are "big-endian" or "little-endian" — it just reads memory
- There is no invalid bit pattern — every combination of bytes is a valid integer
- The program runs to completion with wrong values
- The results may look plausible (they are valid numbers, just wrong ones)
- Some values — like zero (`00 00 00 00`) — are identical in both byte orders, making testing unreliable unless you use asymmetric test values

---

## 3. Which COBOL Data Types Are Affected?

Not all data types are sensitive to endianness. Understanding which types are affected and which are safe is essential for scoping the migration effort.

### 3.1 Data Type Impact Matrix

| Data Type | Endian-Sensitive? | Affected by `BINARY(BE)`? | Notes |
|-----------|:-:|:-:|-------|
| **COMP / BINARY / COMP-4** | **Yes** | **Yes** — `BINARY(BE)` forces big-endian storage | The primary affected types. These store pure binary integers. |
| **COMP-5** (native binary) | **Yes** | **No** — COMP-5 **ignores** `BINARY(BE)` | Always uses platform-native byte order. This is both a risk and a tool (see Section 5). |
| **COMP-3 / PACKED-DECIMAL** | No | N/A | Binary Coded Decimal (BCD). Each nibble encodes a digit. Byte order is irrelevant. |
| **DISPLAY** (PIC X, PIC 9) | No | N/A | Character representation. Each digit is one byte (EBCDIC or ASCII). Order is character-by-character, not byte-endian. |
| **COMP-1** (single float) | **Yes** | Use `FLOAT(BE)` | IEEE 754 single precision. 4 bytes, endian-dependent. |
| **COMP-2** (double float) | **Yes** | Use `FLOAT(BE)` | IEEE 754 double precision. 8 bytes, endian-dependent. |
| **POINTER / INDEX** | **Yes** | N/A | Platform-native. Must never be persisted to files or sent over the wire. |
| **PIC N** (NATIONAL / UTF-16) | **Yes** | N/A | UTF-16 code units are 2-byte values — byte order matters. |

### 3.2 COMP-3: Why It Is Endian-Safe

COMP-3 (packed decimal) stores each decimal digit in a half-byte (nibble), with the sign in the last nibble. The value **12345** in PIC S9(5) COMP-3 is stored as:

```
┌─────┬─────┬─────┐
│ 12  │ 34  │ 5C  │   (C = positive sign)
└─────┴─────┴─────┘
```

This layout is identical on both big-endian and little-endian platforms. Each nibble represents a specific digit in order. There is no multi-byte integer to "reverse." This is why COMP-3 is recommended for new cross-platform interfaces.

### 3.3 DISPLAY Numerics: Why They Are Endian-Safe

A DISPLAY field `PIC 9(5)` stores the value 12345 as five separate character bytes:

```
┌──────┬──────┬──────┬──────┬──────┐
│ '1'  │ '2'  │ '3'  │ '4'  │ '5'  │
└──────┴──────┴──────┴──────┴──────┘
```

Each byte is an independent character. There is no multi-byte unit whose order could be reversed by endianness. DISPLAY fields are always safe.

---

## 4. The Concrete Problem in This Migration

### 4.1 The Starting Point

On AIX with Micro Focus COBOL, all binary fields (COMP, BINARY, COMP-4, COMP-5) store values in big-endian — because AIX on POWER is big-endian. The platform byte order and the data byte order are the same. Everything works.

### 4.2 What Changes on Linux x86

On Linux x86, the platform is little-endian. Binary fields in COBOL can be stored in either byte order depending on compiler options:

| Field Type | With `BINARY(BE)` | With `BINARY(NATIVE)` (default) |
|---|---|---|
| COMP / BINARY / COMP-4 | Big-endian (matching AIX) | Little-endian (native) |
| COMP-5 | Little-endian (always native) | Little-endian (always native) |

### 4.3 Why This Migration Uses BINARY(BE) as the Default

In this project, the migration is **gradual**: some systems remain on AIX permanently, and others are migrated at different times. The ported application must continue to exchange data (via MQ messages, shared files, and inter-module calls) with big-endian consumers.

Using `BINARY(BE)` as the default compiler option means:

- COMP/BINARY fields are stored in big-endian, **exactly like AIX** — no conversion needed for MQ messages, files, or record structures shared with AIX systems
- The ported code produces identical binary output to the original AIX code
- External consumers on AIX see no change

The trade-off is a small performance cost (the CPU must byte-swap on every binary operation) and the need for special handling where native byte order is required (e.g., Oracle — see Section 5).

### 4.4 A Complete Example: The Wrong Way and the Right Way

**Original code on AIX (works correctly):**

```cobol
       WORKING-STORAGE SECTION.
       01  WS-AMOUNT        PIC S9(9) COMP.
       01  WS-TAX-RATE      PIC S9(9) COMP.
       01  WS-TAX-AMOUNT    PIC S9(9) COMP.

       PROCEDURE DIVISION.
           MOVE 100000 TO WS-AMOUNT.
           MOVE 21     TO WS-TAX-RATE.
           COMPUTE WS-TAX-AMOUNT = WS-AMOUNT * WS-TAX-RATE / 100.
           DISPLAY "Tax amount: " WS-TAX-AMOUNT.
      * Writes WS-TAX-AMOUNT to a shared file read by AIX systems
           WRITE OUTPUT-RECORD FROM WS-TAX-AMOUNT.
```

**On AIX:** `WS-TAX-AMOUNT` = 21000, stored as `00 00 51 F8` (big-endian). Written to the file as `00 00 51 F8`. The AIX consumer reads `00 00 51 F8` as big-endian → 21000. Correct.

**On Linux x86 with `BINARY(BE)`:** The COBOL program still stores `WS-TAX-AMOUNT` = 21000 as `00 00 51 F8` (big-endian, because of `BINARY(BE)`). Written to the file as `00 00 51 F8`. The AIX consumer reads it and gets 21000. **Correct — no source code change needed.**

The COMPUTE, MOVE, and DISPLAY all work correctly because the COBOL compiler knows the fields are `BINARY(BE)` and generates the appropriate byte-swap instructions internally. The program logic is transparent to the endianness.

**On Linux x86 with `BINARY(NATIVE)` (without BINARY(BE)):** `WS-TAX-AMOUNT` = 21000 is stored as `F8 51 00 00` (little-endian). Written to the file as `F8 51 00 00`. The AIX consumer reads `F8 51 00 00` as big-endian → **4,166,221,824**. **Silent corruption.**

This is why `BINARY(BE)` is mandatory for externally-facing modules in this migration.

---

## 5. COMP-5: The Exception That Makes Everything Harder

### 5.1 What Makes COMP-5 Different

COMP-5 is the critical exception in the `BINARY(BE)` strategy. Unlike COMP/BINARY/COMP-4, **COMP-5 always uses the platform's native byte order**, regardless of compiler options:

| Platform | COMP with `BINARY(BE)` | COMP-5 |
|---|---|---|
| AIX (big-endian) | Big-endian | Big-endian (native = big-endian) |
| Linux x86 (little-endian) | Big-endian (forced by compiler) | **Little-endian** (native = little-endian) |

On AIX, there was no visible difference between COMP and COMP-5 — both were big-endian. On Linux x86, they diverge: COMP follows `BINARY(BE)` and stays big-endian, but COMP-5 goes to little-endian.

### 5.2 Why COMP-5 Is Both a Risk and a Tool

**COMP-5 is a risk** when it appears in data exchanged with external big-endian systems (files, MQ messages). The `BINARY(BE)` compiler option does not protect COMP-5 fields — they silently change byte order when moving from AIX to Linux.

**Example of the risk:**

```cobol
       01  MQ-MESSAGE-RECORD.
           05  MSG-TYPE       PIC S9(4)  COMP.
           05  MSG-SEQUENCE   PIC S9(9)  COMP-5.
           05  MSG-PAYLOAD    PIC X(500).
```

On AIX, both `MSG-TYPE` and `MSG-SEQUENCE` are big-endian. On Linux with `BINARY(BE)`, `MSG-TYPE` remains big-endian (protected by `BINARY(BE)`), but `MSG-SEQUENCE` flips to little-endian. An AIX consumer reading this message gets the correct `MSG-TYPE` but a corrupted `MSG-SEQUENCE`.

**Remediation:** Convert `MSG-SEQUENCE` from COMP-5 to COMP so it is covered by `BINARY(BE)`:

```cobol
           05  MSG-SEQUENCE   PIC S9(9)  COMP.
```

**COMP-5 is a tool** when you need to pass data to native libraries that expect the platform's native byte order — most importantly, Oracle (see Section 6).

### 5.3 The COMP-5 Audit Rule

Every COMP-5 field in the codebase must be classified:

| COMP-5 Usage | Action | Reason |
|---|---|---|
| In MQ messages, shared files, or data sent to external systems | **Convert to COMP** | Must be protected by `BINARY(BE)` for AIX compatibility |
| In Oracle host variables | **Keep as COMP-5** (or convert COMP to COMP-5) | Oracle client expects native byte order |
| In purely internal working storage (never crosses a boundary) | **No change needed** | Either byte order works; the compiler handles it transparently |
| In LINKAGE SECTION for inter-module calls | **Assess each case** | Depends on whether the caller/callee expect big-endian or native |

---

## 6. The MQ vs Oracle Conflict: Where Endianness Creates an Architectural Problem

### 6.1 The Conflict

This is the most architecturally significant endianness problem in the migration. Two critical external systems have **opposite** byte-order requirements:

| System | Byte Order Requirement | Why |
|---|---|---|
| **IBM MQ** | Big-endian (`BINARY(BE)`) | MQ API parameters must be big-endian. IBM's documentation explicitly requires `BINARY(BE)` for COBOL programs using MQ on Linux x86. Additionally, MQ messages exchanged with AIX systems must remain big-endian. |
| **Oracle** | Little-endian (native) | The Oracle client library (Pro*COBOL runtime) is a native x86 C library. It reads and writes memory in the platform's native little-endian byte order. It has no awareness of the COBOL compiler's `BINARY(BE)` option. |

A program compiled with `BINARY(BE)` stores COMP fields in big-endian. MQ reads them correctly. But when those same bytes are passed to Oracle as host variables, Oracle reads them as little-endian — **wrong value, no error**.

### 6.2 The Solution: COMP-5 as the Oracle Bridge

The solution uses COMP-5's unique property — it always stores values in native byte order, ignoring `BINARY(BE)`. This means:

- COMP fields (under `BINARY(BE)`) → big-endian → correct for MQ and external systems
- COMP-5 fields → native little-endian → correct for Oracle

The program is compiled with `BINARY(BE)`, but all Oracle host variables are declared as COMP-5.

### 6.3 The Complete Pattern

```cobol
      * Compiled with BINARY(BE) and FLOAT(BE)
       WORKING-STORAGE SECTION.
           EXEC SQL INCLUDE SQLCA5 END-EXEC.

      * MQ-facing fields — COMP (big-endian under BINARY(BE))
       01  MQ-ORDER-ID       PIC S9(9) COMP.
       01  MQ-QUANTITY        PIC S9(9) COMP.

      * Oracle-facing fields — COMP-5 (always native LE)
       01  ORA-ORDER-ID       PIC S9(9) COMP-5.
       01  ORA-QUANTITY        PIC S9(9) COMP-5.

       PROCEDURE DIVISION.
      * Step 1: Receive data from MQ (big-endian COMP)
           CALL "MQGET" USING ...
      * MQ-ORDER-ID now contains 00 00 30 39 (BE) = 12345

      * Step 2: Convert for Oracle — MOVE from COMP (BE) to COMP-5 (native LE)
           MOVE MQ-ORDER-ID TO ORA-ORDER-ID.
      * ORA-ORDER-ID now contains 39 30 00 00 (LE) = 12345
      * The compiler generates the byte-swap automatically.

      * Step 3: Use COMP-5 variable in SQL
           EXEC SQL
               SELECT QUANTITY INTO :ORA-QUANTITY
               FROM ORDERS
               WHERE ORDER_ID = :ORA-ORDER-ID
           END-EXEC.
      * Oracle reads ORA-ORDER-ID as native LE → 12345 → correct

      * Step 4: Convert Oracle result back to COMP (BE) for MQ
           MOVE ORA-QUANTITY TO MQ-QUANTITY.
      * MQ-QUANTITY now contains big-endian bytes, ready for MQPUT.
```

**The MOVE statement is the key.** When the compiler knows the source is COMP (big-endian under `BINARY(BE)`) and the target is COMP-5 (native little-endian), it automatically inserts the byte-swap instruction. You never write byte-swap code manually.

### 6.4 What Goes Wrong Without This Pattern

If you use a COMP field directly as an Oracle host variable:

```
COBOL stores ORDER-ID = 12345 as:     00 00 30 39  (big-endian, BINARY(BE))
Oracle reads those bytes as LE:        39300000 hex = 959,447,040 decimal
Oracle searches for ORDER_ID = 959,447,040
Result: wrong row (or no row) — no error raised
```

If Oracle writes SQLCODE = 100 (not found) into a COMP field:

```
Oracle writes 100 as LE bytes:         64 00 00 00
COBOL reads those bytes as BE:         00000064 hex... wait — reversed:
  Bytes are 64 00 00 00, read as BE:   64000000 hex = 1,677,721,600 decimal
COBOL sees SQLCODE = 1,677,721,600 — not 0, not 100, just wrong
```

This corruption affects every numeric value exchanged with Oracle: host variables, SQLCODE, SQLERRD, indicator variables — all of them.

---

## 7. The REDEFINES Hazard

### 7.1 What Is the Problem?

When a COMP field is REDEFINE'd as PIC X (to access individual bytes), the code is making explicit assumptions about byte order. These assumptions break silently on a different-endian platform.

### 7.2 Example

```cobol
       01  WS-FLAGS         PIC S9(4) COMP VALUE 256.
       01  WS-FLAG-BYTES    REDEFINES WS-FLAGS PIC X(2).
```

The value 256 in hexadecimal is `0x0100`.

**On AIX (big-endian):**
```
WS-FLAGS:       01 00
WS-FLAG-BYTES:  WS-FLAG-BYTES(1:1) = 0x01  (high byte)
                WS-FLAG-BYTES(2:1) = 0x00  (low byte)
```

**On Linux x86 with `BINARY(BE)`:**
```
WS-FLAGS:       01 00     (still big-endian because of BINARY(BE))
WS-FLAG-BYTES:  WS-FLAG-BYTES(1:1) = 0x01  (same as AIX — correct)
                WS-FLAG-BYTES(2:1) = 0x00  (same as AIX — correct)
```

With `BINARY(BE)`, the REDEFINES works the same as on AIX because the bytes are in the same order. **However**, if `BINARY(NATIVE)` is used instead:

**On Linux x86 with `BINARY(NATIVE)`:**
```
WS-FLAGS:       00 01     (little-endian, native)
WS-FLAG-BYTES:  WS-FLAG-BYTES(1:1) = 0x00  (low byte — REVERSED!)
                WS-FLAG-BYTES(2:1) = 0x01  (high byte — REVERSED!)
```

**Any code that tests or manipulates individual bytes of a COMP field via REDEFINES will break** under `BINARY(NATIVE)`.

### 7.3 Why BINARY(BE) Mostly Protects REDEFINES — But Not Always

Under the recommended `BINARY(BE)` strategy, most REDEFINES of COMP fields are safe because the byte layout matches AIX. But there are exceptions:

1. **REDEFINES of COMP-5 fields** — COMP-5 is always native, so its byte layout changes on Linux even with `BINARY(BE)`
2. **REDEFINES across data received from external native libraries** — if a C library writes native-endian data into a buffer that COBOL REDEFINES as COMP fields, the bytes are little-endian regardless of `BINARY(BE)`

### 7.4 Remediation

- **Audit all REDEFINES** of binary fields in the codebase
- Under `BINARY(BE)`: REDEFINES of COMP/BINARY fields are safe — verify only COMP-5 cases
- Under `BINARY(NATIVE)`: all REDEFINES of any binary field must be reviewed and byte access must be adjusted
- **Best practice:** Replace byte-level access with COBOL arithmetic or reference modification where possible, to avoid endian-dependent code entirely

---

## 8. Floating-Point Fields (COMP-1 and COMP-2)

### 8.1 The Problem

COMP-1 (single-precision float, 4 bytes) and COMP-2 (double-precision float, 8 bytes) use IEEE 754 format. The floating-point value is stored as a sequence of bytes whose order depends on the platform's endianness.

**Example:** The value **1.0** as a COMP-1 (IEEE 754 single-precision):

```
Hexadecimal representation: 3F800000

Big-endian (AIX):      3F 80 00 00
Little-endian (Linux):  00 00 80 3F
```

### 8.2 The Solution: FLOAT(BE)

IBM COBOL for Linux provides the `FLOAT(BE)` compiler option, which forces COMP-1 and COMP-2 fields to be stored in big-endian byte order — analogous to `BINARY(BE)` for integer types.

**When to use `FLOAT(BE)`:**
- When float fields appear in MQ messages, shared files, or data exchanged with AIX systems
- When COMP-1/COMP-2 fields are in REDEFINES overlays

**When NOT to use `FLOAT(BE)`:**
- When float fields are passed to native C libraries (e.g., Oracle) — these expect native byte order

The same MQ-vs-Oracle conflict applies to floating-point fields: MQ expects big-endian (`FLOAT(BE)`), Oracle expects native little-endian.

---

## 9. PIC N (NATIONAL / UTF-16)

### 9.1 The Problem

PIC N fields store UTF-16 characters. Each character is a 2-byte (or 4-byte for surrogate pairs) code unit. The byte order of these code units depends on the platform:

- **AIX (big-endian):** UTF-16BE — the character 'A' (U+0041) is stored as `00 41`
- **Linux x86 (little-endian):** UTF-16LE — the character 'A' is stored as `41 00`

If a PIC N field written on AIX is read on Linux without conversion, every character is garbled.

### 9.2 Remediation

- If PIC N fields are exchanged with AIX systems, the data must be converted at the boundary (UTF-16BE ↔ UTF-16LE)
- If PIC N fields are internal-only, no conversion is needed — the compiler handles it
- Consider whether PIC N can be replaced with PIC X using UTF-8 encoding, which is endian-independent

---

## 10. Endianness Decision Tree

For every binary field in the codebase, use this decision tree:

```
Is the field COMP-3 or DISPLAY?
├── Yes → No endianness issue. No change needed.
└── No (it's COMP/BINARY/COMP-4/COMP-5/COMP-1/COMP-2)
    │
    Is the field used ONLY within the program (never written to a file,
    MQ message, or passed to an external library)?
    ├── Yes → No change needed. BINARY(BE) or BINARY(NATIVE)
    │         both work — the compiler handles it transparently.
    └── No (the field crosses a boundary)
        │
        What is the boundary?
        ├── MQ message or file shared with AIX systems
        │   ├── COMP/BINARY/COMP-4 → Use BINARY(BE). No source change.
        │   ├── COMP-5 → CONVERT TO COMP so BINARY(BE) covers it.
        │   ├── COMP-1/COMP-2 → Use FLOAT(BE). No source change.
        │   └── PIC N → Convert data at boundary (UTF-16BE ↔ UTF-16LE).
        │
        ├── Oracle host variable
        │   ├── COMP/BINARY/COMP-4 → CONVERT TO COMP-5 (native for Oracle).
        │   ├── COMP-5 → Already correct. No change.
        │   └── COMP-1/COMP-2 → Use native float (no FLOAT(BE)) for Oracle.
        │
        ├── Native C library (non-Oracle)
        │   └── Same as Oracle — use native byte order (COMP-5 / no FLOAT(BE)).
        │
        └── LINKAGE SECTION (inter-module CALL)
            ├── Caller and callee both compiled with BINARY(BE)?
            │   ├── Yes → COMP fields match. No change needed.
            │   └── No → MOVE to a local variable of the correct type
            │             before use (see Section 6.3).
            └── Field is COMP-5?
                └── COMP-5 is always native on both sides. No conversion
                    needed for the CALL itself — but assess how the callee
                    uses the field (Oracle? MQ? File?).
```

---

## 11. Byte-Level Walkthrough: A Complete Example

To make the endianness problem fully concrete, here is a byte-level trace of a value through the entire system.

### 11.1 The Scenario

An MQ message arrives from an AIX system containing an order ID. The COBOL program reads the message, queries Oracle for the order details, and sends a response back via MQ.

**Order ID value:** 70,000 (hexadecimal: `0x00011170`)

### 11.2 Step-by-Step Byte Trace

**Step 1 — MQ message arrives from AIX (big-endian)**

```
Raw bytes in MQ message: 00 01 11 70
AIX interpretation (BE): 0x00011170 = 70,000 ✓
```

**Step 2 — COBOL reads the MQ message (compiled with BINARY(BE))**

```cobol
       01  MQ-ORDER-ID     PIC S9(9) COMP.
       ...
       CALL "MQGET" USING ...
```

```
MQ-ORDER-ID bytes:       00 01 11 70
COBOL reads as BE:       0x00011170 = 70,000 ✓
(BINARY(BE) matches the message format — no conversion needed)
```

**Step 3 — MOVE from COMP (BE) to COMP-5 (native LE) for Oracle**

```cobol
       01  ORA-ORDER-ID    PIC S9(9) COMP-5.
       ...
       MOVE MQ-ORDER-ID TO ORA-ORDER-ID.
```

```
Source (MQ-ORDER-ID, COMP BE):   00 01 11 70  (value: 70,000)
Compiler byte-swaps automatically during MOVE.
Target (ORA-ORDER-ID, COMP-5):   70 11 01 00  (value: 70,000 in LE)
```

**Step 4 — Oracle reads the host variable**

```cobol
       EXEC SQL
           SELECT DESCRIPTION INTO :ORA-DESC
           FROM ORDERS WHERE ORDER_ID = :ORA-ORDER-ID
       END-EXEC.
```

```
ORA-ORDER-ID bytes:      70 11 01 00
Oracle reads as LE:      0x00011170 = 70,000 ✓
Oracle queries ORDER_ID = 70,000 — correct row found.
```

**Step 5 — Oracle returns SQLCODE (in SQLCA5, COMP-5)**

```
Oracle writes SQLCODE = 0 as LE:  00 00 00 00
COBOL reads SQLCODE as COMP-5:    0 ✓
```

**Step 6 — MOVE Oracle result back from COMP-5 (LE) to COMP (BE) for MQ**

```cobol
       01  ORA-STATUS-CODE  PIC S9(9) COMP-5.
       01  MQ-STATUS-CODE   PIC S9(9) COMP.
       ...
       MOVE ORA-STATUS-CODE TO MQ-STATUS-CODE.
```

```
Source (ORA-STATUS-CODE, COMP-5 LE):  01 00 00 00  (value: 1 in LE)
Compiler byte-swaps automatically during MOVE.
Target (MQ-STATUS-CODE, COMP BE):     00 00 00 01  (value: 1 in BE)
```

**Step 7 — MQ message sent to AIX consumer**

```
MQ-STATUS-CODE bytes:    00 00 00 01
AIX reads as BE:         0x00000001 = 1 ✓
```

Every step is correct. The values are preserved throughout the entire chain because each boundary is handled:
- **MQ ↔ COBOL**: `BINARY(BE)` ensures matching byte order
- **COBOL ↔ Oracle**: COMP-5 ensures native byte order for Oracle
- **COMP ↔ COMP-5**: the MOVE statement performs automatic byte-swap

### 11.3 What Would Go Wrong Without the Pattern

If we had used COMP (not COMP-5) as the Oracle host variable:

```
MQ-ORDER-ID bytes (COMP, BE):  00 01 11 70
Passed directly to Oracle.
Oracle reads as LE:             0x70110100 = 1,880,228,096
Oracle searches for ORDER_ID = 1,880,228,096 — WRONG
SQLCODE = 100 (not found), written as LE: 64 00 00 00
COBOL reads SQLCODE as BE:     0x64000000 = 1,677,721,600
SQLCODE is not 0 and not 100 — all error handling is broken.
```

---

## 12. Values That Mask Endianness Bugs

Some values are identical in both big-endian and little-endian representation. These values will make buggy code appear to work, which is why they are dangerous in test data.

### 12.1 Values That Are Endian-Identical

| Value | Hex (4 bytes) | BE bytes | LE bytes | Same? |
|---|---|---|---|---|
| 0 | 00000000 | 00 00 00 00 | 00 00 00 00 | Yes |
| -1 (two's complement) | FFFFFFFF | FF FF FF FF | FF FF FF FF | Yes |
| 16,843,009 | 01010101 | 01 01 01 01 | 01 01 01 01 | Yes |

### 12.2 Values That Expose Endianness Bugs

| Value | Hex (4 bytes) | BE bytes | LE bytes | Same? |
|---|---|---|---|---|
| 1 | 00000001 | 00 00 00 01 | 01 00 00 00 | **No** |
| 256 | 00000100 | 00 00 01 00 | 00 01 00 00 | **No** |
| 12,345 | 00003039 | 00 00 30 39 | 39 30 00 00 | **No** |
| 100 (SQLCODE) | 00000064 | 00 00 00 64 | 64 00 00 00 | **No** |

### 12.3 Testing Recommendation

Always use **asymmetric** test values where all four bytes are different (e.g., 12345, 70000, 98765). Never rely on tests that use only 0, -1, or symmetric values — these will pass even when endianness handling is completely broken.

---

## 13. Summary: The Three Endianness Rules

For this migration (Micro Focus COBOL on AIX → IBM COBOL for Linux x86, gradual migration, mixed-endian landscape):

### Rule 1 — Default to BINARY(BE) and FLOAT(BE)

Compile all modules with `BINARY(BE)` (and `FLOAT(BE)` if COMP-1/COMP-2 are used). This makes COMP/BINARY/COMP-4 fields big-endian on Linux, matching AIX byte order. All existing data formats, MQ messages, shared files, and inter-module interfaces continue to work without change.

### Rule 2 — Use COMP-5 for Oracle (and other native libraries)

All numeric host variables used in Oracle embedded SQL must be COMP-5. Use SQLCA5/ORACA5/SQLDA5. Set `COMP5=YES` in Pro*COBOL. MOVE from COMP to COMP-5 before SQL, and MOVE back from COMP-5 to COMP after SQL. The compiler handles the byte-swap automatically.

### Rule 3 — Audit every COMP-5 in external data

Every existing COMP-5 field that appears in MQ messages, shared files, or data sent to external systems must be converted to COMP (so that `BINARY(BE)` covers it). COMP-5 in external data is the single highest-risk data type in this migration because `BINARY(BE)` does not protect it.

---

## 14. Checklist for Endianness Review

When reviewing any COBOL module being ported from AIX to Linux:

- [ ] Module compiled with `BINARY(BE)` (and `FLOAT(BE)` if float fields exist)
- [ ] All COMP-5 fields in externally-exchanged data structures identified
- [ ] External-facing COMP-5 fields converted to COMP (or justified as exceptions)
- [ ] Oracle host variables declared as COMP-5
- [ ] SQLCA replaced with SQLCA5, ORACA with ORACA5, SQLDA with SQLDA5
- [ ] COMP5=YES set in Pro*COBOL precompiler options
- [ ] All REDEFINES of binary fields as PIC X audited (especially COMP-5 cases)
- [ ] LINKAGE SECTION parameters assessed: COMP-5 fields that cross module boundaries with different compilation options need MOVE conversion
- [ ] Test data includes asymmetric values (not just 0, -1, or symmetric patterns)
- [ ] PIC N (NATIONAL/UTF-16) fields assessed for byte-order conversion at boundaries
