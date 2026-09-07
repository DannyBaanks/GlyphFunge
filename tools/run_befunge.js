// Independent-execution harness for GlyphFunge tests.
//
// Loads a third-party Befunge-93 interpreter (by default the befunge.js from
// the sibling Interpret-Esolangs-Online project, overridable with
// BEFUNGE_JS_LIB), executes the .bf file given on argv, and writes the raw
// program output to stdout. Exit code 2 = interpreter library not found,
// 3 = program did not halt before the harness step guard.
const fs = require("fs");
const path = require("path");

const libPath = process.env.BEFUNGE_JS_LIB || path.resolve(__dirname, "..", "..", "..", "Interpret-Esolangs-Online", "befunge.js");
if (!fs.existsSync(libPath)) {
  console.error("independent interpreter not found: " + libPath);
  process.exit(2);
}
eval(fs.readFileSync(libPath, "utf8")); // defines befunge(program, input)

const programFile = process.argv[2];
const program = fs.readFileSync(programFile, "utf8").replace(/\r\n/g, "\n") .replace(/\n$/, "");
const out = befunge(program, process.env.BEFUNGE_INPUT || "");
process.stdout.write(out);
