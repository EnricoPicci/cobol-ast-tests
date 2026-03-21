      ******************************************************************
      * SAFE02-CALLED.cob — Oracle Sub-Program with Correct
      *                     Endianness Handling
      *
      * PURPOSE:
      *   Demonstrates the CORRECT 5-step pattern for using Oracle
      *   host variables when compiled with BINARY(BE):
      *
      *   1. Receive parameters as COMP via LINKAGE SECTION
      *   2. MOVE from COMP (BE) to COMP-5 (native LE) before SQL
      *   3. Use COMP-5 variables as Oracle host variables
      *   4. MOVE results from COMP-5 back to COMP after SQL
      *   5. Use SQLCA5 (not SQLCA) so SQLCODE is COMP-5
      *
      *   The MOVE between COMP and COMP-5 triggers automatic
      *   byte-order conversion by the compiler. No manual
      *   byte-swap code is ever needed.
      *
      *   Compare with ENDIAN02-CALLED.cob for the WRONG pattern.
      *
      * COMPILE: BINARY(BE) on Linux x86, with COMP5=YES for
      *          Pro*COBOL precompilation.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAFE02-CALLED.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *> STEP 5: Use SQLCA5 instead of SQLCA.
      *> SQLCA5 declares SQLCODE and all numeric diagnostic fields
      *> as COMP-5 (native byte order), so Oracle and COBOL agree
      *> on the byte layout of SQLCODE, SQLERRD, etc.
           EXEC SQL INCLUDE SQLCA5 END-EXEC.

      *> Oracle-facing host variables — all COMP-5.
      *> COMP-5 always uses native byte order (little-endian on
      *> Linux x86), regardless of the BINARY(BE) compiler option.
      *> This matches what the Oracle client library expects.
       01  WS-ORA-ORDER-ID    PIC S9(9) COMP-5.
       01  WS-ORA-QUANTITY    PIC S9(9) COMP-5.

       LINKAGE SECTION.
      *> STEP 1: Receive parameters as COMP (big-endian under
      *> BINARY(BE)), matching the caller's byte layout.
      *> NEVER change these to COMP-5 — that would cause the
      *> caller's big-endian bytes to be misinterpreted as
      *> little-endian (see COMP5_ORACLE_PROBLEM_EXPLAINED.md
      *> Section 5.3 for why this is also wrong).
       01  LS-ORDER-ID        PIC S9(9) COMP.
       01  LS-QUANTITY         PIC S9(9) COMP.
       01  LS-RETURN-CODE      PIC S9(4) COMP.

       PROCEDURE DIVISION USING
           LS-ORDER-ID
           LS-QUANTITY
           LS-RETURN-CODE.

       MAIN-PARA.

      *> STEP 2: MOVE from COMP (BE) to COMP-5 (native LE).
      *> The compiler knows COMP is big-endian (BINARY(BE)) and
      *> COMP-5 is native little-endian. It automatically inserts
      *> a byte-swap instruction during this MOVE.
      *>
      *> Example for ORDER-ID = 12345:
      *>   LS-ORDER-ID  (COMP, BE):   00 00 30 39
      *>   After MOVE:
      *>   WS-ORA-ORDER-ID (COMP-5):  39 30 00 00  (LE, still 12345)
           MOVE LS-ORDER-ID TO WS-ORA-ORDER-ID

      *> STEP 3: Use COMP-5 variables as Oracle host variables.
      *> Oracle reads WS-ORA-ORDER-ID as native little-endian:
      *>   39 30 00 00 → 0x00003039 = 12345 → CORRECT.
           EXEC SQL
               SELECT QUANTITY
               INTO :WS-ORA-QUANTITY
               FROM ORDERS
               WHERE ORDER_ID = :WS-ORA-ORDER-ID
           END-EXEC

      *> SQLCODE is now COMP-5 (from SQLCA5), so Oracle and COBOL
      *> agree on its value. If Oracle writes SQLCODE = 0:
      *>   Bytes: 00 00 00 00 (same in both LE and BE for zero)
      *> If Oracle writes SQLCODE = 100:
      *>   LE bytes: 64 00 00 00
      *>   COBOL reads as COMP-5 (LE): 0x00000064 = 100 → CORRECT.
           IF SQLCODE = 0
      *> STEP 4: MOVE results from COMP-5 (LE) back to COMP (BE).
      *> The compiler automatically converts LE → BE.
      *>
      *> Example if Oracle returned QUANTITY = 70000:
      *>   WS-ORA-QUANTITY (COMP-5, LE): 70 11 01 00
      *>   After MOVE:
      *>   LS-QUANTITY (COMP, BE):       00 01 11 70  (still 70000)
      *>
      *> The caller receives the value in the byte order it
      *> expects — big-endian, compatible with MQ and AIX.
               MOVE WS-ORA-QUANTITY TO LS-QUANTITY
               MOVE 0 TO LS-RETURN-CODE
           ELSE
               MOVE 0 TO LS-QUANTITY
               MOVE SQLCODE TO LS-RETURN-CODE
           END-IF

           GOBACK.
