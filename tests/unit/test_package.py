"""Minimal structure: the package imports and exposes a version."""

import pongwars


def test_engineering_package_exposes_version() -> None:
    assert pongwars.__version__
