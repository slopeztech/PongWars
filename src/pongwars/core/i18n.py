"""@package pongwars.core.i18n
@brief Translation catalogs with fallback, placeholders and plural forms.
"""

import json
from pathlib import Path

DEFAULT_LANGUAGE = "en"
LOCALES_DIR = Path(__file__).resolve().parent.parent / "data" / "locales"


def load_catalog(language: str, locales_dir: Path = LOCALES_DIR) -> dict[str, str]:
    """@brief Load a flat key -> text catalog.
    @param language Language code, e.g. "en".
    @param locales_dir Directory containing `<language>.json` files.
    @return The catalog, or an empty dict if the language has no file.
    """
    path = locales_dir / f"{language}.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()}


def available_languages(locales_dir: Path = LOCALES_DIR) -> list[str]:
    """@brief Language codes that have a catalog file, sorted."""
    return sorted(p.stem for p in locales_dir.glob("*.json"))


class Translator:
    """@brief Resolves translation keys using the chain selected -> English -> key."""

    def __init__(self, language: str = DEFAULT_LANGUAGE, locales_dir: Path = LOCALES_DIR) -> None:
        """@brief Create a translator.
        @param language Active language code.
        @param locales_dir Directory with the catalogs.
        """
        self._dir = locales_dir
        self._source = load_catalog(DEFAULT_LANGUAGE, locales_dir)
        self._language = DEFAULT_LANGUAGE
        self._active: dict[str, str] = self._source
        self.set_language(language)

    @property
    def language(self) -> str:
        """@brief The active language code."""
        return self._language

    def set_language(self, language: str) -> None:
        """@brief Switch the active language (unknown languages fall back to English).
        @param language Language code.
        """
        catalog = load_catalog(language, self._dir)
        if catalog or language == DEFAULT_LANGUAGE:
            self._language = language
            self._active = catalog
        else:
            self._language = DEFAULT_LANGUAGE
            self._active = self._source

    def _lookup(self, key: str) -> str | None:
        return self._active.get(key) or self._source.get(key)

    def translate(self, key: str, count: int | None = None, **params: object) -> str:
        """@brief Translate a key.
        @param key Dotted translation key.
        @param count Optional count selecting the `.one` / `.other` plural form.
        @param params Values for `{name}` placeholders.
        @return The translated text, or the key itself when it is missing everywhere.
        """
        text: str | None = None
        if count is not None:
            form = "one" if count == 1 else "other"
            text = self._lookup(f"{key}.{form}")
            params.setdefault("count", count)
        if text is None:
            text = self._lookup(key)
        if text is None:
            return key
        try:
            return text.format(**params)
        except (KeyError, IndexError, ValueError):
            return text

    __call__ = translate
