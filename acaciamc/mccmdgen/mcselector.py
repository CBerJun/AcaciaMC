"""Low-level utility for Minecraft selectors."""

__all__ = ["MCSelector", "SELECTORVAR_T"]

from copy import deepcopy
from typing import Union, Dict, Any, Optional, List

from acaciamc.mccmdgen.cmds import mc_str

SELECTORVAR_T = str  # Literal["a", "e", "r", "p", "s", "initiator"]


class MCSelector:
    """Low-level utility for Minecraft selectors."""

    def __init__(self, var: Union[SELECTORVAR_T, None] = None) -> None:
        # When `var` is None, the variable is unknown.
        self.var = var
        self.args: Dict[str, Any] = {}

    def copy(self) -> "MCSelector":
        res = MCSelector(self.var)
        res.args = deepcopy(self.args)
        return res

    def is_var_set(self) -> bool:
        return self.var is not None

    def has_arg(self, arg: str) -> bool:
        return arg in self.args

    def get_tags(self) -> List[str]:
        """
        Return the list of tags in the selector.
        Modifying the returned list will modify the selector.
        """
        return self.args.setdefault("tag", [])

    @staticmethod
    def arg_to_str(arg: str, value):
        if arg in ("type", "name", "m"):
            return "%s=%s" % (arg, value)
        elif arg in ("tag", "family"):
            return ",".join(("%s=%s" % (arg, v)) for v in value)
        elif arg in ("tag!", "type!", "name!", "family!", "m!"):
            n = arg[:-1]  # strip "!"
            return ",".join(("%s=!%s" % (n, v)) for v in value)
        elif arg in ("c", "l", "lm"):
            return "%s=%d" % (arg, value)
        elif arg in ("dx", "dy", "dz", "rx", "rxm", "ry", "rym", "r", "rm"):
            return "%s=%.3f" % (arg, value)
        elif arg == "hasitem":
            res = []
            for defi in value:
                options = [
                    "item=%s" % defi["item"],
                    "quantity=%s" % defi["quantity"]
                ]
                if "slot_type" in defi:
                    options.append("location=%s" % defi["slot_type"])
                    if "slot_num" in defi:
                        options.append("slot=%s" % defi["slot_num"])
                if "data" in defi:
                    options.append("data=%d" % defi["data"])
                res.append("{%s}" % ",".join(options))
            if len(res) == 1:
                return "hasitem=%s" % res[0]
            else:
                return "hasitem=[%s]" % ",".join(res)
        elif arg == "scores":
            return "scores={%s}" % ",".join(
                "%s=%s" % (scb, range_) for scb, range_ in value
            )
        elif arg == "haspermission":
            return "haspermission={%s}" % ",".join(
                [("%s=enabled" % p) for p in value[0]]
                + [("%s=disabled" % p) for p in value[1]]
            )
        else:
            raise ValueError("Unknown selector argument: %r" % arg)

    def to_str(self):
        var = self.var
        if var is None:
            var = "e"  # when var is not set it should be all entities
        return "@%s%s" % (
            var,
            "[%s]" % ",".join(self.arg_to_str(arg, value)
                              for arg, value in self.args.items())
            if self.args else ""
        )

    def player_type(self):
        if self.has_arg("type"):
            if self.args["type"] not in ("player", "minecraft:player"):
                raise ValueError
        else:
            self.type("player")

    def tag(self, *tag: str):
        if not self.has_arg("tag"):
            self.args["tag"] = []
        self.args["tag"].extend(map(mc_str, tag))

    def tag_n(self, *tag: str):
        if not self.has_arg("tag!"):
            self.args["tag!"] = []
        self.args["tag!"].extend(map(mc_str, tag))

    def type(self, type_: str):
        self.args["type"] = type_

    def type_n(self, *types: str):
        if not self.has_arg("type!"):
            self.args["type!"] = []
        self.args["type!"].extend(types)

    def family(self, *families: str):
        if not self.has_arg("family"):
            self.args["family"] = []
        self.args["family"].extend(families)

    def family_n(self, *families: str):
        if not self.has_arg("family!"):
            self.args["family!"] = []
        self.args["family!"].extend(families)

    def limit(self, limit: int):
        self.args["c"] = limit

    def distance(self, min_: Optional[float], max_: Optional[float]):
        if min_ is not None:
            self.args["rm"] = min_
        if max_ is not None:
            self.args["r"] = max_

    def volume(self, dx: float, dy: float, dz: float):
        self.args["dx"] = dx
        self.args["dy"] = dy
        self.args["dz"] = dz

    def rot_vertical(self, min_: float, max_: float):
        self.args["rxm"] = min_
        self.args["rx"] = max_

    def rot_horizontal(self, min_: float, max_: float):
        self.args["rym"] = min_
        self.args["ry"] = max_

    def name(self, name: str):
        self.args["name"] = mc_str(name)

    def name_n(self, *names: str):
        if not self.has_arg("name!"):
            self.args["name!"] = []
        self.args["name!"].extend(map(mc_str, names))

    def has_item(self, item: str, quantity: str, data: Optional[int],
                 slot_type: Optional[str], slot_num: Optional[int]):
        if not self.has_arg("hasitem"):
            self.args["hasitem"] = []
        v = {"item": item, "quantity": quantity}
        if data is not None:
            v["data"] = data
        if slot_type is not None:
            v["slot_type"] = slot_type
            if slot_num is not None:
                v["slot_num"] = slot_num
        self.args["hasitem"].append(v)

    def scores(self, objective: str, range_: str):
        if not self.has_arg("scores"):
            self.args["scores"] = []
        self.args["scores"].append((mc_str(objective), range_))

    def level(self, min_: Optional[int], max_: Optional[int]):
        if min_ is not None:
            self.args["lm"] = min_
        if max_ is not None:
            self.args["l"] = max_

    def game_mode(self, mode: str):
        self.args["m"] = mode

    def game_mode_n(self, *modes: str):
        if not self.has_arg("m!"):
            self.args["m!"] = []
        self.args["m!"].extend(modes)

    def has_permission(self, *permissions: str):
        if not self.has_arg("haspermission"):
            self.args["haspermission"] = ([], [])
        self.args["haspermission"][0].extend(permissions)

    def has_permission_n(self, *permissions: str):
        if not self.has_arg("haspermission"):
            self.args["haspermission"] = ([], [])
        self.args["haspermission"][1].extend(permissions)
