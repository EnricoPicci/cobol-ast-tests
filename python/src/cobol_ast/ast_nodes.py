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
Later steps add ParagraphNode and statement nodes for executable code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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


@dataclass(frozen=True)
class IdentificationDivisionNode:
    """IDENTIFICATION DIVISION — names the program.

    Every COBOL program begins with this division. The only
    required entry is PROGRAM-ID.
    """

    program_id: str


@dataclass(frozen=True)
class EnvironmentDivisionNode:
    """ENVIRONMENT DIVISION — describes the computing environment.

    In the sample files, this division is always present but empty.
    """

    pass  # Extended in future steps if needed


@dataclass(frozen=True)
class WorkingStorageSectionNode:
    """WORKING-STORAGE SECTION — local variables.

    Items declared here are allocated when the program starts and
    persist for its lifetime.
    """

    items: tuple[DataItemNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class LinkageSectionNode:
    """LINKAGE SECTION — parameters passed from a calling program.

    Items declared here describe the layout of data passed via
    CALL ... USING. The memory is owned by the caller.
    """

    items: tuple[DataItemNode, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DataDivisionNode:
    """DATA DIVISION — declares all variables used by the program.

    Contains sections: WORKING-STORAGE, LINKAGE, FILE, etc.
    Only WORKING-STORAGE and LINKAGE are modelled so far, matching
    the sections used in the sample COBOL files.
    """

    working_storage: WorkingStorageSectionNode | None = None
    linkage: LinkageSectionNode | None = None


@dataclass(frozen=True)
class ProcedureDivisionNode:
    """PROCEDURE DIVISION — the executable code.

    May include a USING clause listing parameters (matching the
    LINKAGE SECTION items) for called programs.

    The ``paragraphs`` list will hold ``ParagraphNode`` instances once
    that type is defined in Step 7.
    """

    using_items: tuple[str, ...] = field(default_factory=tuple)
    paragraphs: tuple[object, ...] = field(default_factory=tuple)


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
