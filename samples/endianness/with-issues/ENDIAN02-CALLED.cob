      ******************************************************************
      * ENDIAN02-CALLED.cob — Oracle Sub-Program with Endianness Bug
      *
      * PURPOSE:
      *   Demonstrates the WRONG pattern: using COMP LINKAGE
      *   parameters directly as Oracle host variables when
      *   compiled with BINARY(BE).
      *
      *   Oracle is a native x86 library — it reads memory as
      *   little-endian. But COMP fields under BINARY(BE) are
      *   stored big-endian. Passing COMP directly to Oracle
      *   causes silent data corruption.
      *
      *   See SAFE02-CALLED.cob for the CORRECT pattern.
      *
      * COMPILE: BINARY(BE) on Linux x86.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ENDIAN02-CALLED.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *> BUG: Using SQLCA instead of SQLCA5.
      *> SQLCA declares SQLCODE as COMP (big-endian under
      *> BINARY(BE)), but Oracle writes SQLCODE as native
      *> little-endian. Result: SQLCODE is always wrong.
      *>
      *> Example: Oracle writes SQLCODE = 100 (not found)
      *>   Oracle writes LE bytes: 64 00 00 00
      *>   COBOL reads as BE:      0x64000000 = 1,677,721,600
      *>   The IF SQLCODE = 0 test fails, but SQLCODE is not
      *>   100 either — error handling is completely broken.
           EXEC SQL INCLUDE SQLCA END-EXEC.

      *> BUG: WS-QUANTITY is COMP, but it is used as a SELECT INTO
      *> host variable below. Oracle will write the result as
      *> native little-endian bytes, but COBOL will read them as
      *> big-endian (BINARY(BE)) — the returned quantity is wrong.
       01  WS-QUANTITY         PIC S9(9) COMP.

       LINKAGE SECTION.
      *> Parameters received from the caller as COMP (big-endian).
       01  LS-ORDER-ID         PIC S9(9) COMP.
       01  LS-QUANTITY         PIC S9(9) COMP.
       01  LS-RETURN-CODE      PIC S9(4) COMP.

       PROCEDURE DIVISION USING
           LS-ORDER-ID
           LS-QUANTITY
           LS-RETURN-CODE.

       MAIN-PARA.

      *> ============================================================
      *> BUG: Using LS-ORDER-ID directly as an Oracle host variable.
      *>
      *> LS-ORDER-ID is COMP, stored big-endian under BINARY(BE).
      *> Value 12345 is stored as bytes: 00 00 30 39
      *>
      *> Oracle reads those bytes as little-endian:
      *>   0x39300000 = 959,447,040
      *>
      *> Oracle searches for ORDER_ID = 959,447,040 — WRONG.
      *> No error is raised. The query simply returns the wrong
      *> row (or no row at all).
      *> ============================================================
           EXEC SQL
               SELECT QUANTITY
               INTO :WS-QUANTITY
               FROM ORDERS
               WHERE ORDER_ID = :LS-ORDER-ID
           END-EXEC

      *> BUG: SQLCODE check is broken because SQLCA uses COMP.
      *> Oracle wrote SQLCODE in little-endian, but COBOL reads
      *> it as big-endian. The value is garbled.
           IF SQLCODE = 0
               MOVE WS-QUANTITY TO LS-QUANTITY
               MOVE 0 TO LS-RETURN-CODE
           ELSE
               MOVE 0 TO LS-QUANTITY
               MOVE SQLCODE TO LS-RETURN-CODE
           END-IF

           GOBACK.

      *> ============================================================
      *> CORRECT FIX (commented out) — see SAFE02-CALLED.cob for
      *> the full working version:
      *>
      *> 1. Replace SQLCA with SQLCA5
      *> 2. Declare COMP-5 working-storage variables:
      *>        01  WS-ORA-ORDER-ID  PIC S9(9) COMP-5.
      *>        01  WS-ORA-QUANTITY  PIC S9(9) COMP-5.
      *> 3. MOVE from COMP to COMP-5 before SQL:
      *>        MOVE LS-ORDER-ID TO WS-ORA-ORDER-ID
      *> 4. Use COMP-5 variables in the SQL statement:
      *>        WHERE ORDER_ID = :WS-ORA-ORDER-ID
      *> 5. MOVE results back from COMP-5 to COMP:
      *>        MOVE WS-ORA-QUANTITY TO LS-QUANTITY
      *>
      *> The MOVE between COMP and COMP-5 triggers automatic
      *> byte-order conversion by the compiler.
      *> ============================================================
