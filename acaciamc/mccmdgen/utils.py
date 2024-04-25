"""Miscellaneous utility stuffs."""

__all__ = ["InvalidOpError", "unreachable"]

class InvalidOpError(Exception):
    """Can be raised in some methods to indicate an invalid operation."""
    pass

def unreachable(message: str = ""):
    """Indicates an unreachable code path."""
    suffix = f": {message}" if message else ""
    raise AssertionError("unreachable() called" + suffix)
