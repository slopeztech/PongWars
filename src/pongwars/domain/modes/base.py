"""@package pongwars.domain.modes.base
@brief Pluggable game-mode contract, option validation and the mode registry.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from pongwars.core.registry import Registry
from pongwars.domain.config import ConfigError, MatchConfig
from pongwars.domain.events import Event

if TYPE_CHECKING:
    from pongwars.domain.world import World


@dataclass(frozen=True)
class OptionSpec:
    """@brief Declaration of one configurable mode option.

    @param name Option key (also used for translation keys).
    @param default Default value.
    @param minimum Smallest accepted value.
    @param maximum Largest accepted value.
    @param kind "int" or "bool" (a bool is 0 or 1).
    """

    name: str
    default: int
    minimum: int
    maximum: int
    kind: str = "int"


def resolve_options(specs: tuple[OptionSpec, ...], given: dict[str, float]) -> dict[str, int]:
    """@brief Merge user values over defaults and validate them.
    @param specs Options declared by the mode.
    @param given User-provided values.
    @return Complete option values.
    @throws ConfigError For unknown options or out-of-range values.
    """
    known = {s.name: s for s in specs}
    for name in given:
        if name not in known:
            raise ConfigError("error.config.unknown_option", option=name)
    values: dict[str, int] = {}
    for spec in specs:
        value = int(given.get(spec.name, spec.default))
        if not spec.minimum <= value <= spec.maximum:
            raise ConfigError(
                "error.config.option_out_of_range",
                option=spec.name,
                minimum=spec.minimum,
                maximum=spec.maximum,
            )
        values[spec.name] = value
    return values


class Mode:
    """@brief Base class of game modes; subclasses define scoring and the end condition."""

    id: ClassVar[str] = ""
    options: ClassVar[tuple[OptionSpec, ...]] = ()

    def __init__(self, values: dict[str, int]) -> None:
        """@param values Validated option values."""
        self.values = values

    def on_goal(
        self, world: "World", scorer: int | None, conceded: int, events: list[Event]
    ) -> None:
        """@brief React to a goal; the default awards a point to the scorer, if any.
        @param world Match state.
        @param scorer Player credited with the point, or None.
        @param conceded Player whose goal was crossed.
        @param events Event list to append to.
        """
        if scorer is not None:
            world.scores[scorer] += 1

    def on_tick(self, world: "World", events: list[Event]) -> None:
        """@brief Per-tick hook (timers, zones). Does nothing by default.
        @param world Match state.
        @param events Event list to append to.
        """

    def winner(self, world: "World") -> int | None:
        """@brief The winner if the match is over.
        @param world Match state.
        @return Player index, or None while the match continues.
        """
        raise NotImplementedError


MODES: Registry[type[Mode]] = Registry("mode")


def register_mode(name: str) -> Callable[[type[Mode]], type[Mode]]:
    """@brief Class decorator registering a mode under `name`.
    @param name Mode id.
    """

    def decorator(cls: type[Mode]) -> type[Mode]:
        cls.id = name
        MODES.add(name, cls)
        return cls

    return decorator


def create_mode(config: MatchConfig) -> Mode:
    """@brief Instantiate the mode selected by a configuration.
    @param config Match configuration.
    @throws ConfigError For unknown modes or invalid options.
    """
    if config.mode not in MODES:
        raise ConfigError("error.config.unknown_mode", mode=config.mode)
    cls = MODES.get(config.mode)
    return cls(resolve_options(cls.options, config.option_dict()))
