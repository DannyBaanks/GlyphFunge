# GlyphFunge v0.4 — Design

GlyphFunge is a deterministic geometric frontend/compiler for Befunge-93.

> **Geometry is control flow. Describe the path. Let Befunge crawl it.**

## Why it exists

GlyphFuck was created because LLMs (and tired humans) can reliably describe
the *intent* of an ASCII artifact but fail at maintaining exact
character-by-character spatial layout. Befunge has the complementary
problem: exact spatial layout **is** the program semantics. GlyphFunge
composes the two: you describe geometry and intent, the compiler emits the
exact character grid, an ordinary Befunge-93 interpreter executes it.

```
GlyphFuck-style geometric authoring (routes, turns, joins)
        ↓
GlyphFunge pipeline (parse → route → validate → serialize)
        ↓
ordinary Befunge-93 playfield (.bf text file)
        ↓
any Befunge-93 interpreter (none of GlyphFunge needed at runtime)
```

## What comes conceptually from GlyphFuck

Inspected before writing a line (see `../GlyphFuck/`). Reused as **concepts**
— deliberately not as imports, so GlyphFunge has zero dependencies:

| GlyphFuck concept | GlyphFunge counterpart |
|---|---|
| `canvas W H` + rectangular grid | `canvas W H` + `Playfield` (geometry.py) |
| Regex token table + line-structured parser, `ParseError` with `line:col` | same shape (parser.py) |
| Immutable frozen-dataclass AST | ast.py (`Program`, `Route`, `Op`) |
| Explicit ops, no hidden layout | routes = explicit `go`/`turn`/`label`/`goto`; only `goto` adds arrows, on a straight line, deterministically |
| Per-pixel ownership + `expect no_overlap` | per-cell ownership; overlaps report both route names and the coordinate |
| `expect …` contracts | `expect output "…"` + validator (bounds, terminator, stack, reachability) |
| Determinism (same source → same bytes) | two-pass compile is pure; tests pin the SHA-256 |
| CLI: subcommands, exit codes, stderr for problems | `compile / inspect / run / verify` |

## What is Befunge-specific (invented here)

- The playfield **is** the program. Every cell executes. There is no "dead
  canvas": a space is a no-op instruction, an arrow is a steering
  instruction.
- The emission model in `router.py` is a literal simulation of the Befunge
  instruction pointer: write at the current cell, move one cell in the
  current direction. Nothing auto-placed beyond what the ops say.
- `branch_zero A B` emits `|`: **zero → down, nonzero → up** (Befunge-93
  semantics of `|`). Both arms must be declared one cell away from the
  branch cell; the compiler refuses any other geometry instead of guessing.
- `goto X` walks in a straight line drawing arrows until it enters the
  target cell. Joins must reproduce the target's declared facing — with one
  honest exception: an **arrow cell is a wildcard join**, because executing
  an arrow overwrites the direction no matter how you arrive.
- **String mode**: `print "Hello"` emits `"` + the string reversed + `"` +
  one `,` per character, so forward text survives Befunge's push order.
- Every route must terminate in `halt` / `goto` / `branch_zero`; otherwise
  the IP would execute spaces until it wraps, and we call that an error.

## Code IR boundary (v0.4)

`glyphfunge/code_ir.py` accepts Code IR's canonical JSON shape directly. It
does not import `py_transpile_toy`, preserving GlyphFunge's standalone public
boundary. Layer 1 accepts a parameterless `main() -> int` with declared `int`
locals, straight-line assignment, literal arithmetic, `Emit`, and final
`Return`, then emits a normal route of Befunge operations. A variable read is
expanded to its last assigned pure expression. This is intentionally static:
there is no Code IR bytecode interpreter, memory store, or substitute VM at
runtime.

The Code IR frontend's floor division is compatible with Befunge's truncating
division only when operands are nonnegative; this backend rejects the other
case rather than silently changing semantics. It also fixes evidence to the
signed 32-bit domain. Calls, comparisons and control flow await their own
explicit geometric lowering layer.

## What is deliberately NOT inherited / NOT done (v0.4)

- **No glyphs, text layout, anchors, transforms, Bresenham lines.** Those
  draw pictures; here pixels are instructions. Different job.
- **No arbitrary entry point.** Befunge-93 interpreters always start at
  (0, 0) heading right; `entry main` fixes exactly that. Inventing custom
  entry physics would produce programs ordinary interpreters can't run.
- **No auto-layout.** If two routes overlap or a `goto` is not on a straight
  heading, you get an error naming routes and coordinates — never a silent
  rearrangement.
- **Not implemented**: `p`/`g` self-modification, concurrency, multiple IPs,
  Befunge-98, fingerprints, input ops in the language (deferred), numbers
  above 9 as literals (compose them arithmetically), an optimizer.
- Static stack analysis is **exact only within the declared op set** (all
  stack effects are constant). Where it cannot know (a label re-entered at
  a different depth), it says MAYBE instead of claiming safety.

## Error formats (contract with the author)

```
GLYPH_ERROR:
route 'main' overlaps route 'helper' at (7, 2) ('+' vs 'v')

ROUTE_ERROR:
route 'main' line 12: branch_zero arm 'nope' must start exactly one cell
above (nonzero) of the branch cell (3, 1), i.e. at (3, 0); it starts at (1, 0)

STACK_ERROR:
possible underflow before 'add' on route 'main' (line 4): needs 2 value(s),
route arrives with 1
```

## Pipeline / files

| file | role |
|---|---|
| `parser.py` | source text → `Program` AST |
| `ast.py` | immutable AST dataclasses |
| `geometry.py` | playfield, directions, per-cell ownership |
| `router.py` | op emission (IP simulation), label/goto/branch resolution |
| `validator.py` | contracts: entry, bounds, stack, reachability |
| `compiler.py` | orchestration, issues, sha256 |
| `code_ir.py` | canonical Code IR JSON -> native GlyphFunge arithmetic layer |
| `interpreter.py` | reference Befunge-93 interpreter (for `run`/`verify`) |
| `cli.py` | `compile / compile-ir / inspect / run / verify` |
| `tools/run_befunge.js` | harness for an *independent* interpreter |

## Interpreter semantics pinned by the reference implementation

- pop on empty stack → 0; division/modulo by zero → 0;
- `.` prints `N ` (number + space); `,` prints the raw character;
- playfield edges wrap (torus);
- `verify` runs both the reference interpreter and, when `node` plus the
  sibling `Interpret-Esolangs-Online/befunge.js` are present, that
  independent third-party interpreter — and says SKIPPED explicitly when it
  is absent rather than pretending.
