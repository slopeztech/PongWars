"""Localization tests (spec: localization)."""

import json
from pathlib import Path

from pongwars.core.i18n import LOCALES_DIR, Translator, available_languages, load_catalog


def _locales(tmp_path: Path) -> Path:
    (tmp_path / "en.json").write_text(
        json.dumps(
            {
                "a": "Hello",
                "w": "{p} wins!",
                "n.one": "{count} point",
                "n.other": "{count} points",
                "only_en": "E",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "es.json").write_text(json.dumps({"a": "Hola"}), encoding="utf-8")
    return tmp_path


def test_localization_lookup_uses_active_language(tmp_path: Path) -> None:
    assert Translator("es", _locales(tmp_path))("a") == "Hola"


def test_localization_fallback_english_then_key(tmp_path: Path) -> None:
    t = Translator("es", _locales(tmp_path))
    assert t("only_en") == "E"
    assert t("nope.key") == "nope.key"


def test_localization_unknown_language_falls_back(tmp_path: Path) -> None:
    t = Translator("xx", _locales(tmp_path))
    assert t.language == "en"
    assert t("a") == "Hello"


def test_localization_placeholder_and_plural(tmp_path: Path) -> None:
    t = Translator("en", _locales(tmp_path))
    assert t("w", p="P1") == "P1 wins!"
    assert t("n", count=1) == "1 point"
    assert t("n", count=3) == "3 points"


def test_localization_switch_language(tmp_path: Path) -> None:
    t = Translator("en", _locales(tmp_path))
    t.set_language("es")
    assert t("a") == "Hola"


def test_localization_catalogs_consistent_with_english() -> None:
    english = load_catalog("en")
    assert english
    for lang in available_languages(LOCALES_DIR):
        catalog = load_catalog(lang)
        assert set(catalog) <= set(english), f"{lang} has unknown keys"
        for key, text in catalog.items():
            assert text.count("{") == english[key].count("{"), f"{lang}:{key} placeholders differ"
