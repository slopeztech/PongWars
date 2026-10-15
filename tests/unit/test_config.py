"""MatchConfig tests (spec: match-configuration)."""

import pytest

from pongwars.domain.config import ConfigError, MatchConfig


def test_match_configuration_json_round_trip() -> None:
    cfg = MatchConfig(
        mode="timed", options=(("points_to_win", 3),), controllers=("human", "ai"), seed=42
    )
    assert MatchConfig.from_json(cfg.to_json()) == cfg


@pytest.mark.parametrize(
    "kwargs",
    [
        {"options": (("x", "y"),)},
        {"controllers": ("human", "bot")},
        {"ai_difficulty": "god"},
        {"mode": ""},
    ],
)
def test_match_configuration_rejects_invalid_values(kwargs: dict[str, object]) -> None:
    with pytest.raises(ConfigError) as err:
        MatchConfig(**kwargs)  # type: ignore[arg-type]
    assert err.value.key == "error.config.invalid_value"


def test_match_configuration_rejects_unknown_version() -> None:
    with pytest.raises(ConfigError) as err:
        MatchConfig(schema_version=99)
    assert err.value.key == "error.config.unsupported_version"


def test_match_configuration_bad_json_is_config_error() -> None:
    with pytest.raises(ConfigError):
        MatchConfig.from_json("{not json")
