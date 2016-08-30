import random

import flags
from constants import PYFIND_BUILDABLE_ROADS
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


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
        priority_list = self.room.get_cached_property("building_targets")
        if priority_list is not None:
            return priority_list
        current_targets = {}
        low_priority = []
        med_priority = []
        high_priority = []

        for site in self.room.find(FIND_CONSTRUCTION_SITES):
            if site.structureType in (STRUCTURE_SPAWN, STRUCTURE_EXTENSION, STRUCTURE_LINK, STRUCTURE_TOWER):
                high_priority.append(site.id)
            elif site.structureType in (STRUCTURE_WALL, STRUCTURE_RAMPART, STRUCTURE_STORAGE):
                med_priority.append(site.id)
            # elif site.structureType == STRUCTURE_ROAD:
            #     # let's only have haulers repairing roads, that way we won't build too many where we don't need them,
            #     # if the pathfinding doesn't work.
            #     # TODO: Remove this statement once we rewrite the remote pathfinding to iterate over remote mines and
            #     # only place paths for a single path to each mine, instead of using recently-used cached paths.
            #     continue
            else:
                low_priority.append(site.id)
            if current_targets[site.structureType]:
                current_targets[site.structureType] += 1
            else:
                current_targets[site.structureType] = 1

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

        new_site_placed = False

        currently_built_structures = {}

        for flag, flag_type in _.sortBy(
                flags.find_by_main_with_sub(self.room, flags.MAIN_BUILD),
                lambda flag_tuple: movement.distance_squared_room_pos(spawn_pos, flag_tuple[0].pos)):
            structure_type = flags.flag_sub_to_structure_type[flag_type]
            if not structure_type:
                print("[{}][building] Warning: structure type corresponding to flag type {} not found!".format(
                    self.room.room_name, flag_type
                ))
            if flags.look_for(self.room, flag, flags.MAIN_DESTRUCT, flags.structure_type_to_flag_sub[structure_type]):
                continue
            if currently_built_structures[structure_type]:
                currently_built = currently_built_structures[structure_type]
            else:
                currently_built = 0
                for s in self.room.find(FIND_STRUCTURES):
                    if s.structureType == structure_type and (not s.owner or s.my):
                        currently_built += 1
                currently_built_structures[structure_type] = currently_built
            if CONTROLLER_STRUCTURES[structure_type][controller_level] \
                    > currently_built + (current_targets[structure_type] or 0):
                if len(_.filter(flag.pos.lookFor(LOOK_STRUCTURES), {"structureType": structure_type})) \
                        or len(_.filter(flag.pos.lookFor(LOOK_CONSTRUCTION_SITES), {"structureType": structure_type})):
                    continue  # already built.
                flag.pos.createConstructionSite(structure_type)
                if structure_type in (STRUCTURE_SPAWN, STRUCTURE_TOWER, STRUCTURE_LINK):
                    high_priority.append("flag-{}".format(flag.name))
                elif structure_type in (STRUCTURE_WALL, STRUCTURE_RAMPART, STRUCTURE_STORAGE, STRUCTURE_EXTENSION):
                    med_priority.append("flag-{}".format(flag.name))
                else:
                    low_priority.append("flag-{}".format(flag.name))
                new_site_placed = True

        if len(high_priority):
            # We're going to want to work on high priority targets anyways, even if new ones are placed. Long TTL!
            self.room.store_cached_property("building_targets", high_priority, 400)
        elif len(med_priority):
            # We're halfway done. Somewhat random TTL!
            self.room.store_cached_property("building_targets", med_priority, 200)
        elif len(low_priority):
            # These are the last of the targets placed - there won't be any more unless more are placed manually.
            # TODO: This should be lower if auto-placing is ever implemented. Or, autoplacing should just use refresh()
            self.room.store_cached_property("building_targets", low_priority, 300)
        else:
            # No targets available at current controller level. TODO: refresh when controller upgrades!
            self.room.store_cached_property("building_targets", low_priority, 70)

        if new_site_placed:
            # expires in one tick, when new construction sites are active.
            self.room.mem.cache.building_targets.dead_at = Game.time + 1

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
        # TODO: I'm not sure if this or iterating over all mining flags and the paths to them would be better:
        # if we start using HoneyTrails for more things, we might want to do that instead of this - or we could
        # just pave those paths too?
        current_method_version = 14
        last_run_version = self.room.get_cached_property("placed_mining_roads")
        if last_run_version and last_run_version == current_method_version:
            # print("[{}][building] Not paving: already ran".format(self.room.room_name))
            return  # Don't do this every tick, even though this function is called every tick.

        if not self.room.paving():
            print("[{}][building] Not paving.".format(self.room.room_name))
            self.room.store_cached_property("placed_mining_roads", current_method_version, 100)
            return

        if self.room.my:
            sponsoring_rooms = [self.room]
        else:
            sponsoring_rooms = []
            for flag in flags.find_flags(self.room, flags.REMOTE_MINE):
                if flag.memory.sponsor:
                    room = self.hive.get_room(flag.memory.sponsor)
                    for r2 in sponsoring_rooms:
                        if r2.room_name == room.room_name:
                            break
                    else:
                        sponsoring_rooms.append(room)

        checked_positions = __pragma__('js', 'new Set()')
        placed_count = 0
        path_count = 0

        # print("Found sponsoring rooms: {}".format(sponsoring_rooms))

        for room in sponsoring_rooms:
            for mine in room.mining.active_mines:
                home_pos = room.mining.closest_deposit_point_to_mine(mine)
                positions = room.honey.list_of_room_positions_in_path(home_pos, mine)
                path_count += 1
                # print("Found position list {} for mine {} from sponsoring room {} (path used: {} to {})"
                #       .format(positions, mine, room, home_pos, mine))
                for pos in positions:
                    # TODO: this is a hacky inefficient way to do this - we should refactor to only have this function
                    # performed once per owned room, and just do all of the subsidiary rooms there.
                    if pos.roomName != self.room.room_name:
                        # print("Skipping {} ({} != {}).".format(pos, pos.roomName, self.room.room_name))
                        continue
                    # print("Checking pos {}.".format(pos))

                    # I don't know how to do this more efficiently in JavaScript - a list [x, y] doesn't have a good
                    # equals, and thus wouldn't be unique in the set - but this *is* unique.
                    pos_key = pos.x * 64 + pos.y
                    if not checked_positions.has(pos_key):
                        destruct_flag = flags.look_for(self.room, pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                        if destruct_flag:
                            destruct_flag.remove()
                        if not _.find(self.room.find_at(FIND_STRUCTURES, pos.x, pos.y),
                                      {"structureType": STRUCTURE_ROAD}) \
                                and not len(self.room.find_at(PYFIND_BUILDABLE_ROADS, pos.x, pos.y)):
                            self.room.room.createConstructionSite(pos.x, pos.y, STRUCTURE_ROAD)
                            placed_count += 1
                        checked_positions.add(pos_key)

        to_destruct = 0
        for site in self.room.find(FIND_MY_CONSTRUCTION_SITES):
            if site.structureType == STRUCTURE_ROAD:
                pos_key = site.pos.x * 64 + site.pos.y
                if not checked_positions.has(pos_key):
                    if flags.look_for(self.room, site.pos, flags.MAIN_BUILD, flags.SUB_ROAD):
                        continue
                    to_destruct += 1
                    destruct_flag = flags.look_for(self.room, site.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                    if destruct_flag:
                        site.remove()
                        destruct_flag.remove()
                    elif site.progress / site.progressTotal < 0.2:
                        site.remove()

        # if not self.room.my:
        for road in self.room.find(FIND_STRUCTURES):
            if road.structureType == STRUCTURE_ROAD:
                pos_key = road.pos.x * 64 + road.pos.y
                if not checked_positions.has(pos_key):
                    if flags.look_for(self.room, road.pos, flags.MAIN_BUILD, flags.SUB_ROAD):
                        continue
                    to_destruct += 1
                    destruct_flag = flags.look_for(self.room, road.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                    if not destruct_flag:
                        flags.create_ms_flag(road.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)

        # print("[{}][building] Found {} pos ({} new, {} due for removal) for remote roads, from {} paths.".format(
        #     self.room.room_name, checked_positions.size, placed_count, to_destruct, path_count))

        # stagger updates after a version change.
        self.room.store_cached_property("placed_mining_roads", current_method_version, random.randint(200, 300))
        # Done!


profiling.profile_whitelist(ConstructionMind, [
    "next_priority_construction_targets",
    "next_priority_repair_targets",
    "next_priority_big_repair_targets",
    "next_priority_destruct_targets",
    "place_remote_mining_roads",
])
