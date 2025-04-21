set shell := ["zsh", "-uc"]

devenv:
    tox devenv -e dev .venv
    pre-commit install

clear:
    rm -r .venv
    rm -r .ruff_cache
    rm -r .tox
    rm -r .vagrant
