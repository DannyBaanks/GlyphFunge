"""Compiler pipeline: GlyphFunge source -> Befunge-93 playfield text.

    parse  ->  route (geometry emission + connection resolution)  ->  validate
            ->  serialize

Compilation is deterministic: same source bytes in, same playfield bytes out,
on any machine. There is no clock, no randomness, no environment dependence.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from .parser import parse
from .router import Issue, LayoutResult, route_program
from .validator import validate


@dataclass
class CompileResult:
    ok: bool
    program: object | None
    layout: LayoutResult | None
    befunge: str | None
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.kind != "WARNING"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.kind == "WARNING"]

    def sha256(self) -> str:
        if self.befunge is None:
            return ""
        return hashlib.sha256(self.befunge.encode("utf-8")).hexdigest()


def compile_source(text: str) -> CompileResult:
    """Compile GlyphFunge source text to a Befunge-93 playfield."""
    try:
        program = parse(text)
    except Exception as exc:
        return CompileResult(
            ok=False,
            program=None,
            layout=None,
            befunge=None,
            issues=[Issue("PARSE_ERROR", str(exc))],
        )

    layout = route_program(program)
    issues = list(layout.issues)
    issues.extend(validate(program, layout))

    errors = [i for i in issues if i.kind != "WARNING"]
    befunge = None if errors else layout.playfield.to_text()
    return CompileResult(
        ok=not errors,
        program=program,
        layout=layout,
        befunge=befunge,
        issues=issues,
    )


def compile_file(path: str | Path) -> CompileResult:
    return compile_source(Path(path).read_text(encoding="utf-8"))


def format_issues(result: CompileResult) -> str:
    return "\n".join(issue.render() for issue in result.issues)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
