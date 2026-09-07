# GlyphFunge v0.2 self-reference demo: Befunge emitting Befunge.
# This GlyphFunge program compiles to Befunge-93 whose OUTPUT is itself a
# valid Befunge-93 program ("93+.@"), which in turn prints "12 ".
# Chain: meta_befunge.bf --run--> "93+.@" --run--> "12 "
canvas 20 2
entry main
expect output "93+.@"

route main:
    print "93+.@"
    halt
end
