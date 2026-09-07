"""Closed-world Code IR v0.1 arithmetic lowering.

This module deliberately consumes the canonical JSON data shape, not the
experimental Python package that produces it.  GlyphFunge remains standalone:
the host may hand it a validated Code IR document from any frontend.

Layer 0 is intentionally narrow.  It lowers one parameterless ``main``
function with literal arithmetic, ``Emit``, and a final ``Return`` directly to
GlyphFunge operations.  The result is ordinary Befunge-93, never a Code IR VM.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .compiler import CompileResult, compile_source

_I32_MIN = -(2**31)
_I32_MAX = 2**31 - 1
_BINARY_OPS = {
    "add": "add",
    "subtract": "sub",
    "multiply": "mul",
    "floor_divide": "div",
    "modulo": "mod",
}


@dataclass(frozen=True)
class CodeIRLoweringError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


@dataclass(frozen=True)
class CodeIRLowering:
    """The inspectable bridge artifact before GlyphFunge compiles it."""

    glyphfunge: str
    expected_output: str
    code_ir_sha256: str


@dataclass(frozen=True)
class CodeIRCompileResult:
    lowering: CodeIRLowering
    compiled: CompileResult


def _fail(message: str) -> None:
    raise CodeIRLoweringError("UNSUPPORTED_CODE_IR", message)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail(f"{path} must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(f"{path} must be an array")
    return value


def _check_i32(value: int, path: str) -> int:
    if not _I32_MIN <= value <= _I32_MAX:
        _fail(f"{path} evaluates outside the declared signed 32-bit domain: {value}")
    return value


def _lower_expression(value: Any, path: str) -> tuple[list[str], int]:
    node = _mapping(value, path)
    kind = node.get("kind")
    if kind == "IntLiteral":
        literal = node.get("value")
        if type(literal) is not int or not 0 <= literal <= 9:
            _fail(f"{path}.value must be a Befunge digit literal in 0..9")
        return [f"push {literal}"], literal

    if kind != "Binary":
        _fail(f"{path}.kind {kind!r} is not in the native arithmetic layer")
    operator = node.get("operator")
    glyph_op = _BINARY_OPS.get(operator)
    if glyph_op is None:
        _fail(f"{path}.operator {operator!r} is not supported")

    left_ops, left = _lower_expression(node.get("left"), f"{path}.left")
    right_ops, right = _lower_expression(node.get("right"), f"{path}.right")
    if operator in {"floor_divide", "modulo"}:
        if right == 0:
            _fail(f"{path} divides by zero")
        # Befunge's division is truncating. It equals Code IR's floor model
        # only in the nonnegative region declared by this first layer.
        if left < 0 or right < 0:
            _fail(f"{path} needs nonnegative operands for Code IR floor semantics")

    if operator == "add":
        result = left + right
    elif operator == "subtract":
        result = left - right
    elif operator == "multiply":
        result = left * right
    elif operator == "floor_divide":
        result = left // right
    else:
        result = left % right
    return [*left_ops, *right_ops, glyph_op], _check_i32(result, path)


def _canonical_mapping(value: str | bytes | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise CodeIRLoweringError("INVALID_CODE_IR_JSON", str(exc)) from exc
    return _mapping(value, "module")


def lower_code_ir(value: str | bytes | Mapping[str, Any]) -> CodeIRLowering:
    """Lower the Code IR arithmetic layer to readable GlyphFunge source.

    The accepted document is the canonical JSON shape emitted by Code IR v0.1.
    Its only entry convention is a parameterless ``main() -> int`` function.
    ``Emit`` statements must precede one final ``Return``.
    """
    module = _canonical_mapping(value)
    if module.get("contract_version") != "code-ir/0.1-draft":
        _fail("module.contract_version must be 'code-ir/0.1-draft'")
    functions = _list(module.get("functions"), "module.functions")
    if len(functions) != 1:
        _fail("layer 0 requires exactly one function: main")
    function = _mapping(functions[0], "module.functions[0]")
    if function.get("name") != "main":
        _fail("layer 0 entry function must be named 'main'")
    if _list(function.get("parameters"), "main.parameters"):
        _fail("layer 0 does not support function parameters")
    if _list(function.get("locals"), "main.locals"):
        _fail("layer 0 does not support variables or locals")
    return_type = _mapping(function.get("return_type"), "main.return_type")
    if return_type.get("name") != "int":
        _fail("layer 0 main return type must be int")

    body = _mapping(function.get("body"), "main.body")
    statements = _list(body.get("statements"), "main.body.statements")
    if not statements:
        _fail("main.body must contain a final Return")

    route_ops: list[str] = []
    output_parts: list[str] = []
    for index, raw_statement in enumerate(statements):
        statement = _mapping(raw_statement, f"main.body.statements[{index}]")
        kind = statement.get("kind")
        is_last = index == len(statements) - 1
        if kind == "Emit":
            if is_last:
                _fail("Emit cannot be the final statement; Code IR requires Return")
            emitted_ops, emitted = _lower_expression(
                statement.get("value"), f"main.body.statements[{index}].value"
            )
            route_ops.extend(emitted_ops)
            route_ops.append("print_num")
            output_parts.append(f"{emitted} ")
            continue
        if kind == "Return" and is_last:
            return_ops, _ = _lower_expression(
                statement.get("value"), f"main.body.statements[{index}].value"
            )
            route_ops.extend(return_ops)
            route_ops.extend(("drop", "halt"))
            continue
        _fail(
            f"main.body.statements[{index}].kind {kind!r} is unsupported; "
            "only Emit* followed by one final Return is native in layer 0"
        )

    expected = "".join(output_parts)
    source = "\n".join(
        [
            "# Generated by GlyphFunge Code IR layer 0. Do not hand-edit.",
            "canvas 80 1",
            "entry main",
            f"expect output {json.dumps(expected)}",
            "",
            "route main:",
            *(f"    {operation}" for operation in route_ops),
            "end",
            "",
        ]
    )
    canonical = json.dumps(
        module, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return CodeIRLowering(source, expected, hashlib.sha256(canonical).hexdigest())


def compile_code_ir(value: str | bytes | Mapping[str, Any]) -> CodeIRCompileResult:
    lowering = lower_code_ir(value)
    return CodeIRCompileResult(lowering, compile_source(lowering.glyphfunge))
