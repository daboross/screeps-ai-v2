import hivemind
import upgrading

from base import *

__pragma__('noalias', 'name')


class Builder(upgrading.Upgrader):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self.creep)
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            self.harvest_energy()
        else:
            target = self.target_mind.get_existing_target(self.creep,
                                                          hivemind.target_repair)
            if target:
                return self.execute_repair_target(target, 350000, hivemind.target_repair)
            target = self.target_mind.get_existing_target(self.creep,
                                                          hivemind.target_construction)
            if target:
                return self.execute_construction_target(target)

            target = self.get_new_repair_target(350000, hivemind.target_repair)
            if target:
                self.target_mind.untarget(self.creep, hivemind.target_big_repair)
                del self.memory.last_big_repair_max_hits
                return self.execute_repair_target(target, 350000, hivemind.target_repair)

            target = self.get_new_construction_target()
            if target:
                self.target_mind.untarget(self.creep, hivemind.target_big_repair)
                del self.memory.last_big_repair_max_hits
                return self.execute_construction_target(target)

            if self.memory.last_big_repair_max_hits:
                max_hits = self.memory.last_big_repair_max_hits
                target = self.get_new_repair_target(max_hits,
                                                    hivemind.target_big_repair)
                if target:
                    return self.execute_repair_target(
                        target, max_hits, hivemind.target_big_repair)
            for max_hits in range(400000, 600000, 50000):
                target = self.get_new_repair_target(max_hits,
                                                    hivemind.target_big_repair)
                if target:
                    self.memory.last_big_repair_max_hits = max_hits
                    return self.execute_repair_target(
                        target, max_hits, hivemind.target_big_repair)

            print("[{}] Couldn't find any building targets.".format(self.name))
            return upgrading.Upgrader.run(self)

    def get_new_repair_target(self, max_hits, type):
        # def find_list():
        #     return self.creep.room.find(FIND_STRUCTURES, {"filter": lambda structure: (
        #         structure.my != False and
        #         structure.hits < structure.hitsMax and
        #         structure.hits < max_hits
        #     )})
        #
        # def max_builders(structure):
        #     return min((1 + (structure.hitsMax - min(structure.hits, max_hits))
        #                 / self.creep.carryCapacity), 3)
        #
        # return self.get_spread_out_target(type, find_list, max_builders, True)
        return self.target_mind.get_new_target(self.creep,
                                               type,
                                               max_hits)

    def get_new_construction_target(self):
        return self.target_mind.get_new_target(self.creep,
                                               hivemind.target_construction)

    def execute_repair_target(self, target, max_hits, type):
        # if target.hits >= target.hitsMax or target.hits >= max_hits + 2000:
        #     self.target_mind.untarget(self.creep, type)
        #     del self.memory.last_big_repair_max_hits
        #     return True
        # Will automatically untarget when done spending all energy.
        result = self.creep.repair(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
        elif result == ERR_NOT_IN_RANGE:
            self.move_to(target)
        elif result == ERR_INVALID_TARGET:
            self.target_mind.untarget(self.creep, type)
            del self.memory.last_big_repair_max_hits
            return True
        return False

    def execute_construction_target(self, target):
        result = self.creep.build(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
        elif result == ERR_NOT_IN_RANGE:
            self.move_to(target)
        elif result == ERR_INVALID_TARGET:
            self.target_mind.untarget(self.creep, hivemind.target_construction)
            return True
