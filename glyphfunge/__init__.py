"""GlyphFunge — deterministic geometric frontend/compiler for Befunge-93."""

from __future__ import annotations

__version__ = "0.1.0"

from .compiler import CompileResult, compile_file, compile_source
from .interpreter import RunResult, run_befunge
from .parser import ParseError, parse

__all__ = [
    "CompileResult",
    "ParseError",
    "RunResult",
    "compile_file",
    "compile_source",
    "parse",
    "run_befunge",
]
