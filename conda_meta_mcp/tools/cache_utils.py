"""Caching utilities with TTL (time-to-live) expiration support."""

from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import TypeVar

T = TypeVar("T")


def lru_cache_with_ttl(
    ttl_minutes: int = 60,
    maxsize: int = 128,
):
    """LRU cache decorator with TTL expiration.

    Provides a function cache with:
    - Maximum number of cached entries (LRU eviction)
    - Time-to-live expiration (automatic cache invalidation)
    - Minimal overhead for cache hits

    Args:
        ttl_minutes: Cache entry lifetime in minutes. After this time,
                     cached entries are considered stale and recomputed.
        maxsize: Maximum number of cache entries. When exceeded, the oldest
                entry (by timestamp) is evicted.

    Returns:
        Decorator function for caching callables with TTL support.

    Example:
        @lru_cache_with_ttl(ttl_minutes=60, maxsize=1024)
        def expensive_operation(arg1: str, arg2: int) -> str:
            return f"Result for {arg1} and {arg2}"

        # First call: computes result (~100ms)
        result1 = expensive_operation("test", 42)

        # Second call: returns cached result (<1ms)
        result2 = expensive_operation("test", 42)

        # After 60 minutes: TTL expires, recomputes result
        # Different args: cache miss, computes new result
        result3 = expensive_operation("other", 99)
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cache_dict = {}
        timestamps = {}

        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Create cache key from function arguments
            cache_key = (args, tuple(sorted(kwargs.items())))
            now = datetime.now()

            # Check if cached and not expired
            if cache_key in cache_dict:
                timestamp = timestamps[cache_key]
                age_seconds = (now - timestamp).total_seconds()

                if age_seconds < ttl_minutes * 60:
                    # Cache hit and not expired
                    return cache_dict[cache_key]
                else:
                    # Cache expired, remove it
                    del cache_dict[cache_key]
                    del timestamps[cache_key]

            # Enforce maxsize limit (LRU eviction)
            if len(cache_dict) >= maxsize:
                # Find and remove oldest entry
                oldest_key = min(timestamps, key=lambda k: timestamps[k])
                del cache_dict[oldest_key]
                del timestamps[oldest_key]

            # Compute result and cache it
            result = func(*args, **kwargs)
            cache_dict[cache_key] = result
            timestamps[cache_key] = now

            return result

        # Attach cache introspection methods
        wrapper.cache_info = lambda: {  # type: ignore[attr-defined]
            "hits": len(cache_dict),
            "maxsize": maxsize,
            "ttl_minutes": ttl_minutes,
            "entries": len(cache_dict),
        }
        wrapper.cache_clear = lambda: (cache_dict.clear(), timestamps.clear())  # type: ignore[attr-defined]

        return wrapper

    return decorator
