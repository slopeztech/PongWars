# PongWars

Classic Pong with an **8-bit** look and **pseudo-3D** view, built with Python and pygame.

- 2 players on the same keyboard or over **LAN**; **1 vs AI** with several difficulties.
- Configurable matches: game mode, arenas (some with obstacles), limits.
- In-match extras: **weapons, powers and penalties**.
- Localizable UI (English source catalog; add languages by dropping a JSON file).

> Status: playable locally (2-4 players on one keyboard, 1 vs AI, extras, settings, audio).
> LAN play is planned and not implemented yet.

## Quick start

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
python -m pongwars
```

Full instructions and controls: [docs/user-guide.md](docs/user-guide.md).

## Development

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .[dev]
.\scripts\check.ps1          # lint + types + tests + coverage
.\scripts\docs.ps1           # Doxygen docs (requires doxygen)
```

## OpenSpec + AI workflow

The source of truth is in [`openspec/`](openspec). Each change follows:

1. `/opsx-propose "idea"` -> proposal, specs, design and tasks.
2. `/opsx-apply` -> the AI implements the tasks (with tests).
3. `/opsx-archive` -> the change specs move to `openspec/specs/`.

Current change: [`bootstrap-pongwars`](openspec/changes/bootstrap-pongwars) with the design,
the 13 capabilities and the phased plan (`tasks.md`).

Architecture: [docs/architecture.md](docs/architecture.md).

## Conventions

Everything (code, comments, docs, OpenSpec) is in English. User-visible text goes through
translation keys. See `openspec/config.yaml`.

## License

Released under the [MIT License](LICENSE).

