import math
from typing import Any, Callable, List, Optional, TYPE_CHECKING, Tuple, Union, cast

from cache import volatile_cache
from constants import *
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

_MAX_BUILDERS = 4
_MAX_REPAIR_WORKFORCE = 10


def _find_new_source(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    has_work = not not creep.creep.hasActiveBodyparts(WORK)
    any_miners = not not creep.home.role_count(role_miner)
    highest_priority = -Infinity
    best_source = None
    for source in creep.home.sources:
        if not has_work and not _.some(creep.home.find_in_range(FIND_MY_CREEPS, 1, source.pos),
                                       lambda c: c.memory.role == role_miner):
            continue
        distance = movement.chebyshev_distance_room_pos(source.pos, creep.pos)
        current_work_force = targets.workforce_of(target_source, source.id)
        if any_miners:
            energy = _.sum(creep.home.find_in_range(FIND_DROPPED_RESOURCES, 1, source.pos), 'amount')
            priority = energy - current_work_force * 100 - distance * 2
        else:
            oss = creep.home.get_open_source_spaces_around(source)
            priority = oss * 10 - 100 * current_work_force / oss - distance
        if source.energy <= 0:
            priority -= 200
        if not priority:
            print("[targets] Strange priority result for source {}: {}".format(source, priority))
        if priority > highest_priority:
            best_source = source.id
            highest_priority = priority

    return best_source


def _find_new_spawn_fill_site(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    closest_distance = Infinity
    best_id = None
    stealing_from = None
    structures = cast(List[Union[StructureExtension, StructureSpawn]],
                      _.filter(creep.home.find(FIND_MY_STRUCTURES),
                               lambda s: ((s.structureType == STRUCTURE_EXTENSION
                                           or s.structureType == STRUCTURE_SPAWN)
                                          and s.energy < s.energyCapacity)))
    if len(structures):
        for structure in structures:
            structure_id = structure.id
            if volatile_cache.mem("extensions_filled").has(structure_id):
                continue
            current_carry = targets.workforce_of(target_spawn_deposit, structure_id)
            distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
            if distance < closest_distance:
                max_to_deposit = structure.energyCapacity / 50.0
                if not current_carry or current_carry < max_to_deposit:
                    closest_distance = distance
                    best_id = structure_id
                    stealing_from = None
                else:
                    targeting = targets.reverse_targets[target_spawn_deposit][structure_id]
                    if len(targeting):
                        for name in targeting:
                            if not Game.creeps[name] or movement.distance_squared_room_pos(
                                    Game.creeps[name].pos, structure.pos) > distance * 2.25:
                                # If we're at least 1.5x closer than them, let's steal their place.
                                # Note that 1.5^2 is 2.25, which is what we should be using since we're comparing
                                # squared distances. d1 > d2 * 1.5 is equivalent to d1^2 > d2^2 * 1.5^2 which is
                                # equivalent to d1^2 > d2^2 * 2.25
                                closest_distance = distance
                                best_id = structure_id
                                stealing_from = name
                                break
                    else:
                        closest_distance = distance
                        best_id = structure_id
                        stealing_from = None
        if stealing_from is not None:
            targets.unregister_name(stealing_from, target_spawn_deposit)
    elif creep.home.full_storage_use:
        flag_list = flags.find_flags(creep.home, SPAWN_FILL_WAIT)
        if len(flag_list):
            best_id = _(flag_list).map(lambda f: "flag-{}".format(f.name)) \
                .min(lambda fid: targets.reverse_targets[target_spawn_deposit][fid] or 0)
            if best_id is Infinity:
                best_id = None
    return best_id


def _find_new_construction_site(targets, creep, walls_only=False):
    # type: (TargetMind, RoleBase, Optional[bool]) -> Optional[str]
    smallest_work_force = Infinity
    best_id = None
    if walls_only:
        sites = creep.home.building.get_high_value_construction_targets()
    else:
        sites = creep.home.building.get_construction_targets()
    for site_id in sites:
        if site_id.startswith("flag-"):
            max_work = _MAX_BUILDERS
        else:
            site = cast(ConstructionSite, Game.getObjectById(site_id))
            if not site:
                continue
            max_work = min(_MAX_BUILDERS, math.ceil((site.progressTotal - site.progress) / 50))
        current_work = targets.workforce_of(target_construction, site_id)

        if not current_work or current_work < max_work:
            best_id = site_id
            break
        elif current_work < smallest_work_force:
            best_id = site_id
            smallest_work_force = current_work
    if not best_id and len(sites):
        creep.home.building.refresh_building_targets(True)
        # TODO: Infinite loop warning!!!
        return _find_new_construction_site(targets, creep, walls_only)
    return best_id


def _find_new_repair_site(targets, creep, max_hits, max_work=_MAX_REPAIR_WORKFORCE):
    # type: (TargetMind, RoleBase, int, int) -> Optional[str]
    repair_targets = creep.home.building.get_repair_targets()
    if not len(repair_targets):
        return None
    # closest_distance = Infinity
    # smallest_num_builders = Infinity
    # best_id = None
    if len(repair_targets) <= 1 and not len(creep.home.building.get_construction_targets()):
        max_work = Infinity
    best_id = None
    second_best_id = None
    for struct_id in repair_targets:
        structure = cast(Structure, Game.getObjectById(struct_id))
        if not structure:
            continue
        # TODO: merge this logic with ConstructionMind _efficiently!_
        this_hits_max = min(structure.hitsMax, max_hits)
        if structure and structure.hits < this_hits_max * 0.9:
            distance = movement.chebyshev_distance_room_pos(structure.pos, creep.pos)
            ticks_to_repair = (structure.hitsMax - structure.hits) \
                              / (creep.creep.getActiveBodyparts(WORK) * REPAIR_POWER)
            if ticks_to_repair < 10 and distance < 3:
                return structure.id
            elif distance + ticks_to_repair < 15:
                best_id = structure.id
            if second_best_id:
                continue
            if max_work is Infinity:
                current_max = Infinity
            else:
                current_max = min(max_work, math.ceil((this_hits_max - structure.hits) / 50))
            current_workforce = targets.workforce_of(target_repair, struct_id)
            if not current_workforce or current_workforce < current_max:
                #     or current_workforce < smallest_num_builders + 1:
                # Already priority sorted
                second_best_id = structure.id
                # distance = movement.distance_squared_room_pos(structure.pos, creep.creep.pos)
                # if distance < closest_distance:
                #     smallest_num_builders = current_workforce
                #     closest_distance = distance
                #     best_id = struct_id
    if best_id:
        return best_id
    else:
        return second_best_id


def _find_new_big_repair_site(targets, creep, max_hits):
    # type: (TargetMind, RoleBase, int) -> Optional[str]
    # print("[targets][{}] Finding new big repair site in room {} with max_hits {} "
    #       .format(creep.name, creep.home.name, max_hits))
    best_id = None
    smallest_num = Infinity
    smallest_hits = Infinity
    for struct_id in creep.home.building.get_big_repair_targets():
        struct = cast(Structure, Game.getObjectById(struct_id))
        if struct and struct.hits < struct.hitsMax and struct.hits < max_hits:
            struct_num = targets.workforce_of(target_big_repair, struct_id)
            if struct_num < smallest_num or (struct_num == smallest_num and struct.hits < smallest_hits):
                smallest_num = struct_num
                smallest_hits = struct.hits
                best_id = struct_id
    return best_id


def _find_new_big_big_repair_site(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    # print("[targets][{}] Finding new big repair site in room {} with max_hits {} "
    #       .format(creep.name, creep.home.name, max_hits))
    best_id = None
    smallest_num = Infinity
    smallest_hits = Infinity
    for struct_id in creep.home.building.get_big_repair_targets():
        struct = cast(Structure, Game.getObjectById(struct_id))
        if struct and struct.hits < struct.hitsMax \
                and (struct.structureType == STRUCTURE_WALL or struct.structureType == STRUCTURE_RAMPART):
            struct_num = targets.workforce_of(target_big_big_repair, struct_id)
            if struct_num < smallest_num or (struct_num == smallest_num and struct.hits < smallest_hits):
                smallest_num = struct_num
                smallest_hits = struct.hits
                best_id = struct_id
    return best_id


def _find_new_destruction_site(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    construct_count = {}
    for struct_id in creep.home.building.get_destruction_targets():
        struct = cast(Structure, Game.getObjectById(struct_id))
        if struct:
            current_num = targets.targets[target_destruction_site][struct_id]
            if not current_num or current_num < _MAX_BUILDERS:
                # List is already in priority.
                if struct.structureType not in construct_count:
                    construct_count[struct.structureType] = _.sum(creep.home.find(FIND_MY_CONSTRUCTION_SITES),
                                                                  lambda s: s.structureType == struct.structureType)
                if construct_count[struct.structureType] < 2:
                    return struct_id


def _find_new_tower(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    most_lacking = 0
    best_id = None
    for tower in creep.room.defense.towers():
        if tower.energy >= tower.energyCapacity * 0.9:
            continue
        # 50 per carry part, but we don't know if it's full. this is a safe compromise
        carry_targeting = targets.workforce_of(target_tower_fill, tower.id) * 25
        tower_lacking = tower.energyCapacity - tower.energy - carry_targeting
        if tower_lacking > most_lacking:
            most_lacking = tower_lacking
            best_id = tower.id

    return best_id


def _find_new_energy_miner_mine(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    best_id = None
    closest_flag = Infinity
    for flag in creep.home.mining.available_mines:
        flag_id = "flag-{}".format(flag.name)
        miners = targets.targets[target_energy_miner_mine][flag_id]
        if not miners or miners < 1:
            distance = movement.distance_squared_room_pos(flag.pos, creep.creep.pos)
            if distance < closest_flag:
                closest_flag = distance
                best_id = flag_id

    return best_id


def _find_new_energy_hauler_mine(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    best_id = None
    # don't go to any rooms with 100% haulers in use.
    smallest_percentage = 1
    for flag in creep.home.mining.active_mines:
        flag_id = "flag-{}".format(flag.name)
        if not creep.home.mining.haulers_can_target_mine(flag):
            continue
        hauler_mass = targets.workforce_of(target_energy_hauler_mine, flag_id)
        hauler_percentage = float(hauler_mass) / creep.home.mining.calculate_current_target_mass_for_mine(flag)
        too_long = creep.creep.ticksToLive < 2.2 * creep.home.mining.distance_to_mine(flag)
        if too_long:
            if hauler_percentage < 0.5:
                hauler_percentage *= 2
            else:
                hauler_percentage = 0.99
        if not hauler_mass or hauler_percentage < smallest_percentage:
            smallest_percentage = hauler_percentage
            best_id = flag_id

    return best_id


def _find_closest_deposit_site(targets, creep, pos):
    # type: (TargetMind, RoleBase, Optional[RoomPosition]) -> Optional[str]
    if not pos:
        pos = creep.pos
    if creep.home.full_storage_use:
        best = creep.home.room.storage
        # Still usually prefer storage over any links, unless a lot longer distance (>13 more away)
        best_priority = movement.chebyshev_distance_room_pos(pos, best.pos) - 13
        if creep.home.links.enabled:
            for struct in creep.home.links.links:
                current_targets = targets.targets[target_closest_energy_site][struct.id]
                priority = movement.chebyshev_distance_room_pos(pos, struct.pos)
                if priority < best_priority and (not current_targets or current_targets < 2):
                    best = struct
                    best_priority = priority
        return best.id
    else:
        return None


def _find_top_priority_reservable_room(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    closest_flag = None
    closest_distance = Infinity
    for flag in flags.find_flags_global(RESERVE_NOW):
        room_name = flag.pos.roomName
        room = Game.rooms[room_name]
        if not room or (room.controller and not room.controller.my and not room.controller.owner):
            # claimable!
            flag_id = "flag-{}".format(flag.name)
            current_targets = targets.targets[target_reserve_now][flag_id]
            if not current_targets or current_targets < 1:
                distance = movement.distance_squared_room_pos(creep.pos,
                                                              __new__(RoomPosition(25, 25, room_name)))

                if distance < closest_distance:
                    closest_distance = distance
                    closest_flag = flag_id
    return closest_flag


def _find_new_defendable_wall(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    hot_spots, cold_spots = creep.home.defense.get_current_defender_spots()
    nearest = None
    nearest_distance = Infinity
    for location in hot_spots:
        if not targets.targets[target_rampart_defense][location.name]:
            distance = movement.chebyshev_distance_room_pos(location, creep.pos)
            if distance < nearest_distance:
                nearest = location
                nearest_distance = distance
    if nearest is None:
        for location in cold_spots:
            if not targets.targets[target_rampart_defense][location.name]:
                distance = movement.chebyshev_distance_room_pos(location, creep.pos)
                if distance < nearest_distance:
                    nearest = location
                    nearest_distance = distance
        if nearest is None:
            for location in creep.home.defense.get_old_defender_spots():
                if not targets.targets[target_rampart_defense][location.name]:
                    distance = movement.chebyshev_distance_room_pos(location, creep.pos)
                    if distance < nearest_distance:
                        nearest = location
                        nearest_distance = distance
    if nearest:
        return nearest.name
    else:
        return None


def _find_closest_flag(targets, creep, args):
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


def _find_closest_flag2(targets, creep, args):
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


def _find_closest_home_flag(targets, creep, args):
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


def _find_refill_target(targets, creep):
    # type: (TargetMind, RoleBase) -> Optional[str]
    best_priority = Infinity
    best_id = None
    stealing_from = None
    structures = _.filter(creep.home.find(FIND_MY_STRUCTURES),
                          lambda s: (s.structureType == STRUCTURE_EXTENSION or s.structureType == STRUCTURE_SPAWN
                                     or s.structureType == STRUCTURE_CONTAINER
                                     or s.structureType == STRUCTURE_TOWER)
                                    and s.energy < s.energyCapacity)
    creeps = _.filter(creep.home.creeps,
                      lambda c: (c.memory.role == role_upgrader or c.memory.role == role_builder)
                                and c.carry.energy < c.carryCapacity)
    extra = creep.home.get_extra_fill_targets()
    for structure in structures.concat(extra).concat(creeps):
        structure_id = structure.id
        if volatile_cache.mem("extensions_filled").has(structure_id):
            continue
        current_carry = targets.workforce_of(target_spawn_deposit, structure_id) \
                        + targets.workforce_of(target_refill, structure_id)
        empty = ((structure.energyCapacity or structure.carryCapacity or structure.storeCapacity)
                 - ((structure.store and _.sum(structure.store.energy))
                    or (structure.carry and _.sum(structure.carry.energy))
                    or structure.energy or 0))
        empty_percent = empty / (structure.energyCapacity or structure.carryCapacity or structure.storeCapacity) \
                        * 30
        if empty <= 0 or (empty <= 2 and not structure.structureType):
            continue
        distance = movement.chebyshev_distance_room_pos(structure.pos, creep.creep.pos)
        priority = distance - empty_percent
        if structure.memory and not structure.memory.filling:
            priority -= 15
        elif structure.structureType == STRUCTURE_CONTAINER:
            priority -= 40
        elif structure.structureType:
            priority -= 25
        if priority < best_priority:
            max_work_mass = empty / 50
            if not current_carry or current_carry < max_work_mass:
                best_priority = priority
                best_id = structure_id
                stealing_from = None
            else:
                targeting = targets.reverse_targets[target_refill][structure_id]
                if len(targeting):
                    for name in targeting:
                        if not Game.creeps[name] or movement.chebyshev_distance_room_pos(
                                Game.creeps[name].pos, structure.pos) > distance * 1.5:
                            # If we're at least 1.5x closer than them, let's steal their place.
                            best_priority = priority
                            best_id = structure_id
                            stealing_from = name
                            break
    if stealing_from is not None:
        targets.unregister_name(stealing_from, target_refill)

    return best_id


find_functions = {
    target_source: _find_new_source,
    target_construction: _find_new_construction_site,
    target_repair: _find_new_repair_site,
    target_big_repair: _find_new_big_repair_site,
    target_big_big_repair: _find_new_big_big_repair_site,
    target_destruction_site: _find_new_destruction_site,
    target_spawn_deposit: _find_new_spawn_fill_site,
    target_tower_fill: _find_new_tower,
    target_energy_miner_mine: _find_new_energy_miner_mine,
    target_energy_hauler_mine: _find_new_energy_hauler_mine,
    target_reserve_now: _find_top_priority_reservable_room,
    target_closest_energy_site: _find_closest_deposit_site,
    target_single_flag: _find_closest_flag,
    target_single_flag2: _find_closest_flag2,
    target_home_flag: _find_closest_home_flag,
    target_refill: _find_refill_target,
    target_rampart_defense: _find_new_defendable_wall,
}  # type: List[Callable[[TargetMind, RoleBase, Any]]]
