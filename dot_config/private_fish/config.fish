if status is-interactive
# Commands to run in interactive sessions can go here
end
fnm env --use-on-cd --resolve-engines=false | source
set -gx SUDO_EDITOR nvim
set -gx VISUAL nvim
set -gx EDITOR nvim
abbr -a a 'cd ~/Projects/NewProject/'


# Added by Antigravity CLI installer
set -gx PATH "/home/domixi/.local/bin" $PATH
