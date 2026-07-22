# Python Stack Rules

## Build & Test

- Check for `pyproject.toml`, `setup.py`, or `requirements.txt` to determine package manager
- Prefer `pytest` for testing. Run with `pytest -v` for verbose output
- Use virtual environments — never install to system Python

## Conventions

- Follow PEP 8 style as established in the project
- Prefer type hints where the project uses them
- Use `pathlib.Path` over `os.path` in new code

## Safe Commands

pytest, python -m pytest, pip install, pip install -e ., python -m, ruff check, ruff format, mypy
