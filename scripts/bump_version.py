"""Increment the authoritative PongWars version's patch component."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from pongwars.version import __version__, next_patch_version  # noqa: E402

VERSION_FILE = ROOT / "src" / "pongwars" / "version.py"


def main() -> int:
    """Increment the package version in its single source file and print it."""
    updated_version = next_patch_version(__version__)
    source = VERSION_FILE.read_text(encoding="utf-8")
    updated, replacements = re.subn(
        r'(?m)^__version__ = "[^"]+"$',
        f'__version__ = "{updated_version}"',
        source,
    )
    if replacements != 1:
        raise RuntimeError(f"expected one version declaration in {VERSION_FILE}")
    VERSION_FILE.write_text(updated, encoding="utf-8", newline="\n")
    print(updated_version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
