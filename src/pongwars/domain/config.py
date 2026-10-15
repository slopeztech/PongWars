"""@package pongwars.domain.config
@brief Immutable, serializable and validated match configuration.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from pongwars.domain.constants import (
    DEFAULT_EXTRAS_INTERVAL,
    DEFAULT_EXTRAS_MAX_ACTIVE,
    MAX_EXTRAS_INTERVAL,
)

SCHEMA_VERSION = 1
PENALTY_TARGETS = ("collector", "opponents")
CONTROLLERS = ("human", "ai", "remote")
MIN_PLAYERS = 2
MAX_PLAYERS = 4
AI_DIFFICULTIES = ("easy", "normal", "hard", "insane")


class ConfigError(ValueError):
    """@brief Validation error carrying a translation key and parameters."""

    def __init__(self, key: str, **params: object) -> None:
        """@param key Translation key. @param params Translation parameters."""
        super().__init__(f"{key} {params}")
        self.key = key
        self.params = params


@dataclass(frozen=True)
class MatchConfig:
    """@brief Everything needed to start a match.

    `controllers` has one entry per player (2-4) and must match the arena's player count.
    Mode-specific settings travel in `options` as (name, value) pairs; the selected
    mode validates names and ranges when the match is created.
    """

    mode: str = "classic"
    arena: str = "classic"
    options: tuple[tuple[str, float], ...] = ()
    controllers: tuple[str, ...] = ("human", "human")
    ai_difficulty: str = "normal"
    ai_strategy: str = "predictive"
    extras: tuple[str, ...] = ()
    extras_interval: float = DEFAULT_EXTRAS_INTERVAL
    extras_max_active: int = DEFAULT_EXTRAS_MAX_ACTIVE
    penalty_target: str = "collector"
    seed: int = 0
    schema_version: int = field(default=SCHEMA_VERSION)

    def __post_init__(self) -> None:
        """@brief Validate the fields.
        @throws ConfigError On any invalid value.
        """
        if self.schema_version != SCHEMA_VERSION:
            raise ConfigError("error.config.unsupported_version", version=self.schema_version)
        for pair in self.options:
            if len(pair) != 2 or not isinstance(pair[0], str) or isinstance(pair[1], bool | str):
                raise ConfigError("error.config.invalid_value", field="options")
        if not MIN_PLAYERS <= len(self.controllers) <= MAX_PLAYERS or any(
            c not in CONTROLLERS for c in self.controllers
        ):
            raise ConfigError("error.config.invalid_value", field="controllers")
        if self.ai_difficulty not in AI_DIFFICULTIES:
            raise ConfigError("error.config.invalid_value", field="ai_difficulty")
        if not self.ai_strategy:
            raise ConfigError("error.config.invalid_value", field="ai_strategy")
        if not self.mode or not self.arena:
            raise ConfigError("error.config.invalid_value", field="mode/arena")
        if any(not isinstance(name, str) or not name for name in self.extras):
            raise ConfigError("error.config.invalid_value", field="extras")
        if not 0 < self.extras_interval <= MAX_EXTRAS_INTERVAL:
            raise ConfigError("error.config.invalid_value", field="extras_interval")
        if self.extras_max_active < 1:
            raise ConfigError("error.config.invalid_value", field="extras_max_active")
        if self.penalty_target not in PENALTY_TARGETS:
            raise ConfigError("error.config.invalid_value", field="penalty_target")

    def option_dict(self) -> dict[str, float]:
        """@brief The mode options as a dict."""
        return dict(self.options)

    def to_json(self) -> str:
        """@brief Serialize to a JSON string."""
        return json.dumps(asdict(self), sort_keys=True)

    @staticmethod
    def from_json(text: str) -> "MatchConfig":
        """@brief Deserialize and validate.
        @param text JSON produced by to_json().
        @throws ConfigError If the content is invalid.
        """
        try:
            data: dict[str, Any] = json.loads(text)
            data["controllers"] = tuple(data["controllers"])
            data["extras"] = tuple(data.get("extras", ()))
            data["options"] = tuple((str(k), v) for k, v in data.get("options", []))
            return MatchConfig(**data)
        except ConfigError:
            raise
        except (ValueError, KeyError, TypeError) as exc:
            raise ConfigError("error.config.invalid_value", field="json") from exc
