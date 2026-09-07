"""Canvas geometry for GlyphFunge.

Conceptually inherited from GlyphFuck: a rectangular grid of single
characters, explicit bounds (no clipping here: out-of-canvas writes are
*errors*, because in Befunge every cell is program semantics), and per-cell
ownership so overlap detection can name the colliding routes.
"""

from __future__ import annotations

from dataclasses import dataclass

DIRECTION_DELTA = {
    "right": (1, 0),
    "left": (-1, 0),
    "up": (0, -1),
    "down": (0, 1),
}

DIRECTION_ARROW = {
    "right": ">",
    "left": "<",
    "up": "^",
    "down": "v",
}

ARROW_DIRECTION = {arrow: name for name, arrow in DIRECTION_ARROW.items()}

SPACE = " "


@dataclass(frozen=True)
class CellWrite:
    """What a single playfield cell contains and who put it there."""

    char: str
    owner: str  # route name


class Playfield:
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self.grid: list[list[str]] = [[SPACE] * width for _ in range(height)]
        self.owners: dict[tuple[int, int], str] = {}

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def cell_char(self, x: int, y: int) -> str:
        if self.in_bounds(x, y):
            return self.grid[y][x]
        return SPACE

    def owner(self, x: int, y: int) -> str | None:
        return self.owners.get((x, y))

    def is_free(self, x: int, y: int) -> bool:
        return self.cell_char(x, y) == SPACE and (x, y) not in self.owners

    def write(self, x: int, y: int, char: str, route: str) -> str | None:
        """Write a cell. Returns None on success, or an error message.

        Overwriting with the *same* character is a legal intentional merge
        (a loop re-entering its own corridor); overwriting with a different
        character is an overlap error naming both routes.
        """
        if not self.in_bounds(x, y):
            return f"route '{route}' writes outside canvas at ({x}, {y})"
        existing = self.grid[y][x]
        if (x, y) in self.owners and existing != char:
            other = self.owners[(x, y)]
            if other != route:
                return (
                    f"route '{route}' overlaps route '{other}' at ({x}, {y}) "
                    f"('{existing}' vs '{char}')"
                )
            return (
                f"route '{route}' crosses itself at ({x}, {y}) with a different "
                f"character ('{existing}' vs '{char}')"
            )
        self.grid[y][x] = char
        self.owners.setdefault((x, y), route)
        return None

    def used_cells(self) -> int:
        return len(self.owners)

    def to_text(self) -> str:
        """Exact rectangular serialization: every row padded to canvas width,
        LF line endings, single trailing newline. Deterministic by construction."""
        return "\n".join("".join(row) for row in self.grid) + "\n"
