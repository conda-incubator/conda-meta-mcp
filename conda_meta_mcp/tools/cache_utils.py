"""Minimal external cache clearing registry utilities."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from typing import TypeVar

F = TypeVar("F", bound=Callable)

ExternalCacheClearer = Callable[[], None]
_external_cache_clearers: list[ExternalCacheClearer] = []


def register_external_cache_clearer(clearer: ExternalCacheClearer) -> None:
    """Register a callback that clears external or tool-level caches."""
    _external_cache_clearers.append(clearer)


def clear_external_library_caches() -> None:
    """Call all registered cache clearers (best-effort; ignore their errors)."""
    for clearer in list(_external_cache_clearers):
        with suppress(Exception):
            clearer()
