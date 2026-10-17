# Development and contribution

This guide is for contributors working on the PongWars source code. Players should
install the Windows setup from the [releases page](https://github.com/slopeztech/PongWars/releases)
instead.

## Development setup

Requirements: Python 3.11 or newer. From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Run quality checks

```powershell
.\scripts\check.ps1
```

This runs Ruff linting and formatting checks, mypy, and the pytest suite with coverage.
To build the Doxygen documentation, install Doxygen and run:

```powershell
.\scripts\docs.ps1
```

## Build a Windows installer

Install [Inno Setup 6](https://jrsoftware.org/isinfo.php), then install the packaging
dependency and build from the repository root:

```powershell
python -m pip install -e ".[build]"
.\scripts\build-windows-installer.ps1
```

The script packages the game, Python runtime, pygame, and bundled content. It creates
`build\windows\installer\PongWars-Setup-<version>.exe`; the recipient does not need to
install Python or pygame. Inno Setup's `ISCC.exe` must be on `PATH` or installed in its
default location.

## Automatic GitHub releases

Every push to `main` runs the GitHub Actions workflow in
`.github/workflows/release.yml`. After quality checks pass, it increments the patch
version, commits that version change, creates a `v<version>` tag, and publishes a
GitHub Release with the Windows installer, Python wheel and source archive, plus
SHA-256 checksums. The version is defined only in `src/pongwars/version.py`; package
metadata and the Windows installer read it from there. Pushes to other branches do
not publish releases. The bot's version commit does not trigger another workflow run,
so one user push produces one version increment.

In the repository's GitHub settings, Actions must be allowed to write repository
contents. Branch protection on `main` and any tag rules for `v*` must also allow the
workflow's version-bump commit and tag push.

## Project references

- [Architecture](architecture.md)
- [Music file format](music-format.md)
- [OpenSpec changes and specifications](../openspec/)

To add content, see the instructions near the end of the
[player guide](user-guide.md#adding-content).

## Documentation is part of the change

Every new feature and every change to existing behavior must update the relevant
documentation in the same change. Explain the behavior in the appropriate guide,
update summaries that would otherwise become inaccurate, and add or repair links
from the README and related guides. For content catalogs, document each built-in
item and its meaningful behavior rather than only its internal identifier.

Keep the README as an overview and link to focused guides for detailed catalogs:
[game modes](game-modes.md), [arenas](arenas.md), and [extras](extras.md).
Documentation should describe the shipped behavior, not implementation details
that players cannot observe.
