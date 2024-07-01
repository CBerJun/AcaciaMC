"""Miscellaneous utility stuffs."""

__all__ = ["InvalidOpError", "unreachable", "apply_decorators"]

from typing import Reversible


class InvalidOpError(Exception):
    """Can be raised in some methods to indicate an invalid operation."""
    pass


def unreachable(message: str = ""):
    """Indicates an unreachable code path."""
    suffix = f": {message}" if message else ""
    raise AssertionError("unreachable() called" + suffix)


def apply_decorators(decorators: Reversible):
    """
    Return a decorator that applies a sequence of decorators.
        @apply_decorators([a, b])
    is equivalent to
        @a
        @b
    """

    def decorator(func):
        for deco in reversed(decorators):
            func = deco(func)
        return func

    return decorator
