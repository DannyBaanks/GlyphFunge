# GlyphFunge canonical example D: Hello World via Befunge string mode.
# `print "TEXT"` emits " <reversed chars> " and one print_char per character,
# so the text comes out forwards even though the playfield stores it reversed.
canvas 30 1
entry main
expect output "Hello, World!"

route main:
    print "Hello, World!"
    halt
end
