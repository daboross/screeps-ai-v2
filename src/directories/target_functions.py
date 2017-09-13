from typing import Any, Callable, List, Optional, TYPE_CHECKING, Tuple, Union, cast

from constants import *
from creeps.base import find_new_target_energy_site, find_new_target_source
from creeps.behaviors.refill import find_new_target_refill_destination
from creeps.roles.building import find_new_target_big_repair_site, find_new_target_construction_site, \
    find_new_target_destruction_site, find_new_target_extra_big_repair_site, find_new_target_small_repair_site
from creeps.roles.colonizing import find_new_target_reserve_now_room
from creeps.roles.defensive import find_new_target_rampart_defense_spot
from creeps.roles.mining import find_new_energy_hauler_target_mine, find_new_energy_miner_target_mine
from creeps.roles.spawn_fill import find_new_target_extension
from creeps.roles.tower_fill import find_new_target_tower
from jstools.screeps import *
from position_management import flags
from utilities import movement

if TYPE_CHECKING:
    from creeps.base import RoleBase
    from empire.targets import TargetMind

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


def find_new_target_typed_flag(targets, creep, args):
    # type: (TargetMind, RoleBase, Union[Tuple[int, Union[RoomPosition, RoomObject, None]], None, int]) -> Optional[str]
    pos = creep.pos
    if _.isNumber(args):
        flag_type = cast(int, args)
    elif args != undefined:
        flag_type, center_pos = cast(Tuple[int, Union[RoomPosition, RoomObject, None]], args)
        pos = cast(RoomObject, center_pos).pos or cast(RoomPosition, center_pos)
    else:
        raise ValueError("_find_closest_flag called for creep {} without second parameter!".format(creep))
    closest_flag = None
    closest_distance = Infinity
    for flag in flags.find_flags_global(flag_type):
        flag_id = "flag-{}".format(flag.name)
        current = targets.targets[target_single_flag][flag_id]
        if not current or current < 1:
            distance = movement.distance_squared_room_pos(pos, flag.pos)
            if distance < closest_distance:
                closest_distance = distance
                closest_flag = flag_id
    return closest_flag


def find_new_target_second_typed_flag(targets, creep, args):
    # type: (TargetMind, RoleBase, Union[Tuple[int, Union[RoomPosition, RoomObject, None]], None, int]) -> Optional[str]
    pos = creep.pos
    if _.isNumber(args):
        flag_type = cast(int, args)
    elif args != undefined:
        flag_type, center_pos = cast(Tuple[int, Union[RoomPosition, RoomObject, None]], args)
        pos = cast(RoomObject, center_pos).pos or cast(RoomPosition, center_pos)
    else:
        raise ValueError("_find_closest_flag2 called for creep {} without second parameter!".format(creep))
    closest_flag = None
    closest_distance = Infinity
    for flag in flags.find_flags_global(flag_type):
        flag_id = "flag-{}".format(flag.name)
        current = targets.targets[target_single_flag2][flag_id]
        if not current or current < 1:
            distance = movement.distance_squared_room_pos(pos, flag.pos)
            if distance < closest_distance:
                closest_distance = distance
                closest_flag = flag_id
    return closest_flag


def find_new_target_owned_typed_flag(targets, creep, args):
    # type: (TargetMind, RoleBase, Union[Tuple[int, Union[RoomPosition, RoomObject, None]], None, int]) -> Optional[str]
    pos = creep.pos
    if _.isNumber(args):
        flag_type = cast(int, args)
    elif args != undefined:
        flag_type, center_pos = cast(Tuple[int, Union[RoomPosition, RoomObject, None]], args)
        pos = cast(RoomObject, center_pos).pos or cast(RoomPosition, center_pos)
    else:
        raise ValueError("_find_closest_home_flag called for creep {} without second parameter!".format(creep))
    closest_flag = None
    closest_distance = Infinity
    for flag in flags.find_flags(creep.home, flag_type):
        flag_id = "flag-{}".format(flag.name)
        current = targets.targets[target_home_flag][flag_id]
        if not current or current < 1:
            distance = movement.distance_squared_room_pos(pos, flag.pos)
            if distance < closest_distance:
                closest_distance = distance
                closest_flag = flag_id
    return closest_flag


find_functions = cast(List[Callable[[TargetMind, RoleBase, Optional[Any]], None]], {
    target_source: find_new_target_source,
    target_construction: find_new_target_construction_site,
    target_repair: find_new_target_small_repair_site,
    target_big_repair: find_new_target_big_repair_site,
    target_big_big_repair: find_new_target_extra_big_repair_site,
    target_destruction_site: find_new_target_destruction_site,
    target_spawn_deposit: find_new_target_extension,
    target_tower_fill: find_new_target_tower,
    target_energy_miner_mine: find_new_energy_miner_target_mine,
    target_energy_hauler_mine: find_new_energy_hauler_target_mine,
    target_reserve_now: find_new_target_reserve_now_room,
    target_closest_energy_site: find_new_target_energy_site,
    target_single_flag: find_new_target_typed_flag,
    target_single_flag2: find_new_target_second_typed_flag,
    target_home_flag: find_new_target_owned_typed_flag,
    target_refill: find_new_target_refill_destination,
    target_rampart_defense: find_new_target_rampart_defense_spot,
})
