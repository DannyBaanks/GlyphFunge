# GlyphFunge v0.2 flagship: FizzBuzz 1..15, pure Befunge-93 output.
#
# Four branches, one shared "elevator" column (x=44) where the corridors of
# every branch arm meet as '^' cells, and a return corridor across row 1 that
# closes the loop. Canonical spacing: "Fizz" and "Buzz" alone, a space after
# each token, so c=15 prints exactly "FizzBuzz ".
canvas 60 8
entry main
expect output "1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz "

route main:
    push 1
    turn down
    go 3
    label loop
    turn right
    dup
    push 3
    mod
    branch_zero fizz path_show
end

route fizz at 5 5 facing down:
    turn right
    print "Fizz"
    go 4
    dup
    push 5
    mod
    branch_zero buzz_a no_buzz_a
end

route buzz_a at 23 6 facing down:
    turn right
    print "Buzz "
    go 8
    turn up
    goto converge
end

route no_buzz_a at 23 4 facing up:
    turn right
    print " "
    go 16
    turn up
    goto converge
end

route path_show at 5 3 facing up:
    turn right
    dup
    push 5
    mod
    branch_zero buzz_b show_num
end

route buzz_b at 9 4 facing down:
    turn right
    print "Buzz "
    turn up
    go 1
    turn right
    goto converge
end

route show_num at 9 2 facing up:
    turn right
    dup
    print_num
    go 30
    goto converge
end

route next at 44 2 facing right:
    label converge
    turn right
    push 1
    add
    dup
    push 4
    push 4
    mul
    sub
    branch_zero fin loopback
end

route fin at 52 3 facing down:
    drop
    halt
end

route loopback at 52 1 facing up:
    turn left
    go 50
    turn down
    goto loop
end
