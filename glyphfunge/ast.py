"""AST nodes for the GlyphFunge DSL.

GlyphFunge source describes geometry and intent; the AST keeps that intent.
Lowering to raw Befunge-93 characters happens later, in the router.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OpKind(Enum):
    PUSH = "push"
    ADD = "add"
    SUB = "sub"
    MUL = "mul"
    DIV = "div"
    MOD = "mod"
    DUP = "dup"
    SWAP = "swap"
    DROP = "drop"
    PRINT_NUM = "print_num"
    PRINT_CHAR = "print_char"
    PRINT_STR = "print"
    BRANCH_ZERO = "branch_zero"
    GOTO = "goto"
    LABEL = "label"
    GO = "go"
    TURN = "turn"
    SKIP = "skip"
    HALT = "halt"


# Direction names used in source (`turn left`, `facing right`, ...).
DIRECTIONS = ("right", "left", "up", "down")


@dataclass(frozen=True)
class Op:
    """A single route operation, with its source position for diagnostics."""

    kind: OpKind
    line: int
    column: int
    value: int = 0        # push digit / go count
    text: str = ""        # print string literal
    target: str = ""      # goto target (route or label name)
    zero: str = ""        # branch_zero: zero arm
    nonzero: str = ""     # branch_zero: nonzero arm
    direction: str = ""   # turn direction


@dataclass(frozen=True)
class Route:
    """A named path. ``x``/``y``/``facing`` are None only for the entry route
    when declared without them; the compiler forces (0, 0, right) there."""

    name: str
    x: Optional[int]
    y: Optional[int]
    facing: Optional[str]
    ops: tuple[Op, ...]
    line: int


@dataclass(frozen=True)
class Program:
    canvas_width: int = 80
    canvas_height: int = 25
    entry: Optional[str] = None
    entry_line: int = 0
    expect_output: Optional[str] = None
    routes: tuple[Route, ...] = ()
