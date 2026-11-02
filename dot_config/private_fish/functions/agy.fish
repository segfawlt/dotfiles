# Managed by agy-stats
function agy --wraps agy --description 'Antigravity CLI wrapper with stats subcommand support'
    if test (count $argv) -ge 1 -a "$argv[1]" = "stats"
        if command -q agy-stats
            agy-stats $argv[2..-1]
        else if test -x "$HOME/.local/bin/agy-stats"
            "$HOME/.local/bin/agy-stats" $argv[2..-1]
        else
            echo "agy-stats not found at ~/.local/bin/agy-stats" >&2
            return 127
        end
    else
        command agy $argv
    end
end
