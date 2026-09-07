"""Static validation for GlyphFunge programs.

What is checked *exactly* (the op set has constant stack effects, so depth
tracking is not a heuristic):

* entry declared and starting at the Befunge-93 start cell (0, 0) facing
  right;
* canvas inside the Befunge-93 80x25 compatibility bounds;
* possible stack underflow along every walk of the route graph;
* unreachable routes (warning).

What is checked *approximately* (we say so):

* stack depth at a point reached twice with different depths is reported as
  MAYBE path-dependent — a loop that grows the stack per iteration trips
  this and may still be a correct program.

What is not checked: any data-dependent behavior (division by zero at
runtime, branch conditions that always go one way). Geometry and control
flow are the contract; arithmetic validity is the runtime's.
"""

from __future__ import annotations

from .ast import OpKind, Program
from .router import Issue, LayoutResult

# op kind -> (values it consumes, net stack effect)
_STACK_EFFECT = {
    OpKind.PUSH: (0, +1),
    OpKind.ADD: (2, -1),
    OpKind.SUB: (2, -1),
    OpKind.MUL: (2, -1),
    OpKind.DIV: (2, -1),
    OpKind.MOD: (2, -1),
    OpKind.DUP: (1, +1),
    OpKind.SWAP: (2, 0),
    OpKind.DROP: (1, -1),
    OpKind.PRINT_NUM: (1, -1),
    OpKind.PRINT_CHAR: (1, -1),
    OpKind.PRINT_STR: (0, 0),
    OpKind.BRANCH_ZERO: (1, -1),
}

_BEFUNGE93_W, _BEFUNGE93_H = 80, 25


def validate(program: Program, layout: LayoutResult) -> list[Issue]:
    issues: list[Issue] = []

    # -- structural contracts -------------------------------------------------
    if program.entry is None:
        issues.append(
            Issue(
                "ROUTE_ERROR",
                "missing entry: declare 'entry <route>' — a Befunge-93 program starts "
                "executing at (0, 0) facing right",
            )
        )
    elif program.entry not in layout.starts:
        issues.append(
            Issue(
                "ROUTE_ERROR",
                f"entry route '{program.entry}' has no placeable start "
                "(see its other errors above)",
            )
        )

    if program.canvas_width > _BEFUNGE93_W or program.canvas_height > _BEFUNGE93_H:
        issues.append(
            Issue(
                "GLYPH_ERROR",
                f"canvas {program.canvas_width}x{program.canvas_height} exceeds the "
                f"Befunge-93 compatibility playfield {_BEFUNGE93_W}x{_BEFUNGE93_H}",
            )
        )

    # -- reachability -----------------------------------------------------------
    referenced = {program.entry} if program.entry else set()
    for route in program.routes:
        for op in route.ops:
            if op.kind == OpKind.GOTO:
                referenced.add(op.target)
            elif op.kind == OpKind.BRANCH_ZERO:
                referenced.add(op.zero)
                referenced.add(op.nonzero)
    for route in program.routes:
        if route.name not in referenced:
            issues.append(
                Issue(
                    "WARNING",
                    f"route '{route.name}' is never entered; no path leads to it "
                    "(MAYBE dead code)",
                )
            )

    # -- static stack analysis ----------------------------------------------------
    issues.extend(_stack_analysis(program, layout))
    return issues


def _stack_analysis(program: Program, layout: LayoutResult) -> list[Issue]:
    issues: list[Issue] = []
    if program.entry is None or program.entry not in layout.route_ops:
        return issues

    def target_point(name: str):
        if name in layout.starts:
            return (name, 0)
        if name in layout.labels:
            return (layout.labels[name].route, layout.labels[name].op_index)
        return None

    reported_underflow: set[tuple[str, int]] = set()
    visited: dict[tuple[str, int], int] = {}

    def walk(route_name: str, index: int, depth: int) -> None:
        key = (route_name, index)
        if key in visited:
            if visited[key] != depth:
                issues.append(
                    Issue(
                        "WARNING",
                        f"MAYBE: stack depth at '{route_name}' op {index} is "
                        f"path-dependent (saw {visited[key]} and {depth}); the program "
                        "may still be correct — static analysis is conservative here",
                    )
                )
            return
        visited[key] = depth

        ops = layout.route_ops[route_name]
        for i in range(index, len(ops)):
            op = ops[i]
            need, effect = _STACK_EFFECT.get(op.kind, (0, 0))
            if need > depth and (route_name, i) not in reported_underflow:
                reported_underflow.add((route_name, i))
                issues.append(
                    Issue(
                        "STACK_ERROR",
                        f"possible underflow before '{op.kind.value}' on route "
                        f"'{route_name}' (line {op.line}): needs {need} value(s), "
                        f"route arrives with {depth}",
                    )
                )
            # Missing values read as 0 in most interpreters; depth already
            # floored by the need-check above, so just apply the effect.
            depth = max(0, depth + effect)
            if op.kind == OpKind.HALT:
                return
            if op.kind == OpKind.GOTO:
                target = target_point(op.target)
                if target is not None:
                    walk(target[0], target[1], depth)
                return
            if op.kind == OpKind.BRANCH_ZERO:
                for arm in (op.zero, op.nonzero):
                    target = target_point(arm)
                    if target is not None:
                        walk(target[0], target[1], depth)
                return

    walk(program.entry, 0, 0)
    return issues
