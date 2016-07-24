from base import *

__pragma__('noalias', 'name')
_MAX_BUILDERS = 3

target_source = "source"
target_construction = "construction_site"
target_repair = "repair_site"
target_big_repair = "extra_repair_site"


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
            target_construction: self._find_new_construction_site,
            target_repair: self._find_new_repair_site,
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

    def _find_new_target(self, type, room, extra_var):
        if not self.targets[type]:
            self.targets[type] = {}
            print("Creating targets[{}]".format(type))
        return self.find_functions[type](room, extra_var)

    def _get_existing_target_id(self, type, targeter_id):
        if self.targeters[targeter_id]:
            return self.targeters[targeter_id][type]
        return None

    def _get_new_target_id(self, type, targeter_id, room, extra_var):
        existing_target = self._get_existing_target_id(type, targeter_id)
        if existing_target:
            return existing_target
        new_target = self._find_new_target(type, room, extra_var)
        if not new_target:
            return None
        self._register_new_targeter(type, targeter_id, new_target)
        return new_target

    def get_new_target(self, creep, type, extra_var=None, second_time=False):
        id = self._get_new_target_id(type, creep.name, creep.room, extra_var)
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

    def _find_new_source(self, room):
        smallest_num_harvesters = 8000
        best_source_id = None
        for source in room.find(FIND_SOURCES):
            id = source.id
            if not self.targets[target_source][id]:
                return id
            elif self.targets[target_source][id] < smallest_num_harvesters:
                smallest_num_harvesters = self.targets[target_source][id]
                best_source_id = id
        # for name in Object.keys(Game.flags):
        #     flag = Game.flags[name]
        #     if not flag.memory.harvesting_spot:
        #         continue
        #     id = "flag-" + name
        #     if not self.targets[target_source][id]:
        #         return id
        #     elif self.targets[target_source][id] < smallest_num_harvesters:
        #         smallest_num_harvesters = self.targets[target_source][id]
        #         best_source_id = id

        return best_source_id

    def _find_new_construction_site(self, room):
        for site in room.find(FIND_CONSTRUCTION_SITES):
            id = site.id
            if not self.targets[target_source][id]:
                return id
            elif self.targets[target_source][id] < _MAX_BUILDERS:
                return id
        return None

    def _find_new_repair_site(self, room, max_hits):
        smallest_num_builders = 8000
        best_source_id = None
        for structure in room.find(FIND_STRUCTURES):
            if (structure.my != False and structure.hits < structure.hitsMax
                and (not max_hits or structure.hits >= max_hits)):

                id = structure.id
                if not self.targets[target_repair][id]:
                    return id
                elif self.targets[target_source][id] < _MAX_BUILDERS:
                    return id
                elif self.targets[target_repair][id] < smallest_num_builders:
                    smallest_num_builders = self.targets[target_repair][id]
                    best_source_id = id

        return best_source_id

    def _find_new_big_repair_site(self, room, max_hits):
        for structure in room.find(FIND_STRUCTURES):
            if (structure.my == False or
                        structure.hits >= structure.hitsMax or
                    (max_hits and structure.hits >= max_hits)):
                continue
            id = structure.id
            if not self.targets[target_repair][id]:
                return id
            elif self.targets[target_source][id] < 1:
                return id
        return None
