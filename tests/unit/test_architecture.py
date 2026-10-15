"""Architecture rules (spec: engineering-quality, game-core).

Allowed imports: app -> ui/render/input/audio/net -> domain <- ai.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "pongwars"

ALLOWED: dict[str, set[str]] = {
    "core": set(),
    "domain": {"core"},
    "ai": {"core", "domain"},
    "net": {"core", "domain"},
    "render": {"core", "domain"},
    "input": {"core", "domain"},
    "audio": {"core", "domain"},
    "ui": {"core", "domain", "render", "input", "audio", "net", "ai"},
    "app": {"core", "domain", "render", "input", "audio", "net", "ai", "ui"},
}
FORBIDDEN_IN_DOMAIN = {"pygame", "socket", "asyncio", "threading", "subprocess"}


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
    return found


def _layer(path: Path) -> str:
    rel = path.relative_to(SRC)
    return rel.parts[0].removesuffix(".py")


def test_engineering_layer_dependencies() -> None:
    for path in SRC.rglob("*.py"):
        layer = _layer(path)
        if layer not in ALLOWED:
            continue
        for mod in _imports(path):
            parts = mod.split(".")
            if parts[0] == "pongwars" and len(parts) > 1 and parts[1] != layer:
                assert parts[1] in ALLOWED[layer], f"{path}: {layer} must not import {mod}"


def test_game_core_domain_has_no_io_imports() -> None:
    for path in (SRC / "domain").rglob("*.py"):
        bad = {m.split(".")[0] for m in _imports(path)} & FORBIDDEN_IN_DOMAIN
        assert not bad, f"{path} imports forbidden modules {bad}"
