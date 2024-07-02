"""
String templating utilities.

Arguments are substituted through `${name args}` where `name` is the
argument name and `args` is an optional string that contains
argument-specific metadata. `name` can only consist of English letters,
ASCII digits and hyphen '-'.
"""

from typing import Match, Mapping
from abc import ABCMeta, abstractmethod
from enum import Enum
import re

_ARGUMENT_PATTERN = re.compile(
    r'''
    \$  # Begin with $
    (?:
        (?:\{
            (?P<name>[-a-zA-Z0-9]+)
            (?P<metadata>[^}]*)
        \})  # Actual substitution
        |
        (?P<dollar>\$)  # $$ escape
    )
    ''',
    flags=re.VERBOSE
)

def substitute(template: str, args: Mapping[str, "STArgument"]):
    """
    Substitute `template` with `args`.
    `args` keys are argument names and values are argument values.
    """
    def _replace(match: Match) -> str:
        dollar = match.group("dollar")
        if dollar is not None:
            # Double dollar escape, delete one '$'
            return ''
        name = match.group("name")
        metadata = match.group("metadata")
        assert isinstance(name, str)
        assert isinstance(metadata, str)
        return args[name].process(metadata.strip())
    return _ARGUMENT_PATTERN.sub(_replace, template)

def repr_single(s: str) -> str:
    """Similar to Python's `repr` but always use single quotes."""
    # This relies on the fact that Python always uses single quote for
    # repr() if there is any double quote in string:
    return "'" + repr('"' + s)[2:]

class STArgument(metaclass=ABCMeta):
    """An argument in a template message."""

    @abstractmethod
    def process(self, metadata: str) -> str:
        pass

class STStr(STArgument):
    """
    A string argument in template message.
    ${name} => display value quoted in single quotes "'".
        Escapes will be created for single quote itself as well as
        some other characters (Python's repr is used).
    ${name raw} => display value
    """

    def __init__(self, value: str):
        self.value = value

    def process(self, metadata: str) -> str:
        if metadata == 'raw':
            return self.value
        assert not metadata
        return repr_single(self.value)

class STInt(STArgument):
    """
    An integer argument in template message.
    ${name} => display integer (using Python's str(integer) conversion)
    ${name plural} => display 's' if value != 1, else ''
    ${name plural es} => display 'es' if value != 1, else ''
    ${name plural ies y} => display 'ies' if value != 1, else 'y'
    """

    def __init__(self, value: int):
        self.value = value

    def process(self, metadata: str) -> str:
        # Plural suffix
        if metadata.startswith('plural'):
            suffix = metadata[6:]  # len('plural') == 6
            suffix = suffix.lstrip()
            if ' ' in suffix:
                # Both plural and singular given
                plural, singular = suffix.split(' ')
            elif not suffix:
                # No suffix given -> use 's'
                plural, singular = 's', ''
            else:
                # Only plural given
                plural, singular = suffix, ''
            if self.value == 1:
                return singular
            else:
                return plural
        # Just the number
        assert not metadata
        return str(self.value)

class DisplayableEnum(Enum):
    """
    Usage:
    >>> class E(DisplayableEnum):
    ...     x = 1, "X!"
    ...     y = 2, "Y!"
    >>> E.x.value
    1
    >>> E.y.display
    'Y!'
    """

    display: str

    def __new__(cls, value: object, display: str):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.display = display
        return obj

class STEnum(STStr):
    """Subclass of `STStr` that displays a `DisplayableEnum`."""

    def __init__(self, value: DisplayableEnum):
        super().__init__(value.display)
        self.enum_value = value
