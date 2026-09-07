"""Reference Befunge-93 interpreter.

This is a plain, general Befunge-93 interpreter. It knows nothing about
GlyphFunge and is used (a) by `glyphfunge run|verify` and (b) by the test
suite as the in-repo executor. The test suite additionally executes the same
generated programs with an *independent third-party* interpreter
(Interpret-Esolangs-Online's befunge.js, via Node) when available.

Semantics choices, documented because Befunge-93 leaves them open:

* pop on an empty stack yields 0 (matches the reference of most interpreters);
* integer division / modulo by zero push 0;
* `.` prints the number followed by one space; `,` prints the raw character;
* the playfield is the loaded program's bounding box; edges wrap (torus);
* unknown characters are no-ops; spaces continue in the current direction;
* a step limit guards against infinite loops (error, not a hang).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunResult:
    output: str
    steps: int
    status: str  # "halted" | "step_limit_exceeded"


def run_befunge(
    source: str,
    input_text: str = "",
    step_limit: int = 1_000_000,
) -> RunResult:
    lines = source.replace("\r\n", "\n").rstrip("\n").split("\n")
    height = len(lines)
    width = max((len(line) for line in lines), default=0)
    grid = [list(line.ljust(width)) for line in lines]

    x = y = 0
    dx, dy = 1, 0
    stack: list[int] = []
    output: list[str] = []
    inp = input_text
    steps = 0

    def pop() -> int:
        return stack.pop() if stack else 0

    while steps < step_limit:
        steps += 1
        cmd = grid[y][x]

        if "0" <= cmd <= "9":
            stack.append(ord(cmd) - 48)
        elif cmd in "+-*/%":
            a, b = pop(), pop()
            if cmd == "+":
                stack.append(b + a)
            elif cmd == "-":
                stack.append(b - a)
            elif cmd == "*":
                stack.append(b * a)
            elif cmd == "/":
                if a == 0:
                    stack.append(0)
                else:
                    q = abs(b) // abs(a)
                    stack.append(-q if (b < 0) != (a < 0) else q)
            else:
                stack.append(0 if a == 0 else b % a)
        elif cmd == "!":
            stack.append(0 if pop() else 1)
        elif cmd == "`":
            a, b = pop(), pop()
            stack.append(1 if b > a else 0)
        elif cmd == ">":
            dx, dy = 1, 0
        elif cmd == "<":
            dx, dy = -1, 0
        elif cmd == "^":
            dx, dy = 0, -1
        elif cmd == "v":
            dx, dy = 0, 1
        elif cmd == "?":
            raise ValueError("GlyphFunge programs are deterministic: '?' must not appear")
        elif cmd == "_":
            dx, dy = (1, 0) if pop() == 0 else (-1, 0)
        elif cmd == "|":
            dx, dy = (0, 1) if pop() == 0 else (0, -1)
        elif cmd == '"':
            x, y = (x + dx) % width, (y + dy) % height
            while grid[y][x] != '"':
                stack.append(ord(grid[y][x]))
                x, y = (x + dx) % width, (y + dy) % height
        elif cmd == ":":
            stack.append(stack[-1] if stack else 0)
        elif cmd == "\\":
            a, b = pop(), pop()
            stack.append(a)
            stack.append(b)
        elif cmd == "$":
            pop()
        elif cmd == ".":
            output.append(f"{pop()} ")
        elif cmd == ",":
            output.append(chr(pop() % 256))
        elif cmd == "#":
            x, y = (x + dx) % width, (y + dy) % height
        elif cmd == "g":
            gy, gx = pop(), pop()
            if 0 <= gy < height and 0 <= gx < width:
                stack.append(ord(grid[gy][gx]))
            else:
                stack.append(0)
        elif cmd == "p":
            gy, gx, gv = pop(), pop(), pop()
            if 0 <= gy < height and 0 <= gx < width:
                grid[gy][gx] = chr(gv % 256)
        elif cmd == "&":
            num = ""
            while inp and inp[0] not in "0123456789-":
                inp = inp[1:]
            if inp.startswith("-"):
                num = "-"
                inp = inp[1:]
            while inp and inp[0].isdigit():
                num += inp[0]
                inp = inp[1:]
            stack.append(int(num) if num.lstrip("-") else 0)
        elif cmd == "~":
            if inp:
                stack.append(ord(inp[0]))
                inp = inp[1:]
            else:
                stack.append(-1)
        elif cmd == "@":
            return RunResult("".join(output), steps, "halted")
        # anything else (including spaces) is a no-op

        x, y = (x + dx) % width, (y + dy) % height

    return RunResult("".join(output), steps, "step_limit_exceeded")
