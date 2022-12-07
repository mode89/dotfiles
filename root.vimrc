set nocompatible

execute pathogen#infect()
Helptags

" Setup swap directory
if !isdirectory($HOME . "/.cache/vim")
    call mkdir($HOME . "/.cache/vim", "p")
endif
set directory=$HOME/.cache/vim

syntax on
colorscheme delek

" Setup font
if has("gui_running")
    if has("win32")
        set guifont=Consolas\ 12
    else
        set guifont=Monospace\ 11
    endif
endif

if has("gui_running")
    set go-=T "Hide toolbar
    set go-=m "Hide menu
endif

set hidden "Enable hidden buffers

set showcmd "Show command in the status line

set number "Turn on line numbers

set incsearch "Enable incrementa search
set nohlsearch "Turn off search highlighting

set tabstop=4 "Size of a hard tabstop
set expandtab "Always expand tabs as spaces
set shiftwidth=4 "Size of indent
set autoindent
set backspace=indent

set nofoldenable

" Highlight the 77th column
set colorcolumn=77

set viminfo+=:1000
set history=1000

set cursorline " Highlight cursor line

highlight TrailingWhitespace ctermbg=red guibg=red
match TrailingWhitespace /\s\+$/
