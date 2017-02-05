import math

import random

from cache import context, volatile_cache
from constants import DEPOT, max_repath_mine_roads_every, max_repave_mine_roads_every, min_repath_mine_roads_every, \
    min_repave_mine_roads_every, rmem_key_building_priority_spawn, rmem_key_building_priority_walls
from creep_management import mining_paths
from empire import honey
from jstools.js_set_map import new_map, new_set
from jstools.screeps import *
from position_management import flags
from utilities import movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

_cache_key_placed_roads_for_mine = 'prfm'
_cache_key_found_roads_for_mine = 'frfm'
_build_roads_constant_missing_rooms = 'mr'
_build_roads_constant_not_enough_sites = 'ns'

building_priorities = {
    STRUCTURE_EXTENSION: 0,
    STRUCTURE_SPAWN: 1,
    STRUCTURE_LINK: 1,
    STRUCTURE_TOWER: 2,
    STRUCTURE_STORAGE: 3,
    # STRUCTURE_LINK when bootstrapping: 4
    # STRUCTURE_SPAWN when bootstrapping: 5
    STRUCTURE_WALL: 6,
    STRUCTURE_RAMPART: 6,
    STRUCTURE_TERMINAL: 8,
}
rcl_lt4_priorities = {
    STRUCTURE_SPAWN: 0,
    STRUCTURE_TOWER: 1,
    STRUCTURE_EXTENSION: 2,
    STRUCTURE_ROAD: 3,
    # STRUCTURE_SPAWN when bootstrapping: 5
    STRUCTURE_WALL: 11,
    STRUCTURE_RAMPART: 12,
}
default_priority = 10
max_priority_for_non_wall_sites = 5


def get_priority(room, structure_type):
    """
    :type room: rooms.room_mind.RoomMind
    :type structure_type: str
    """
    if not room.spawn:
        if structure_type == STRUCTURE_SPAWN:
            if room.being_bootstrapped():
                if room.mem[rmem_key_building_priority_spawn]:
                    return -2
                else:
                    return 5
            else:
                return -2
        elif structure_type == STRUCTURE_LINK:
            if room.being_bootstrapped():
                return 4
        elif (structure_type == STRUCTURE_WALL or structure_type == STRUCTURE_EXTENSION) and room.being_bootstrapped():
            if room.mem[rmem_key_building_priority_walls]:
                return -1
            else:
                return -3
    if room.rcl < 4:
        if structure_type in rcl_lt4_priorities:
            return rcl_lt4_priorities[structure_type]
    else:
        if structure_type in building_priorities:
            return building_priorities[structure_type]
    return default_priority


def not_road(id):
    thing = Game.getObjectById(id)
    if thing is not None:
        return thing.structureType != STRUCTURE_ROAD
    else:
        flag = Game.flags[id]
        return flag is not undefined and flags.flag_secondary_to_sub[flag.secondaryColor] != flags.SUB_ROAD


protect_with_ramparts = [
    STRUCTURE_SPAWN,
    STRUCTURE_POWER_SPAWN,
    STRUCTURE_TERMINAL,
    STRUCTURE_STORAGE,
    STRUCTURE_TOWER,
    STRUCTURE_LAB,
]
rampart_priorities = {
    STRUCTURE_STORAGE: 1,
    STRUCTURE_TOWER: 2,
    STRUCTURE_SPAWN: 3,
    STRUCTURE_TERMINAL: 4,
    STRUCTURE_POWER_SPAWN: 5,
    STRUCTURE_LAB: 6,
}


class ConstructionMind:
    """
    :type room: rooms.room_mind.RoomMind
    :type hive: empire.hive.HiveMind
    """

    def __init__(self, room):
        """
        :type room: rooms.room_mind.RoomMind
        :param room:
        """
        self.room = room
        self.hive = room.hive

    def toString(self):
        return "ConstructionMind[room: {}]".format(self.room.name)

    def refresh_building_targets(self, now=False):
        self.refresh_num_builders(now)
        if now:
            self.room.delete_cached_property('building_targets')
            self.room.delete_cached_property('non_wall_construction_targets')
            self.room.delete_cached_property('sieged_walls_unbuilt')
        else:
            self.room.expire_property_next_tick('building_targets')
            self.room.expire_property_next_tick('non_wall_construction_targets')
            self.room.expire_property_next_tick('sieged_walls_unbuilt')

    def refresh_repair_targets(self, now=False):
        self.refresh_num_builders(now)
        if now:
            self.room.delete_cached_property('repair_targets')
            self.room.delete_cached_property('big_repair_targets')
        else:
            self.room.expire_property_next_tick('repair_targets')
            self.room.expire_property_next_tick('big_repair_targets')

    def refresh_destruction_targets(self):
        self.room.delete_cached_property('destruct_targets')

    def _max_hits_at(self, struct, big_repair=False):
        if struct.structureType == STRUCTURE_WALL:
            if big_repair:
                return self.room.max_sane_wall_hits
            else:
                return self.room.min_sane_wall_hits
        elif struct.structureType == STRUCTURE_RAMPART:
            if big_repair:
                return min(self.room.max_sane_wall_hits, struct.hitsMax)
            else:
                return min(self.room.min_sane_wall_hits, struct.hitsMax)
        else:
            return struct.hitsMax

    def _get_is_relatively_decayed_callback(self, big_repair=False):
        def is_relatively_decayed(thing_id):
            thing = Game.getObjectById(thing_id)
            if thing is None:
                return False
            if thing.structureType == STRUCTURE_ROAD:
                return thing.hits < thing.hitsMax * 0.35
            else:
                max_hits = self._max_hits_at(thing, big_repair)
                max_hits = max_hits - min(max_hits * 0.4, 50 * 1000)
                return thing.hits < max_hits

        return is_relatively_decayed

    def _hits_left_to_repair_at(self, thing_id):
        thing = Game.getObjectById(thing_id)
        if thing is None:
            return 0
        if thing.structureType != STRUCTURE_RAMPART and thing.structureType != STRUCTURE_WALL:
            return thing.hitsMax - thing.hits
        return max(0, self.room.max_sane_wall_hits - thing.hits)

    def get_target_num_builders(self):
        num = self.room.get_cached_property("builders_needed")
        if num is not None:
            return num

        sites_and_repair = _.sum(self.get_construction_targets(), not_road) \
                           + _.sum(self.get_repair_targets(),
                                   self._get_is_relatively_decayed_callback(False))
        if sites_and_repair > 0:
            if sites_and_repair < 4:
                num = 1
            elif sites_and_repair < 12:
                num = 2
            else:
                num = 4
        else:
            extra_repair = _.sum(self.get_big_repair_targets(),
                                 self._get_is_relatively_decayed_callback(True))
            if extra_repair > 0:
                num = 1
            else:
                num = 0
        # will be manually refreshed
        self.room.store_cached_property("builders_needed", num, 1000)
        return num

    def get_max_builder_work_parts(self):
        parts = self.room.get_cached_property("max_builder_work_parts")
        if parts is not None:
            return parts

        construction = 0
        for site_id in self.get_construction_targets():
            site = Game.getObjectById(site_id)
            if site and site.progressTotal:
                construction += site.progressTotal - site.progress
        repair = _.sum(self.get_big_repair_targets(), self._hits_left_to_repair_at)
        total_work_ticks_needed = construction / BUILD_POWER + repair / REPAIR_POWER
        # We are assuming here that each creep spends about half it's life moving between storage and the build/repair
        # site.
        total_work_parts_needed = math.ceil(total_work_ticks_needed / (CREEP_LIFE_TIME / 2))

        self.room.store_cached_property("max_builder_work_parts", total_work_parts_needed, 1000)
        return total_work_parts_needed

    def get_max_builder_work_parts_noextra(self):
        parts = self.room.get_cached_property("max_builder_work_parts_noextra")
        if parts is not None:
            return parts

        construction = 0
        for site_id in self.get_construction_targets():
            site = Game.getObjectById(site_id)
            if site and site.progressTotal:
                construction += site.progressTotal - site.progress
        repair = _.sum(self.get_repair_targets(), self._hits_left_to_repair_at)
        total_work_ticks_needed = construction / BUILD_POWER + repair / REPAIR_POWER
        # We are assuming here that each creep spends about half it's life moving between storage and the build/repair
        # site.
        total_work_parts_needed = math.ceil(total_work_ticks_needed / (CREEP_LIFE_TIME / 2))

        self.room.store_cached_property("max_builder_work_parts_noextra", total_work_parts_needed, 1000)
        return total_work_parts_needed

    def get_max_builder_work_parts_urgent(self):
        parts = self.room.get_cached_property("max_builder_work_parts_urgent_only")
        if parts is not None:
            return parts

        construction = 0
        for site_id in self.get_construction_targets():
            site = Game.getObjectById(site_id)
            if not site:
                continue
            if site and (site.structureType == STRUCTURE_WALL or site.structureType == STRUCTURE_RAMPART
                         or site.structureType == STRUCTURE_SPAWN or site.structureType == STRUCTURE_ROAD):
                construction += site.progressTotal - site.progress
        repair = 0
        for struct_id in self.get_repair_targets():
            struct = Game.getObjectById(struct_id)
            if struct and struct.hits:
                if struct.structureType == STRUCTURE_WALL or struct.structureType == STRUCTURE_RAMPART:
                    repair += max(0, self.room.min_sane_wall_hits / 2 - struct.hits)
                else:
                    repair += struct.hitsMax - struct.hits

        total_work_ticks_needed = construction / BUILD_POWER + repair / REPAIR_POWER
        # We are assuming here that each creep spends about half it's life moving between storage and the build/repair
        # site.
        total_work_parts_needed = math.ceil(total_work_ticks_needed / (CREEP_LIFE_TIME / 2))

        self.room.store_cached_property("max_builder_work_parts_urgent_only", total_work_parts_needed, 1000)
        return total_work_parts_needed

    def refresh_num_builders(self, now=False):
        if now:
            self.room.delete_cached_property('builders_needed')
            self.room.delete_cached_property('max_builder_work_parts')
            self.room.delete_cached_property('max_builder_work_parts_noextra')
            self.room.delete_cached_property('max_builder_work_parts_urgent_only')
        else:
            self.room.expire_property_next_tick('builders_needed')
            self.room.expire_property_next_tick('max_builder_work_parts')
            self.room.expire_property_next_tick('max_builder_work_parts_noextra')
            self.room.expire_property_next_tick('max_builder_work_parts_urgent_only')

    def get_high_value_construction_targets(self):
        if self.room.under_siege():
            targets = self.room.get_cached_property("sieged_walls_unbuilt")
            if targets is not None:
                return targets

            targets = _(self.get_construction_targets()) \
                .map(lambda x: Game.getObjectById(x)) \
                .filter(lambda x: x is not None and (x.structureType == STRUCTURE_WALL
                                                     or x.structureType == STRUCTURE_RAMPART)
                                  and not len(x.pos.lookFor(LOOK_STRUCTURES))) \
                .sortBy(lambda x: -1 * max(abs(25 - x.pos.x), abs(25 - x.pos.y))) \
                .pluck('id') \
                .value()
            # Sort by the closest to the edge of the room
            self.room.store_cached_property("seiged_walls_unbuilt", targets, 200)
            return targets
        else:
            targets = self.room.get_cached_property("non_wall_construction_targets")
            if targets is not None:
                return targets

            targets = _(self.get_construction_targets()) \
                .map(lambda x: Game.getObjectById(x)) \
                .filter(lambda x: x is not None
                                  and get_priority(self.room, x.structureType)
                                      <= max_priority_for_non_wall_sites) \
                .pluck('id').value()
            self.room.store_cached_property("non_wall_construction_targets", targets, 200)
            return targets

    def get_construction_targets(self):
        targets = self.room.get_cached_property("building_targets")
        if targets is not None:
            last_rcl = self.room.get_cached_property("bt_last_checked_rcl")
            if last_rcl >= self.room.rcl:
                return targets
        print("[{}] Calculating new construction targets".format(self.room.name))
        self.room.delete_cached_property('non_wall_construction_targets')
        self.room.delete_cached_property('seiged_walls_unbuilt')
        self.refresh_num_builders(True)

        if self.room.spawn:
            spawn_pos = self.room.spawn.pos
        else:
            spawn_flag = flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)
            if len(spawn_flag):
                spawn_pos = spawn_flag[0].pos
            else:
                print("[{}][building] Warning: Finding construction targets for room {},"
                      " which has no spawn planned!".format(self.room.name, self.room.name))
                spawn_pos = movement.center_pos(self.room.name)
        volatile = volatile_cache.volatile()
        total_count = len(Game.constructionSites) + (volatile.get("construction_sites_placed") or 0)
        new_sites = []
        if _.sum(self.room.find(FIND_CONSTRUCTION_SITES), not_road) < 15 \
                and total_count < MAX_CONSTRUCTION_SITES:
            currently_existing = _(self.room.find(FIND_STRUCTURES)) \
                .concat(self.room.find(FIND_MY_CONSTRUCTION_SITES)) \
                .countBy('structureType').value()
            # currently_existing = {}
            # for s in self.room.find(FIND_STRUCTURES):
            #     if s.structureType in currently_existing:
            #         currently_existing[s.structureType] += 1
            #     else:
            #         currently_existing[s.structureType] = 1
            # for s in self.room.find(FIND_CONSTRUCTION_SITES):
            #     if s.structureType in currently_existing:
            #         currently_existing[s.structureType] += 1
            #     else:
            #         currently_existing[s.structureType] = 1

            all_walls = (
                self.room.rcl < 5
                and self.room.being_bootstrapped()
                and self.room.mem[rmem_key_building_priority_walls]
            )
            prio_spawn = (
                self.room.rcl < 5
                and self.room.being_bootstrapped()
                and not not self.room.mem[rmem_key_building_priority_spawn]
            )

            no_walls = not all_walls and (self.room.rcl < 3 or (
                self.room.rcl == 3
                and not _.find(self.room.find(FIND_MY_STRUCTURES), lambda s: s.structureType == STRUCTURE_TOWER)
            ))

            def flag_priority(flag_tuple):
                struct_type = flags.flag_sub_to_structure_type[flag_tuple[1]]
                return (
                    get_priority(self.room, struct_type) * 50
                    + movement.distance_room_pos(spawn_pos, flag_tuple[0].pos)
                )

            for flag, flag_type in _.sortBy(flags.find_by_main_with_sub(self.room, flags.MAIN_BUILD), flag_priority):
                structure_type = flags.flag_sub_to_structure_type[flag_type]
                if not structure_type:
                    print("[{}][building] Warning: structure type corresponding to flag type {} not found!".format(
                        self.room.name, flag_type
                    ))
                    continue
                if structure_type == STRUCTURE_EXTRACTOR and not self.room.look_at(LOOK_MINERALS, flag.pos):
                    structure_type = STRUCTURE_CONTAINER  # hack, since both use the same color.
                if no_walls or all_walls or prio_spawn:
                    selected = False
                    if all_walls and structure_type == STRUCTURE_RAMPART or structure_type == STRUCTURE_WALL:
                        selected = True
                    elif no_walls and not all_walls and not prio_spawn \
                            and structure_type != STRUCTURE_RAMPART and structure_type != STRUCTURE_WALL:
                        selected = True
                    elif prio_spawn and structure_type == STRUCTURE_SPAWN:
                        selected = True
                    if not selected:
                        continue
                if CONTROLLER_STRUCTURES[structure_type][self.room.rcl] \
                        > (currently_existing[structure_type] or 0) and \
                        not flags.look_for(self.room, flag, flags.MAIN_DESTRUCT,
                                           flags.structure_type_to_flag_sub[structure_type]) \
                        and not (_.find(self.room.look_at(LOOK_STRUCTURES, flag.pos), {"structureType": structure_type})
                                 or _.find(self.room.look_at(LOOK_CONSTRUCTION_SITES, flag.pos))):
                    total_count += 1
                    flag.pos.createConstructionSite(structure_type)
                    new_sites.append("flag-{}".format(flag.name))
                    currently_existing[structure_type] = (currently_existing[structure_type] or 0) + 1
                    # Don't go all-out and set construction sites for everything at once! That's a recipe to run into
                    # the 100-site limit!
                    if len(new_sites) >= 4 or total_count >= MAX_CONSTRUCTION_SITES:
                        break

            volatile.set("construction_sites_placed", total_count)

        sites = _(self.room.find(FIND_MY_CONSTRUCTION_SITES)) \
            .sortBy(lambda s: get_priority(self.room, s.structureType) * 50
                              + movement.distance_room_pos(spawn_pos, s.pos)) \
            .pluck('id').value().concat(new_sites)
        # sites = [x.id for x in _.sortBy(self.room.find(FIND_MY_CONSTRUCTION_SITES),
        #                                 lambda s: get_priority(self.room, s.structureType) * 50
        #                                           + movement.distance_room_pos(spawn_pos, s.pos))]

        self.room.store_cached_property("building_targets", sites, 1000)
        self.room.store_cached_property("bt_last_checked_rcl", self.room.rcl, 1000)
        return self.room.get_cached_property("building_targets")

    def get_repair_targets(self):
        structures = self.room.get_cached_property("repair_targets")
        if structures is not None:
            last_rcl = self.room.get_cached_property("rt_last_checked_rcl")
            if last_rcl >= self.room.rcl:
                return structures
            else:
                self.refresh_num_builders(True)

        if self.room.spawn:
            spawn_pos = self.room.spawn.pos
        else:
            spawn_flag = flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)
            if len(spawn_flag):
                spawn_pos = spawn_flag[0].pos
            else:
                print("[{}][building] Warning: Finding repair targets for room {},"
                      " which has no spawn planned!".format(self.room.name, self.room.name))
                spawn_pos = movement.center_pos(self.room.name)

        max_hits = self.room.min_sane_wall_hits
        any_destruct_flags = len(flags.find_by_main_with_sub(self.room, flags.MAIN_DESTRUCT))

        # TODO: spawn one large repairer (separate from builders) which is boosted with LO to build walls!
        # TODO: At some point, I think it might just be more efficient to store a list in
        # memory of (target_id, target_hits, target_priority) and not have to keep looking
        # at everything.
        structures = _(self.room.find(FIND_STRUCTURES)).map(
            lambda s: (
                s, min(s.hitsMax, max_hits)
                if (s.structureType == STRUCTURE_WALL or s.structureType == STRUCTURE_RAMPART)
                else s.hitsMax
            )
        ).filter(
            lambda t: (t[0].my or not t[0].owner) and t[0].hits < t[1] * 0.9
                      and (t[0].structureType != STRUCTURE_ROAD or t[0].hits < t[0].hitsMax * 0.8)
                      and (not any_destruct_flags
                           or not flags.look_for(self.room, t[0].pos, flags.MAIN_DESTRUCT,
                                                 flags.structure_type_to_flag_sub[t[0].structureType]))
        ).sortBy(
            lambda t: get_priority(self.room, t[0].structureType) * 10
                      + (movement.distance_room_pos(spawn_pos, t[0].pos)
                         if t[0].structureType != STRUCTURE_RAMPART and t[0].structureType != STRUCTURE_WALL
                         else -movement.distance_room_pos(spawn_pos, t[0].pos)) / 50 * 10
                      - ((t[1] - t[0].hits) / t[1]) * 100  # more important than the above
        ).map(lambda t: t[0].id).value()

        self.room.store_cached_property("repair_targets", structures, 50)
        self.room.store_cached_property("rt_last_checked_rcl", self.room.rcl, 50)
        return structures

    def get_big_repair_targets(self):
        target_list = self.room.get_cached_property("big_repair_targets")
        if target_list is not None:
            return target_list

        # TODO: spawn one large repairer (separate from builders) which is boosted with LO to build walls!
        max_hits = self.room.max_sane_wall_hits
        any_destruct_flags = len(flags.find_by_main_with_sub(self.room, flags.MAIN_DESTRUCT))
        target_list = (
            _(self.room.find(FIND_STRUCTURES))
                .filter(lambda s: (s.my or not s.owner) and s.hits < s.hitsMax
                                  and s.hits < max_hits
                                  and (s.structureType != STRUCTURE_ROAD or s.hits < s.hitsMax * 0.5)
                                  and (not any_destruct_flags
                                       or not flags.look_for(self.room, s, flags.MAIN_DESTRUCT,
                                                             flags.structure_type_to_flag_sub[
                                                                 s.structureType])))
                .sortBy(lambda s: s.hits)
                .pluck('id').value()
        )

        self.room.store_cached_property("big_repair_targets", target_list, 200)
        return target_list

    def get_destruction_targets(self):
        target_list = self.room.get_cached_property("destruct_targets")
        if target_list is not None:
            return target_list

        target_list = []

        if self.room.spawn:
            spawn_pos = self.room.spawn.pos
        else:
            spawn_flag = flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)
            if len(spawn_flag):
                spawn_pos = spawn_flag[0].pos
            else:
                print("[{}][building] Warning: Finding destruct targets for room {},"
                      " which has no spawn planned!".format(self.room.name, self.room.name))
                spawn_pos = movement.center_pos(self.room.name)

        for flag, secondary in _.sortBy(flags.find_by_main_with_sub(self.room, flags.MAIN_DESTRUCT),
                                        lambda t: -movement.distance_squared_room_pos(t[0].pos, spawn_pos)):
            structure_type = flags.flag_sub_to_structure_type[secondary]
            if structure_type == STRUCTURE_ROAD:
                continue
            structures = _.filter(self.room.look_at(LOOK_STRUCTURES, flag.pos),
                                  lambda s: s.structureType == structure_type)
            if structure_type != STRUCTURE_RAMPART and _.find(self.room.look_at(LOOK_STRUCTURES, flag.pos),
                                                              {"structureType": STRUCTURE_RAMPART}):
                for struct in structures:
                    print("[{}][building] Not dismantling {}, as it is under a rampart.".format(
                        self.room.name, struct))
                continue
            if len(structures) and not flags.look_for(self.room, flag.pos, flags.MAIN_BUILD, secondary):
                for struct in structures:
                    target_list.append(struct.id)
            else:
                flag.remove()

        self.room.store_cached_property("destruct_targets", target_list, 200)
        return target_list

    def build_most_needed_road(self):
        for mine_flag in self.room.mining.active_mines:
            re_checked = self.build_road(mine_flag)
            if re_checked:
                return True
        return False

    def build_road(self, mine_flag):
        current_method_version = 1

        last_built_roads_key = _cache_key_placed_roads_for_mine + mine_flag.name
        cached_version = self.room.get_cached_property(last_built_roads_key)

        deposit_point = self.room.mining.closest_deposit_point_to_mine(mine_flag)

        if not deposit_point:
            return False

        latest_version = str(current_method_version) + "-" + deposit_point.id
        if cached_version == latest_version:
            return False
        elif cached_version is not None and cached_version.startswith(_build_roads_constant_missing_rooms):
            only_search_rooms = cached_version[len(_build_roads_constant_missing_rooms):].split('-')
            for name in only_search_rooms:
                if name in Game.rooms:
                    break
            else:
                return False
        elif cached_version is not None and cached_version.startswith(_build_roads_constant_not_enough_sites):
            needed = int(cached_version[len(_build_roads_constant_not_enough_sites):])
            current = _.size(Game.constructionSites) + (volatile_cache.volatile().get("construction_sites_placed") or 0)
            if min(needed, 25) < MAX_CONSTRUCTION_SITES * 0.8 - current:
                return False
        print("[{}][building] Building roads for {}.".format(self.room.name, mine_flag.name))
        last_found_roads_key = _cache_key_found_roads_for_mine + mine_flag.name
        latest_found_roads = self.room.get_cached_property(last_found_roads_key)
        if latest_found_roads != latest_version:
            self._repath_roads_for(mine_flag, deposit_point)
            self.room.store_cached_property(last_found_roads_key, latest_version,
                                            random.randint(min_repath_mine_roads_every, max_repath_mine_roads_every))

        checked_positions = {}
        missing_rooms = []
        all_modified_rooms = []
        hive = self.hive
        site_count = _.size(Game.constructionSites) + (volatile_cache.volatile().get("construction_sites_placed") or 0)

        need_more_sites = 0

        def check_route(serialized_obj, not_near_start_of, not_near_end_of):
            nonlocal site_count, need_more_sites
            for room_name in Object.keys(serialized_obj):
                if not movement.is_valid_room_name(room_name):  # Special key
                    continue
                if room_name not in Game.rooms:
                    if not missing_rooms.includes(room_name):
                        missing_rooms.push(room_name)
                    continue
                if not all_modified_rooms.includes(room_name):
                    all_modified_rooms.push(room_name)
                if room_name in checked_positions:
                    checked_here = checked_positions[room_name]
                else:
                    checked_here = checked_positions[room_name] = new_set()
                room = hive.get_room(room_name)
                path = Room.deserializePath(serialized_obj[room_name])
                if room_name == not_near_end_of:
                    rest = path.slice(-2)
                    path = path.slice(0, -2)
                if room_name == not_near_start_of:
                    rest = path.slice(0, 2)
                    path = path.slice(2)
                for position in path:
                    xy_key = positions.serialize_pos_xy(position)
                    if checked_here.has(xy_key):
                        continue
                    else:
                        checked_here.add(xy_key)
                    structures = room.look_at(LOOK_STRUCTURES, position.x, position.y)
                    if not _.some(structures, 'structureType', STRUCTURE_ROAD):
                        if site_count >= MAX_CONSTRUCTION_SITES * 0.9:
                            need_more_sites += 1
                        else:
                            room.room.createConstructionSite(position.x, position.y, STRUCTURE_ROAD)
                            site_count += 1

        honey = self.hive.honey
        if deposit_point.pos.isNearTo(mine_flag):
            all_positions = []
        else:
            route_to_mine = honey.get_serialized_path_obj(mine_flag, deposit_point, {
                'paved_for': mine_flag,
                'keep_for': min_repath_mine_roads_every * 2,
            })
            check_route(route_to_mine, (mine_flag.pos or mine_flag).roomName, None)

            all_positions = honey.list_of_room_positions_in_path(mine_flag, deposit_point, {
                'paved_for': mine_flag,
                'keep_for': min_repath_mine_roads_every * 2,
            })

        for spawn in self.room.spawns:
            # TODO: this is used in both this method and the one above, and should be a utility.
            if len(all_positions):
                closest = None
                closest_distance = Infinity
                for index, pos in enumerate(all_positions):
                    # NOTE: 0.7 is used in transport.follow_energy_path and should be changed there if changed here.
                    distance = movement.chebyshev_distance_room_pos(spawn, pos) - index * 0.7
                    if pos.roomName != spawn.pos.roomName or pos.x < 2 or pos.x > 48 or pos.y < 2 or pos.y > 48:
                        distance += 10
                    if distance < closest_distance:
                        closest = pos
                        closest_distance = distance
                if closest.isNearTo(mine_flag) and closest.roomName != (mine_flag.pos or mine_flag).roomName:
                    no_pave_end = closest.roomName
                else:
                    no_pave_end = None
            else:
                closest = mine_flag.pos or mine_flag
                no_pave_end = closest.roomName
            if closest.isNearTo(spawn):
                continue
            route_to_spawn = honey.get_serialized_path_obj(spawn, closest, {
                'paved_for': [mine_flag, spawn],
                'keep_for': min_repath_mine_roads_every * 2,
            })
            check_route(route_to_spawn, None, no_pave_end)

        # Now, clean up sites which we don't need anymore!
        for room_name in all_modified_rooms:
            room = hive.get_room(room_name)
            if room and not room.my:
                all_planned_sites_set = mining_paths.get_set_of_all_serialized_positions_in(room_name)
                for site in room.find(FIND_MY_CONSTRUCTION_SITES):
                    xy = positions.serialize_pos_xy(site)
                    if site.structureType == STRUCTURE_ROAD and not all_planned_sites_set.has(xy):
                        print("[building] Removing {} at {}.".format(site, site.pos))
                        site.remove()

        if need_more_sites > 0:
            self.room.store_cached_property(last_built_roads_key,
                                            _build_roads_constant_not_enough_sites + str(need_more_sites),
                                            min_repath_mine_roads_every)
            print("[{}][building] Stopped: need more sites. ({}/{})".format(self.room.name,
                                                                            MAX_CONSTRUCTION_SITES - site_count,
                                                                            need_more_sites))
        elif len(missing_rooms) > 0:
            self.room.store_cached_property(last_built_roads_key,
                                            _build_roads_constant_missing_rooms + '-'.join(missing_rooms),
                                            min_repath_mine_roads_every)
            print("[{}][building] Stopped: missing rooms. ({})".format(self.room.name, ', '.join(missing_rooms)))
        else:
            self.room.store_cached_property(last_built_roads_key, latest_version,
                                            random.randint(min_repave_mine_roads_every, max_repave_mine_roads_every))
        return True

    def _repath_roads_for(self, mine_flag, deposit_point):
        hive_honey = self.hive.honey

        if deposit_point.pos.isNearTo(mine_flag):
            mine_path = []
            mining_paths.register_new_mining_path(mine_flag, mine_path)
        else:
            # NOTE: HoneyTrails now knows how to register paths with mining_paths, and will do so implicitly
            # when 'paved_for' is passed in.
            mine_path = hive_honey.completely_repath_and_get_raw_path(mine_flag, deposit_point, {
                'paved_for': mine_flag,
                'keep_for': min_repath_mine_roads_every * 2,
            })
            honey.clear_cached_path(deposit_point, mine_flag)

        for spawn in self.room.spawns:
            # TODO: this is used in both this method and the one above, and should be a utility.
            if len(mine_path):
                closest = None
                closest_distance = Infinity
                for index, pos in enumerate(mine_path):
                    # NOTE: 0.7 is used in transport.follow_energy_path and should be changed there if changed here.
                    distance = movement.chebyshev_distance_room_pos(spawn, pos) - index * 0.7
                    if pos.roomName != spawn.pos.roomName or pos.x < 2 or pos.x > 48 or pos.y < 2 or pos.y > 48:
                        distance += 10
                    if distance < closest_distance:
                        closest = pos
                        closest_distance = distance
            else:
                closest = mine_flag.pos or mine_flag
            if closest.isNearTo(spawn):
                mining_paths.register_new_mining_path([mine_flag, spawn], [])
                continue
            # NOTE: HoneyTrails now knows how to register paths with mining_paths, and will do so implicitly
            # when 'paved_for' is passed in.
            hive_honey.completely_repath_and_get_raw_path(spawn, closest, {
                'paved_for': [mine_flag, spawn],
                # NOTE: We really aren't going to be using this path for anything besides paving,
                #  but it should be small.
                'keep_for': min_repath_mine_roads_every * 2,
            })

    def place_home_ramparts(self):
        last_run = self.room.get_cached_property("placed_ramparts")
        if last_run:
            return

        if self.room.rcl < 3 or not len(self.room.defense.towers()):
            self.room.store_cached_property("placed_ramparts", "lower_rcl", 20)
            return
        if _(self.get_construction_targets()).concat(self.get_repair_targets()) \
                .map(lambda x: Game.getObjectById(x)).sum(
            lambda c: c and c.structureType == STRUCTURE_RAMPART or 0) >= 3:
            self.room.store_cached_property("placed_ramparts", "existing_sites", 20)
            return

        volatile = volatile_cache.volatile()

        site_count = len(Game.constructionSites)
        prev_sites_placed = volatile.get("construction_sites_placed") or 0
        sites_placed_now = 0

        if site_count + prev_sites_placed >= MAX_CONSTRUCTION_SITES * 0.9:
            return

        ramparts = new_set()
        need_ramparts = new_map()

        for structure in self.room.find(FIND_MY_STRUCTURES):
            pos_key = structure.pos.x * 64 + structure.pos.y
            if structure.structureType == STRUCTURE_RAMPART:
                ramparts.add(pos_key)
            elif protect_with_ramparts.includes(structure.structureType) \
                    and (structure.structureType != STRUCTURE_EXTENSION or len(self.room.mining.active_mines) > 1):
                need_ramparts.set(pos_key, structure)

        for site in self.room.find(FIND_MY_CONSTRUCTION_SITES):
            pos_key = site.pos.x * 64 + site.pos.y
            if site.structureType == STRUCTURE_RAMPART:
                ramparts.add(pos_key)

        entries = Array.js_from(need_ramparts.entries())
        sorted_entries = _.sortBy(entries, lambda t: rampart_priorities[t[1].structureType] or 10)
        # Need to make this a list in order to iterate it.
        for pos_key, structure in sorted_entries:
            if not ramparts.has(pos_key):
                print("[{}][building] Protecting {} with a rampart."
                      .format(self.room.name, structure))
                structure.pos.createConstructionSite(STRUCTURE_RAMPART)
                sites_placed_now += 1
                if site_count + prev_sites_placed + sites_placed_now >= MAX_CONSTRUCTION_SITES or sites_placed_now >= 5:
                    break

        volatile.set("construction_sites_placed", sites_placed_now)

        if sites_placed_now > 0:
            self.refresh_building_targets()

        self.room.store_cached_property("placed_ramparts", 1, random.randint(500, 600))

    def re_place_home_ramparts(self):
        self.room.expire_property_next_tick('placed_ramparts')

    def find_loc_near_away_from(self, near, away_from):
        if near.pos:
            near = near.pos
        path = PathFinder.search(near, away_from, {
            'roomCallback': self.hive.honey._get_callback(near, near, {}),
            'flee': True,
            'maxRooms': 1,
        })
        if path.incomplete:
            print("[{}][building] WARNING: Couldn't find full path near {} and away from {}!"
                  .format(self.room.name, near, [x.pos for x in away_from]))
            if not len(path.path):
                return
        return path.path[len(path) - 1]

    def place_depot_flag(self):
        center = self.room.spawn
        if not center:
            center = flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)[0]
            if not center:
                center = self.room.spawns[0]
                if not center:
                    return
        cache = volatile_cache.setmem("npcf")
        cache_key = "depot_{}".format(self.room.name)
        if cache.has(cache_key):
            return
        away_from = [{'pos': center.pos, 'range': 4}]
        for source in self.room.sources:
            away_from.append({'pos': source.pos, 'range': 5})
        for spawn in self.room.spawns:
            away_from.append({'pos': spawn.pos, 'range': 4})
        for mineral in self.room.find(FIND_MINERALS):
            away_from.append({'pos': mineral.pos, 'range': 4})
        for flag in flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_WALL):
            away_from.append({'pos': flag.pos, 'range': 1})
        for flag in flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_RAMPART):
            away_from.append({'pos': flag.pos, 'range': 1})
        target = self.find_loc_near_away_from(center, away_from)
        flags.create_flag(target, DEPOT)
        cache.add(cache_key)


def clean_up_all_road_construction_sites():
    rooms_to_sites = _.groupBy(Game.constructionSites, 'pos.roomName')
    for room_name in Object.keys(rooms_to_sites):
        if _.get(Game.rooms, [room_name, 'controller', 'my'], False):
            continue
        planned_roads = mining_paths.get_set_of_all_serialized_positions_in(room_name)
        for site in rooms_to_sites[room_name]:
            xy = positions.serialize_pos_xy(site)
            if site.structureType == STRUCTURE_ROAD:
                if not planned_roads.has(xy):
                    print("[building] Removing {} at {}.".format(site, site.pos))
                    site.remove()
            else:
                msg = "[building] WARNING: Construction site for a {} found in unowned room {}. Non-road construction" \
                      " sites are generally not supported in unowned rooms!".format(site.structureType, room_name)
                print(msg)
                Game.notify(msg)


def clean_up_owned_room_roads(hive):
    """
    :type hive: empire.hive.HiveMind
    """
    for room in hive.my_rooms:
        roads = []
        non_roads = new_set()
        for structure in room.find(FIND_STRUCTURES):
            if structure.structureType == STRUCTURE_ROAD:
                roads.push(structure)
            elif structure.structureType != STRUCTURE_RAMPART and structure.structureType != STRUCTURE_CONTAINER:
                non_roads.add(positions.serialize_pos_xy(structure))
        for road in roads:
            if non_roads.has(positions.serialize_pos_xy(road)):
                road.destroy()


def repave(mine_name):
    """
    Command which is useful for use from console.
    :param mine_name: The name of a mine flag
    :return:
    """
    flag = Game.flags[mine_name]
    if not flag:
        return "error: flag {} does not exist!".format(mine_name)
    if 'sponsor' in flag.memory:
        sponsor = flag.memory.sponsor
    else:
        sponsor = flag.name.split('_')[0]
    room = context.hive().get_room(sponsor)
    if not room:
        return "error: room {} not visible.".format(sponsor)
    if not room.my:
        return "error: room {} not owned.".format(sponsor)
    room.delete_cached_property(_cache_key_found_roads_for_mine + flag.name)
    room.delete_cached_property(_cache_key_placed_roads_for_mine + flag.name)
    room.building.build_road(flag)
