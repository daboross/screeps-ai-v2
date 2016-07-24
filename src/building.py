import upgrading

from base import *

__pragma__('noalias', 'name')


class Builder(upgrading.Upgrader):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
            self.untarget_spread_out_target("structure_repair")
            self.untarget_spread_out_target("structure_build")
            self.untarget_spread_out_target("structure_repair_big")
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            self.harvest_energy()
        else:
            target = self.get_possible_spread_out_target("structure_repair")
            if target:
                self.execute_repair_target(target, 350000, "structure_repair")
            target = self.get_possible_spread_out_target("structure_build")
            if target:
                self.execute_construction_target(target)
                return

            target = self.get_new_repair_target(350000, "structure_repair")
            if target:
                self.untarget_spread_out_target("structure_repair_big")
                self.execute_repair_target(target, 350000, "structure_repair")
                return

            target = self.get_new_construction_target()
            if target:
                self.untarget_spread_out_target("structure_repair_big")
                self.execute_construction_target(target)
                return

            for max_energy in range(400000, 600000, 50000):
                target = self.get_new_repair_target(max_energy, "structure_repair_big")
                if target:
                    self.execute_repair_target(target, max_energy, "structure_repair_big")
                    return

            upgrading.Upgrader.run(self)

    def get_new_repair_target(self, max_hits, type):
        def find_list():
            return self.creep.room.find(FIND_STRUCTURES, {"filter": lambda structure: (
                structure.my != False and
                structure.hits < structure.hitsMax and
                structure.hits < max_hits
            )})

        def max_builders(structure):
            return min((1 + (structure.hitsMax - min(structure.hits, max_hits))
                        / self.creep.carryCapacity), 3)

        return self.get_spread_out_target(type, find_list, max_builders, True)

    def get_new_construction_target(self):
        def find_list():
            return self.creep.room.find(FIND_CONSTRUCTION_SITES)

        return self.get_spread_out_target("structure_build", find_list, 3, True)

    def execute_repair_target(self, target, max_hits, type):
        if target.hits >= target.hitsMax or target.hits >= max_hits + 2000:
            self.untarget_spread_out_target(type)
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
                self.untarget_spread_out_target(type)

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
                self.untarget_spread_out_target("structure_build")
