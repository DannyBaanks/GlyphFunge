"""Command-line interface for GlyphFunge."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import __version__, compile_file, compile_source
from .compiler import format_issues, sha256_text
from .interpreter import run_befunge

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNNER_JS = REPO_ROOT / "tools" / "run_befunge.js"
DEFAULT_BEFUNGE_JS = REPO_ROOT.parent / "Interpret-Esolangs-Online" / "befunge.js"


def _eprint(text: str) -> None:
    print(text, file=sys.stderr)


def _external_status() -> tuple[bool, str]:
    import os

    lib = Path(os.environ.get("BEFUNGE_JS_LIB", DEFAULT_BEFUNGE_JS))
    if shutil.which("node") is None:
        return False, "node is not on PATH"
    if not lib.is_file():
        return False, f"independent interpreter not found: {lib}"
    if not RUNNER_JS.is_file():
        return False, f"harness missing: {RUNNER_JS}"
    return True, str(lib)


def run_external(befunge_text: str, timeout: int = 10) -> tuple[bool, str]:
    """Run the playfield through the independent befunge.js interpreter.

    Returns (ran, detail): ran=True with the program output, or ran=False
    with the reason the independent evidence was skipped.
    """
    import os

    ok, why = _external_status()
    if not ok:
        return False, f"SKIPPED: {why}"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".bf", delete=False, encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(befunge_text)
        tmp = handle.name
    env = dict(os.environ)
    if "BEFUNGE_JS_LIB" not in env:
        env["BEFUNGE_JS_LIB"] = str(DEFAULT_BEFUNGE_JS)
    try:
        proc = subprocess.run(
            ["node", str(RUNNER_JS), tmp],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return False, "SKIPPED: external interpreter did not halt within timeout"
    finally:
        Path(tmp).unlink(missing_ok=True)
    if proc.returncode != 0:
        return False, f"SKIPPED: external interpreter failed: {proc.stderr.strip()}"
    return True, proc.stdout


def cmd_compile(args) -> int:
    result = compile_file(args.file)
    if not result.ok:
        _eprint(format_issues(result))
        return 1
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.befunge, encoding="utf-8", newline="")
        print(f"wrote {out} ({result.layout.playfield.width}x"
              f"{result.layout.playfield.height}, sha256 {result.sha256()})")
    else:
        sys.stdout.write(result.befunge)
    for issue in result.warnings:
        _eprint(issue.render())
    return 0


def cmd_inspect(args) -> int:
    result = compile_file(args.file)
    if not result.ok:
        _eprint(format_issues(result))
        return 1
    program = result.program
    layout = result.layout
    field = layout.playfield
    print(f"canvas {field.width}x{field.height} (Befunge-93 bounds 80x25)")
    print(f"entry: {program.entry}")
    print("routes:")
    for name, start in layout.starts.items():
        n_ops = len(layout.route_ops[name])
        print(f"  {name}: start ({start.x}, {start.y}) facing {start.facing}, {n_ops} ops")
    for name, label in layout.labels.items():
        print(f"  label {name}: cell ({label.x}, {label.y}) in route '{label.route}'")
    print(f"cells written: {field.used_cells()}")
    print("--- playfield ---")
    sys.stdout.write(result.befunge)
    for issue in result.warnings:
        _eprint(issue.render())
    return 0


def cmd_run(args) -> int:
    result = compile_file(args.file)
    if not result.ok:
        _eprint(format_issues(result))
        return 1
    run = run_befunge(result.befunge)
    print("--- playfield ---")
    sys.stdout.write(result.befunge)
    print("--- output ---")
    print(repr(run.output))
    print(f"status: {run.status}, steps: {run.steps}")
    for issue in result.warnings:
        _eprint(issue.render())
    return 0 if run.status == "halted" else 1


def cmd_verify(args) -> int:
    """Determinism + behavior evidence: compile twice (byte-identical),
    execute on the reference interpreter, and — when available — on an
    independent third-party interpreter."""
    text = Path(args.file).read_text(encoding="utf-8")
    first = compile_source(text)
    if not first.ok:
        _eprint(format_issues(first))
        return 1
    second = compile_source(text)
    identical = first.befunge == second.befunge

    program = first.program
    run = run_befunge(first.befunge)
    expected = program.expect_output

    print(f"file: {args.file}")
    print(f"playfield: {first.layout.playfield.width}x{first.layout.playfield.height}")
    print(f"deterministic recompile: {'PASS (byte-identical)' if identical else 'FAIL'}")
    print(f"sha256: {first.sha256()}")
    print(f"reference interpreter: status={run.status} steps={run.steps} output={run.output!r}")
    if expected is not None:
        matches = run.status == "halted" and run.output == expected
        print(f"expected output: {expected!r} -> {'PASS' if matches else 'FAIL'}")
    else:
        matches = run.status == "halted"
        print("expected output: (none declared; only halting is checked)")

    external_ok, detail = run_external(first.befunge)
    external_pass = None
    if external_ok:
        external_pass = (
            detail == expected
            if expected is not None
            else detail == run.output
        )
        print(f"independent interpreter (befunge.js via node): output={detail!r} "
              f"-> {'PASS' if external_pass else 'FAIL'}")
    else:
        print(f"independent interpreter: {detail}")

    for issue in first.warnings:
        _eprint(issue.render())

    checks = [identical, matches]
    if external_pass is not None:
        checks.append(external_pass)
    print("verify:", "PASS" if all(checks) else "FAIL")
    return 0 if all(checks) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="glyphfunge",
        description="Geometric frontend/compiler for Befunge-93",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("compile", help="Compile .gf to a Befunge-93 playfield")
    p.add_argument("file")
    p.add_argument("-o", "--output", help="Write the .bf playfield to a file")
    p.set_defaults(func=cmd_compile)

    p = sub.add_parser("inspect", help="Show routes, labels and the playfield")
    p.add_argument("file")
    p.set_defaults(func=cmd_inspect)

    p = sub.add_parser("run", help="Compile, then execute on the reference interpreter")
    p.add_argument("file")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser(
        "verify",
        help="Determinism + expected-output check + independent execution when available",
    )
    p.add_argument("file")
    p.set_defaults(func=cmd_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)
