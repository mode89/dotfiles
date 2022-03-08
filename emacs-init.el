(require 'package)

(add-to-list 'package-archives
             '("melpa" . "https://melpa.org/packages/"))
(package-initialize)

(menu-bar-mode -1)
(tool-bar-mode -1)
(toggle-scroll-bar -1)
(set-face-attribute 'default nil :height 120)

(global-display-line-numbers-mode)
(column-number-mode)
(setq-default display-fill-column-indicator-column 76)
(global-display-fill-column-indicator-mode)
(global-hl-line-mode)
(setq-default indent-tabs-mode nil)
(setq-default tab-width 4)
(show-paren-mode 1)
(setq-default show-trailing-whitespace t)

;; Tell where to find color themes
(let ((basedir "~/.emacs.d/themes/"))
  (dolist (f (directory-files basedir))
    (if (and (not (or (equal f ".") (equal f "..")))
             (file-directory-p (concat basedir f)))
        (add-to-list 'custom-theme-load-path (concat basedir f)))))
(load-theme 'one-half t)

;; Keep auto-saves and backups in a separate directory
(let ((temp-directory "~/.emacs.d/temp"))
  (setq backup-directory-alist `((".*" . ,temp-directory)))
  (setq auto-save-file-name-transforms `((".*" ,temp-directory))))

(use-package evil
  :init
    (setq evil-want-C-u-scroll t)
    (setq evil-want-C-w-delete t)
  :config
    (evil-mode 1)
    (evil-set-leader 'normal (kbd "\\"))
    (evil-define-key 'normal 'global (kbd "<leader>rg") 'rgrep)
)

(use-package undo-tree
  :config
    (evil-set-undo-system 'undo-tree)
    (global-undo-tree-mode 1)
)

(use-package lsp-mode
  :config
    (use-package lsp-ui)
)
(use-package lsp-python-ms
  :config
    (add-hook 'hack-local-variables-hook
            (lambda ()
                (when (derived-mode-p 'python-mode)
                (require 'lsp-python-ms)
                (lsp))))
)

(use-package magit)

(use-package fzf
  :config
    (evil-define-key 'normal 'global (kbd "<leader>ff") 'fzf-find-file)
    (evil-define-key 'normal 'global (kbd "<leader>fb") 'fzf-switch-buffer)
)

(use-package projectile
  :config
    (projectile-mode)
)

(use-package helm
  :config
    (global-set-key (kbd "M-x") 'helm-M-x)
)
