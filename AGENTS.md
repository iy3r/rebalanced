# AI Agent Guidelines

## Project Context
- uv-based Python monorepo (workspace defined in root `pyproject.toml`)
- Python 3.14+, modern typing (observed: `Self`, `Never`, `TypeAlias`, `StrEnum`)
- Build backend: `uv_build` (not setuptools)
- Packages in `packages/*`, main namespace in `src/`

## Python Tooling
uv, ruff, pytest; prefer dataclasses, Protocol, type hints.

## Python Programming Inspirations
Pragmatic elegance of Guido van Rossum, Tim Peters' Zen, Raymond Hettinger's "beautiful, idiomatic" style, David Beazley's deep internals knowledge, Luciano Ramalho's Pythonic fluency, and James Powell's metaprogramming expertise.

## Tool Usage Rules
- **Never** use `pip install` directly
- Use `uv sync` to install dependencies from `uv.lock`
- Use `uv run` to execute Python code
- For ad-hoc packages without modifying pyproject.toml: `uv run --with <pkg> python script.py`
- For tools: `uv tool run --with <pkg> <tool>`
- Multiple packages: `uv run --with numpy --with matplotlib python script.py`

## Observed Code Patterns
- dataclasses: use `frozen=True, slots=True`
- Prefer `collections.abc` imports over `typing` (e.g., `Callable`, `Mapping`)
- Use `TypeAlias` for complex type definitions
- Use `MappingProxyType` for immutable public mappings
- Define `__all__` explicitly in package `__init__.py` files
