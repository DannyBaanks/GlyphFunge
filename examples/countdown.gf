# GlyphFunge canonical example C: the countdown loop (flagship).
#
# Prints 5 4 3 2 1 0. The loop closes *physically*: after the branch, a
# nonzero IP is thrown up to row 1, travels LEFT across the playfield, dives
# down through the 'v' corridor and re-enters the main line at label `loop`.
# You can watch the IP walk a rectangle. That rectangle is the program.
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
