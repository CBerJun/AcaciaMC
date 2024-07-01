"""Named tuple style compile-time immutable objects in Acacia."""

__all__ = ["named_tuple"]

from types import new_class, SimpleNamespace
from typing import Dict, NamedTuple, Tuple, Any, Type as PyType, Sequence

from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.mccmdgen.utils import apply_decorators
from acaciamc.objects.types import Type
from acaciamc.tools import axe, cmethod_of


class WithOrigin(axe.ConverterContainer):
    def __init__(self, converter: axe._CONVERTER_T):
        super().__init__(converter)
        self.converter = converter

    def convert(self, origin):
        return origin, self.converter.convert(origin)

    def cconvert(self, origin):
        return origin, self.converter.cconvert(origin)

    def get_show_name(self) -> str:
        return self.converter.get_show_name()


class _NamedTupleInfo(NamedTuple):
    name: str
    cls_datatype: PyType[DefaultDataType]
    cls_expr: PyType[ConstExprCombined]
    cls_type: PyType[Type]
    cdata_type: CTDataType


_MISSING = object()


def named_tuple(
        name: str, fields: Sequence[Tuple[str, axe._CONVERTER_T]],
        defaults: Dict[str, Any]
) -> _NamedTupleInfo:
    field_names = [name for name, _ in fields]
    if any(s.startswith("__") for s in field_names):
        raise ValueError("Field names cannot start with '__'")

    def dt_body(ns):
        ns["name"] = name

    dt = new_class(f"NamedTupleDataType_{name}", (DefaultDataType,),
                   exec_body=dt_body)
    ctdt = CTDataType(name)

    def expr_body(ns):
        def __init__(self: AcaciaExpr, data: Dict[str, Tuple[Any, Any]]):
            super(expr, self).__init__(dt())
            self.fields = SimpleNamespace()
            for fname, (raw, converted) in data.items():
                setattr(self.fields, fname, converted)
                self.attribute_table.set(fname, raw)

        ns["__init__"] = __init__
        ns["cdata_type"] = ctdt

    expr = new_class(f"NamedTuple_{name}", (ConstExprCombined,),
                     exec_body=expr_body)
    ctor_args1 = [
        axe.arg(fname, WithOrigin(conv))
        for fname, conv in fields
        if fname not in defaults
    ]
    ctor_args2 = [
        axe.arg(
            fname, WithOrigin(conv),
            default=(
                defaults[fname],  # raw
                axe._get_convert(defaults[fname], conv)()  # converted
            )
        )
        for fname, conv in fields
        if fname in defaults
    ]
    evolve_args = [
        axe.arg(fname, WithOrigin(conv), default=_MISSING)
        for fname, conv in fields
    ]

    def type_body(ns):
        def do_init(self):
            @cmethod_of(self, "__new__")
            @axe.chop
            @apply_decorators(ctor_args1)
            @apply_decorators(ctor_args2)
            def _new(compiler, **kwds):
                return expr(kwds)

            @cmethod_of(self, "evolve")
            @axe.chop
            @axe.arg("__original", dt)
            @axe.slash
            @apply_decorators(evolve_args)
            def _evolve(compiler, __original: AcaciaExpr, **kwds):
                for fname in field_names:
                    if kwds[fname] is _MISSING:
                        kwds[fname] = (
                            __original.attribute_table.lookup(fname),  # raw
                            getattr(__original.fields, fname)  # converted
                        )
                return expr(kwds)

        def datatype_hook(self):
            return dt()

        def cdatatype_hook(self):
            return ctdt

        ns["do_init"] = do_init
        ns["datatype_hook"] = datatype_hook
        ns["cdatatype_hook"] = cdatatype_hook

    typecls = new_class(f"NamedTupleType_{name}", (Type,),
                        exec_body=type_body)
    return _NamedTupleInfo(name, dt, expr, typecls, ctdt)
