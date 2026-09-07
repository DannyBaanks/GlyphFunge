"""Behavioral tests for GlyphFunge.

The property that matters most: tests compile from *source text*, never from
precomputed answers, and the compiler contains no example lookup, no filename
switches, and no expected-output matching. Every expectation below is checked
by an interpreter, not by the compiler.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from glyphfunge import CodeIRLoweringError, compile_code_ir, compile_source, lower_code_ir, parse, run_befunge
from glyphfunge.cli import run_external
from glyphfunge.parser import ParseError

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"
GENERATED = ROOT / "generated"


def compile_ok(source: str) -> str:
    result = compile_source(source)
    assert result.ok, "\n".join(i.render() for i in result.issues)
    assert result.befunge is not None
    return result.befunge


def run_source(source: str) -> str:
    run = run_befunge(compile_ok(source))
    assert run.status == "halted"
    return run.output


# --------------------------------------------------------------------------
# Canonical examples: compile -> reference interpreter -> expected output
# --------------------------------------------------------------------------

ARITHMETIC = """
canvas 8 2
entry main

route main:
    push 9
    push 3
    add
    print_num
    halt
end
"""


def test_arithmetic_playfield_is_exact_single_line():
    bf = compile_ok(ARITHMETIC)
    assert bf.splitlines()[0].rstrip() == "93+.@"


def test_arithmetic_executes_to_12():
    assert run_source(ARITHMETIC) == "12 "


def test_code_ir_arithmetic_lowers_to_native_befunge():
    """Code IR is lowered to real stack operations, not interpreted by a VM."""
    fixture = (EXAMPLES / "code_ir_arithmetic.json").read_text(encoding="utf-8")
    bridge = compile_code_ir(fixture)
    assert bridge.compiled.ok
    assert bridge.lowering.expected_output == "24 "
    assert "push 9" in bridge.lowering.glyphfunge
    assert "add" in bridge.lowering.glyphfunge
    assert "mul" in bridge.lowering.glyphfunge
    assert "greater" in bridge.lowering.glyphfunge
    assert "branch_zero if_zero if_nonzero" in bridge.lowering.glyphfunge
    assert "Variable" not in bridge.lowering.glyphfunge
    assert "Emit" not in bridge.lowering.glyphfunge
    run = run_befunge(bridge.compiled.befunge)
    assert run.status == "halted"
    assert run.output == "24 "


def test_code_ir_is_deterministic_and_runs_independently():
    fixture = (EXAMPLES / "code_ir_arithmetic.json").read_text(encoding="utf-8")
    first = compile_code_ir(fixture)
    second = compile_code_ir(fixture)
    assert first.lowering == second.lowering
    assert first.compiled.befunge == second.compiled.befunge
    ran, output = run_external(first.compiled.befunge)
    if not ran:
        pytest.skip(output)
    assert output == "24 "


def test_code_ir_compile_matches_committed_bridge_artifact():
    fixture = (EXAMPLES / "code_ir_arithmetic.json").read_text(encoding="utf-8")
    committed = (GENERATED / "code_ir_arithmetic.bf").read_text(encoding="utf-8")
    bridge = compile_code_ir(fixture)
    assert bridge.compiled.befunge == committed
    assert bridge.compiled.sha256() == "a60e2bd45dd6a76c12d3c72463357a736730ba81118d143614aa8a4f88a76879"


def test_code_ir_rejects_assignment_to_undeclared_local():
    module = {
        "contract_version": "code-ir/0.1-draft",
        "functions": [{
            "name": "main",
            "parameters": [],
            "locals": [],
            "return_type": {"name": "int"},
            "body": {"statements": [
                {"kind": "Assign", "target": "x", "value": {"kind": "IntLiteral", "value": 1}},
                {"kind": "Return", "value": {"kind": "IntLiteral", "value": 0}},
            ]},
        }],
    }
    with pytest.raises(CodeIRLoweringError, match="not a declared local"):
        lower_code_ir(module)


def test_code_ir_rejects_read_before_assignment():
    module = {
        "contract_version": "code-ir/0.1-draft",
        "functions": [{
            "name": "main",
            "parameters": [],
            "locals": [{"name": "x", "type": {"name": "int"}}],
            "return_type": {"name": "int"},
            "body": {"statements": [
                {"kind": "Emit", "value": {"kind": "Variable", "name": "x"}},
                {"kind": "Return", "value": {"kind": "IntLiteral", "value": 0}},
            ]},
        }],
    }
    with pytest.raises(CodeIRLoweringError, match="used before assignment"):
        lower_code_ir(module)


def test_code_ir_preserves_floor_contract_by_rejecting_negative_division():
    module = {
        "contract_version": "code-ir/0.1-draft",
        "functions": [{
            "name": "main",
            "parameters": [],
            "locals": [],
            "return_type": {"name": "int"},
            "body": {"statements": [
                {"kind": "Emit", "value": {"kind": "Binary", "operator": "floor_divide",
                    "left": {"kind": "Binary", "operator": "subtract",
                             "left": {"kind": "IntLiteral", "value": 1},
                             "right": {"kind": "IntLiteral", "value": 2}},
                    "right": {"kind": "IntLiteral", "value": 2}}},
                {"kind": "Return", "value": {"kind": "IntLiteral", "value": 0}},
            ]},
        }],
    }
    with pytest.raises(CodeIRLoweringError, match="nonnegative"):
        lower_code_ir(module)


def test_all_canonical_examples_execute():
    expected = {
        "arithmetic.gf": "12 ",
        "branch.gf": "0 ",
        "countdown.gf": "5 4 3 2 1 0 ",
        "hello.gf": "Hello, World!",
        "fizzbuzz.gf": "1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz ",
        "meta_befunge.gf": "93+.@",
    }
    for name, want in expected.items():
        source = (EXAMPLES / name).read_text(encoding="utf-8")
        assert run_source(source) == want, name


# --------------------------------------------------------------------------
# Determinism: same source -> byte-identical playfield, and identical to the
# committed generated/*.bf artifacts.
# --------------------------------------------------------------------------

ALL_EXAMPLES = ["arithmetic", "branch", "countdown", "hello", "fizzbuzz", "meta_befunge"]


@pytest.mark.parametrize("name", ALL_EXAMPLES)
def test_compile_is_byte_identical_across_runs(name):
    source = (EXAMPLES / f"{name}.gf").read_text(encoding="utf-8")
    a = compile_ok(source)
    b = compile_ok(source)
    assert a == b
    assert hashlib.sha256(a.encode()).hexdigest() == hashlib.sha256(b.encode()).hexdigest()


@pytest.mark.parametrize("name", ALL_EXAMPLES)
def test_compile_matches_committed_generated_file(name):
    source = (EXAMPLES / f"{name}.gf").read_text(encoding="utf-8")
    committed = (GENERATED / f"{name}.bf").read_text(encoding="utf-8")
    assert compile_ok(source) == committed


def test_known_sha256_pin_countdown():
    # If this hash ever changes, the layout algorithm changed; that must be a
    # deliberate, documented event.
    bf = (GENERATED / "countdown.bf").read_text(encoding="utf-8")
    assert (
        hashlib.sha256(bf.encode("utf-8")).hexdigest()
        == "4cb51acb1184e87cab9176644cc8443dbbe51a1c1e15f94c06cea02e67220085"
    )


# --------------------------------------------------------------------------
# Geometry structure of the flagship loop
# --------------------------------------------------------------------------

def test_countdown_loop_is_a_physical_rectangle():
    bf = compile_ok((EXAMPLES / "countdown.gf").read_text(encoding="utf-8"))
    rows = bf.splitlines()
    assert rows[0][:2] == "5v"
    assert rows[1].strip() == "v<<<<<<" or rows[1].lstrip().startswith("v<<<<<<")
    assert rows[2].lstrip().startswith(">:.1-:|")
    assert rows[3].rstrip().endswith(".")
    assert rows[4].rstrip().endswith("@")


def test_branch_example_uses_two_physically_distinct_corridors():
    from glyphfunge.compiler import compile_source as _compile

    result = _compile((EXAMPLES / "branch.gf").read_text(encoding="utf-8"))
    assert result.ok
    z = result.layout.starts["zero_hit"]
    n = result.layout.starts["nonzero_hit"]
    assert (z.x, z.y) != (n.x, n.y)
    # both branch arms sit exactly one cell away from the '|'
    field = result.layout.playfield
    bx = by = None
    for yy in range(field.height):
        for xx in range(field.width):
            if field.grid[yy][xx] == "|":
                bx, by = xx, yy
    assert bx is not None
    assert (z.x, z.y) == (bx, by + 1)
    assert (n.x, n.y) == (bx, by - 1)


def test_branch_both_arms_execute_correctly():
    zero_source = (EXAMPLES / "branch.gf").read_text(encoding="utf-8")
    assert "push 0" in zero_source
    nonzero_source = zero_source.replace("push 0", "push 4")
    assert run_source(zero_source) == "0 "
    assert run_source(nonzero_source) == "9 "


# --------------------------------------------------------------------------
# String mode
# --------------------------------------------------------------------------

def test_hello_world_via_string_mode():
    bf = compile_ok((EXAMPLES / "hello.gf").read_text(encoding="utf-8"))
    # The playfield stores the string reversed inside quotes, then prints
    # one character at a time.
    assert bf.startswith('"!dlroW ,olleH"')
    assert run_befunge(bf).output == "Hello, World!"


# --------------------------------------------------------------------------
# Validation errors: precise messages in the documented formats
# --------------------------------------------------------------------------

def test_missing_entry_is_route_error():
    result = compile_source("canvas 8 2\nroute a:\n    halt\nend\n")
    kinds = [i.kind for i in result.issues]
    assert "ROUTE_ERROR" in kinds
    assert any("missing entry" in i.message for i in result.issues)


def test_overlap_error_names_both_routes_and_cell():
    source = """
canvas 10 4
entry main

route main:
    push 1
    turn down
    halt
end

route bad at 1 0 facing right:
    push 9
    halt
end
"""
    result = compile_source(source)
    assert not result.ok
    text = "\n".join(i.render() for i in result.issues)
    assert "overlaps" in text and "(1, 0)" in text


def test_route_without_terminator_is_error():
    source = "canvas 8 2\nentry main\nroute main:\n    push 1\nend\n"
    result = compile_source(source)
    assert not result.ok
    assert any("no terminator" in i.message for i in result.issues)


def test_dead_code_after_halt_is_error():
    source = "canvas 8 2\nentry main\nroute main:\n    halt\n    push 1\nend\n"
    result = compile_source(source)
    assert not result.ok
    assert any("unreachable" in i.message for i in result.issues)


def test_stack_underflow_is_reported_as_possible():
    source = "canvas 8 2\nentry main\nroute main:\n    push 1\n    add\n    halt\nend\n"
    result = compile_source(source)
    assert not result.ok
    kinds = {i.kind for i in result.issues}
    assert "STACK_ERROR" in kinds
    assert any("possible underflow" in i.message for i in result.issues)


def test_canvas_beyond_befunge93_bounds_is_error():
    source = "canvas 100 30\nentry main\nroute main:\n    halt\nend\n"
    result = compile_source(source)
    assert not result.ok
    assert any("80x25" in i.message for i in result.issues)


def test_goto_unknown_target_is_error():
    source = "canvas 8 2\nentry main\nroute main:\n    push 1\n    goto nowhere\nend\n"
    result = compile_source(source)
    assert not result.ok
    assert any("names no route or label" in i.message for i in result.issues)


def test_branch_arm_not_adjacent_is_error():
    source = """
canvas 8 4
entry main

route main:
    push 0
    dup
    branch_zero zed nope
end

route zed at 3 3 facing down:
    halt
end

route nope at 1 0 facing up:
    halt
end
"""
    result = compile_source(source)
    assert not result.ok
    assert any("exactly one cell" in i.message for i in result.issues)


def test_push_multi_digit_rejected():
    with pytest.raises(ParseError):
        parse("canvas 8 2\nentry main\nroute main:\n    push 42\nend\n")


def test_entry_route_not_at_origin_is_rejected():
    source = (
        "canvas 8 2\nentry main\n"
        "route main at 2 1 facing right:\n    halt\nend\n"
    )
    result = compile_source(source)
    assert not result.ok
    assert any("must start at (0, 0)" in i.message for i in result.issues)


# --------------------------------------------------------------------------
# The no-cheating test: independent third-party Befunge-93 interpreter
# (Interpret-Esolangs-Online befunge.js via node). If unavailable, the test
# SKIPS *loudly* — it never fakes a pass.
# --------------------------------------------------------------------------

def _external_available() -> tuple[bool, str]:
    lib = os.environ.get("BEFUNGE_JS_LIB", str(ROOT.parent / "Interpret-Esolangs-Online" / "befunge.js"))
    if shutil.which("node") is None:
        return False, "node is not installed"
    if not Path(lib).is_file():
        return False, f"independent interpreter not found at {lib}"
    return True, lib


EXT_OK, EXT_REASON = _external_available()


@pytest.mark.skipif(not EXT_OK, reason=f"independent interpreter unavailable: {EXT_REASON}")
@pytest.mark.parametrize("name", ALL_EXAMPLES)
def test_independent_interpreter_agrees(name):
    source = (EXAMPLES / f"{name}.gf").read_text(encoding="utf-8")
    bf = compile_ok(source)
    expected = parse(source).expect_output
    assert expected is not None  # every canonical example declares its output
    ran, output = run_external(bf)
    assert ran, output  # if it ran, it produced output
    reference = run_befunge(bf)
    assert reference.status == "halted"
    assert output == reference.output == expected


def test_meta_emits_a_valid_befunge_program():
    """Self-reference chain: compile meta -> run -> its output is Befunge ->
    run THAT -> '12 '. Two levels, no compiler involved downstream."""
    source = (EXAMPLES / "meta_befunge.gf").read_text(encoding="utf-8")
    level1 = run_source(source)
    assert level1 == "93+.@"  # the emitted program
    level2 = run_befunge(level1)
    assert level2.status == "halted"
    assert level2.output == "12 "


def test_route_entered_only_via_label_is_not_dead_code():
    # Regression: a goto may target a *label* inside another route; that
    # route is reachable through the label and must not be flagged dead.
    source = """
canvas 8 5
entry main

route main:
    push 5
    turn down
    goto work
end

route worker at 1 3 facing down:
    label work
    print_num
    halt
end
"""
    result = compile_source(source)
    assert result.ok, "\n".join(i.render() for i in result.issues)
    assert not any(
        "never entered" in i.message for i in result.issues
    ), "label-entered route wrongly flagged as unreachable"


def test_independent_evidence_status_is_explicit(capsys=None):
    # Documentation-only test: the report must state whether the independent
    # run happened, and why not if it didn't.
    if not EXT_OK:
        print(f"INDEPENDENT EXECUTION: SKIPPED — {EXT_REASON}")
    else:
        print(f"INDEPENDENT EXECUTION: AVAILABLE — {EXT_REASON}")
    assert True
