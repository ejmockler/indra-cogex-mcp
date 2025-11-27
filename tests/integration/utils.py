"""
Shared assertion and helper utilities for integration tests that hit live backends.

These helpers keep assertions consistent and concise while avoiding brittle,
high-threshold checks. They intentionally validate both shape and minimal
presence of data.
"""

from __future__ import annotations

import json
from typing import Any, Iterable


class AssertionErrorWithContext(AssertionError):
    """Assertion error that carries sample context for quicker debugging."""

    def __init__(self, message: str, sample: Any | None = None):
        if sample is not None:
            message = f"{message}\nSample: {sample!r}"
        super().__init__(message)


def assert_json(result: str) -> dict[str, Any]:
    """Parse JSON string and return dict, raising informative assertion on failure."""
    try:
        return json.loads(result)
    except json.JSONDecodeError as exc:
        raise AssertionErrorWithContext("Response was not valid JSON", result) from exc


def assert_keys(data: dict[str, Any], required_keys: Iterable[str]) -> None:
    """Ensure all required keys are present in a dictionary."""
    missing = [k for k in required_keys if k not in data]
    if missing:
        raise AssertionErrorWithContext(f"Missing required keys: {missing}", data)


def assert_non_empty(data: dict[str, Any], key: str, min_len: int = 1) -> None:
    """
    Assert that a key exists and its value has at least min_len items/characters.
    Works for list/dict/str types.
    """
    if key not in data:
        raise AssertionErrorWithContext(f"Key '{key}' not present", data)
    value = data[key]
    if value is None:
        raise AssertionErrorWithContext(f"Key '{key}' is None", data)
    if hasattr(value, "__len__"):
        if len(value) < min_len:
            raise AssertionErrorWithContext(
                f"Key '{key}' expected length >= {min_len}, got {len(value)}",
                value,
            )
    else:
        raise AssertionErrorWithContext(f"Key '{key}' has no length", value)


def assert_id_format(value: str, predicate, description: str) -> None:
    """
    Validate identifier format with a predicate function.

    Args:
        value: identifier string
        predicate: function that returns True when format is correct
        description: human-readable description for error messages
    """
    if not predicate(value):
        raise AssertionErrorWithContext(f"Identifier format invalid for {description}", value)


def assert_pagination(first_page: Any, second_page: Any) -> None:
    """
    Basic pagination sanity: two pages should differ and union should be larger.
    Accepts list-like or dict with 'items' key; no strict schema assumption.
    """
    def _extract_items(page: Any):
        if isinstance(page, dict) and "items" in page:
            return page["items"]
        return page

    items1 = _extract_items(first_page) or []
    items2 = _extract_items(second_page) or []

    if items1 == items2:
        raise AssertionErrorWithContext("Pagination yielded identical pages", {"page1": items1, "page2": items2})

    combined = {json.dumps(item, sort_keys=True) for item in items1} | {
        json.dumps(item, sort_keys=True) for item in items2
    }
    if len(combined) <= max(len(items1), len(items2)):
        raise AssertionErrorWithContext(
            "Pagination did not increase unique item count",
            {"len1": len(items1), "len2": len(items2), "combined": len(combined)},
        )
