      ******************************************************************
      * SAFE01.cob — Endianness-Safe Program Using Only Safe Types
      *
      * PURPOSE:
      *   Equivalent in purpose to ENDIAN01.cob, but uses ONLY
      *   data types that are NOT affected by endianness:
      *
      *   - COMP-3 (packed decimal / BCD) — each nibble encodes
      *     a digit; there is no multi-byte integer to reverse.
      *   - DISPLAY (zoned decimal) — each digit is one character
      *     byte; no multi-byte unit whose order could change.
      *
      *   This program produces correct output regardless of
      *   whether it runs on big-endian AIX or little-endian
      *   Linux x86, with or without BINARY(BE).
      *
      * COMPILE: Any platform, any BINARY option. Safe everywhere.
      ******************************************************************
       IDENTIFICATION DIVISION.
       PROGRAM-ID. SAFE01.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *> --- COMP-3 (Packed Decimal) ---
      *> COMP-3 stores each digit in a half-byte (nibble), with
      *> the sign in the last nibble. PIC S9(9) = 9 digits + sign
      *> = 10 nibbles = 5 bytes.
      *> Value 000012345 packed: 00 00 12 34 5C  (C = positive)
      *>   Nibbles: (0,0)(0,0)(1,2)(3,4)(5,C)
      *> This layout is identical on big-endian and little-endian
      *> platforms. There is no multi-byte integer to reverse —
      *> each nibble is a digit, read left to right.
       01  WS-ORDER-ID        PIC S9(9) COMP-3 VALUE 12345.

      *> Another COMP-3 field with an asymmetric value.
      *> Value 000070000 packed: 00 00 70 00 0C  (C = positive)
      *>   Nibbles: (0,0)(0,0)(7,0)(0,0)(0,C)
      *> Same bytes on AIX and Linux — always correct.
       01  WS-AMOUNT          PIC S9(9) COMP-3 VALUE 70000.

      *> --- DISPLAY (Zoned Decimal) ---
      *> DISPLAY stores each digit as a separate character byte.
      *> For value 98765:
      *>   Bytes: F9 F8 F7 F6 F5  (EBCDIC) or 39 38 37 36 35 (ASCII)
      *> Each byte is independent — no multi-byte unit to reverse.
      *> Endianness does not affect character-by-character storage.
       01  WS-COUNTER         PIC 9(5) DISPLAY VALUE 98765.

      *> A signed DISPLAY numeric with a trailing sign.
       01  WS-BALANCE         PIC S9(7) DISPLAY VALUE -54321.

      *> Alphanumeric fields are also endianness-safe.
       01  WS-STATUS          PIC X(10) VALUE "ACTIVE".

       PROCEDURE DIVISION.
       MAIN-PARA.

      *> All DISPLAY statements below produce correct output on
      *> both big-endian and little-endian platforms, because
      *> none of the data types depend on byte order.

           DISPLAY "=== COMP-3 (Packed Decimal) ==="
           DISPLAY "ORDER-ID (COMP-3): " WS-ORDER-ID
           DISPLAY "AMOUNT   (COMP-3): " WS-AMOUNT

           DISPLAY " "
           DISPLAY "=== DISPLAY (Zoned Decimal) ==="
           DISPLAY "COUNTER  (DISPLAY): " WS-COUNTER
           DISPLAY "BALANCE  (DISPLAY): " WS-BALANCE

           DISPLAY " "
           DISPLAY "=== Alphanumeric ==="
           DISPLAY "STATUS   (PIC X):   " WS-STATUS

      *> Arithmetic on COMP-3 and DISPLAY is also safe.
      *> The compiler handles these types identically on all
      *> platforms — no byte-order dependency.
           ADD 1000 TO WS-AMOUNT
           DISPLAY " "
           DISPLAY "AMOUNT after ADD 1000: " WS-AMOUNT

      *> WHY these types are safe:
      *> - COMP-3: Binary Coded Decimal — digit-by-digit encoding
      *>   with no multi-byte integer representation.
      *> - DISPLAY: Character-by-character encoding — each digit
      *>   occupies exactly one byte, read left to right.
      *> - PIC X: Alphanumeric — single-byte characters.
      *>
      *> The ONLY COBOL types affected by endianness are binary
      *> types: COMP, BINARY, COMP-4, COMP-5, COMP-1, COMP-2.

           STOP RUN.
