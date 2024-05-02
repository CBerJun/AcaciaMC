"""
Compile time data returned by __spawn__ method in entity templates that
is used to specify the options of spawning the entity.
"""

__all__ = ["SpawnInfoDataType", "SpawnInfo", "SpawnInfoType"]

from acaciamc.tools import axe
from acaciamc.tools.named_tuple import named_tuple
from .position import PosDataType
from .none import NoneLiteral

_nt = named_tuple(
    "SpawnInfo",
    (
        ("type", axe.Nullable(axe.LiteralString())),
        ("pos", axe.Nullable(axe.Typed(PosDataType))),
        ("event", axe.Nullable(axe.LiteralString())),
        ("name", axe.Nullable(axe.LiteralString())),
    ),
    {
        "type": NoneLiteral(),
        "pos": NoneLiteral(),
        "event": NoneLiteral(),
        "name": NoneLiteral(),
    }
)
SpawnInfoDataType = _nt.cls_datatype
SpawnInfoType = _nt.cls_type
SpawnInfo = _nt.cls_expr
ctdt_spawninfo = _nt.cdata_type
