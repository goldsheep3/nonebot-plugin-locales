from __future__ import annotations

import re
import random
from typing import Any, TypeAlias
from pathlib import Path
from collections.abc import Mapping, Callable, Awaitable

import yaml
from nonebot.params import Depends
from nonebot.adapters import Bot, Event

from .api import (
    LocalesAccountError,
    get_aid,
    get_language,
    normalize_language_code,
)
from .config import plugin_config

LocaleData = dict[str, Any]
_MISSING = object()
_LOCALE_FILE_STEM = re.compile(r"^[a-z]{2}_[A-Z]{2}$")


Reply: TypeAlias = Callable[..., Awaitable[str]]


class LocaleError(ValueError):
    pass


class LocaleFileError(LocaleError):
    pass


class _SafeFormatMap(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class LocaleStore:
    def __init__(
        self,
        lang_dir: str | Path,
        *,
        default_language: str | None = None,
        fallback_language: str | None = None,
    ) -> None:
        self.lang_dir = Path(lang_dir)
        self.default_language = normalize_language_code(
            default_language or plugin_config.locales_default_lang
        )
        self.fallback_language = (
            normalize_language_code(fallback_language)
            if fallback_language is not None
            else None
        )
        self.languages: dict[str, LocaleData] = {}
        self.reload()

    def reload(self) -> None:
        self.languages = {}
        if not self.lang_dir.exists():
            return
        if not self.lang_dir.is_dir():
            raise LocaleFileError(f"{self.lang_dir} is not a directory")

        for file in sorted(self.lang_dir.iterdir()):
            if file.suffix.lower() not in {".yaml", ".yml"}:
                continue
            if not _LOCALE_FILE_STEM.fullmatch(file.stem):
                raise LocaleFileError(
                    f"invalid locale file name {file.name}; expected xx_XX"
                )
            language_code = file.stem
            if language_code in self.languages:
                raise LocaleFileError(
                    f"duplicate locale language code {language_code}: {file.name}"
                )
            self.languages[language_code] = self._load_yaml(file)

    def render(
        self,
        key: str,
        language_code: str | None = None,
        **kwargs: object,
    ) -> str:
        normalized_key = key.strip()
        if not normalized_key:
            return key

        for language in self._language_chain(language_code):
            value = self._lookup(language, normalized_key)
            if value is _MISSING:
                continue
            if isinstance(value, str):
                return self._format(value, kwargs)
            if (
                isinstance(value, list)
                and value
                and all(isinstance(item, str) for item in value)
            ):
                return self._format(random.choice(value), kwargs)
            return normalized_key

        return normalized_key

    def has_language(self, language_code: str) -> bool:
        return normalize_language_code(language_code) in self.languages

    def _language_chain(self, language_code: str | None) -> tuple[str, ...]:
        languages = (
            normalize_language_code(language_code) if language_code else None,
            self.fallback_language,
            self.default_language,
        )
        result: list[str] = []
        for language in languages:
            if language and language not in result:
                result.append(language)
        return tuple(result)

    def _lookup(self, language_code: str, key: str) -> object:
        data: object = self.languages.get(language_code, {})
        for part in key.split("."):
            if not isinstance(data, Mapping) or part not in data:
                return _MISSING
            data = data[part]
        return data

    def _load_yaml(self, file: Path) -> LocaleData:
        try:
            with file.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise LocaleFileError(f"failed to parse locale file {file}") from e
        if not isinstance(data, dict):
            raise LocaleFileError(f"{file} must contain a YAML mapping")
        return data

    def _format(self, template: str, values: Mapping[str, object]) -> str:
        try:
            return template.format_map(_SafeFormatMap(values))
        except (AttributeError, IndexError, KeyError, TypeError, ValueError):
            return template


async def _resolve_event_language(
    bot: Bot,
    event: Event,
    default_language: str,
) -> str:
    try:
        aid = await get_aid(bot, event)
        return await get_language(aid)
    except LocalesAccountError:
        return default_language


def create_reply(store: LocaleStore, language_code: str | None = None) -> Reply:
    async def reply(key: str, **kwargs: object) -> str:
        return store.render(key, language_code, **kwargs)

    return reply


def locales_init(
    lang_dir: str | Path | None = None,
    *,
    store: LocaleStore | None = None,
    default_language: str | None = None,
    fallback_language: str | None = None,
):
    if store is None:
        if lang_dir is None:
            raise ValueError("lang_dir is required when store is not provided")
        store = LocaleStore(
            lang_dir,
            default_language=default_language,
            fallback_language=fallback_language,
        )
    elif lang_dir is not None:
        raise ValueError("lang_dir and store cannot be provided together")

    async def _dependency(bot: Bot, event: Event) -> Reply:
        language_code = await _resolve_event_language(
            bot,
            event,
            store.default_language,
        )
        return create_reply(store, language_code)

    return Depends(_dependency)
__all__ = [
    "LocaleError",
    "LocaleFileError",
    "LocaleStore",
    "Reply",
    "create_reply",
    "locales_init",
    "normalize_language_code",
]
