"""
world - Interact with the Minecraft world.

Types:
Item: str (item id) or Item object (id + data + components)
Block: str (block id) or Block object (id + block states)
Selector: entity or Engroup
PlayerSelector: player type selector

TODO list:
Block related:
/clone
clone(origin: Pos, offset: Offset, dest: Offset,
      mode: "move" | "force" | "replace", no_air=False)
clone_only(origin: Pos, offset: Offset, dest: Offset,
           block: Block, mode: "move" | "force" | "replace")
/fill
fill(origin: Pos, offset: Offset, block: Block,
     replacement: "destroy" | "hollow" | "outline" | "aironly" | "all")
fill_replace(origin: Pos, offset: Offset, block: Block,
             replaces: Block)
/setblock
setblock(pos: Pos, block: Block,
         replacement: "aironly" | "destroy" | "all")

Entity related:
/damage
damage(target: Selector, amount: int-literal, cause: None | str,
       damager: None | entity)
/effect
effect_give(target: Selector, effect: str, duration: int-literal,
            amplifier: int-literal = 0, particle=True)
effect_clear(target: Selector)
/enchant
enchant(target: Selector, enchantment: str, level: int-literal = 1)
/event
event_entity(target: Selector, event: str)
/kill
kill(target: Selector)
/me
msg_me(sender: entity, message: str)
/replaceitem
replaceitem_block(pos: Pos, slot: int-literal, item: Item,
                  amount=1, keep_old=False)
replaceitem_entity(target: Selector, location: str, slot: int-literal,
                   item: Item, amount=1, keep_old=False)
/ride
ride_start_tp_ride(rider: entity, ride: entity)
ride_start_tp_rider(rider: Selector, ride: entity,
                    fill: "if_group_fits" | "until_full" = "until_full")
ride_stop(rider: Selector)
ride_evict_riders(ride: Selector)
summon_rider(ride: Selector, type: str, event: None | str = None,
             name: None | str)
summon_ride(rider: Selector, type: str, event: None | str = None,
            name: None | str, mode: "skip_riders" | "no_ride_change"
            | "reassign_rides" = "reassign_rides")
/say
msg_say(sender: entity, message: str)
/spreadplayers
spread(target: Selector, center: Pos, range: float, interval=0.0)
/summon (pending)
# Consider using Acacia's entity system first.
summon(type: str, pos: Pos,
       event: None | str = None, name: None | str = None,
       rot [1.19.70+]: Rot = Rot(0, 0))
/tag (pending)
# Consider using Acacia's entity system first.
tag_add(target: Selector, tag: str)
tag_remove(target: Selector, tag: str)
/tell
msg_tell(sender: entity, receiver: Selector, message: str)
/tp
tp(target: Selector, dest: Pos, check_for_blocks=False)
rotate(target: Selector, rot: Rot)
# Just for convenience:
move(target: Selector, x=0.0, y=0.0, z=0.0, check_for_blocks=False)
move_local(target: Selector, left=0.0, up=0.0, front=0.0,
           check_for_blocks=False)

Player only:
/ability (EDU)
ability(player: PlayerSelector, ability: str, value: bool-literal)
/clear
clear_inventory(player: PlayerSelector)
clear(player: PlayerSelector, item_id: str, item_data: int-literal = -1,
      max_count: int-literal = -1)
/clearspawnpoint
spawnpoint_clear(player: PlayerSelector)
/gamemode
gamemode(player: PlayerSelector, mode: "survival" | "creative"
         | "adventure" | "default" | "spectator")
/give
give(player: PlayerSelector, item: Item, amount=1)
/kick
kick(player_name: str, reason: str | None = None)
/recipe
recipe(player: PlayerSelector, recipe: str, unlock: bool-literal)
/spawnpoint
spawnpoint_set(player: PlayerSelector, pos: Pos)
/xp
xp_add_levels(player: PlayerSelector, amount: int-literal)
xp_add_points(player: PlayerSelector, amount: int-literal)

Client side:
/camera (WIP)
camera_clear(player: Selector)
camera_fade(player: Selector,
            red: int-literal | None,
            green: int-literal | None,
            blue: int-literal | None,
            fade_in: float | None,
            hold: float | None,
            fade_out: float | None)
camera_set(player: Selector, preset: str,
           pos: Pos | None, rot: Rot | None,
           ease_time: float | None, ease_type: str | None)
/camerashake
camerashake_add(player: Selector, intensity: float,
                seconds: float, type: "positional" | "rotational")
camerashake_stop(player: Selector)
/dialogue
dialogue_open(npc: entity, player: Selector, scene: str | None = None)
dialogue_change(npc: entity, scene: str,
                player: Selector = <All players>)
/fog
fog_remove(player: Selector, name: str)
fog_pop(player: Selector, name: str)
fog_push(player: Selector, fog: str, name: str | None = None) -> str
/particle
particle(particle: str, pos: Pos)
/playanimation
playanimation(target: Selector, animation: str, next_state="default",
              fade_out=0.0, stop_molang="query.any_animation_finished",
              controller: str | None)
/playsound
sound_play(player: Selector, sound: str, pos: Pos, volume=1.0,
           pitch=1.0, min_volume=0.0)
/stopsound
sound_stop(player: Selector, sound: str | None = None)

Global:
/difficulty
settings_difficulty(value: "easy" | "normal" | "hard" | "peaceful")
/function
# Just for calling other works that have been done in mcfunction.
function(function: str)
/gamerule
settings(name: str, value: bool-literal | int-literal)
/gametest (?, pending)
/immutableworld (EDU)
settings_immutableworld(value: bool-literal)
/mobevent
settings_mobevent_master(value: bool-literal)
settings_mobevent(event: str, value: bool-literal)
/music
music_play(track: str, volume=1.0, fade=0.0, repeat=False)
music_queue(track: str, volume=1.0, fade=0.0, repeat=False)
music_stop(fade=0.0)
music_volume(volume: float)
/scoreboard (pending)
# Maybe add a module for displaying scoreboard instead of these?
scoreboard_add_objective(display_name: None | str = None,
                         name: None | str = None) -> str
scoreboard_remove_objective(name: str)
scoreboard_display(name: str, slot: "sidebar" | "list" | "belowname",
                   order: "ascending" | "descending")
scoreboard_display_clear(slot: "sidebar" | "list" | "belowname")
/script (?, pending)
/scriptevent (?)
scriptevent(message_id: str, message: str)
/setworldspawn
spawnpoint_world(pos: Pos)
/tickingarea
tickingarea_add(origin: Pos, offset: Offset, preload=False,
                name: str | None = None) -> str
tickingarea_add_circle(center: Pos, radius: int-literal, preload=False,
                       name: str | None = None) -> str
tickingarea_remove(name: str)
tickingarea_remove_pos(pos: Pos)
tickingarea_remove_all()
tickingarea_preload(name: str, state: bool-literal)
tickingarea_preload_pos(pos: Pos, state: bool-literal)
/time
time_add(ticks: int-literal)
time_set(value: int-literal | "day" | "night" | "noon"
                | "midnight" | "sunrise" | "sunset")
/toggledownfall
weather_toggle()
/volumearea (?)
volumearea_add(id: str, origin: Pos, offset: Offset,
               name: str | None = None) -> str
volumearea_remove(name: str)
volumearea_remove_pos(pos: Pos)
volumearea_remove_all()
/weather
weather(weather: "clear" | "rain" | "thunder",
        duration: int-literal | None = None)
/wsserver
wsserver_connect(url: str)
wsserver_out()

Miscellaneous:
/loot
# Loot object
Loot.kill(target: entity, weapon: str) -> Loot
Loot.kill_hand(target: entity, killer: entity,
               hand: "mainhand" | "offhand") -> Loot
Loot(table: str, tool: str) -> Loot
Loot.hand(table: str, creator: entity,
          hand: "mainhand" | "offhand") -> Loot
# Use objects
loot.to_container(pos: Pos)
loot.give(player: Selector)
loot.spawn(pos: Pos)
loot.replace_block(pos: Pos, slot: int-literal, slot_num: int-literal)
loot.replace_entity(target: Selector, location: str,
                    slot: int-literal, slot_num: int-literal)
/structure
structure_save(origin: Pos, offset: Offset,
               location: "disk" | "memory" = "memory",
               entities=True, blocks=True,
               name: str | None = None) -> str
structure_load(name: str, dest: Pos,
               rotation: 0 | 90 | 180 | 270,
               mirror: "x" | "z" | "xz" | "none",
               entities=True, blocks=True, waterlog=False,
               integrity=1.0, seed: str | None = None,
               animation: "block_by_block" | "layer_by_layer"
               | None = None, animation_seconds: float | None = None)
structure_delete(name: str)

Judgement:
is_block(pos: Pos, block: Block) -> bool
is_same_area(origin: Pos, offset: Offset, other: Offset) -> bool
is_entity(ent: entity, entity_filter: Enfilter) -> bool
"""

import json
from typing import Dict, Callable, List, Union, Optional, TYPE_CHECKING

import acaciamc.mccmdgen.cmds as cmds
from acaciamc.localization import localize
from acaciamc.mccmdgen.ctexpr import CTDataType
from acaciamc.mccmdgen.datatype import DefaultDataType
from acaciamc.mccmdgen.expr import *
from acaciamc.objects import *
from acaciamc.tools import axe, resultlib, cmethod_of
from acaciamc.tools.versionlib import edu_only

if TYPE_CHECKING:
    from acaciamc.compiler import Compiler
    from acaciamc.mccmdgen.mcselector import MCSelector
    from acaciamc.objects.entity import _EntityBase

_methods: Dict[str, Callable] = {}


def _register(name: str):
    def _decorator(func: Callable):
        _methods[name] = func
        return func

    return _decorator


def _fmt_bool(value: bool):
    return "true" if value else "false"


class ItemDataType(DefaultDataType):
    name = "Item"


ctdt_item = CTDataType("Item")


class ItemType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("id", axe.LiteralString(), rename="id_")
        @axe.arg("data", axe.RangedLiteralInt(0, 32767), default=0)
        @axe.arg("keep_on_death", axe.LiteralBool(), default=False)
        @axe.arg("can_destroy", axe.ListOf(axe.LiteralString()), default=[])
        @axe.arg("can_place_on", axe.ListOf(axe.LiteralString()), default=[])
        @axe.arg("lock", axe.Nullable(
            axe.LiteralStringEnum("lock_in_slot", "lock_in_inventory")
        ), default=None)
        def _new(compiler, id_: str, data: int, keep_on_death: bool,
                 can_destroy: List[str], can_place_on: List[str], lock: str):
            components = {}
            if can_destroy:
                components["minecraft:can_destroy"] = {"blocks": can_destroy}
            if can_place_on:
                components["minecraft:can_place_on"] = {"blocks": can_place_on}
            if keep_on_death:
                components["minecraft:keep_on_death"] = {}
            if lock:
                components["minecraft:item_lock"] = {"mode": lock}
            return Item(id_, data, components)

    def datatype_hook(self):
        return ItemDataType()

    def cdatatype_hook(self):
        return ctdt_item


class Item(ConstExprCombined):
    cdata_type = ctdt_item

    def __init__(self, id_: str, data: int, components: dict):
        super().__init__(ItemDataType())
        self.id = id_
        self.data = data
        self.components = components

    def to_str(self, fmt: str) -> str:
        c = "" if not self.components else " " + json.dumps(self.components)
        return fmt.format(id=self.id, data=self.data, components=c)


class BlockDataType(DefaultDataType):
    name = "Block"


ctdt_block = CTDataType("Block")


class BlockType(Type):
    def do_init(self):
        @cmethod_of(self, "__new__")
        @axe.chop
        @axe.arg("id", axe.LiteralString(), rename="id_")
        @axe.arg("states", axe.MapOf(
            axe.LiteralString(),
            axe.AnyOf(axe.LiteralInt(), axe.LiteralBool(), axe.LiteralString())
        ), default={})
        def _new(compiler, id_: str, states: Dict[str, Union[str, int, bool]]):
            return Block(id_, states)

    def datatype_hook(self):
        return BlockDataType()

    def cdatatype_hook(self):
        return ctdt_block


class Block(ConstExprCombined):
    cdata_type = ctdt_block

    def __init__(self, id_: str,
                 states: Dict[str, Union[str, int, bool]]):
        super().__init__(BlockDataType())
        self.id = id_
        self.states = states

    @staticmethod
    def format_bs_value(value: Union[str, int, bool]) -> str:
        if isinstance(value, bool):
            return _fmt_bool(value)
        elif isinstance(value, int):
            return str(value)
        else:
            assert isinstance(value, str)
            return '"%s"' % value

    def to_str(self, compiler: "Compiler", fmt: str = "{id} {states}") -> str:
        if compiler.cfg.mc_version >= (1, 20, 10):
            EQ = "="
        else:
            EQ = ":"
        return fmt.format(id=self.id, states="[%s]" % ",".join(
            "".join(('"%s"' % key, EQ, self.format_bs_value(value)))
            for key, value in self.states.items()
        ))


class ArgBlock(axe.AnyOf):
    def __init__(self):
        super().__init__(axe.Typed(BlockDataType), axe.LiteralString())

    def convert(self, origin: AcaciaExpr) -> Block:
        res = super().convert(origin)
        if isinstance(res, str):
            res = Block(res, {})
        return res


class ArgItem(axe.AnyOf):
    def __init__(self):
        super().__init__(axe.Typed(ItemDataType), axe.LiteralString())

    def convert(self, origin: AcaciaExpr) -> Item:
        res = super().convert(origin)
        if isinstance(res, str):
            res = Item(res, 0, {})
        return res


##### Block related #####

@_register("clone")
@axe.chop
@axe.arg("origin", PosDataType)
@axe.arg("offset", PosOffsetDataType)
@axe.arg("dest", PosOffsetDataType)
@axe.arg("mode", axe.Nullable(
    axe.LiteralStringEnum("move", "force")
), default=None)
@axe.arg("no_air", axe.LiteralBool(), default=False)
def clone(compiler: "Compiler", origin: Position, offset: PosOffset,
          dest: PosOffset, mode: Optional[str], no_air: bool):
    if mode is None:
        mode = "normal"
    mask = "masked" if no_air else "replace"
    cmd = cmds.Execute(
        origin.context,
        runs="clone ~ ~ ~ %s %s %s %s" % (offset, dest, mask, mode)
    )
    return resultlib.commands([cmd])


@_register("clone_only")
@axe.chop
@axe.arg("origin", PosDataType)
@axe.arg("offset", PosOffsetDataType)
@axe.arg("dest", PosOffsetDataType)
@axe.arg("block", ArgBlock())
@axe.arg("mode", axe.Nullable(
    axe.LiteralStringEnum("move", "force")
), default=None)
def clone_only(compiler, origin: Position, offset: PosOffset, dest: PosOffset,
               mode: Optional[str], block: Block):
    if mode is None:
        mode = "normal"
    cmd = cmds.Execute(
        origin.context, runs="clone ~ ~ ~ %s %s filtered %s %s" % (
            offset, dest, mode, block.to_str(compiler)
        )
    )
    return resultlib.commands([cmd])


@_register("fill")
@axe.chop
@axe.arg("origin", PosDataType)
@axe.arg("offset", PosOffsetDataType)
@axe.arg("block", ArgBlock())
@axe.arg("replacement", axe.LiteralStringEnum(
    "destroy", "hollow", "outline", "aironly", "all"
), default="all")
def fill(compiler, origin: Position, offset: PosOffset, block: Block,
         replacement: str):
    if replacement == "aironly":
        replacement = "keep"
    elif replacement == "all":
        replacement = "replace"
    cmd = cmds.Execute(
        origin.context, runs="fill ~ ~ ~ %s %s %s" % (
            offset, block.to_str(compiler), replacement
        )
    )
    return resultlib.commands([cmd])


@_register("fill_replace")
@axe.chop
@axe.arg("origin", PosDataType)
@axe.arg("offset", PosOffsetDataType)
@axe.arg("block", ArgBlock())
@axe.arg("replaces", ArgBlock())
def fill_replace(compiler, origin: Position, offset: PosOffset, block: Block,
                 replaces: Block):
    cmd = cmds.Execute(
        origin.context, runs="fill ~ ~ ~ %s %s replace %s" % (
            offset, block.to_str(compiler), replaces.to_str(compiler)
        )
    )
    return resultlib.commands([cmd])


@_register("setblock")
@axe.chop
@axe.arg("pos", PosDataType)
@axe.arg("block", ArgBlock())
@axe.arg("replacement", axe.LiteralStringEnum(
    "aironly", "destroy", "all"
), default="all")
def setblock(compiler, pos: Position, block: Block, replacement: str):
    if replacement == "aironly":
        replacement = "keep"
    elif replacement == "all":
        replacement = "replace"
    cmd = cmds.Execute(
        pos.context, runs="setblock ~ ~ ~ %s %s" % (
            block.to_str(compiler), replacement
        )
    )
    return resultlib.commands([cmd])


##### Entity related #####

@_register("damage")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("amount", axe.RangedLiteralInt(0, None))
@axe.arg("cause", axe.Nullable(axe.LiteralString()), default=None)
@axe.arg("damager", axe.Nullable(axe.Typed(EntityDataType)), default=None)
def damage(compiler, target: "MCSelector", amount: int,
           cause: Optional[str], damager: Optional["_EntityBase"]):
    if damager is not None:
        if cause is None:
            raise axe.ArgumentError(
                "cause", localize("modules.world.damage.damagerpresent")
            )
        suffix = " %s entity %s" % (cause, damager)
    elif cause is not None:
        suffix = " " + cause
    else:
        suffix = ""
    cmd = "damage %s %d%s" % (target.to_str(), amount, suffix)
    return resultlib.commands([cmd])


@_register("effect_give")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("effect", axe.LiteralString())
@axe.arg("duration", axe.RangedLiteralInt(0, None))
@axe.arg("amplifier", axe.RangedLiteralInt(0, 255), default=0)
@axe.arg("particle", axe.LiteralBool(), default=True)
def effect_give(compiler, target: "MCSelector", effect: str,
                duration: int, amplifier: int, particle: bool):
    cmd = "effect %s %s %d %d %s" % (
        target.to_str(), effect, duration, amplifier, _fmt_bool(not particle)
    )
    return resultlib.commands([cmd])


@_register("effect_clear")
@axe.chop
@axe.arg("target", axe.Selector())
def effect_clear(compiler, target: "MCSelector"):
    return resultlib.commands(["effect %s clear" % target.to_str()])


@_register("enchant")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("enchantment", axe.LiteralString())
@axe.arg("level", axe.RangedLiteralInt(1, None), default=1)
def enchant(compiler, target: "MCSelector", enchantment: str, level: int):
    cmd = "enchant %s %s %d" % (target.to_str(), enchantment, level)
    return resultlib.commands([cmd])


@_register("event_entity")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("event", axe.LiteralString())
def event_entity(compiler, target: "MCSelector", event: str):
    cmd = "event entity %s %s" % (target.to_str(), event)
    return resultlib.commands([cmd])


@_register("kill")
@axe.chop
@axe.arg("target", axe.Selector())
def kill(compiler, target: "MCSelector"):
    cmd = "kill %s" % target.to_str()
    return resultlib.commands([cmd])


@_register("msg_me")
@axe.chop
@axe.arg("sender", EntityDataType)
@axe.arg("message", axe.LiteralString())
def msg_me(compiler, sender: "_EntityBase", message: str):
    cmd = cmds.Execute(
        [cmds.ExecuteEnv("as", sender.to_str())],
        runs="me %s" % message
    )
    return resultlib.commands([cmd])


@_register("replaceitem_block")
@axe.chop
@axe.arg("pos", PosDataType)
@axe.arg("slot", axe.LiteralInt())
@axe.arg("item", ArgItem())
@axe.arg("amount", axe.RangedLiteralInt(1, None), default=1)
@axe.arg("keep_old", axe.LiteralBool(), default=False)
def replaceitem_block(compiler, pos: Position, slot: int, item: Item,
                      amount: int, keep_old: bool):
    cmd = cmds.Execute(
        pos.context,
        "replaceitem block ~ ~ ~ slot.container %d %s %s" % (
            slot, "keep" if keep_old else "destroy",
            item.to_str("{id} %s {data}{components}" % amount)
        )
    )
    return resultlib.commands([cmd])


@_register("replaceitem_entity")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("location", axe.LiteralString())
@axe.arg("slot", axe.LiteralInt())
@axe.arg("item", ArgItem())
@axe.arg("amount", axe.RangedLiteralInt(1, None), default=1)
@axe.arg("keep_old", axe.LiteralBool(), default=False)
def replaceitem_entity(compiler, target: "MCSelector", location: str,
                       slot: int, item: Item, amount: int, keep_old: bool):
    cmd = "replaceitem entity %s %s %d %s %s" % (
        target.to_str(), location, slot, "keep" if keep_old else "destroy",
        item.to_str("{id} %s {data}{components}" % amount)
    )
    return resultlib.commands([cmd])


@_register("ride_start_tp_ride")
@axe.chop
@axe.arg("rider", EntityDataType)
@axe.arg("ride", EntityDataType)
def ride_start_tp_ride(compiler, rider: "_EntityBase", ride: "_EntityBase"):
    cmd = "ride %s start_riding %s teleport_ride" % (rider, ride)
    return resultlib.commands([cmd])


@_register("ride_start_tp_rider")
@axe.chop
@axe.arg("rider", axe.Selector())
@axe.arg("ride", EntityDataType)
@axe.arg("fill", axe.LiteralStringEnum("if_group_fits", "until_full"),
         default="until_full")
def ride_start_tp_rider(compiler, rider: "MCSelector",
                        ride: "_EntityBase", fill: str):
    cmd = "ride %s start_riding %s teleport_rider %s" % (
        rider.to_str(), ride, fill
    )
    return resultlib.commands([cmd])


@_register("ride_stop")
@axe.chop
@axe.arg("rider", axe.Selector())
def ride_stop(compiler, rider: "MCSelector"):
    return resultlib.commands(["ride %s stop_riding" % rider.to_str()])


@_register("ride_evict_riders")
@axe.chop
@axe.arg("ride", axe.Selector())
def ride_evict_riders(compiler, ride: "MCSelector"):
    return resultlib.commands(["ride %s evict_riders" % ride.to_str()])


@_register("summon_rider")
@axe.chop
@axe.arg("ride", axe.Selector())
@axe.arg("type", axe.LiteralString(), rename="type_")
@axe.arg("event", axe.Nullable(axe.LiteralString()), default=None)
@axe.arg("name", axe.Nullable(axe.LiteralString()), default=None)
def summon_rider(compiler, ride: "MCSelector", type_: str,
                 event: Optional[str], name: Optional[str]):
    if name is None:
        suffix = ""
    else:
        suffix = " %s" % cmds.mc_str(name)
    cmd = "ride %s summon_rider %s %s%s" % (
        ride.to_str(), type_, "*" if event is None else event, suffix
    )
    return resultlib.commands([cmd])


@_register("summon_ride")
@axe.chop
@axe.arg("rider", axe.Selector())
@axe.arg("type", axe.LiteralString(), rename="type_")
@axe.arg("event", axe.Nullable(axe.LiteralString()), default=None)
@axe.arg("name", axe.Nullable(axe.LiteralString()), default=None)
@axe.arg("mode", axe.LiteralStringEnum(
    "skip_riders", "no_ride_change", "reassign_rides"
), default="reassign_rides")
def summon_ride(compiler, rider: "MCSelector", type_: str,
                event: Optional[str], name: Optional[str], mode: str):
    if name is None:
        suffix = ""
    else:
        suffix = " %s" % cmds.mc_str(name)
    cmd = "ride %s summon_ride %s %s %s %s" % (
        rider.to_str(), type_, mode, "*" if event is None else event, suffix
    )
    return resultlib.commands([cmd])


@_register("msg_say")
@axe.chop
@axe.arg("sender", EntityDataType)
@axe.arg("message", axe.LiteralString())
def msg_say(compiler, sender: "_EntityBase", message: str):
    cmd = cmds.Execute(
        [cmds.ExecuteEnv("as", sender.to_str())],
        "say %s" % message
    )
    return resultlib.commands([cmd])


@_register("spread")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("center", PosDataType)
@axe.arg("range", axe.LiteralFloat(), rename="range_")
@axe.arg("interval", axe.LiteralFloat(), default=0.0)
def spread(compiler, target: "MCSelector", center: Position,
           range_: float, interval: float):
    if range_ < 1.0:
        raise axe.ArgumentError(
            "range", localize("modules.world.spread.biggerthan1")
        )
    if interval < 0.0:
        raise axe.ArgumentError(
            "interval", localize("modules.world.spread.nonnegative")
        )
    if interval + 1 > range_:
        raise axe.ArgumentError(
            "interval", localize("modules.world.spread.intervaltoobig")
        )
    cmd = cmds.Execute(
        center.context, "spreadplayers ~ ~ %s %s %s" % (
            interval, range_, target.to_str()
        )
    )
    return resultlib.commands([cmd])


@_register("summon")
@axe.chop
@axe.arg("type", axe.LiteralString(), rename="type_")
@axe.arg("pos", PosDataType)
@axe.arg("event", axe.Nullable(axe.LiteralString()), default=None)
@axe.arg("name", axe.Nullable(axe.LiteralString()), default=None)
@axe.arg("rot", RotDataType, default=None)
def summon(compiler: "Compiler", type_: str, pos: Position,
           rot: Optional[Rotation], event: Optional[str], name: Optional[str]):
    if event is None:
        event = "*"
    if name is None:
        suffix = ""
    else:
        suffix = " %s" % cmds.mc_str(name)
    if compiler.cfg.mc_version >= (1, 19, 70):
        if rot is None:
            ctx = pos.context
            rot_s = "0 0"
        else:
            ctx = pos.context + rot.context
            rot_s = "~ ~"
        cmd = cmds.Execute(
            ctx,
            runs="summon %s ~ ~ ~ %s %s%s" % (type_, rot_s, event, suffix)
        )
    else:
        if rot is not None:
            raise axe.ArgumentError(
                "rot", localize("modules.world.summon.versiontoolow")
            )
        cmd = cmds.Execute(
            pos.context, runs="summon %s ~ ~ ~ %s%s" % (type_, event, suffix)
        )
    return resultlib.commands([cmd])


@_register("tag_add")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("tag", axe.LiteralString())
def tag_add(compiler, target: "MCSelector", tag: str):
    cmd = "tag %s add %s" % (target.to_str(), cmds.mc_str(tag))
    return resultlib.commands([cmd])


@_register("tag_remove")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("tag", axe.LiteralString())
def tag_add(compiler, target: "MCSelector", tag: str):
    cmd = "tag %s remove %s" % (target.to_str(), cmds.mc_str(tag))
    return resultlib.commands([cmd])


@_register("msg_tell")
@axe.chop
@axe.arg("sender", EntityDataType)
@axe.arg("receiver", axe.Selector())
@axe.arg("message", axe.LiteralString())
def msg_tell(compiler, sender: "_EntityBase", receiver: "MCSelector",
             message: str):
    cmd = cmds.Execute(
        [cmds.ExecuteEnv("as", sender.to_str())],
        "tell %s %s" % (receiver.to_str(), message)
    )
    return resultlib.commands([cmd])


@_register("tp")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("dest", PosDataType)
@axe.arg("check_for_blocks", axe.LiteralBool(), default=False)
def tp(compiler, target: "MCSelector", dest: Position, check_for_blocks: bool):
    cmd = cmds.Execute(
        dest.context,
        "tp %s ~ ~ ~ %s" % (
            target.to_str(), _fmt_bool(check_for_blocks)
        )
    )
    return resultlib.commands([cmd])


@_register("rotate")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("rot", RotDataType)
def rotate(compiler, target: "MCSelector", rot: Rotation):
    cmd = cmds.Execute(
        [
            cmds.ExecuteEnv("as", target.to_str()),
            cmds.ExecuteEnv("at", "@s"),
            *rot.context
        ],
        "tp @s ~ ~ ~ ~ ~"
    )
    return resultlib.commands([cmd])


@_register("move")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("x", axe.LiteralFloat(), default=0.0)
@axe.arg("y", axe.LiteralFloat(), default=0.0)
@axe.arg("z", axe.LiteralFloat(), default=0.0)
@axe.arg("check_for_blocks", axe.LiteralBool(), default=False)
def move(compiler, target: "MCSelector", x: float, y: float, z: float,
         check_for_blocks: bool):
    cmd = cmds.Execute(
        [cmds.ExecuteEnv("as", target.to_str()),
         cmds.ExecuteEnv("at", "@s")],
        "tp @s ~%.3f ~%.3f ~%.3f %s" % (
            x, y, z, _fmt_bool(check_for_blocks)
        )
    )
    return resultlib.commands([cmd])


@_register("move_local")
@axe.chop
@axe.arg("target", axe.Selector())
@axe.arg("left", axe.LiteralFloat(), default=0.0)
@axe.arg("up", axe.LiteralFloat(), default=0.0)
@axe.arg("front", axe.LiteralFloat(), default=0.0)
@axe.arg("check_for_blocks", axe.LiteralBool(), default=False)
def move_local(compiler, target: "MCSelector", left: float, up: float,
               front: float, check_for_blocks: bool):
    cmd = cmds.Execute(
        [cmds.ExecuteEnv("as", target.to_str()),
         cmds.ExecuteEnv("at", "@s")],
        "tp @s ^%.3f ^%.3f ^%.3f %s" % (
            left, up, front, _fmt_bool(check_for_blocks)
        )
    )
    return resultlib.commands([cmd])


##### Player Only #####

@_register("ability")
@edu_only
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("ability", axe.LiteralString())
@axe.arg("value", axe.LiteralBool())
def ability(compiler, player: "MCSelector", ability: str, value: bool):
    cmd = "ability %s %s %s" % (
        player.to_str(), ability, _fmt_bool(value)
    )
    return resultlib.commands([cmd])


@_register("clear_inventory")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
def clear_inventory(compiler, player: "MCSelector"):
    return resultlib.commands(["clear %s" % player.to_str()])


@_register("clear")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("item_id", axe.LiteralString())
@axe.arg("item_data", axe.RangedLiteralInt(-1, None), default=-1)
@axe.arg("max_count", axe.RangedLiteralInt(-1, None), default=-1)
def clear(compiler, player: "MCSelector", item_id: str, item_data: int,
          max_count: int):
    cmd = "clear %s %s %d %d" % (
        player.to_str(), item_id, item_data, max_count
    )
    return resultlib.commands([cmd])


@_register("spawnpoint_clear")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
def spawnpoint_clear(compiler, player: "MCSelector"):
    cmd = "clearspawnpoint %s" % player.to_str()
    return resultlib.commands([cmd])


@_register("gamemode")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("gamemode", axe.LiteralStringEnum(
    "survival", "creative", "adventure", "spectator", "default"
))
def gamemode(compiler, player: "MCSelector", gamemode: str):
    cmd = "gamemode %s %s" % (gamemode, player.to_str())
    return resultlib.commands([cmd])


@_register("give")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("item", ArgItem())
@axe.arg("amount", axe.RangedLiteralInt(1, 32767), default=1)
def give(compiler, player: "MCSelector", item: Item, amount: int):
    cmd = "give %s %s" % (
        player.to_str(),
        item.to_str("{id} %s {data}{components}" % amount)
    )
    return resultlib.commands([cmd])


@_register("kick")
@axe.chop
@axe.arg("player_name", axe.LiteralString())
@axe.arg("reason", axe.Nullable(axe.LiteralString()), default=None)
def kick(compiler, player_name: str, reason: Optional[str]):
    reason = "" if reason is None else " " + reason
    cmd = "kick %s%s" % (cmds.mc_str(player_name), reason)
    return resultlib.commands([cmd])


@_register("recipe")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("recipe", axe.LiteralString())
@axe.arg("unlock", axe.LiteralBool())
def recipe(compiler, player: "MCSelector", recipe: str, unlock: bool):
    if recipe != "*":
        recipe = cmds.mc_str(recipe)
    cmd = "recipe %s %s %s" % (
        "give" if unlock else "take",
        player.to_str(), recipe
    )
    return resultlib.commands([cmd])


@_register("spawnpoint_set")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("pos", PosDataType)
def spawnpoint_set(compiler, player: "MCSelector", pos: Position):
    cmd = cmds.Execute(
        pos.context,
        "spawnpoint %s ~ ~ ~" % player.to_str()
    )
    return resultlib.commands([cmd])


@_register("xp_add_levels")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("amount", axe.LiteralInt())
def xp_add_levels(compiler, player: "MCSelector", amount: int):
    cmd = "xp %dL %s" % (amount, player.to_str())
    return resultlib.commands([cmd])


@_register("xp_add_points")
@axe.chop
@axe.arg("player", axe.PlayerSelector())
@axe.arg("amount", axe.RangedLiteralInt(0, None))
def xp_add_points(compiler, player: "MCSelector", amount: int):
    cmd = "xp %d %s" % (amount, player.to_str())
    return resultlib.commands([cmd])


##### Client Side #####
...

##### Global #####
...

##### Misc. #####
...


##### Judgement #####

@_register("is_block")
@axe.chop
@axe.arg("pos", PosDataType)
@axe.arg("block", ArgBlock())
def is_block(compiler, pos: Position, block: Block):
    subcmds = [
        *pos.context,
        cmds.ExecuteCond("block", "~ ~ ~ %s" % block.to_str(compiler))
    ]
    return WildBool(subcmds, [])


@_register("is_same_area")
@axe.chop
@axe.arg("pos", PosDataType)
@axe.arg("offset", PosOffsetDataType)
@axe.arg("other", PosOffsetDataType)
@axe.arg("ignore_air", axe.LiteralBool(), default=False)
def is_same_area(compiler, pos: Position, offset: PosOffset,
                 other: PosOffset, ignore_air: bool):
    subcmds = [
        *pos.context,
        cmds.ExecuteCond("blocks", "~ ~ ~ %s %s %s" % (
            offset, other, "masked" if ignore_air else "all"
        ))
    ]
    return WildBool(subcmds, [])


@_register("is_entity")
@axe.chop
@axe.arg("ent", EntityDataType)
@axe.arg("entity_filter", EFilterDataType)
def is_entity(compiler: "Compiler", ent: "_EntityBase", entity_filter: EntityFilter):
    """
    Select entities that match the entity_filter and return whether given
    entity is in those entities.
    """
    tmp = compiler.allocate_entity_tag()
    selector = ent.get_selector()
    selector.tag(tmp)
    commands = entity_filter.dump("tag {selected} add %s" % tmp)
    subcommands = [cmds.ExecuteCond("entity", selector.to_str())]
    return (WildBool(subcommands, commands),
            ["tag @e[tag={0}] remove {0}".format(tmp)])


def acacia_build(compiler: "Compiler"):
    attrs = {}
    for key, value in _methods.items():
        attrs[key] = BinaryFunction(value)
    attrs["Block"] = BlockType()
    attrs["Item"] = ItemType()
    return attrs
