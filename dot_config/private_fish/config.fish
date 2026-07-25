if status is-interactive
# Commands to run in interactive sessions can go here
end
fnm env --use-on-cd | source
set -gx SUDO_EDITOR nvim
set -gx VISUAL nvim
set -gx EDITOR nvim
