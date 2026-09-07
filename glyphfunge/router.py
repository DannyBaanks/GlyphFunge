"""Router: walks each route over the playfield and emits Befunge-93 cells.

The emission model is literal IP simulation:

* ``pos`` is the cell the instruction pointer is about to enter.
* Every emitted character is written at ``pos``; then ``pos`` advances one
  cell along the current facing.
* ``turn DIR`` writes the new direction's arrow at ``pos`` (executing it
  redirects the IP) and updates the facing before advancing.
* ``go N`` writes N facing arrows.
* ``goto`` and ``branch_zero`` are resolved in a second pass, once every
  label position is known.

Nothing here guesses geometry. Every arrow on the playfield exists because
the source asked for it (directly, or via a ``goto`` straight-line walk).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .ast import Op, OpKind, Program, Route
from .geometry import ARROW_DIRECTION, DIRECTION_ARROW, DIRECTION_DELTA, Playfield

STACK_CHARS = {
    OpKind.ADD: "+",
    OpKind.SUB: "-",
    OpKind.MUL: "*",
    OpKind.DIV: "/",
    OpKind.MOD: "%",
    OpKind.DUP: ":",
    OpKind.SWAP: "\\",
    OpKind.DROP: "$",
    OpKind.PRINT_NUM: ".",
    OpKind.PRINT_CHAR: ",",
}

TERMINATORS = {OpKind.HALT, OpKind.GOTO, OpKind.BRANCH_ZERO}


@dataclass(frozen=True)
class Issue:
    kind: str      # GLYPH_ERROR | ROUTE_ERROR | STACK_ERROR | WARNING
    message: str

    def render(self) -> str:
        return f"{self.kind}:\n{self.message}"


@dataclass(frozen=True)
class Label:
    """A named join point: its cell, and the direction the IP is moving
    *while entering* that cell. (Arrow cells redirect on arrival, so a join
    onto an arrow accepts any approach direction; a join onto a non-arrow
    cell must reproduce this facing.)"""

    name: str
    x: int
    y: int
    facing: str
    route: str
    op_index: int


@dataclass(frozen=True)
class RouteStart:
    name: str
    x: int
    y: int
    facing: str


@dataclass
class LayoutResult:
    playfield: Playfield
    labels: dict[str, Label] = field(default_factory=dict)
    starts: dict[str, RouteStart] = field(default_factory=dict)
    route_ops: dict[str, tuple] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)

    def targets(self) -> dict[str, tuple[int, int, str]]:
        """All goto/branch addressable points: name -> (x, y, facing)."""
        out: dict[str, tuple[int, int, str]] = {}
        for name, s in self.starts.items():
            out[name] = (s.x, s.y, s.facing)
        for name, label in self.labels.items():
            out[name] = (label.x, label.y, label.facing)
        return out


class Router:
    def __init__(self, program: Program):
        self.program = program
        self.field = Playfield(program.canvas_width, program.canvas_height)
        self.result = LayoutResult(playfield=self.field)
        self._route_names = {route.name for route in program.routes}
        self._gotos: list[tuple[str, int, int, str, str, int]] = []
        self._branches: list[tuple[str, int, int, str, str, int]] = []

    # -- emission -----------------------------------------------------------

    def emit_all(self) -> None:
        for route in self.program.routes:
            self._emit_route(route)
        self._resolve_connections()

    def _error(self, kind: str, message: str) -> None:
        self.result.issues.append(Issue(kind, message))

    def _write(self, route: str, x: int, y: int, char: str) -> bool:
        err = self.field.write(x, y, char, route)
        if err is not None:
            self._error("GLYPH_ERROR", err)
            return False
        return True

    def _route_start(self, route: Route) -> tuple[int, int, str] | None:
        if route.name == self.program.entry:
            if (route.x, route.y, route.facing) != (None, None, None) and (
                route.x != 0 or route.y != 0 or route.facing != "right"
            ):
                self._error(
                    "ROUTE_ERROR",
                    f"entry route '{route.name}' must start at (0, 0) facing right: "
                    "Befunge-93 interpreters always begin execution there",
                )
                return None
            return 0, 0, "right"
        if route.x is None or route.y is None or route.facing is None:
            self._error(
                "ROUTE_ERROR",
                f"route '{route.name}' needs an explicit 'at X Y facing DIR' "
                "(only the entry route defaults to 0 0 right)",
            )
            return None
        if not self.field.in_bounds(route.x, route.y):
            self._error(
                "GLYPH_ERROR",
                f"route '{route.name}' starts outside canvas at ({route.x}, {route.y})",
            )
            return None
        return route.x, route.y, route.facing

    def _emit_route(self, route: Route) -> None:
        start = self._route_start(route)
        if start is None:
            return
        x, y, facing = start
        self.result.starts[route.name] = RouteStart(route.name, x, y, facing)
        self.result.route_ops[route.name] = route.ops

        pos = (x, y)
        pending_label: Optional[Op] = None
        terminated = False

        for index, op in enumerate(route.ops):
            if terminated:
                self._error(
                    "ROUTE_ERROR",
                    f"route '{route.name}' line {op.line}: unreachable operation after "
                    "halt/goto/branch_zero (dead code)",
                )
                break

            if op.kind == OpKind.LABEL:
                if pending_label is not None:
                    self._error(
                        "ROUTE_ERROR",
                        f"route '{route.name}' line {op.line}: label '{op.target}' follows "
                        f"label '{pending_label.target}' with no geometry between",
                    )
                    break
                if op.target in self._route_names:
                    self._error(
                        "ROUTE_ERROR",
                        f"label '{op.target}' (line {op.line}) shadows a route name",
                    )
                    break
                if op.target in self.result.labels:
                    self._error("ROUTE_ERROR", f"duplicate label name '{op.target}'")
                    break
                pending_label = op
                continue

            if op.kind == OpKind.GOTO:
                self._gotos.append((route.name, pos[0], pos[1], facing, op.target, op.line))
                terminated = True
                continue

            if op.kind == OpKind.BRANCH_ZERO:
                if not self._write(route.name, pos[0], pos[1], "|"):
                    terminated = True
                    continue
                if pending_label is not None:
                    self._error(
                        "ROUTE_ERROR",
                        f"label '{pending_label.target}' (line {pending_label.line}) binds to "
                        "a branch cell, which has no deterministic exit direction",
                    )
                    pending_label = None
                    terminated = True
                    continue
                self._branches.append(
                    (route.name, pos[0], pos[1], op.zero, op.nonzero, op.line)
                )
                terminated = True
                continue

            # Every remaining op emits >= 1 cell.
            chars = self._op_chars(op, facing)
            ok = True
            for k, char in enumerate(chars):
                if op.kind == OpKind.TURN and k == 0:
                    facing = op.direction
                    char = DIRECTION_ARROW[facing]
                if not self._write(route.name, pos[0], pos[1], char):
                    terminated = True
                    ok = False
                    break
                if pending_label is not None:
                    self.result.labels[pending_label.target] = Label(
                        name=pending_label.target,
                        x=pos[0],
                        y=pos[1],
                        facing=facing,
                        route=route.name,
                        op_index=index,
                    )
                    pending_label = None
                dx, dy = DIRECTION_DELTA[facing]
                pos = (pos[0] + dx, pos[1] + dy)
            if not ok:
                break

            if op.kind == OpKind.SKIP:
                dx, dy = DIRECTION_DELTA[facing]
                skipped = (pos[0], pos[1])
                if self.field.is_free(*skipped):
                    self._error(
                        "WARNING",
                        f"route '{route.name}' line {op.line}: 'skip' jumps over an empty "
                        f"cell at {skipped}; nothing there needed skipping (MAYBE pointless)",
                    )
                pos = (pos[0] + dx, pos[1] + dy)
            if op.kind == OpKind.HALT:
                terminated = True

        if pending_label is not None:
            self._error(
                "ROUTE_ERROR",
                f"label '{pending_label.target}' in route '{route.name}' (line "
                f"{pending_label.line}) is never followed by geometry",
            )
        if not terminated and route.ops:
            last = route.ops[-1]
            if last.kind not in TERMINATORS:
                self._error(
                    "ROUTE_ERROR",
                    f"route '{route.name}' has no terminator: after its last operation the IP "
                    "would keep executing spaces until it wraps the canvas; end every route "
                    "with halt, goto, or branch_zero",
                )
        if not route.ops:
            self._error("ROUTE_ERROR", f"route '{route.name}' is empty")

    def _op_chars(self, op: Op, facing: str) -> list[str]:
        kind = op.kind
        if kind == OpKind.PUSH:
            return [str(op.value)]
        if kind in STACK_CHARS:
            return [STACK_CHARS[kind]]
        if kind == OpKind.PRINT_STR:
            # String mode: opening quote, the string in reverse (so its first
            # character ends up on top of the stack for the first ','), the
            # closing quote, then one print_char per character.
            return ['"'] + list(reversed(op.text)) + ['"'] + [","] * len(op.text)
        if kind == OpKind.GO:
            return [DIRECTION_ARROW[facing]] * op.value
        if kind == OpKind.TURN:
            return ["?"]  # replaced with the new facing's arrow during emission
        if kind == OpKind.HALT:
            return ["@"]
        if kind == OpKind.SKIP:
            return ["#"]
        raise AssertionError(f"unhandled op {kind}")

    # -- connection resolution ----------------------------------------------

    def _validate_join(
        self, route: str, line: int, kind: str, name: str,
        x: int, y: int, facing: str, approach: str,
    ) -> None:
        """Validate that arriving at cell (x, y) moving ``approach`` may
        continue as target ``name`` whose declared facing is ``facing``."""
        char = self.field.cell_char(x, y)
        if char in ARROW_DIRECTION:
            return  # arrow cells redirect any arrival deterministically
        if char == " " and (x, y) not in self.field.owners:
            self._error(
                "ROUTE_ERROR",
                f"route '{route}' line {line}: {kind} '{name}' joins an empty cell "
                f"at ({x}, {y}); nothing to execute there",
            )
            return
        if char in "|_@#":
            self._error(
                "ROUTE_ERROR",
                f"route '{route}' line {line}: cannot join '{name}' at ({x}, {y}): the "
                f"cell holds '{char}' (halt/branch/skip), which has no dependable "
                "exit direction",
            )
            return
        if approach != facing:
            self._error(
                "ROUTE_ERROR",
                f"route '{route}' line {line}: joining '{name}' at ({x}, {y}) the IP "
                f"arrives moving {approach}, but '{name}' expects facing {facing}",
            )

    def _resolve_connections(self) -> None:
        targets = self.result.targets()

        for route, x, y, facing, target, line in self._gotos:
            if target not in targets:
                self._error(
                    "ROUTE_ERROR",
                    f"route '{route}' line {line}: goto '{target}' names no route or label",
                )
                continue
            tx, ty, tfacing = targets[target]
            pos = (x, y)
            limit = self.field.width * self.field.height + 1
            reached = False
            for _ in range(limit):
                if pos == (tx, ty):
                    reached = True
                    break
                if not self.field.in_bounds(pos[0], pos[1]):
                    break
                if not self._write(route, pos[0], pos[1], DIRECTION_ARROW[facing]):
                    break
                dx, dy = DIRECTION_DELTA[facing]
                pos = (pos[0] + dx, pos[1] + dy)
            if not reached:
                if not any(
                    issue.kind == "GLYPH_ERROR" for issue in self.result.issues[-1:]
                ):
                    self._error(
                        "ROUTE_ERROR",
                        f"route '{route}' line {line}: goto '{target}' cannot reach "
                        f"({tx}, {ty}) walking {facing} from ({x}, {y}) "
                        "(the target is not on this heading or lies outside the canvas)",
                    )
                continue
            self._validate_join(route, line, "goto", target, tx, ty, tfacing, facing)

        for route, bx, by, zero, nonzero, line in self._branches:
            for arm, dx, dy in ((zero, 0, 1), (nonzero, 0, -1)):
                side = "below (zero)" if dy == 1 else "above (nonzero)"
                approach = "down" if dy == 1 else "up"
                if arm not in targets:
                    self._error(
                        "ROUTE_ERROR",
                        f"route '{route}' line {line}: branch_zero arm '{arm}' names no "
                        "route or label",
                    )
                    continue
                ax, ay, afacing = targets[arm]
                if (ax, ay) != (bx + dx, by + dy):
                    self._error(
                        "ROUTE_ERROR",
                        f"route '{route}' line {line}: branch_zero arm '{arm}' must start "
                        f"exactly one cell {side} of the branch cell ({bx}, {by}), i.e. at "
                        f"({bx + dx}, {by + dy}); it starts at ({ax}, {ay})",
                    )
                    continue
                self._validate_join(route, line, "branch arm", arm, ax, ay, afacing, approach)


def route_program(program: Program) -> LayoutResult:
    router = Router(program)
    router.emit_all()
    return router.result
