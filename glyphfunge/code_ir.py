"""Closed-world Code IR v0.1 straight-line lowering.

This module deliberately consumes the canonical JSON data shape, not the
experimental Python package that produces it.  GlyphFunge remains standalone:
the host may hand it a validated Code IR document from any frontend.

Layer 1 adds declared integer locals and straight-line assignment. Reads are
expanded statically to the last assigned expression, so the generated program
still contains ordinary Befunge-93 operations, never a Code IR VM or store.
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
_COMPARE_OPS = {
    "equal": ("sub", "not"),
    "not_equal": ("sub", "not", "not"),
    "greater": ("greater",),
    "less": ("swap", "greater"),
    "greater_equal": ("swap", "greater", "not"),
    "less_equal": ("greater", "not"),
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


def _lower_expression(
    value: Any,
    path: str,
    bindings: Mapping[str, tuple[tuple[str, ...], int]],
) -> tuple[list[str], int]:
    node = _mapping(value, path)
    kind = node.get("kind")
    if kind == "IntLiteral":
        literal = node.get("value")
        if type(literal) is not int or not 0 <= literal <= 9:
            _fail(f"{path}.value must be a Befunge digit literal in 0..9")
        return [f"push {literal}"], literal

    if kind == "Variable":
        name = node.get("name")
        if not isinstance(name, str) or not name:
            _fail(f"{path}.name must be a declared local name")
        binding = bindings.get(name)
        if binding is None:
            _fail(f"{path}.name {name!r} is used before assignment")
        operations, result = binding
        return list(operations), result

    if kind == "Compare":
        operator = node.get("operator")
        compare_ops = _COMPARE_OPS.get(operator)
        if compare_ops is None:
            _fail(f"{path}.operator {operator!r} is not supported")
        left_ops, left = _lower_expression(node.get("left"), f"{path}.left", bindings)
        right_ops, right = _lower_expression(node.get("right"), f"{path}.right", bindings)
        if operator == "equal":
            result = int(left == right)
        elif operator == "not_equal":
            result = int(left != right)
        elif operator == "greater":
            result = int(left > right)
        elif operator == "less":
            result = int(left < right)
        elif operator == "greater_equal":
            result = int(left >= right)
        else:
            result = int(left <= right)
        return [*left_ops, *right_ops, *compare_ops], result

    if kind != "Binary":
        _fail(f"{path}.kind {kind!r} is not in the native arithmetic layer")
    operator = node.get("operator")
    glyph_op = _BINARY_OPS.get(operator)
    if glyph_op is None:
        _fail(f"{path}.operator {operator!r} is not supported")

    left_ops, left = _lower_expression(node.get("left"), f"{path}.left", bindings)
    right_ops, right = _lower_expression(node.get("right"), f"{path}.right", bindings)
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
    Declared integer locals may be assigned in straight-line code. ``Emit``
    statements must precede one final ``Return``.
    """
    module = _canonical_mapping(value)
    if module.get("contract_version") != "code-ir/0.1-draft":
        _fail("module.contract_version must be 'code-ir/0.1-draft'")
    functions = _list(module.get("functions"), "module.functions")
    if len(functions) != 1:
        _fail("layer 1 requires exactly one function: main")
    function = _mapping(functions[0], "module.functions[0]")
    if function.get("name") != "main":
        _fail("layer 1 entry function must be named 'main'")
    if _list(function.get("parameters"), "main.parameters"):
        _fail("layer 1 does not support function parameters")
    locals_ = _list(function.get("locals"), "main.locals")
    local_names: set[str] = set()
    for index, raw_local in enumerate(locals_):
        local = _mapping(raw_local, f"main.locals[{index}]")
        name = local.get("name")
        type_ref = _mapping(local.get("type"), f"main.locals[{index}].type")
        if not isinstance(name, str) or not name:
            _fail(f"main.locals[{index}].name must be a nonempty string")
        if name in local_names:
            _fail(f"main.locals[{index}].name {name!r} is duplicated")
        if type_ref.get("name") != "int":
            _fail(f"main.locals[{index}] must have type int")
        local_names.add(name)
    return_type = _mapping(function.get("return_type"), "main.return_type")
    if return_type.get("name") != "int":
        _fail("layer 1 main return type must be int")

    body = _mapping(function.get("body"), "main.body")
    statements = _list(body.get("statements"), "main.body.statements")
    if not statements:
        _fail("main.body must contain a final Return")

    def lower_sequence(
        raw_statements: list[Any],
        path: str,
        initial_bindings: Mapping[str, tuple[tuple[str, ...], int]],
        *,
        needs_return: bool,
    ) -> tuple[list[str], list[str], dict[str, tuple[tuple[str, ...], int]]]:
        operations: list[str] = []
        output: list[str] = []
        current = dict(initial_bindings)
        for index, raw_statement in enumerate(raw_statements):
            statement = _mapping(raw_statement, f"{path}[{index}]")
            kind = statement.get("kind")
            is_last = index == len(raw_statements) - 1
            if kind == "Assign":
                if needs_return and is_last:
                    _fail(f"{path}[{index}] cannot be final; Code IR requires Return")
                target = statement.get("target")
                if not isinstance(target, str) or target not in local_names:
                    _fail(f"{path}[{index}].target {target!r} is not a declared local")
                assigned_ops, assigned = _lower_expression(
                    statement.get("value"), f"{path}[{index}].value", current
                )
                # Straight-line expressions are pure: expansion is native
                # Befunge, rather than a hidden local-variable store.
                current[target] = (tuple(assigned_ops), assigned)
                continue
            if kind == "Emit":
                if needs_return and is_last:
                    _fail(f"{path}[{index}] cannot be final; Code IR requires Return")
                emitted_ops, emitted = _lower_expression(
                    statement.get("value"), f"{path}[{index}].value", current
                )
                operations.extend(emitted_ops)
                operations.append("print_num")
                output.append(f"{emitted} ")
                continue
            if kind == "Return" and needs_return and is_last:
                return_ops, _ = _lower_expression(
                    statement.get("value"), f"{path}[{index}].value", current
                )
                operations.extend(return_ops)
                operations.extend(("drop", "halt"))
                continue
            _fail(
                f"{path}[{index}].kind {kind!r} is unsupported; only straight-line "
                "Assign/Emit* followed by one final Return is native here"
            )
        if needs_return and (not raw_statements or _mapping(raw_statements[-1], path).get("kind") != "Return"):
            _fail(f"{path} must end with Return")
        return operations, output, current

    bindings: dict[str, tuple[tuple[str, ...], int]] = {}
    last_statement = _mapping(statements[-1], "main.body.statements[-1]")
    if last_statement.get("kind") != "If":
        route_ops, output_parts, _ = lower_sequence(
            statements, "main.body.statements", bindings, needs_return=True
        )
        routes = [("main", None, route_ops)]
        expected = "".join(output_parts)
        canvas = "canvas 80 1"
    else:
        prefix_ops, prefix_output, bindings = lower_sequence(
            statements[:-1], "main.body.statements", bindings, needs_return=False
        )
        test_ops, test_value = _lower_expression(
            last_statement.get("test"), "main.body.statements[-1].test", bindings
        )
        then_body = _mapping(last_statement.get("then_body"), "main.body.statements[-1].then_body")
        else_body = _mapping(last_statement.get("else_body"), "main.body.statements[-1].else_body")
        then_ops, then_output, _ = lower_sequence(
            _list(then_body.get("statements"), "if.then_body.statements"),
            "if.then_body.statements", bindings, needs_return=True
        )
        else_ops, else_output, _ = lower_sequence(
            _list(else_body.get("statements"), "if.else_body.statements"),
            "if.else_body.statements", bindings, needs_return=True
        )
        # Enter the branch row from the origin before evaluating the test. This
        # leaves both vertical arm cells free: a branch arm cannot share the
        # arrow that a route would otherwise need to descend into the branch.
        branch_x = 1 + len(prefix_ops) + len(test_ops)
        main_ops = ["turn down", "turn right", *prefix_ops, *test_ops, "branch_zero if_zero if_nonzero"]
        routes = [
            ("main", None, main_ops),
            ("if_nonzero", f"at {branch_x} 0 facing up", ["turn right", *then_ops]),
            ("if_zero", f"at {branch_x} 2 facing down", ["turn right", *else_ops]),
        ]
        expected = "".join([*prefix_output, *(then_output if test_value else else_output)])
        canvas = "canvas 80 3"

    source_lines = [
        "# Generated by GlyphFunge Code IR layer 2. Do not hand-edit.",
        canvas,
        "entry main",
        f"expect output {json.dumps(expected)}",
        "",
    ]
    for name, placement, operations in routes:
        header = f"route {name}" + (f" {placement}" if placement else "") + ":"
        source_lines.extend((header, *(f"    {operation}" for operation in operations), "end", ""))
    source = "\n".join(source_lines)
    canonical = json.dumps(
        module, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return CodeIRLowering(source, expected, hashlib.sha256(canonical).hexdigest())


def compile_code_ir(value: str | bytes | Mapping[str, Any]) -> CodeIRCompileResult:
    lowering = lower_code_ir(value)
    return CodeIRCompileResult(lowering, compile_source(lowering.glyphfunge))
