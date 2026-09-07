# GlyphFunge

**A deterministic geometric frontend for Befunge-93. You describe the path. Befunge crawls it.**

```text
GlyphFuck solves deterministic ASCII geometry.
Befunge makes geometry executable.
GlyphFunge joins those two ideas.
```

## 30-second explanation

Befunge-93 programs are 2D grids of one-character instructions, walked by an
instruction pointer that moves around like a caterpillar. Writing them means
hand-placing every arrow on the grid — exactly the kind of exact spatial
layout humans and LLMs are bad at.

GlyphFunge lets you write *routes* instead: named paths with push/add/print
operations, turns, loops and branches. The compiler emits the exact
Befunge-93 playfield — real `.bf` you can run on any Befunge-93 interpreter.
No runtime, no VM of its own. The compiler only builds the grid; Befunge
executes it.

```
countdown.gf → parser → router (geometry) → validator → countdown.bf → any Befunge-93 interpreter
```

## Install & run

No dependencies. Python ≥ 3.10.

```bash
cd GlyphFunge
python -m glyphfunge compile examples/countdown.gf -o generated/countdown.bf
python -m glyphfunge inspect examples/countdown.gf
python -m glyphfunge run examples/countdown.gf
python -m glyphfunge verify examples/countdown.gf
```

## Why this beats writing the grid by hand — the countdown

`examples/countdown.gf`:

```text
canvas 12 6
entry main
expect output "5 4 3 2 1 0 "

route main:
    push 5
    turn down
    go 1
    label loop
    turn right
    dup
    print_num
    push 1
    sub
    dup
    branch_zero exit loopback
end

route exit at 7 3 facing down:
    print_num
    halt
end

route loopback at 7 1 facing up:
    turn left
    go 5
    turn down
    goto loop
end
```

compiles to this Befunge-93 playfield (`generated/countdown.bf`):

```
5v
 v<<<<<<
 >:.1-:|
       .
       @
```

Read the rectangle: `push 5` at top-left, `v` down into the main line
`>:.1-:|`, and when the counter is nonzero the `|` throws the IP **up** into
the `<<<<<<` corridor, which leads it around the loop and back into the `>`
at the start. The loop is literally visible as a loop. That is the whole
point of GlyphFunge.

Output — on both the bundled reference interpreter **and** the independent
third-party `befunge.js`:

```
5 4 3 2 1 0
```

## Syntax reference (v0.1)

```text
canvas W H                   # optional; must fit the Befunge-93 80x25 field
entry NAME                   # the entry route always starts (0, 0) facing right
expect output "STRING"       # optional, used by `verify`

route NAME:                  # entry route: no placement needed
route NAME at X Y facing right|left|up|down:   # every other route
    push N                   # N in 0..9  -> digit
    add | sub | mul | div | mod
    dup | swap | drop
    print_num | print_char
    print "TEXT"             # string mode: emits " + reversed + " + commas
    label NAME               # passable join point for `goto`
    go N                     # draw N arrows continuing straight
    turn right|left|up|down  # one arrow cell that bends the IP
    skip                     # '#' trampoline (jumps the next cell)
    branch_zero Z NZ         # '|': zero goes DOWN to Z, nonzero UP to NZ
    goto NAME                # walks straight into route/label NAME
    halt                     # '@'; every route must end with halt|goto|branch_zero
end
```

Rules the compiler enforces instead of guessing:

- The **zero** arm of `branch_zero` must start exactly one cell **below** the
  branch; the **nonzero** arm exactly one cell **above**. That is what `|`
  does in Befunge-93 — so GlyphFunge refuses any other geometry.
- `goto` walks straight in the current direction and must enter the target
  cell. If it can't, you get `ROUTE_ERROR` with coordinates, not a surprise.
- Two routes writing different characters on one cell is a `GLYPH_ERROR`
  naming both routes and the cell. (Two routes sharing a cell with the
  *same* character is a legal, inspectable merge.)
- Every route ends in `halt`, `goto` or `branch_zero`.
- `push` takes only 0..9 (Befunge-93 digit push; compose larger numbers).

## Side-by-side: arithmetic

`examples/arithmetic.gf` core:

```text
route main:
    push 9
    push 3
    add
    print_num
    halt
end
```

generated `generated/arithmetic.bf`:

```
93+.@
```

output: `12 ` (Befunge-93 `.` prints the number followed by a space).

## Evidence (v0.1, all reproducible with `python -m glyphfunge verify`)

| example | playfield | sha256 (generated .bf) | output | reference | independent (befunge.js) |
|---|---|---|---|---|---|
| arithmetic | 8x2 | `221797a271b9e7a1bab20a4173a4ea867f85ea11f3d47642537717e71f360266` | `12 ` | PASS, 5 steps | PASS |
| branch | 8x5 | `d4250e98adfd548928be31d5ec0c13cb0caa86588e766397e3bd7079f8a99490` | `0 ` | PASS, 7 steps | PASS |
| countdown | 12x6 | `4cb51acb1184e87cab9176644cc8443dbbe51a1c1e15f94c06cea02e67220085` | `5 4 3 2 1 0 ` | PASS, 68 steps | PASS |
| hello | 30x1 | `753072bf869627c921e722bde32881fa7ffbfe971edc74256b559e0c48dfc4cc` | `Hello, World!` | PASS, 15 steps | PASS |

Same `.gf` source always produces byte-identical `.bf` output
(tested in CI-style tests, including a pinned SHA-256 for `countdown.bf`).

## Independent-execution test (no cheating)

`tests/test_glyphfunge.py` includes a test that hands each generated program
to a third-party Befunge-93 interpreter — the `befunge.js` from
[*Interpret-Esolangs-Online*](https://github.com/ARaza448/Interpret-Esolangs-Online)
if present as a sibling checkout, via `node tools/run_befunge.js` (override
with `BEFUNGE_JS_LIB`). The compiler never sees expected outputs; tests check
behavior, not filenames. If the independent interpreter cannot be found, the
test **skips with an explicit reason printed** — it never fakes a pass.

```bash
python -m pytest tests -q -rs     # 31 tests; skip reasons shown if any
```

## Limitations (v0.1, on purpose)

- No `p`/`g` self-modification, no concurrency, no multiple IPs, no
  Befunge-98, no fingerprints, no `?` (source of randomness is banned).
- No input ops in the language yet (`&`/`~` deferred).
- Only single digits push directly; larger numbers must be composed
  arithmetically.
- One branch shape: `|` with zero-down / nonzero-up. (`_` needs horizontal
  arms; intentionally left out of v0.1.)
- Entry is fixed at (0, 0) facing right — that is simply how Befunge-93
  starts.
- Static stack analysis is exact within the op set, but crosses into MAYBE
  wording where a path-dependent depth is possible; it does not claim
  general safety.

## Layout

```
glyphfunge/            parser, ast, geometry, router, compiler, validator, cli, interpreter
examples/              arithmetic / branch / countdown / hello
generated/             committed .bf artifacts (compile output, byte-stable)
tests/                 pytest suite (31 tests)
tools/run_befunge.js   harness for the independent third-party interpreter
DESIGN.md              what came from GlyphFuck, what is Befunge-specific, why
```

GlyphFuck is the geometric reference and is **not** touched by this project.

## License

MIT — see LICENSE.
