"""Lexer and parser for the GlyphFunge DSL.

Mirrors the GlyphFuck parser structure (regex token table, explicit line
structure, ParseError with exact source positions) because that architecture
proved honest: no guessing, no silent recovery.
"""

from __future__ import annotations

import ast as py_ast
import re
from dataclasses import dataclass

from .ast import DIRECTIONS, Op, OpKind, Program, Route


class ParseError(Exception):
    """Syntax error carrying an exact source location."""

    def __init__(self, message: str, line: int, column: int):
        self.line = line
        self.column = column
        super().__init__(f"Parse error at {line}:{column}: {message}")


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    line: int
    column: int


class Lexer:
    TOKEN_SPEC = [
        ("COMMENT", r"\#[^\n]*"),
        ("CANVAS", r"canvas\b"),
        ("ENTRY", r"entry\b"),
        ("ROUTE", r"route\b"),
        ("END", r"end\b"),
        ("EXPECT", r"expect\b"),
        ("OUTPUT", r"output\b"),
        ("AT", r"at\b"),
        ("FACING", r"facing\b"),
        ("PUSH", r"push\b"),
        ("PRINT_NUM", r"print_num\b"),
        ("PRINT_CHAR", r"print_char\b"),
        ("PRINT", r"print\b"),
        ("ADD", r"add\b"),
        ("SUB", r"sub\b"),
        ("MUL", r"mul\b"),
        ("DIV", r"div\b"),
        ("MOD", r"mod\b"),
        ("DUP", r"dup\b"),
        ("SWAP", r"swap\b"),
        ("DROP", r"drop\b"),
        ("BRANCH_ZERO", r"branch_zero\b"),
        ("GOTO", r"goto\b"),
        ("LABEL", r"label\b"),
        ("GO", r"go\b"),
        ("TURN", r"turn\b"),
        ("SKIP", r"skip\b"),
        ("HALT", r"halt\b"),
        ("DIR", r"right\b|left\b|up\b|down\b"),
        ("STRING", r'"(?:[^"\\]|\\.)*"'),
        ("NUMBER", r"-?\d+"),
        ("COLON", r":"),
        ("IDENT", r"[a-zA-Z_][a-zA-Z0-9_]*"),
        ("NEWLINE", r"\r?\n"),
        ("WS", r"[ \t]+"),
        ("MISMATCH", r"."),
    ]

    def __init__(self, text: str):
        self.tokens: list[Token] = []
        self._tokenize(text)

    def _tokenize(self, text: str) -> None:
        line = 1
        column = 1
        regex = "|".join(f"(?P<{name}>{pattern})" for name, pattern in self.TOKEN_SPEC)
        for match in re.finditer(regex, text):
            kind = match.lastgroup
            value = match.group()
            assert kind is not None
            if kind == "NEWLINE":
                self.tokens.append(Token(kind, value, line, column))
                line += 1
                column = 1
            elif kind in {"WS", "COMMENT"}:
                column += len(value)
            elif kind == "MISMATCH":
                raise ParseError(f"Unexpected character {value!r}", line, column)
            else:
                self.tokens.append(Token(kind, value, line, column))
                column += len(value)
        self.tokens.append(Token("EOF", "", line, column))


SIMPLE_OPS = {
    "ADD": OpKind.ADD,
    "SUB": OpKind.SUB,
    "MUL": OpKind.MUL,
    "DIV": OpKind.DIV,
    "MOD": OpKind.MOD,
    "DUP": OpKind.DUP,
    "SWAP": OpKind.SWAP,
    "DROP": OpKind.DROP,
    "PRINT_NUM": OpKind.PRINT_NUM,
    "PRINT_CHAR": OpKind.PRINT_CHAR,
    "SKIP": OpKind.SKIP,
    "HALT": OpKind.HALT,
}


class Parser:
    def __init__(self, text: str):
        self.tokens = Lexer(text).tokens
        self.pos = 0

    # -- token plumbing ----------------------------------------------------

    def current(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        token = self.current()
        if token.type != "EOF":
            self.pos += 1
        return token

    def expect(self, token_type: str) -> Token:
        token = self.current()
        if token.type != token_type:
            raise ParseError(
                f"Expected {token_type}, got {token.type} ({token.value!r})",
                token.line,
                token.column,
            )
        return self.advance()

    def _skip_newlines(self) -> None:
        while self.current().type == "NEWLINE":
            self.advance()

    def _end_of_line(self) -> None:
        if self.current().type not in {"NEWLINE", "EOF"}:
            token = self.current()
            raise ParseError("Expected end of line", token.line, token.column)

    def _decode_string(self, token: Token) -> str:
        try:
            value = py_ast.literal_eval(token.value)
        except (SyntaxError, ValueError) as exc:
            raise ParseError("Invalid string literal", token.line, token.column) from exc
        if not isinstance(value, str):
            raise ParseError("Expected a string literal", token.line, token.column)
        return value

    # -- grammar -----------------------------------------------------------

    def parse(self) -> Program:
        canvas_width, canvas_height = 80, 25
        entry = None
        entry_line = 0
        expect_output = None
        routes: list[Route] = []
        seen_names: set[str] = set()

        while True:
            self._skip_newlines()
            token = self.current()
            if token.type == "EOF":
                break
            if token.type == "CANVAS":
                self.advance()
                canvas_width = int(self.expect("NUMBER").value)
                canvas_height = int(self.expect("NUMBER").value)
                if canvas_width <= 0 or canvas_height <= 0:
                    raise ParseError(
                        "canvas width and height must be positive", token.line, token.column
                    )
                self._end_of_line()
            elif token.type == "ENTRY":
                self.advance()
                if entry is not None:
                    raise ParseError("entry specified more than once", token.line, token.column)
                entry = self.expect("IDENT").value
                entry_line = token.line
                self._end_of_line()
            elif token.type == "EXPECT":
                self.advance()
                out_tok = self.expect("OUTPUT")
                str_tok = self.expect("STRING")
                if expect_output is not None:
                    raise ParseError(
                        "expect output specified more than once", token.line, token.column
                    )
                expect_output = self._decode_string(str_tok)
                self._end_of_line()
            elif token.type == "ROUTE":
                route = self._parse_route()
                if route.name in seen_names:
                    raise ParseError(
                        f"Duplicate route name {route.name!r}", token.line, token.column
                    )
                seen_names.add(route.name)
                routes.append(route)
            else:
                raise ParseError(
                    f"Unexpected token {token.type} ({token.value!r})", token.line, token.column
                )

        return Program(
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            entry=entry,
            entry_line=entry_line,
            expect_output=expect_output,
            routes=tuple(routes),
        )

    def _parse_route(self) -> Route:
        header = self.expect("ROUTE")
        name = self.expect("IDENT").value
        x = y = None
        facing = None
        if self.current().type == "AT":
            self.advance()
            x = int(self.expect("NUMBER").value)
            y = int(self.expect("NUMBER").value)
            self.expect("FACING")
            dir_tok = self.expect("DIR")
            facing = dir_tok.value
        self.expect("COLON")
        self._end_of_line()
        self._skip_newlines()

        ops: list[Op] = []
        while self.current().type not in {"END", "EOF"}:
            ops.append(self._parse_op())
            self._end_of_line()
            self._skip_newlines()

        if self.current().type == "EOF":
            token = self.current()
            raise ParseError(
                f"Unterminated route {name!r}; expected 'end'", token.line, token.column
            )
        self.expect("END")
        return Route(name=name, x=x, y=y, facing=facing, ops=tuple(ops), line=header.line)

    def _parse_op(self) -> Op:
        token = self.current()
        line, column = token.line, token.column

        if token.type in SIMPLE_OPS:
            self.advance()
            return Op(SIMPLE_OPS[token.type], line, column)

        if token.type == "PUSH":
            self.advance()
            num = self.expect("NUMBER")
            value = int(num.value)
            if not 0 <= value <= 9:
                raise ParseError(
                    "push only supports single digits 0..9 in v0.1 "
                    "(Befunge-93 digit push); compose larger numbers with arithmetic",
                    num.line,
                    num.column,
                )
            return Op(OpKind.PUSH, line, column, value=value)

        if token.type == "PRINT":
            self.advance()
            str_tok = self.expect("STRING")
            text = self._decode_string(str_tok)
            if '"' in text:
                raise ParseError(
                    "print strings cannot contain '\"' in v0.1 (it would close string mode)",
                    str_tok.line,
                    str_tok.column,
                )
            if not text:
                raise ParseError("print string must not be empty", str_tok.line, str_tok.column)
            for ch in text:
                if not (32 <= ord(ch) < 127):
                    raise ParseError(
                        "print strings must be printable ASCII in v0.1",
                        str_tok.line,
                        str_tok.column,
                    )
            return Op(OpKind.PRINT_STR, line, column, text=text)

        if token.type == "BRANCH_ZERO":
            self.advance()
            zero = self.expect("IDENT").value
            nonzero = self.expect("IDENT").value
            if zero == nonzero:
                raise ParseError(
                    "branch_zero arms must be two different routes/labels", line, column
                )
            return Op(OpKind.BRANCH_ZERO, line, column, zero=zero, nonzero=nonzero)

        if token.type == "GOTO":
            self.advance()
            return Op(OpKind.GOTO, line, column, target=self.expect("IDENT").value)

        if token.type == "LABEL":
            self.advance()
            return Op(OpKind.LABEL, line, column, target=self.expect("IDENT").value)

        if token.type == "GO":
            self.advance()
            num = self.expect("NUMBER")
            value = int(num.value)
            if value < 1:
                raise ParseError("go requires a count >= 1", num.line, num.column)
            return Op(OpKind.GO, line, column, value=value)

        if token.type == "TURN":
            self.advance()
            dir_tok = self.expect("DIR")
            return Op(OpKind.TURN, line, column, direction=dir_tok.value)

        raise ParseError(
            f"Unexpected token inside route: {token.type} ({token.value!r})", line, column
        )


def parse(text: str) -> Program:
    """Parse GlyphFunge source into an immutable program AST."""
    return Parser(text).parse()
