"""@package pongwars.core.registry
@brief Generic name -> object registry used for modes, arenas, extras and AIs.
"""

from collections.abc import Callable, Iterator
from typing import Generic, TypeVar

T = TypeVar("T")


class RegistryError(KeyError):
    """@brief Raised on duplicate registration or unknown names."""


class Registry(Generic[T]):
    """@brief Maps unique string names to registered objects."""

    def __init__(self, kind: str) -> None:
        """@brief Create an empty registry.
        @param kind Human-readable kind of item, used in error messages.
        """
        self._kind = kind
        self._items: dict[str, T] = {}

    def add(self, name: str, item: T) -> T:
        """@brief Register an item.
        @param name Unique name.
        @param item Object to store.
        @return The same item.
        @throws RegistryError If the name is already registered.
        """
        if name in self._items:
            raise RegistryError(f"{self._kind} '{name}' is already registered")
        self._items[name] = item
        return item

    def register(self, name: str) -> Callable[[T], T]:
        """@brief Decorator form of add().
        @param name Unique name.
        @return A decorator that registers and returns the decorated object.
        """

        def decorator(item: T) -> T:
            return self.add(name, item)

        return decorator

    def get(self, name: str) -> T:
        """@brief Look up an item.
        @param name Registered name.
        @return The stored item.
        @throws RegistryError If the name is unknown.
        """
        try:
            return self._items[name]
        except KeyError:
            raise RegistryError(f"unknown {self._kind} '{name}'") from None

    def remove(self, name: str) -> None:
        """@brief Unregister an item (used by plugins and tests).
        @param name Registered name.
        @throws RegistryError If the name is unknown.
        """
        self.get(name)
        del self._items[name]

    def names(self) -> list[str]:
        """@brief Registered names in sorted order."""
        return sorted(self._items)

    def __contains__(self, name: object) -> bool:
        """@brief True if the name is registered."""
        return name in self._items

    def __iter__(self) -> Iterator[str]:
        """@brief Iterate names in sorted order."""
        return iter(self.names())

    def __len__(self) -> int:
        """@brief Number of registered items."""
        return len(self._items)
