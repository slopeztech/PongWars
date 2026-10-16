"""Minimal structure: the package imports and exposes a version."""

from importlib.metadata import version

import pytest

import pongwars
from pongwars.version import next_patch_version


def test_engineering_package_exposes_version() -> None:
    assert pongwars.__version__
    assert pongwars.__version__ == version("pongwars")


def test_next_patch_version_increments_only_patch() -> None:
    assert next_patch_version("0.1.0") == "0.1.1"
    assert next_patch_version("2.9.17") == "2.9.18"


def test_next_patch_version_rejects_invalid_versions() -> None:
    for invalid in ("1.2", "1.2.3-rc.1", "01.2.3", "v1.2.3"):
        with pytest.raises(ValueError):
            next_patch_version(invalid)
