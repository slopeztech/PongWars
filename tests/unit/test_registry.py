"""Registry tests (spec: engineering-quality)."""

import pytest

from pongwars.core.registry import Registry, RegistryError


def test_registry_decorator_registers_and_gets() -> None:
    reg: Registry[type] = Registry("mode")

    @reg.register("classic")
    class Classic:
        pass

    assert reg.get("classic") is Classic
    assert "classic" in reg
    assert reg.names() == ["classic"]
    assert len(reg) == 1


def test_registry_duplicate_and_unknown_raise() -> None:
    reg: Registry[int] = Registry("mode")
    reg.add("a", 1)
    with pytest.raises(RegistryError):
        reg.add("a", 2)
    with pytest.raises(RegistryError):
        reg.get("missing")
