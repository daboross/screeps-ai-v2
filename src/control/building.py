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

    def next_priority_construction_targets(self):
        priority_list = self.room.get_cached_property("building_targets")
        if priority_list is not None:
            return priority_list
        current_targets = {}
        low_priority = []
        med_priority = []
        high_priority = []

        for site in self.room.find(FIND_CONSTRUCTION_SITES):
            if site.structureType in (STRUCTURE_SPAWN, STRUCTURE_EXTENSION, STRUCTURE_TOWER):
                high_priority.append(site.id)
            elif site.structureType in (STRUCTURE_WALL, STRUCTURE_RAMPART, STRUCTURE_STORAGE, STRUCTURE_LINK):
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
                if structure_type in (STRUCTURE_SPAWN, STRUCTURE_EXTENSION, STRUCTURE_TOWER):
                    high_priority.append("flag-{}".format(flag.name))
                elif structure_type in (STRUCTURE_WALL, STRUCTURE_RAMPART, STRUCTURE_STORAGE, STRUCTURE_LINK):
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
        max_hits = min(350000, self.room.max_sane_wall_hits)

        for structure in _.sortBy(_.filter(self.room.find(FIND_STRUCTURES), lambda s:
                        (s.my or not s.owner) and s.hits < s.hitsMax * 0.9 and s.hits < max_hits),
                                  lambda s: movement.distance_squared_room_pos(spawn_pos, s.pos)):
            structure_type = structure.type

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

    def place_remote_mining_roads(self):
        # TODO: I'm not sure if this or iterating over all mining flags and the paths to them would be better:
        # if we start using HoneyTrails for more things, we might want to do that instead of this - or we could
        # just pave those paths too?
        last_run_version = self.room.get_cached_property("placed_mining_roads")
        if last_run_version and last_run_version >= 3:
            return  # Don't do this every tick, even though this function is called every tick.

        if not self.room.paving():
            self.room.store_cached_property("placed_mining_roads", True, 100)
            return

        room_cache = self.room.mem.cache
        checked_positions = __pragma__('js', 'new Set()')
        placed_count = 0
        path_count = 0
        if room_cache:
            for rhp_key in Object.keys(room_cache):
                # This rhp key is a slight hack to ensure we only count paths remote miners are taking, not other paths
                # cached for calculation.
                if not rhp_key.startswith("rhp_"):
                    continue
                rhp_value = room_cache[rhp_key]

                if rhp_value.dead_at < Game.time:
                    continue

                sx, sy, ex, ey = rhp_value.value

                path_key = "path_{}_{}_{}_{}".format(sx, sy, ex, ey)

                value = room_cache[path_key]

                # If we were checking for anything but paths, we'd want to check if `value.ttl_after_use` is set, as
                # that dictates whether `value.last_used` is set at all. But, for path caching, we always know
                # `ttl_after_use` is used.
                if value and Game.time < value.dead_at and (Game.time < value.last_used + 20):
                    try:
                        path = Room.deserializePath(value.value)
                    except:
                        continue  # not a path, apparently
                    path_count += 1
                    for pos in path:
                        # I don't know how to do this more efficiently in JavaScript - a list [x, y] doesn't have a good
                        # equals, and thus wouldn't be unique in the set - but this *is* unique.
                        path_key = pos.x * 64 + pos.y
                        if not checked_positions.has(path_key):
                            if not _.find(self.room.find_at(FIND_STRUCTURES, pos.x, pos.y),
                                          {"structureType": STRUCTURE_ROAD}) \
                                    and not len(self.room.find_at(PYFIND_BUILDABLE_ROADS, pos.x, pos.y)):
                                self.room.room.createConstructionSite(pos.x, pos.y, STRUCTURE_ROAD)
                                placed_count += 1
                            checked_positions.add(path_key)

        # print("[{}][building] Found {} pos ({} new) for remote roads, from {} paths.".format(
        #     self.room.room_name, checked_positions.size, placed_count, path_count))

        # random to stagger redoing this, as this feature was implemented all at once.
        # the key is the version of code we've ran - so we will re-run it if an update happens.
        self.room.store_cached_property("placed_mining_roads", 3, random.randint(200, 250))
        # Done!


profiling.profile_whitelist(ConstructionMind, "refresh_targets")
