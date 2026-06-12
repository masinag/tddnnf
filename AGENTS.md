# AGENTS.md — tddnnf

## Project

Python library for Knowledge Compilation Modulo Theories (KCMT).
SMT formula → tractable representation (d-DNNF/SDD/OBDD). See ARCHITECTURE.md.

## Stack

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for deps
- [pytest](https://docs.pytest.org/) for tests
- [ruff](https://docs.astral.sh/ruff/) for lint + format
- [mypy](https://mypy-lang.org/) for type checking
- pre-commit hooks (ruff + mypy)
- Google-style docstrings
- Conventional commits (`feat:`, `fix:`, `chore:`, `docs:`, etc.)

## Commands

| Action           | Command                             |
| ---------------- | ----------------------------------- |
| Tests            | `uv run pytest`                     |
| Lint             | `uv run ruff check .`               |
| Format check     | `uv run ruff format . --check`      |
| Format           | `uv run ruff format .`              |
| Type check       | `uv run mypy tddnnf/`               |
| Pre-commit hooks | `uv run pre-commit run --all-files` |

## AI Behavior

- Activate caveman mode on new session by default
- Always run lint + type check after code changes
- Follow ARCHITECTURE.md incremental phases (Phase 1 → 2 → 3 → 4)
- Do not commit unless explicitly asked
- Do not create files outside the `tddnnf/` package tree unless specified

## Project Layout

```
tddnnf/
├── core/
│   ├── abstraction.py       # SMT Atom ↔ Bool Var mappings
│   ├── containers.py         # TheoryCompilation unified wrapper
│   └── interfaces.py         # Python Protocols
├── normalization/
│   └── normalizer.py         # SMT canonicalization
├── builders/
│   ├── reduced.py            # T-Reduced syntax
│   └── extended.py           # T-Extended syntax
├── compilers/
│   ├── d4.py                 # CLI d4 wrapper
│   ├── pysdd.py              # PySDD adapter
│   └── cudd.py               # CUDD adapter
└── queries/
    ├── d4_engine.py          # d4 query handler
    ├── sdd_engine.py         # PySDD query handler
    └── bdd_engine.py         # CUDD query handler
```
