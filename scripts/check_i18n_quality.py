#!/usr/bin/env python3

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "nmos_common"))

from nmos_common.i18n import DEFAULT_UI_LOCALE, LANGUAGE_OPTIONS, TRANSLATIONS  # noqa: E402

PLACEHOLDER_PATTERN = re.compile(r"{([a-zA-Z0-9_]+)}")
BAD_MARKERS = (
    "\u00e2\u20ac\u201d",
    "\u00e2\u20ac\u201c",
    "\u00e2\u2020\u2019",
    "\ufffd",
)
CRITICAL_KEYS = (
    "Language",
    "Security profile",
    "Apply settings",
    "Skip setup",
    "Start using NM-OS",
    "Settings saved. Some privacy changes apply on the next boot.",
)


def locale_language(locale: str) -> str:
    return re.split(r"[_@.]", locale, maxsplit=1)[0].lower()


def repair_mojibake(text: str) -> str:
    if "\u00c3" not in text and "\u00c2" not in text:
        return text
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def placeholders(text: str) -> set[str]:
    return set(PLACEHOLDER_PATTERN.findall(text))


def main() -> int:
    errors: list[str] = []
    locale_entries = list(LANGUAGE_OPTIONS)
    configured_locales = [locale for locale, _label in locale_entries]

    if DEFAULT_UI_LOCALE not in configured_locales:
        errors.append(f"default locale is missing from LANGUAGE_OPTIONS: {DEFAULT_UI_LOCALE}")

    for locale, _label in locale_entries:
        if locale == DEFAULT_UI_LOCALE:
            continue
        language = locale_language(locale)
        table = TRANSLATIONS.get(language)
        if not isinstance(table, dict):
            errors.append(f"missing translation table for locale {locale} (language key '{language}')")
            continue

        for key in CRITICAL_KEYS:
            if key not in table:
                errors.append(f"missing critical translation key for {locale}: {key!r}")

        for source_text, translated in table.items():
            if not isinstance(source_text, str):
                errors.append(f"non-string translation source key in {locale}: {source_text!r}")
                continue
            if not isinstance(translated, str):
                errors.append(f"non-string translation value in {locale} for key {source_text!r}")
                continue
            if not translated.strip():
                errors.append(f"empty translation value in {locale} for key {source_text!r}")
                continue

            source_placeholders = placeholders(source_text)
            translated_placeholders = placeholders(translated)
            if source_placeholders != translated_placeholders:
                errors.append(
                    f"placeholder mismatch in {locale} for {source_text!r}: "
                    f"{sorted(source_placeholders)} != {sorted(translated_placeholders)}"
                )

            repaired_source = repair_mojibake(source_text)
            repaired_value = repair_mojibake(translated)
            for marker in BAD_MARKERS:
                if marker in repaired_source or marker in repaired_value:
                    errors.append(f"mojibake marker {marker!r} in {locale} key/value for {source_text!r}")
                    break

    if errors:
        print("i18n quality check failed:", file=sys.stderr)
        for item in errors:
            print(f"- {item}", file=sys.stderr)
        return 1

    print(f"i18n quality checks passed for {len(locale_entries)} configured locales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
