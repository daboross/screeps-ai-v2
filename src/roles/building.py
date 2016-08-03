import context
import speach
from constants import target_repair, target_construction, target_big_repair
from roles import upgrading
from utils.screeps_constants import *

__pragma__('noalias', 'name')


class Builder(upgrading.Upgrader):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self.creep)
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_existing_target(self.creep, target_repair)
            if target:
                return self.execute_repair_target(target, target_repair)
            target = self.target_mind.get_existing_target(self.creep, target_construction)
            if target:
                return self.execute_construction_target(target)
            target = self.get_new_repair_target(350000, target_repair)
            if target:
                self.target_mind.untarget(self.creep, target_big_repair)
                del self.memory.last_big_repair_max_hits
                return self.execute_repair_target(target, target_repair)

            target = self.get_new_construction_target()
            if target:
                self.target_mind.untarget(self.creep, target_big_repair)
                del self.memory.last_big_repair_max_hits
                return self.execute_construction_target(target)

            if self.memory.last_big_repair_max_hits:
                max_hits = self.memory.last_big_repair_max_hits
                target = self.get_new_repair_target(max_hits, target_big_repair)
                if target:
                    return self.execute_repair_target(target, target_big_repair)
            for max_hits in range(400000, context.room().max_sane_wall_hits, 50000):
                target = self.get_new_repair_target(max_hits, target_big_repair)
                if target:
                    self.memory.last_big_repair_max_hits = max_hits
                    return self.execute_repair_target(target, target_big_repair)

            return upgrading.Upgrader.run(self)

    def get_new_repair_target(self, max_hits, type):
        return self.target_mind.get_new_target(self.creep, type, max_hits)

    def get_new_construction_target(self):
        return self.target_mind.get_new_target(self.creep, target_construction)

    def execute_repair_target(self, target, type):
        self.report(speach.building_repair_target, target.structureType)
        if target.hits >= target.hitsMax:
            self.target_mind.untarget(self.creep, type)
            del self.memory.last_big_repair_max_hits
            return True
        if not self.creep.pos.inRangeTo(target.pos, 3):
            self.pick_up_available_energy()
            self.move_to(target)
            return False

        self.memory.stationary = True
        result = self.creep.repair(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
        elif result == ERR_INVALID_TARGET:
            self.target_mind.untarget(self.creep, type)
            del self.memory.last_big_repair_max_hits
            return True
        else:
            print("[{}] Unknown result from creep.repair({}): {}".format(self.name, target, result))

        return False

    def execute_construction_target(self, target):
        self.report(speach.building_build_target, target.structureType)
        if not self.creep.pos.inRangeTo(target.pos, 3):
            self.pick_up_available_energy()
            self.move_to(target)
            return False

        self.memory.stationary = True
        result = self.creep.build(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
        elif result == ERR_INVALID_TARGET:
            self.target_mind.untarget(self.creep, target_construction)
        else:
            print("[{}] Unknown result from creep.build({}): {}".format(self.name, target, result))
            return True

        return False
