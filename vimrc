set nocompatible

set runtimepath+=/opt/fzf/0.27.0/plugin
runtime fzf.vim

" let g:pathogen_disabled = ["ale"]
execute pathogen#infect()
Helptags

" Setup swap directory
if !isdirectory($HOME . "/.cache/vim")
    call mkdir($HOME . "/.cache/vim", "p")
endif
set directory=$HOME/.cache/vim

syntax on
" colorscheme solarized
set t_Co=256
colorscheme onehalflight

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

" Git acceleration
command -nargs=* -complete=file Git !clear && git <args>
noremap <leader>gda :Git diff
noremap <leader>gdc :Git diff %
noremap <leader>gdi :Git diff --cached
noremap <leader>glo :Git log --oneline
noremap <leader>gla :Git log --oneline --graph --decorate --all
noremap <leader>gs :Git status
noremap <leader>t :!clear && ctags --recurse

highlight TrailingWhitespace ctermbg=red guibg=red
match TrailingWhitespace /\s\+$/

" Ale

" let g:ale_completion_enabled = 1
let g:ale_linters = {
\   "python": [ "mypy", "pylint", "pyls" ],
\   "cpp": [ "clangd" ],
\ }

noremap <leader>ad :ALEDetail<return>
noremap <leader>ah :ALEHover<return>
noremap <leader>ag :ALEGoToDefinition<return>
noremap <leader>ap :ALEPrevious<return>
noremap <leader>an :ALENext<return>
noremap <leader>as :ALESymbolSearch

" FZF

let g:fzf_preview_window = [] " Disable preview window

noremap <leader>ff :FZF<return>
noremap <leader>fg :GFiles<return>
noremap <leader>fb :Buffers<return>

" Enable per-project .vimrc
set exrc
set secure

let g:paredit_mode=0
