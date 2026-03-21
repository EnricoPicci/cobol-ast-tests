      ******************************************************************
      * ENDIAN02-CALLER.cob — Caller Module for Oracle Endianness
      *                       Problem Demonstration
      *
      * PURPOSE:
      *   This is the CALLER in a two-module example showing the
      *   Oracle host variable endianness bug. It simulates a
      *   program that receives data (e.g., from MQ) and passes
      *   it to a sub-program that queries Oracle.
      *
      *   The caller defines parameters as COMP (big-endian under
      *   BINARY(BE)), which is correct for MQ and inter-module
      *   communication. The problem is in the CALLED module,
      *   which uses these COMP values directly as Oracle host
      *   variables — see ENDIAN02-CALLED.cob.
      *
      * COMPILE: BINARY(BE) on Linux x86.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ENDIAN02-CALLER.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *> Parameters to pass to the Oracle sub-program.
      *> These are COMP (big-endian under BINARY(BE)), which is
      *> correct for data received from MQ or shared with AIX.
      *> Value 12345 = hex 0x00003039
      *>   Stored as COMP with BINARY(BE): 00 00 30 39
       01  WS-ORDER-ID        PIC S9(9) COMP.
      *> Will receive the quantity returned by Oracle.
       01  WS-QUANTITY         PIC S9(9) COMP.
      *> Return code from the called module.
       01  WS-RETURN-CODE      PIC S9(4) COMP.

       PROCEDURE DIVISION.
       MAIN-PARA.

      *> Simulate receiving an order ID from MQ.
      *> Using an asymmetric value that exposes byte-order bugs.
           MOVE 12345 TO WS-ORDER-ID
           MOVE ZEROS TO WS-QUANTITY
           MOVE ZEROS TO WS-RETURN-CODE

           DISPLAY "Calling ENDIAN02-CALLED with ORDER-ID: "
               WS-ORDER-ID

      *> CALL the Oracle-facing sub-program.
      *> The parameters are passed BY REFERENCE (default), so the
      *> called program sees the same memory — including the
      *> big-endian byte layout of COMP fields.
           CALL "ENDIAN02-CALLED" USING
               WS-ORDER-ID
               WS-QUANTITY
               WS-RETURN-CODE

           DISPLAY "Returned QUANTITY: " WS-QUANTITY
           DISPLAY "Returned RC:      " WS-RETURN-CODE

           STOP RUN.
