import random

import flags
from constants import PYFIND_BUILDABLE_ROADS
from tools import profiling
from utilities import movement, volatile_cache
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')

building_priorities = {
    STRUCTURE_EXTENSION: 0,
    STRUCTURE_SPAWN: 1,
    STRUCTURE_LINK: 1,
    STRUCTURE_TOWER: 2,
    STRUCTURE_STORAGE: 3,
    STRUCTURE_WALL: 4,
    STRUCTURE_RAMPART: 5,
    STRUCTURE_TERMINAL: 6,
}
default_priority = 10


def get_priority(structure_type):
    if structure_type in building_priorities:
        return building_priorities[structure_type]
    else:
        return default_priority


class ConstructionMind:
    """
    :type room: control.hivemind.RoomMind
    :type hive: control.hivemind.HiveMind
    """

    def __init__(self, room):
        """
        :type room: control.hivemind.RoomMind
        :param room:
        """
        self.room = room
        self.hive = room.hive_mind

    def toString(self):
        return "ConstructionMind[room: {}]".format(self.room.room_name)

    def _get_mem(self):
        if self.room.room.memory.construction is undefined:
            self.room.room.memory.construction = {}
        return self.room.room.memory.construction

    def refresh_building_targets(self):
        del self.room.mem.cache.building_targets

    def refresh_repair_targets(self):
        del self.room.mem.cache.repair_targets

        big_targets = self.room.get_cached_property("big_repair_targets")
        if big_targets:
            max_hits = self.room.max_sane_wall_hits
            i = 0
            while i < len(big_targets):
                target = Game.getObjectById(big_targets[i])
                if not target or target.hits >= min(target.hitsMax, max_hits):
                    big_targets.splice(i, 1)
                else:
                    i += 1

    def refresh_destruction_targets(self):
        del self.room.mem.cache.destruct_targets

    def next_priority_construction_targets(self):
        targets = self.room.get_cached_property("building_targets")
        if targets is not None:
            return targets

        currently_existing = {}
        for s in self.room.find(FIND_STRUCTURES):
            if s.structureType in currently_existing:
                currently_existing[s.structureType] += 1
            else:
                currently_existing[s.structureType] = 1
        for s in self.room.find(FIND_CONSTRUCTION_SITES):
            if s.structureType in currently_existing:
                currently_existing[s.structureType] += 1
            else:
                currently_existing[s.structureType] = 1

        if self.room.spawn:
            spawn_pos = self.room.spawn.pos
        else:
            spawn_flag = flags.find_ms_flag(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)
            if len(spawn_flag):
                spawn_pos = spawn_flag[0].pos
            else:
                print("[{}][building] Warning: Finding construction targets for room {},"
                      " which has no spawn planned!".format(self.room.room_name, self.room.room_name))
                spawn_pos = __new__(RoomPosition(25, 25, self.room.room_name))

        if self.room.room.controller and self.room.room.controller.my:
            controller_level = self.room.room.controller.level
        else:
            print("[{}][building] Warning: finding construction targets for room {},"
                  " which isn't ours!".format(self.room.room_name, self.room.room_name))
            controller_level = 0

        new_sites = []

        for flag, flag_type in _.sortBy(flags.find_by_main_with_sub(self.room, flags.MAIN_BUILD),
                                        lambda flag_tuple: movement.distance_squared_room_pos(spawn_pos,
                                                                                              flag_tuple[0].pos)):
            structure_type = flags.flag_sub_to_structure_type[flag_type]
            if not structure_type:
                print("[{}][building] Warning: structure type corresponding to flag type {} not found!".format(
                    self.room.room_name, flag_type
                ))
            if flags.look_for(self.room, flag, flags.MAIN_DESTRUCT, flags.structure_type_to_flag_sub[structure_type]):
                continue
            if CONTROLLER_STRUCTURES[structure_type][controller_level] > (currently_existing[structure_type] or 0):
                if _.find(self.room.find_at(FIND_STRUCTURES, flag.pos), {"structureType": structure_type}) \
                        or _.find(self.room.find_at(FIND_CONSTRUCTION_SITES, flag.pos),
                                  {"structureType": structure_type}):
                    continue  # already built.
                flag.pos.createConstructionSite(structure_type)
                new_sites.append("flag-{}".format(flag.name))

        sites = [x.id for x in _.sortBy(self.room.find(FIND_MY_CONSTRUCTION_SITES),
                         lambda s: get_priority(s.structureType) * 50
                                   + movement.distance_room_pos(spawn_pos, s.pos))]

        if len(new_sites):
            # Have most things target the new flags first, since the Builder class will auto-re-target next turn when it
            # finds itself targeting a flag.
            self.room.store_cached_property("building_targets", new_sites.concat(sites), 1)
        else:
            self.room.store_cached_property("building_targets", sites, 100)
        return self.room.get_cached_property("building_targets")

    def next_priority_repair_targets(self):
        priority_list = self.room.get_cached_property("repair_targets")
        if priority_list is not None:
            return priority_list
        low_priority = []
        med_priority = []
        high_priority = []

        if self.room.spawn:
            spawn_pos = self.room.spawn.pos
        else:
            spawn_flag = flags.find_ms_flag(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)
            if len(spawn_flag):
                spawn_pos = spawn_flag[0].pos
            else:
                print("[{}][building] Warning: Finding repair targets for room {},"
                      " which has no spawn planned!".format(self.room.room_name, self.room.room_name))
                spawn_pos = __new__(RoomPosition(25, 25, self.room.room_name))

        # TODO: spawn one large repairer (separate from builders) which is boosted with LO to build walls!
        max_hits = min(350000, self.room.min_sane_wall_hits)

        for structure in _.sortBy(_.filter(self.room.find(FIND_STRUCTURES),
                                           lambda s: (s.my or not s.owner)
                                           and s.hits < s.hitsMax * 0.9 and s.hits < max_hits
                                           and (s.structureType != STRUCTURE_ROAD or s.hits < s.hitsMax * 0.4)),
                                  lambda s: movement.distance_squared_room_pos(spawn_pos, s.pos)):
            structure_type = structure.type

            if flags.look_for(self.room, structure.pos, flags.MAIN_DESTRUCT,
                              flags.structure_type_to_flag_sub[structure_type]):
                continue
            if structure_type in (STRUCTURE_SPAWN, STRUCTURE_EXTENSION,
                                  STRUCTURE_TOWER, STRUCTURE_STORAGE, STRUCTURE_LINK):
                high_priority.append(structure.id)
            elif structure_type in (STRUCTURE_WALL, STRUCTURE_RAMPART):
                med_priority.append(structure.id)
            else:
                low_priority.append(structure.id)

        if len(high_priority):
            self.room.store_cached_property("repair_targets", high_priority, 100)
            return high_priority
        elif len(med_priority):
            self.room.store_cached_property("repair_targets", med_priority, 70)
            return med_priority
        elif len(low_priority):
            self.room.store_cached_property("repair_targets", low_priority, 40)
            return low_priority
        else:
            self.room.store_cached_property("repair_targets", low_priority, 70)
            return low_priority

    def next_priority_big_repair_targets(self):
        target_list = self.room.get_cached_property("big_repair_targets")
        if target_list is not None:
            return target_list

        # TODO: spawn one large repairer (separate from builders) which is boosted with LO to build walls!
        max_hits = self.room.max_sane_wall_hits

        target_list = []

        for structure in _.sortBy(_.filter(self.room.find(FIND_STRUCTURES),
                                           lambda s: (s.my or not s.owner) and s.hits < min(s.hitsMax, max_hits)
                                           and (s.structureType != STRUCTURE_ROAD or s.hits < s.hitsMax * 0.5)),
                                  lambda s: s.hits):
            if flags.look_for(self.room, structure, flags.MAIN_DESTRUCT,
                              flags.structure_type_to_flag_sub[structure.structureType]):
                continue
            target_list.append(structure.id)

        self.room.store_cached_property("big_repair_targets", target_list, 200)
        return target_list

    def next_priority_destruct_targets(self):
        target_list = self.room.get_cached_property("destruct_targets")
        if target_list is not None:
            return target_list

        target_list = []

        if self.room.spawn:
            spawn_pos = self.room.spawn.pos
        else:
            spawn_flag = flags.find_ms_flag(self.room, flags.MAIN_BUILD, flags.SUB_SPAWN)
            if len(spawn_flag):
                spawn_pos = spawn_flag[0].pos
            else:
                print("[{}][building] Warning: Finding destruct targets for room {},"
                      " which has no spawn planned!".format(self.room.room_name, self.room.room_name))
                spawn_pos = __new__(RoomPosition(25, 25, self.room.room_name))

        for flag, secondary in _.sortBy(flags.find_by_main_with_sub(self.room, flags.MAIN_DESTRUCT),
                                        lambda t: -movement.distance_squared_room_pos(t[0].pos, spawn_pos)):
            structure_type = flags.flag_sub_to_structure_type[secondary]
            structures = _.filter(self.room.find_at(FIND_STRUCTURES, flag.pos),
                                  lambda s: s.structureType == structure_type)
            if structure_type != STRUCTURE_RAMPART and _.find(self.room.find_at(FIND_STRUCTURES, flag.pos),
                                                              {"structureType": STRUCTURE_RAMPART}):
                for struct in structures:
                    print("[{}][building] Not dismantling {}, as it is under a rampart.".format(
                        self.room.room_name, struct))
                continue
            if len(structures) and not flags.look_for(self.room, flag.pos, flags.MAIN_BUILD, secondary):
                for struct in structures:
                    target_list.append(struct.id)
            else:
                flag.remove()

        self.room.store_cached_property("destruct_targets", target_list, 200)
        return target_list

    def retest_mining_roads(self):
        # TODO: Make a "trigger" function which runs when a controller upgrades which runs things like this.
        del self.room.mem.cache.placed_mining_roads

    def place_remote_mining_roads(self):
        current_method_version = 23
        latest_key = "{}-{}".format(current_method_version, len(self.room.mining.active_mines))
        last_run_version = self.room.get_cached_property("placed_mining_roads")
        if last_run_version and last_run_version == latest_key:
            return
        elif last_run_version == "missing_rooms":
            missing_rooms = self.room.get_cached_property("pmr_missing_rooms")
            if Game.time % 10 != 3:
                return  # don't check every tick
            for name in missing_rooms:
                if Game.rooms[name]:
                    break  # Re-pave if we can now see a room we couldn't before!
            else:
                return
        if not self.room.paving():
            self.room.store_cached_property("placed_mining_roads", latest_key, 100)
            return

        if not self.room.my:
            raise Error("Place remote mining roads ran for non-owned room")

        already_ran_one_this_turn = volatile_cache.mem("run_once").has("place_remote_mining_roads")
        if already_ran_one_this_turn:
            return
        else:
            volatile_cache.mem("run_once").set("place_remote_mining_roads", True)

        checked_positions_per_room = new_map()
        future_road_positions_per_room = {}
        placed_count = 0
        path_count = 0

        # TODO: this does assume that each remote mining room will be unique to one owned room (no remote mining rooms
        # with one mine sponsored by one room, and another mine sponsored by another).
        # I hope this is a safe assumption to make for now.
        road_opts = {'decided_future_roads': future_road_positions_per_room}
        spawn_road_opts = {'range': 3, 'decided_future_roads': future_road_positions_per_room}
        any_non_visible_rooms = False
        non_visible_rooms = None

        def check_route(positions):
            nonlocal path_count, placed_count, any_non_visible_rooms, non_visible_rooms
            path_count += 1
            for pos in positions:
                if checked_positions_per_room.has(pos.roomName):
                    checked_positions = checked_positions_per_room.get(pos.roomName)
                else:
                    checked_positions = __pragma__('js', 'new Set()')
                    checked_positions_per_room.set(pos.roomName, checked_positions)

                room = self.hive.get_room(pos.roomName)
                if not room:
                    # We don't have visibility to this active mine! let's just wait on this one
                    any_non_visible_rooms = True
                    if non_visible_rooms is None:
                        non_visible_rooms = __pragma__('js', 'new Set()')
                    non_visible_rooms.add(pos.roomName)
                    continue

                # I don't know how to do this more efficiently in JavaScript - a list [x, y] doesn't have a good
                # equals, and thus wouldn't be unique in the set - but this *is* unique.
                pos_key = pos.x << 6 + pos.y
                if not checked_positions.has(pos_key):
                    destruct_flag = flags.look_for(room, pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                    if destruct_flag:
                        destruct_flag.remove()
                    if not _.find(room.find_at(FIND_STRUCTURES, pos.x, pos.y),
                                  {"structureType": STRUCTURE_ROAD}) \
                            and not len(room.find_at(PYFIND_BUILDABLE_ROADS, pos.x, pos.y)):
                        room.room.createConstructionSite(pos.x, pos.y, STRUCTURE_ROAD)
                        placed_count += 1
                    checked_positions.add(pos_key)
                    if pos.roomName in future_road_positions_per_room:
                        future_road_positions_per_room[pos.roomName].push(pos)
                    else:
                        future_road_positions_per_room[pos.roomName] = [pos]

        for mine in self.room.mining.active_mines:
            deposit_point = self.room.mining.closest_deposit_point_to_mine(mine)
            self.room.honey.clear_cached_path(deposit_point, mine)
            self.room.honey.clear_cached_path(mine, deposit_point)
            # It's important to run check_route on this path before doing another path, since this updates the
            # future_road_positions_per_room object.
            check_route(self.room.honey.list_of_room_positions_in_path(deposit_point, mine, road_opts))
            for spawn in self.room.spawns:
                self.room.honey.clear_cached_path(mine, spawn, spawn_road_opts)
                check_route(self.room.honey.list_of_room_positions_in_path(mine, spawn, spawn_road_opts))

        to_destruct = 0
        for room_name in checked_positions_per_room.keys():
            checked_positions = checked_positions_per_room.get(room_name)
            room = self.hive.get_room(room_name)

            for road in room.find(FIND_STRUCTURES):
                if road.structureType == STRUCTURE_ROAD:
                    pos_key = road.pos.x * 64 + road.pos.y
                    if not checked_positions.has(pos_key):
                        if flags.look_for(room, road.pos, flags.MAIN_BUILD, flags.SUB_ROAD):
                            continue
                        to_destruct += 1
                        destruct_flag = flags.look_for(room, road.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                        if not destruct_flag:
                            flags.create_ms_flag(road.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)

            for site in room.find(FIND_MY_CONSTRUCTION_SITES):
                if site.structureType == STRUCTURE_ROAD:
                    pos_key = site.pos.x * 64 + site.pos.y
                    if not checked_positions.has(pos_key):
                        if flags.look_for(room, site.pos, flags.MAIN_BUILD, flags.SUB_ROAD):
                            continue
                        to_destruct += 1
                        destruct_flag = flags.look_for(room, site.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                        if destruct_flag:
                            site.remove()
                            destruct_flag.remove()
                        elif site.progress / site.progressTotal < 0.2:
                            site.remove()

            for flag in flags.find_ms_flag(room, flags.MAIN_DESTRUCT, flags.SUB_ROAD):
                if not _.find(room.find_at(FIND_STRUCTURES, flag.pos), {"structureType": STRUCTURE_ROAD}) \
                        and not _.find(room.find_at(FIND_CONSTRUCTION_SITES, flag.pos),
                                       {"structureType": STRUCTURE_ROAD}):
                    flag.remove()

        print("[{}][building] Found {} pos ({} new) for remote roads, from {} paths.".format(
            self.room.room_name, _.sum(checked_positions_per_room.values(), lambda s: s.size),
            placed_count, path_count))

        # stagger updates after a version change.
        # Really don't do this often either - this is an expensive operation.
        if any_non_visible_rooms:
            self.room.store_cached_property("placed_mining_roads", "missing_rooms", 1000)
            self.room.store_cached_property("pmr_missing_rooms", list(non_visible_rooms.values()), 1000)
        else:
            self.room.store_cached_property("placed_mining_roads", latest_key, random.randint(30000, 40000))
            # Done!


profiling.profile_whitelist(ConstructionMind, [
    "next_priority_construction_targets",
    "next_priority_repair_targets",
    "next_priority_big_repair_targets",
    "next_priority_destruct_targets",
    "place_remote_mining_roads",
])
