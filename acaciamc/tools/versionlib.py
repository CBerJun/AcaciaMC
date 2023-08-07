"""Tools for working with Minecraft version related contents."""

__all__ = [
    # Utils
    "only", "format_version",
    # Version requirements
    "at_least", "at_most", "between", "older",
    "VersionRequirement",
    # Type checking
    "VERSION_T"
]

from typing import Callable, Tuple, Optional, TYPE_CHECKING
from abc import ABCMeta, abstractmethod

from acaciamc.constants import Config
from acaciamc.error import Error as AcaciaError, ErrorType

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler

VERSION_T = Tuple[int, ...]

def format_version(version: VERSION_T):
    return ".".join(map(str, version))

class VersionRequirement(metaclass=ABCMeta):
    @abstractmethod
    def to_str(self) -> str:
        pass

    @abstractmethod
    def validate(self, version: VERSION_T) -> bool:
        pass

class VersionRanged(VersionRequirement):
    def __init__(self, min_: Optional[VERSION_T], max_: Optional[VERSION_T]):
        if not min_ and not max_:
            raise ValueError("min and max versions cannot both be None")
        self.min = min_
        self.max = max_

    def to_str(self) -> str:
        if self.min:
            if self.max:
                return "%s~%s" % (
                    format_version(self.min), format_version(self.max)
                )
            return ">=%s" % format_version(self.min)
        assert self.max
        return "<=%s" % format_version(self.max)

    def validate(self, version: VERSION_T) -> bool:
        if self.min:
            if self.max:
                return self.min <= version <= self.max
            return self.min <= version
        assert self.max
        return version <= self.max

class VersionLower(VersionRequirement):
    def __init__(self, version: VERSION_T) -> None:
        super().__init__()
        self.version = version

    def to_str(self) -> str:
        return "<%s" % format_version(self.version)

    def validate(self, version: VERSION_T) -> bool:
        return self.version < version

def at_least(version: VERSION_T) -> VersionRequirement:
    """Requires >= the given version."""
    return VersionRanged(version, None)

def at_most(version: VERSION_T) -> VersionRequirement:
    """Requires <= the given version."""
    return VersionRanged(None, version)

def between(min_: VERSION_T, max_: VERSION_T) -> VersionRequirement:
    """Requires between the given versions (inclusive)."""
    return VersionRanged(min_, max_)

def older(version: VERSION_T):
    """Requires < the given version."""
    return VersionLower(version)

def only(version: VersionRequirement):
    """Return a decorator that makes the decorated binary function only
    available when given version requirement is satisfied.
    """
    def _decorator(func: Callable):
        def _decorated(compiler: "Compiler", args, kwds):
            if version.validate(Config.mc_version):
                return func(compiler, args, kwds)
            raise AcaciaError(
                ErrorType.ANY,
                message="The function is not available for Minecraft "
                        "version %s; expecting %s"
                % (format_version(Config.mc_version), version.to_str())
            )
        return _decorated
    return _decorator
