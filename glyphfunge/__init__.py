"""GlyphFunge — deterministic geometric frontend/compiler for Befunge-93."""

from __future__ import annotations

__version__ = "0.5.0"

from .compiler import CompileResult, compile_file, compile_source
from .code_ir import CodeIRCompileResult, CodeIRLowering, CodeIRLoweringError, compile_code_ir, lower_code_ir
from .interpreter import RunResult, run_befunge
from .parser import ParseError, parse

__all__ = [
    "CompileResult",
    "CodeIRCompileResult",
    "CodeIRLowering",
    "CodeIRLoweringError",
    "ParseError",
    "RunResult",
    "compile_file",
    "compile_code_ir",
    "compile_source",
    "lower_code_ir",
    "parse",
    "run_befunge",
]
