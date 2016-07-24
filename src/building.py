import hivemind
import upgrading

from base import *

__pragma__('noalias', 'name')


class Builder(upgrading.Upgrader):
    def run(self):
        if self.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.harvesting = False
            self.target_mind.untarget_all(self.creep)
        elif not self.harvesting and self.creep.carry.energy <= 0:
            self.harvesting = True

        if self.harvesting:
            self.harvest_energy()
        else:
            target = self.target_mind.get_existing_target(self.creep,
                                                          hivemind.target_repair)
            if target:
                self.execute_repair_target(target, 350000, hivemind.target_repair)
            target = self.target_mind.get_existing_target(self.creep,
                                                          hivemind.target_construction)
            if target:
                self.execute_construction_target(target)
                return

            target = self.get_new_repair_target(350000, hivemind.target_repair)
            if target:
                self.target_mind.untarget(self.creep, hivemind.target_big_repair)
                self.execute_repair_target(target, 350000, hivemind.target_repair)
                return

            target = self.get_new_construction_target()
            if target:
                self.target_mind.untarget(self.creep, hivemind.target_big_repair)
                self.execute_construction_target(target)
                return

            for max_energy in range(400000, 600000, 50000):
                target = self.get_new_repair_target(max_energy,
                                                    hivemind.target_big_repair)
                if target:
                    self.execute_repair_target(target, max_energy,
                                               hivemind.target_big_repair)
                    return

            print("[{}] Couldn't find any building targets.".format(self.name))
            upgrading.Upgrader.run(self)

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
        if target.hits >= target.hitsMax or target.hits >= max_hits + 2000:
            self.target_mind.untarget(self.creep, type)
            return

        result = self.creep.repair(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
        elif result == ERR_NOT_IN_RANGE:
            self.move_to(target)
        else:
            print("[{}] Unknown result from creep.repair({}): {}".format(
                self.name, target, result
            ))
            if result == ERR_INVALID_TARGET:
                self.target_mind.untarget(self.creep, type)

    def execute_construction_target(self, target):
        result = self.creep.build(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
        elif result == ERR_NOT_IN_RANGE:
            self.move_to(target)
        else:
            print("[{}] Unknown result from creep.build({}): {}".format(
                self.name, target, result
            ))
            if result == ERR_INVALID_TARGET:
                self.target_mind.untarget(self.creep, hivemind.target_construction)
