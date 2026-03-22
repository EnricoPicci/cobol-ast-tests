"""Shared test fixtures for the COBOL AST parser test suite.

Provides fixtures for sample COBOL file paths and source text, used by
integration tests that validate preprocessing and parsing against real
COBOL programs from the samples/ directory.
"""

from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "samples"


@pytest.fixture
def samples_dir() -> Path:
    """Path to the shared samples/ directory containing .cob files."""
    return SAMPLES_DIR


@pytest.fixture
def safe01_source(samples_dir: Path) -> str:
    """Raw source text of SAFE01.cob — endianness-safe program using
    only COMP-3 and DISPLAY types (no binary types affected by byte order).
    """
    return (samples_dir / "endianness" / "without-issues" / "SAFE01.cob").read_text()


@pytest.fixture
def safe02_called_source(samples_dir: Path) -> str:
    """Raw source text of SAFE02-CALLED.cob — Oracle sub-program with
    correct COMP-to-COMP-5 conversion pattern for host variables.
    """
    return (
        samples_dir / "endianness" / "without-issues" / "SAFE02-CALLED.cob"
    ).read_text()


@pytest.fixture
def safe02_caller_source(samples_dir: Path) -> str:
    """Raw source text of SAFE02-CALLER.cob — caller module that passes
    COMP parameters to the Oracle-facing sub-program.
    """
    return (
        samples_dir / "endianness" / "without-issues" / "SAFE02-CALLER.cob"
    ).read_text()


@pytest.fixture
def endian01_source(samples_dir: Path) -> str:
    """Raw source text of ENDIAN01.cob — demonstrates REDEFINES hazard
    and COMP vs COMP-5 divergence under BINARY(BE).
    """
    return (samples_dir / "endianness" / "with-issues" / "ENDIAN01.cob").read_text()


@pytest.fixture
def endian02_called_source(samples_dir: Path) -> str:
    """Raw source text of ENDIAN02-CALLED.cob — Oracle sub-program with
    the WRONG pattern (using COMP directly as host variables).
    """
    return (
        samples_dir / "endianness" / "with-issues" / "ENDIAN02-CALLED.cob"
    ).read_text()


@pytest.fixture
def endian02_caller_source(samples_dir: Path) -> str:
    """Raw source text of ENDIAN02-CALLER.cob — caller module for the
    Oracle endianness problem demonstration.
    """
    return (
        samples_dir / "endianness" / "with-issues" / "ENDIAN02-CALLER.cob"
    ).read_text()
