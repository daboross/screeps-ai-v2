import math

import flags
import profiling
from base import *

__pragma__('noalias', 'name')
_MAX_BUILDERS = 3

target_source = "source"
target_big_source = "big_h_source"
target_construction = "construction_site"
target_repair = "repair_site"
target_big_repair = "extra_repair_site"
target_harvester_deposit = "harvester_deposit_site"
target_tower_fill = "fillable_tower"
target_remote_mine_miner = "remote_miner_mine"
target_remote_mine_hauler = "remote_mine_hauler"


class TargetMind:
    def __init__(self):
        if not Memory.targets:
            Memory.targets = {
                "targets_used": {},
                "targeters_using": {},
            }
        self.mem = Memory.targets
        if not self.mem.targets_used:
            self.mem.targets_used = {}
        if not self.mem.targeters_using:
            self.mem.targeters_using = {}
        self.targets = self.mem.targets_used
        self.targeters = self.mem.targeters_using
        self.find_functions = {
            target_source: self._find_new_source,
            target_big_source: self._find_new_big_h_source,
            target_construction: self._find_new_construction_site,
            target_repair: self._find_new_repair_site,
            target_big_repair: self._find_new_big_repair_site,
            target_harvester_deposit: self._find_new_harvester_deposit_site,
            target_tower_fill: self._find_new_tower,
            target_remote_mine_miner: self._find_new_remote_miner_mine,
            target_remote_mine_hauler: self._find_new_remote_hauler_mine,
        }

    def _register_new_targeter(self, type, targeter_id, target_id):
        if not self.targeters[targeter_id]:
            self.targeters[targeter_id] = {
                type: target_id
            }
        elif not self.targeters[targeter_id][type]:
            self.targeters[targeter_id][type] = target_id
        else:
            old_target_id = self.targeters[targeter_id][type]
            self.targeters[targeter_id][type] = target_id
            if old_target_id == target_id:
                return  # everything beyond here would be redundant
            self.targets[type][old_target_id] -= 1

        if not self.targets[type]:
            self.targets[type] = {
                target_id: 1
            }
        elif not self.targets[type][target_id]:
            self.targets[type][target_id] = 1
        else:
            self.targets[type][target_id] += 1

    def _unregister_targeter(self, type, targeter_id):
        existing_target = self._get_existing_target_id(type, targeter_id)
        if existing_target:
            self.targets[type][existing_target] -= 1
            del self.targeters[targeter_id][type]
            if len(self.targeters[targeter_id]) == 0:
                del self.targeters[targeter_id]

    def _unregister_all(self, targeter_id):
        if self.targeters[targeter_id]:
            for type in Object.keys(self.targeters[targeter_id]):
                self.targets[type][self.targeters[targeter_id][type]] -= 1
        del self.targeters[targeter_id]

    def _find_new_target(self, type, creep, extra_var):
        if not self.targets[type]:
            self.targets[type] = {}
            print("Creating targets[{}]".format(type))
        func = self.find_functions[type]
        if func:
            return func(creep, extra_var)
        else:
            raise "Couldn't find find_function for '{}'!".format(type)

    def _get_existing_target_id(self, type, targeter_id):
        if self.targeters[targeter_id]:
            return self.targeters[targeter_id][type]
        return None

    def _get_new_target_id(self, type, targeter_id, creep, extra_var):
        existing_target = self._get_existing_target_id(type, targeter_id)
        if existing_target:
            return existing_target
        new_target = self._find_new_target(type, creep, extra_var)
        if not new_target:
            return None
        self._register_new_targeter(type, targeter_id, new_target)
        return new_target

    def get_new_target(self, creep, type, extra_var=None, second_time=False):
        id = self._get_new_target_id(type, creep.name, creep, extra_var)
        if not id:
            return None
        if id.startswith("flag-"):
            target = Game.flags[id[5:]]
        else:
            target = Game.getObjectById(id)
        if not target:
            self._unregister_targeter(type, creep.name)
            if not second_time:
                return self.get_new_target(creep, type, extra_var, True)
        return target

    def get_existing_target(self, creep, type):
        id = self._get_existing_target_id(type, creep.name)
        if not id:
            return None
        if id.startswith("flag-"):
            target = Game.flags[id[5:]]
        else:
            target = Game.getObjectById(id)
        if not target:
            self._unregister_targeter(type, creep.name)
        return target

    def untarget(self, creep, type):
        self._unregister_targeter(type, creep.name)

    def untarget_all(self, creep):
        self._unregister_all(creep.name)

    def _find_new_source(self, creep):
        smallest_num_harvesters = 8000
        best_id = None
        closest_distance = 8192
        for source in creep.room.find(FIND_SOURCES):
            id = source.id
            current_harvesters = self.targets[target_source][id]
            if not current_harvesters:
                return id
            elif current_harvesters <= smallest_num_harvesters + 1:
                range = source.pos.getRangeTo(creep.pos)
                if range < closest_distance or current_harvesters < smallest_num_harvesters - 1:
                    best_id = id
                    closest_distance = range
                    smallest_num_harvesters = current_harvesters

        return best_id

    def _find_new_big_h_source(self, creep):
        for source in creep.room.find(FIND_SOURCES):
            id = source.id
            current_harvesters = self.targets[target_big_source][id]
            if not current_harvesters or current_harvesters < 1:
                return id

        return None

    def _find_new_harvester_deposit_site(self, creep):
        closest_distance = 8192
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if (structure.structureType == STRUCTURE_EXTENSION or structure.structureType == STRUCTURE_SPAWN) \
                    and structure.energy < structure.energyCapacity and structure.my:
                id = structure.id
                current_num = self.targets[target_source][id]
                # TODO: "1" should be a lot bigger if we have smaller creeps and no extensions.
                if not current_num or current_num < 1:
                    range = structure.pos.getRangeTo(creep.pos)
                    # TODO: use squared distance for faster calculation!
                    if range < closest_distance:
                        closest_distance = range
                        best_id = id

        return best_id

    def _find_new_construction_site(self, creep):
        closest_distance = 8192
        best_id = None
        for site in creep.room.find(FIND_CONSTRUCTION_SITES):
            id = site.id
            current_num = self.targets[target_construction][id]
            # TODO: this 200 should be a decided factor based off of spawn extensions
            if not current_num or current_num < \
                    min(_MAX_BUILDERS, math.ceil((site.progressTotal - site.progress) / 200)):
                range = site.pos.getRangeTo(creep.pos)
                # TODO: use squared distance for faster calculation!
                if range < closest_distance:
                    closest_distance = range
                    best_id = id
        return best_id

    def _find_new_repair_site(self, creep, max_hits):
        closest_distance = 8192
        smallest_num_builders = 8000
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if structure.my != False and structure.hits < structure.hitsMax \
                    and (structure.hits < max_hits or not max_hits):
                id = structure.id
                current_num = self.targets[target_repair][id]
                # TODO: this 200 should be a decided factor based off of spawn extensions
                if not current_num or current_num < \
                        min(_MAX_BUILDERS, math.ceil((min(max_hits, structure.hitsMax) - structure.hits) / 200)) \
                        or current_num <= smallest_num_builders + 1:
                    range = structure.pos.getRangeTo(creep.pos)
                    # TODO: use squared distance for faster calculation!
                    if range < closest_distance:
                        smallest_num_builders = current_num
                        closest_distance = range
                        best_id = id

        return best_id

    def _find_new_big_repair_site(self, creep, max_hits):
        closest_distance = 8192
        best_id = None
        for structure in creep.room.find(FIND_STRUCTURES):
            if structure.my != False and structure.hits < structure.hitsMax \
                    and (structure.hits < max_hits or not max_hits):
                id = structure.id
                current_num = self.targets[target_big_repair][id]
                if not current_num or current_num < 1:
                    range = structure.pos.getRangeTo(creep.pos)
                    # TODO: use squared distance for faster calculation!
                    if range < closest_distance:
                        closest_distance = range
                        best_id = id

        return best_id

    def _find_new_tower(self, creep):
        most_lacking = 0
        best_id = None
        for id in Memory.tower.towers:
            tower = Game.getObjectById(id)
            if tower.room != creep.room:
                continue
            if tower.energyCapacity - tower.energy > most_lacking:
                most_lacking = tower.energyCapacity - tower.energy
                best_id = id

        return best_id

    def _find_new_remote_miner_mine(self, creep):
        for flag in flags.get_global_flags(flags.REMOTE_MINE):
            id = "flag-{}".format(flag.name)
            miners = self.targets[target_remote_mine_miner][id]
            if not miners or miners < 1:
                return id

        return None

    def _find_new_remote_hauler_mine(self, creep):
        for flag in flags.get_global_flags(flags.REMOTE_MINE):
            id = "flag-{}".format(flag.name)
            miners = self.targets[target_remote_mine_hauler][id]
            if not miners or miners < 2:
                return id

        return None


profiling.profile_class(TargetMind)


class HiveMind:
    def __init__(self, target_mind):
        self.target_mind = target_mind
        self.my_rooms = self._find_my_rooms()

    def _find_my_rooms(self):
        result = []
        for name in Object.keys(Game.rooms):
            if Game.rooms[name].controller.my:
                result.append(RoomMind(self, Game.rooms[name]))


profiling.profile_class(HiveMind)


class RoomMind:
    """
    Modes to create:

    - Whether or not to use STORAGE
    - When to create Big Harvesters
    - When to set workers to TOWER FILL

    Variables to consider
    - WORK_MASS: a total count of all WORK bodyparts on worker creeps
    - BIG_HARVESTERS_PLACED: where big harvesters exist
    - TIME_TO_REPLACE_BIG_HARVESTER: We need to count how long till the next big harvester dies plus how long it should
                                     take for the new big harvester to move from spawn to the big harvester's location
    """

    def __init__(self, hivemind, room):
        self.hivemind = hivemind
        self.room = room
        self.sources = None

    def get_sources(self):
        if not self.sources:
            self.sources = self.room.find(FIND_SOURCES)


profiling.profile_class(RoomMind)
