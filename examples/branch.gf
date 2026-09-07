# GlyphFunge canonical example B: conditional branch.
# push 0 forces the ZERO arm: `|` consumes the duped value and throws the IP
# DOWN into zero_hit, which prints the kept copy (0). Change `push 0` to
# `push 4` and the IP is thrown UP into nonzero_hit and prints 9 instead.
# The two outcomes travel through physically different corridors.
canvas 8 5
entry main
expect output "0 "

route main:
    push 0
    dup
    turn down
    turn right
    branch_zero zero_hit nonzero_hit
end

route zero_hit at 3 2 facing down:
    print_num
    halt
end

route nonzero_hit at 3 0 facing up:
    turn right
    drop
    push 9
    print_num
    halt
end
