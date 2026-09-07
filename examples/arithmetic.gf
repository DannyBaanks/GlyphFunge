# GlyphFunge canonical example A: arithmetic.
# 9 + 3 must print 12 (reference and independent interpreters print `12 `).
canvas 8 2
entry main
expect output "12 "

route main:
    push 9
    push 3
    add
    print_num
    halt
end
