"""Typed AST dataclasses for representing COBOL program structure.

These dataclasses form the Abstract Syntax Tree (AST) that captures the
semantic structure of a COBOL program. The hierarchy mirrors COBOL's own
organizational structure:

    ProgramNode (root)
    ├── IdentificationDivisionNode   — names the program (PROGRAM-ID)
    ├── EnvironmentDivisionNode      — computing environment (optional)
    ├── DataDivisionNode             — variable declarations (optional)
    │   ├── WorkingStorageSectionNode — local variables
    │   └── LinkageSectionNode       — parameters from calling program
    └── ProcedureDivisionNode        — executable code (optional)

All nodes are frozen dataclasses where possible, making the AST immutable
after construction. This prevents accidental modification during analysis
passes and makes it safe to share AST references across consumers.

DataItemNode, PicClause, and UsageType capture data description entries
(variable declarations with PIC clauses, USAGE types, and VALUE clauses).

Statement nodes (DisplayNode, MoveNode, AddNode, CallNode, IfNode,
StopRunNode, GobackNode, ExecSqlNode) represent executable PROCEDURE
DIVISION statements. ParagraphNode groups statements under a named label.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Union


@dataclass(frozen=True)
class SourceLocation:
    """Source position of an AST node in the original COBOL file.

    Records the start and end positions (line and column) so that
    downstream tools (error reporters, IDE integrations, code
    highlighters) can map AST nodes back to the source text.

    Lines are 1-based (matching editor conventions). Columns are
    0-based (matching ANTLR4's convention).
    """

    start_line: int
    start_column: int
    end_line: int
    end_column: int


class UsageType(Enum):
    """COBOL USAGE clause values.

    USAGE determines how a data item is stored in memory:
    - DISPLAY: one character per digit (zoned decimal / alphanumeric)
    - COMP/BINARY: binary integer (big-endian under BINARY(BE))
    - COMP_3: packed decimal (BCD), endianness-safe
    - COMP_5: native binary (always machine byte order)
    """

    DISPLAY = "DISPLAY"
    COMP = "COMP"
    COMP_3 = "COMP-3"
    COMP_5 = "COMP-5"


@dataclass(frozen=True)
class PicClause:
    """Represents a COBOL PIC (PICTURE) clause.

    The PIC clause defines the data type and size of a data item.
    Examples:
    - PIC S9(9)   → signed numeric, 9 digits
    - PIC X(10)   → alphanumeric, 10 characters
    - PIC 9(5)    → unsigned numeric, 5 digits
    """

    raw: str  # Original PIC string, e.g., "S9(9)"
    category: str  # "numeric", "alphanumeric", "alphabetic"
    size: int  # Total size in character positions
    signed: bool  # True if PIC contains 'S'
    location: SourceLocation | None = None


@dataclass
class DataItemNode:
    """A COBOL data description entry (a variable declaration).

    COBOL data items are hierarchical. Level 01 items are top-level;
    level 02-49 items are subordinates within a group. Level 77 items
    are standalone (non-group) items.

    Example COBOL:
        01  WS-ORDER-ID  PIC S9(9) COMP VALUE 12345.
    Produces:
        DataItemNode(level=1, name="WS-ORDER-ID",
                     pic=PicClause(raw="S9(9)", ...),
                     usage=UsageType.COMP,
                     value="12345", redefines=None, children=[])
    """

    level: int
    name: str
    pic: PicClause | None  # None for group items (no PIC)
    usage: UsageType | None  # None defaults to DISPLAY
    value: str | None  # VALUE clause literal
    redefines: str | None  # Name of redefined item
    children: list[DataItemNode] = field(default_factory=list)
    location: SourceLocation | None = None


@dataclass(frozen=True)
class IdentificationDivisionNode:
    """IDENTIFICATION DIVISION — names the program.

    Every COBOL program begins with this division. The only
    required entry is PROGRAM-ID.
    """

    program_id: str
    location: SourceLocation | None = None


@dataclass(frozen=True)
class EnvironmentDivisionNode:
    """ENVIRONMENT DIVISION — describes the computing environment.

    In the sample files, this division is always present but empty.
    """

    location: SourceLocation | None = None


@dataclass(frozen=True)
class WorkingStorageSectionNode:
    """WORKING-STORAGE SECTION — local variables.

    Items declared here are allocated when the program starts and
    persist for its lifetime.
    """

    items: tuple[DataItemNode, ...] = field(default_factory=tuple)
    location: SourceLocation | None = None


@dataclass(frozen=True)
class LinkageSectionNode:
    """LINKAGE SECTION — parameters passed from a calling program.

    Items declared here describe the layout of data passed via
    CALL ... USING. The memory is owned by the caller.
    """

    items: tuple[DataItemNode, ...] = field(default_factory=tuple)
    location: SourceLocation | None = None


@dataclass(frozen=True)
class DataDivisionNode:
    """DATA DIVISION — declares all variables used by the program.

    Contains sections: WORKING-STORAGE, LINKAGE, FILE, etc.
    Only WORKING-STORAGE and LINKAGE are modelled so far, matching
    the sections used in the sample COBOL files.
    """

    working_storage: WorkingStorageSectionNode | None = None
    linkage: LinkageSectionNode | None = None
    location: SourceLocation | None = None


@dataclass(frozen=True)
class DisplayNode:
    """DISPLAY statement — outputs values to the console.

    DISPLAY can take a mix of string literals and variable names.
    Example: DISPLAY "ORDER-ID: " WS-ORDER-ID
    """

    operands: list[str]  # String literals and/or data names
    location: SourceLocation | None = None


@dataclass(frozen=True)
class MoveNode:
    """MOVE statement — copies a value from source to target(s).

    MOVE is COBOL's assignment statement.
    Example: MOVE 12345 TO WS-ORDER-ID
    Example: MOVE ZEROS TO WS-QUANTITY
    """

    source: str  # Source value (literal, name, or figurative constant)
    targets: list[str]  # One or more target data names
    location: SourceLocation | None = None


@dataclass(frozen=True)
class AddNode:
    """ADD statement — adds a value to a variable.

    Example: ADD 1000 TO WS-AMOUNT
    """

    value: str
    target: str
    location: SourceLocation | None = None


@dataclass(frozen=True)
class CallNode:
    """CALL statement — invokes a subprogram.

    Example: CALL "SAFE02-CALLED" USING WS-ORDER-ID WS-QUANTITY WS-RETURN-CODE
    """

    program_name: str
    using_items: list[str]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class StopRunNode:
    """STOP RUN — terminates the program.

    Used by main programs to end execution.
    """

    location: SourceLocation | None = None


@dataclass(frozen=True)
class GobackNode:
    """GOBACK — returns control to the calling program.

    Used by called subprograms instead of STOP RUN.
    """

    location: SourceLocation | None = None


@dataclass(frozen=True)
class ExecSqlNode:
    """EXEC SQL ... END-EXEC — embedded SQL statement.

    The SQL content is captured as raw text. The parser does not
    parse SQL itself — it treats the content between EXEC SQL and
    END-EXEC as an opaque block.

    Examples from the samples:
    - EXEC SQL INCLUDE SQLCA END-EXEC
    - EXEC SQL SELECT QUANTITY INTO :WS-ORA-QUANTITY FROM ORDERS
          WHERE ORDER_ID = :WS-ORA-ORDER-ID END-EXEC
    """

    sql_text: str  # Raw SQL between EXEC SQL and END-EXEC
    location: SourceLocation | None = None


# StatementNode is a Union of all statement types. The visitor produces
# these when walking PROCEDURE DIVISION paragraphs.
StatementNode = Union[
    DisplayNode,
    MoveNode,
    AddNode,
    CallNode,
    "IfNode",
    StopRunNode,
    GobackNode,
    ExecSqlNode,
]


@dataclass(frozen=True)
class IfNode:
    """IF / ELSE / END-IF conditional statement.

    Example:
        IF SQLCODE = 0
            MOVE WS-ORA-QUANTITY TO LS-QUANTITY
        ELSE
            MOVE 0 TO LS-QUANTITY
        END-IF
    """

    condition: str  # Raw condition text
    then_statements: list[StatementNode]
    else_statements: list[StatementNode]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class ParagraphNode:
    """A named paragraph in the PROCEDURE DIVISION.

    Paragraphs are labeled blocks of statements. All sample files
    use MAIN-PARA as their primary paragraph.
    """

    name: str
    statements: list[StatementNode]
    location: SourceLocation | None = None


@dataclass(frozen=True)
class ProcedureDivisionNode:
    """PROCEDURE DIVISION — the executable code.

    May include a USING clause listing parameters (matching the
    LINKAGE SECTION items) for called programs.

    The ``paragraphs`` list holds ``ParagraphNode`` instances that
    group named statement blocks.
    """

    using_items: tuple[str, ...] = field(default_factory=tuple)
    paragraphs: tuple[ParagraphNode, ...] = field(default_factory=tuple)
    location: SourceLocation | None = None


@dataclass(frozen=True)
class ProgramNode:
    """Root AST node representing a complete COBOL program.

    A COBOL program has four divisions, each optional except
    IDENTIFICATION DIVISION (which provides the PROGRAM-ID).

    Example — a minimal program with only an identification division::

        ProgramNode(
            program_id="HELLO",
            identification=IdentificationDivisionNode(program_id="HELLO"),
        )
    """

    program_id: str
    identification: IdentificationDivisionNode
    environment: EnvironmentDivisionNode | None = None
    data: DataDivisionNode | None = None
    procedure: ProcedureDivisionNode | None = None
    location: SourceLocation | None = None
