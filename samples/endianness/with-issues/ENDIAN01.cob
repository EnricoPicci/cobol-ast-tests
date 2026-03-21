      ******************************************************************
      * ENDIAN01.cob — Endianness Issues: REDEFINES Hazard and
      *                Mixed COMP/COMP-5 Types
      *
      * PURPOSE:
      *   Demonstrates two endianness problems that occur when
      *   migrating COBOL from big-endian AIX to little-endian
      *   Linux x86:
      *
      *   1. REDEFINES HAZARD — A COMP field redefined as PIC X
      *      to access individual bytes. Under BINARY(NATIVE),
      *      byte positions are reversed compared to AIX/BINARY(BE).
      *
      *   2. COMP vs COMP-5 DIVERGENCE — Under BINARY(BE), COMP
      *      stays big-endian but COMP-5 becomes little-endian.
      *      Code that treats them identically will break.
      *
      * COMPILE: Intended to be compiled with BINARY(BE) on Linux.
      *          The issues shown here affect programs that assume
      *          byte-level layout or mix COMP and COMP-5 in
      *          external data structures.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ENDIAN01.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *> --- REDEFINES HAZARD ---
      *> WS-ORDER-ID is a 4-byte binary integer (COMP).
      *> Under BINARY(BE), it stores 12345 as: 00 00 30 39
      *> Under BINARY(NATIVE), it stores:      39 30 00 00
      *> The REDEFINES accesses raw bytes — their meaning depends
      *> on the byte order, so byte extraction breaks if the
      *> endianness assumption is wrong.
       01  WS-ORDER-ID        PIC S9(9) COMP VALUE 12345.
       01  WS-ORDER-BYTES     REDEFINES WS-ORDER-ID.
           05  WS-BYTE-1      PIC X(1).
           05  WS-BYTE-2      PIC X(1).
           05  WS-BYTE-3      PIC X(1).
           05  WS-BYTE-4      PIC X(1).

      *> --- COMP vs COMP-5 DIVERGENCE ---
      *> Both fields hold the same value (70000 = 0x00011170).
      *> On AIX, both are big-endian — identical byte layout.
      *> On Linux with BINARY(BE):
      *>   WS-COMP-VAL  (COMP)   → big-endian:    00 01 11 70
      *>   WS-COMP5-VAL (COMP-5) → little-endian:  70 11 01 00
      *> Any code that assumes identical byte layout between
      *> COMP and COMP-5 (e.g., comparing via REDEFINES,
      *> writing both to the same MQ message) will see different
      *> bytes for the same numeric value.

      *> COMP field and its REDEFINES (must be contiguous).
       01  WS-COMP-VAL        PIC S9(9) COMP VALUE 70000.
       01  WS-COMP-BYTES      REDEFINES WS-COMP-VAL.
           05  WS-CB-1        PIC X(1).
           05  WS-CB-2        PIC X(1).
           05  WS-CB-3        PIC X(1).
           05  WS-CB-4        PIC X(1).

      *> COMP-5 field and its REDEFINES (must be contiguous).
       01  WS-COMP5-VAL       PIC S9(9) COMP-5 VALUE 70000.
       01  WS-COMP5-BYTES     REDEFINES WS-COMP5-VAL.
           05  WS-C5B-1       PIC X(1).
           05  WS-C5B-2       PIC X(1).
           05  WS-C5B-3       PIC X(1).
           05  WS-C5B-4       PIC X(1).

       PROCEDURE DIVISION.
       MAIN-PARA.

      *> --- Show the REDEFINES hazard ---
      *> On AIX (or Linux with BINARY(BE)):
      *>   Byte 3 = 0x30, Byte 4 = 0x39
      *> On Linux with BINARY(NATIVE):
      *>   Byte 1 = 0x39, Byte 2 = 0x30  (reversed!)
      *> Code that checks WS-BYTE-3 expecting 0x30 will get
      *> 0x00 under BINARY(NATIVE) — silent logic error.
      *>
      *> NOTE: The DISPLAYed bytes are raw binary values (e.g.,
      *> 0x00, 0x30) which are non-printable characters. In
      *> real code, the hazard is in IF/EVALUATE tests on these
      *> bytes, not in DISPLAY. We show DISPLAY here to
      *> illustrate that the byte positions change.
           DISPLAY "=== REDEFINES HAZARD ==="
           DISPLAY "ORDER-ID numeric value: " WS-ORDER-ID
           DISPLAY "Byte 1: " WS-BYTE-1
           DISPLAY "Byte 2: " WS-BYTE-2
           DISPLAY "Byte 3: " WS-BYTE-3
           DISPLAY "Byte 4: " WS-BYTE-4

      *> --- Show COMP vs COMP-5 byte divergence ---
      *> Both variables hold 70000, but on Linux with BINARY(BE)
      *> their raw bytes are in opposite order.
      *> The numeric DISPLAYs below show both fields produce
      *> the same value (70000), while a byte-level comparison
      *> (e.g., via REDEFINES) would show different layouts.
           DISPLAY " "
           DISPLAY "=== COMP vs COMP-5 DIVERGENCE ==="
           DISPLAY "COMP   numeric value: " WS-COMP-VAL
           DISPLAY "COMP-5 numeric value: " WS-COMP5-VAL

      *> If these two fields were written to an MQ message read
      *> by an AIX consumer, the COMP field would be correct
      *> (big-endian, matching AIX) but the COMP-5 field would
      *> be little-endian — the AIX reader would see a corrupted
      *> value for COMP-5.

           STOP RUN.
