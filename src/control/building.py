import math
import random

import flags
from tools import profiling
from utilities import movement, volatile_cache
from utilities.screeps_constants import *
from utilities.screeps_constants import new_set

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')

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
    :type room: control.hivemind.RoomMind
    """
    if not room.spawn:
        if structure_type == STRUCTURE_SPAWN:
            if room.being_bootstrapped():
                if room.mem.prio_spawn:
                    return -2
                else:
                    return 5
            else:
                return -2
        elif structure_type == STRUCTURE_LINK:
            if room.being_bootstrapped():
                return 4
        elif (structure_type == STRUCTURE_WALL or structure_type == STRUCTURE_EXTENSION) and room.being_bootstrapped():
            if room.mem.prio_walls:
                return -1
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
    :type room: control.hivemind.RoomMind
    :type hive: control.hivemind.HiveMind
    """

    def __init__(self, room):
        """
        :type room: control.hivemind.RoomMind
        :param room:
        """
        self.room = room
        self.hive = room.hive

    def toString(self):
        return "ConstructionMind[room: {}]".format(self.room.name)

    def refresh_building_targets(self, now=False):
        self.refresh_num_builders(now)
        if now:
            del self.room.mem.cache.building_targets
            del self.room.mem.cache.non_wall_construction_targets
            del self.room.mem.cache.sieged_walls_unbuilt
        else:
            if 'building_targets' in self.room.mem.cache:
                self.room.mem.cache.building_targets.dead_at = Game.time + 1
            if 'non_wall_construction_targets' in self.room.mem.cache:
                self.room.mem.cache.non_wall_construction_targets.dead_at = Game.time + 1
            if 'sieged_walls_unbuilt' in self.room.mem.cache:
                self.room.mem.cache.sieged_walls_unbuilt.dead_at = Game.time + 1

    def refresh_repair_targets(self, now=False):
        self.refresh_num_builders(now)
        if now:
            del self.room.mem.cache.repair_targets
            del self.room.mem.cache.big_repair_targets
        else:
            if 'repair_targets' in self.room.mem.cache:
                self.room.mem.cache.repair_targets.dead_at = Game.time + 1

            big_targets = self.room.get_cached_property("big_repair_targets")
            if big_targets:
                max_hits = self.room.max_sane_wall_hits
                i = 0
                while i < len(big_targets):
                    target = Game.getObjectById(big_targets[i])
                    if not target or (target.hits >= min(target.hitsMax, max_hits)
                                      and (target.structureType == STRUCTURE_RAMPART
                                           or target.structureType == STRUCTURE_WALL)):
                        big_targets.splice(i, 1)
                    else:
                        i += 1

    def refresh_destruction_targets(self):
        del self.room.mem.cache.destruct_targets

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

        construction = _.sum(self.get_construction_targets(), lambda c: c.progressTotal - c.progress)
        repair = _.sum(self.get_big_repair_targets(), self._hits_left_to_repair_at)
        total_work_ticks_needed = construction / BUILD_POWER + repair / REPAIR_POWER
        # We are assuming here that each creep spends about half it's life moving between storage and the build/repair
        # site.
        total_work_parts_needed = math.ceil(total_work_ticks_needed / (CREEP_LIFE_TIME / 2))

        self.room.store_cached_property("max_builder_work_parts", total_work_parts_needed, 1000)
        return total_work_parts_needed

    def refresh_num_builders(self, now=False):
        if now:
            del self.room.mem.cache.builders_needed
            del self.room.mem.cache.max_builder_work_parts
        else:
            if 'builders_needed' in self.room.mem.cache:
                self.room.mem.cache.builders_needed.dead_at = Game.time + 1
            if 'max_builder_work_parts' in self.room.mem.cache:
                self.room.mem.cache.max_builder_work_parts.dead_at = Game.time + 1

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
        del self.room.mem.cache.non_wall_construction_targets
        del self.room.mem.cache.seiged_walls_unbuilt
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
                and total_count < 100:
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
                and self.room.mem.prio_walls
            )
            prio_spawn = (
                self.room.rcl < 5
                and self.room.being_bootstrapped()
                and not not self.room.mem.prio_spawn
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
                    if len(new_sites) >= 4 or total_count >= 100:
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

    def place_remote_mining_roads(self):
        if Game.cpu.bucket < 4500:
            return

        if (Game.time + self.room.get_unique_owned_index()) % 30 != 3:
            return
        current_method_version = 23
        latest_key = "{}-{}-{}".format(current_method_version, self.room.rcl, len(self.room.mining.active_mines))
        last_run_version = self.room.get_cached_property("placed_mining_roads")
        if last_run_version and last_run_version == latest_key:
            return
        elif last_run_version == "missing_rooms":
            if Game.time % 30 != 3:
                return  # don't check every tick
            missing_rooms = self.room.get_cached_property("pmr_missing_rooms")
            for name in missing_rooms:
                if Game.rooms[name]:
                    break  # Re-pave if we can now see a room we couldn't before!
            else:
                return
        elif last_run_version == "too_many_sites":
            if Game.time % 30 != 3:
                return
            if len(Game.constructionSites) >= 50:
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

        single_mine_num = self.room.get_cached_property("run_only_mine")
        if single_mine_num is None and len(self.room.mining.active_mines) > 5:
            single_mine_num = 0

        # stagger updates after a version change.
        # Really don't do this often either - this is an expensive operation.
        # Calculate this here so we can pass it to HoneyTrails for how long to keep paths.
        ttl = random.randint(200 * 1000, 220 * 1000)

        volatile = volatile_cache.volatile()

        checked_positions_per_room = new_map()
        future_road_positions_per_room = {}
        preexisting_count = len(Game.constructionSites) + (volatile.get("construction_sites_placed") or 0)
        placed_count = 0
        path_count = 0

        # TODO: this does assume that each remote mining room will be unique to one owned room (no remote mining rooms
        # with one mine sponsored by one room, and another mine sponsored by another).
        # I hope this is a safe assumption to make for now.
        road_opts = {'decided_future_roads': future_road_positions_per_room, "keep_for": ttl + 10}
        spawn_road_opts = {'range': 3, 'decided_future_roads': future_road_positions_per_room, "keep_for": ttl + 10}
        any_non_visible_rooms = False
        non_visible_rooms = None

        def check_route(mine, positions):
            nonlocal checked_positions_per_room, future_road_positions_per_room, path_count, \
                placed_count, any_non_visible_rooms, non_visible_rooms
            if mine.pos:
                mine = mine.pos
            path_count += 1
            for pos in positions:
                if checked_positions_per_room.has(pos.roomName):
                    checked_positions = checked_positions_per_room.get(pos.roomName)
                else:
                    checked_positions = new_set()
                    checked_positions_per_room.set(pos.roomName, checked_positions)

                room = self.hive.get_room(pos.roomName)
                if not room:
                    # We don't have visibility to this active mine! let's just wait on this one
                    any_non_visible_rooms = True
                    if non_visible_rooms is None:
                        non_visible_rooms = new_set()
                    non_visible_rooms.add(pos.roomName)
                    continue

                # I don't know how to do this more efficiently in JavaScript - a list [x, y] doesn't have a good
                # equals, and thus wouldn't be unique in the set - but this *is* unique.
                pos_key = pos.x | pos.y << 6
                if not checked_positions.has(pos_key):
                    destruct_flag = flags.look_for(room, pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                    if destruct_flag:
                        destruct_flag.remove()
                    if not _.find(room.look_at(LOOK_STRUCTURES, pos.x, pos.y),
                                  {"structureType": STRUCTURE_ROAD}) \
                            and not len(room.look_at(LOOK_CONSTRUCTION_SITES, pos.x, pos.y)):
                        if placed_count + preexisting_count >= 100:
                            break
                        if abs(pos.x - mine.x) > 1 or abs(pos.y - mine.y) > 1:
                            room.room.createConstructionSite(pos.x, pos.y, STRUCTURE_ROAD)
                        placed_count += 1
                    checked_positions.add(pos_key)
                    if pos.roomName in future_road_positions_per_room:
                        future_road_positions_per_room[pos.roomName].push(pos)
                    else:
                        future_road_positions_per_room[pos.roomName] = [pos]

        if single_mine_num is not None:
            mines = list(reversed(self.room.mining.active_mines))
            if single_mine_num < len(mines):
                mine = mines[single_mine_num]
                target = None
                if mine.pos.roomName != self.room.name or (self.room.rcl >= 4 and self.room.room.storage
                                                           and self.room.room.storage.storeCapacity):

                    deposit_point = self.room.mining.closest_deposit_point_to_mine(mine)
                    if deposit_point:
                        target = self.room.get_cached_property("run_only_mine_target_num") or 0
                        if target == 0:
                            self.hive.honey.clear_cached_path(deposit_point, mine)
                            check_route(mine, reversed(self.hive.honey.list_of_room_positions_in_path(
                                deposit_point, mine, road_opts)))
                        elif target == 1:
                            self.hive.honey.clear_cached_path(mine, deposit_point)
                            check_route(mine, self.hive.honey.list_of_room_positions_in_path(
                                mine, deposit_point, road_opts))
                        elif target == 2:
                            for spawn in self.room.spawns:
                                self.hive.honey.clear_cached_path(mine, spawn, spawn_road_opts)
                                check_route(mine, self.hive.honey.list_of_room_positions_in_path(
                                    mine, spawn, spawn_road_opts))

                if (target is None) or (placed_count + preexisting_count < 100 and not any_non_visible_rooms):
                    if target is not None and target < 2:
                        self.room.store_cached_property("run_only_mine_target_num", target + 1, 500)
                    else:
                        self.room.store_cached_property("run_only_mine_target_num", 0, 500)
                        self.room.store_cached_property("run_only_mine", single_mine_num + 1, 500)
                print("[{}][building] Searched target {}/3 of mine {}/{} for remote mining roads.".format(
                    self.room.name, target, single_mine_num + 1, len(mines)))
                return
            print("[{}][building] Finished searching all mines one at a time!".format(self.room.name))
            self.room.store_cached_property("run_only_mine", 0, 0)
            del self.room.mem.cache['run_only_mine_target_num']

        else:
            try:
                # Prioritize paths for far-away mines (last in the original array)
                for mine in reversed(self.room.mining.active_mines):
                    if mine.pos.roomName == self.room.name \
                            and (self.room.rcl < 4 or not self.room.room.storage
                                 or not self.room.room.storage.storeCapacity):
                        continue

                    deposit_point = self.room.mining.closest_deposit_point_to_mine(mine)
                    if not deposit_point:
                        # If we have no storage nor spawn, don't pave.
                        continue
                    # It's important to run check_route on this path before doing another path, since this updates the
                    # future_road_positions_per_room object.
                    self.hive.honey.clear_cached_path(deposit_point, mine)
                    check_route(mine,
                                reversed(self.hive.honey.list_of_room_positions_in_path(deposit_point, mine,
                                                                                        road_opts)))
                    self.hive.honey.clear_cached_path(mine, deposit_point)
                    check_route(mine, self.hive.honey.list_of_room_positions_in_path(mine, deposit_point, road_opts))
                    for spawn in self.room.spawns:
                        self.hive.honey.clear_cached_path(mine, spawn, spawn_road_opts)
                        check_route(mine, self.hive.honey.list_of_room_positions_in_path(mine, spawn, spawn_road_opts))
            except:
                if not __except0__:
                    # we've run out of CPU!
                    self.room.store_cached_property("run_only_mine", 0, 100)
                __pragma__('js', 'throw __except0__;')
                raise __except0__

        for room_name in Object.keys(checked_positions_per_room):
            checked_positions = checked_positions_per_room.get(room_name)
            room = self.hive.get_room(room_name)

            for road in room.find(FIND_STRUCTURES):
                if road.structureType == STRUCTURE_ROAD:
                    pos_key = road.pos.x * 64 + road.pos.y
                    if not checked_positions.has(pos_key):
                        if flags.look_for(room, road.pos, flags.MAIN_BUILD, flags.SUB_ROAD):
                            continue
                        destruct_flag = flags.look_for(room, road.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                        if not destruct_flag:
                            flags.create_ms_flag(road.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)

            for site in room.find(FIND_MY_CONSTRUCTION_SITES):
                if site.structureType == STRUCTURE_ROAD:
                    pos_key = site.pos.x * 64 + site.pos.y
                    if not checked_positions.has(pos_key):
                        if flags.look_for(room, site.pos, flags.MAIN_BUILD, flags.SUB_ROAD):
                            continue
                        destruct_flag = flags.look_for(room, site.pos, flags.MAIN_DESTRUCT, flags.SUB_ROAD)
                        if destruct_flag:
                            site.remove()
                            destruct_flag.remove()
                        elif site.progress / site.progressTotal < 0.2:
                            site.remove()

            for flag in flags.find_ms_flags(room, flags.MAIN_DESTRUCT, flags.SUB_ROAD):
                if not _.find(room.look_at(LOOK_STRUCTURES, flag.pos), {"structureType": STRUCTURE_ROAD}) \
                        and not _.find(room.look_at(LOOK_CONSTRUCTION_SITES, flag.pos),
                                       {"structureType": STRUCTURE_ROAD}):
                    flag.remove()

        if volatile.has("construction_sites_placed"):
            volatile.set("construction_sites_placed", volatile.get("construction_sites_placed") + placed_count)
        else:
            volatile.set("construction_sites_placed", placed_count)

        if any_non_visible_rooms:
            print("[{}][building] Found {} pos ({} new) for remote roads, from {} paths (missing rooms)".format(
                self.room.name, _.sum(checked_positions_per_room.values(), 'size'),
                placed_count, path_count))
        elif placed_count + preexisting_count >= 100:
            print("[{}][building] Found {} pos ({} new) for remote roads, from {} paths (hit site limit)".format(
                self.room.name, _.sum(checked_positions_per_room.values(), 'size'),
                placed_count, path_count))
        else:
            print("[{}][building] Found {} pos ({} new) for remote roads, from {} paths.".format(
                self.room.name, _.sum(list(checked_positions_per_room.values()), 'size'),
                placed_count, path_count))

        if any_non_visible_rooms:
            self.room.store_cached_property("placed_mining_roads", "missing_rooms", ttl)
            self.room.store_cached_property("pmr_missing_rooms", list(non_visible_rooms.values()), ttl)
        elif placed_count + preexisting_count >= 100:
            self.room.store_cached_property("placed_mining_roads", "too_many_sites", ttl)
        else:
            self.room.store_cached_property("placed_mining_roads", latest_key, ttl)
            # Done!

    def re_place_mining_roads(self):
        cache = self.room.mem.cache
        if 'placed_mining_roads' in cache:
            cache.placed_mining_roads.dead_at = Game.time + 1
        if 'paving_here' in cache:
            cache.paving_here.dead_at = Game.time + 1
        if 'all_paved' in cache:
            cache.all_paved.dead_at = Game.time + 1

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

        if site_count + prev_sites_placed >= 90:
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
                if site_count + prev_sites_placed + sites_placed_now >= 100 or sites_placed_now >= 5:
                    break

        volatile.set("construction_sites_placed", sites_placed_now)

        if sites_placed_now > 0:
            self.refresh_building_targets()

        self.room.store_cached_property("placed_ramparts", 1, random.randint(500, 600))

    def re_place_home_ramparts(self):
        self.room.mem.cache.placed_ramparts.dead_at = Game.time + 1

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
        for flag in flags.find_flags(self.room, flags.SOURCE_QUEUE_START):
            away_from.append({'pos': flag.pos, 'range': 4})
        for flag in flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_WALL):
            away_from.append({'pos': flag.pos, 'range': 1})
        for flag in flags.find_ms_flags(self.room, flags.MAIN_BUILD, flags.SUB_RAMPART):
            away_from.append({'pos': flag.pos, 'range': 1})
        target = self.find_loc_near_away_from(center, away_from)
        flags.create_flag(target, flags.DEPOT)
        cache.add(cache_key)


profiling.profile_whitelist(ConstructionMind, [
    "get_construction_targets",
    "get_repair_targets",
    "get_big_repair_targets",
    "get_destruction_targets",
    "place_remote_mining_roads",
])
