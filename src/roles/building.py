import random

import speech
from constants import target_repair, target_construction, target_big_repair, role_recycling, recycle_time, role_builder
from roles import upgrading
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class Builder(upgrading.Upgrader):
    def any_building_targets(self):
        if self.target_mind.get_existing_target(self, target_repair):
            return True
        if self.target_mind.get_existing_target(self, target_construction):
            return True
        if self.target_mind.get_existing_target(self, target_big_repair):
            return True
        if self.target_mind.get_new_target(self, target_repair, min(350000, self.home.min_sane_wall_hits)):
            self.target_mind.untarget(self, target_repair)
            return True
        if self.target_mind.get_new_target(self, target_construction):
            self.target_mind.untarget(self, target_construction)
            return True
        if self.target_mind.get_new_target(self, target_big_repair, self.home.max_sane_wall_hits):
            self.target_mind.untarget(self, target_big_repair)
            return True
        return False

    def run(self):
        del self.memory.emptying
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_builder
            return False
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self)
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            # don't do this if we don't have targets
            self.target_mind.untarget_all(self)
            self.memory.harvesting = True

        if not self.any_building_targets():
            if not self.home.upgrading_paused():
                return upgrading.Upgrader.run(self)
            else:
                self.memory.emptying = True  # flag for spawn fillers to not refill me.
                if not self.empty_to_storage():
                    self.go_to_depot()
                return False

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_existing_target(self, target_repair)
            if target:
                return self.execute_repair_target(target, min(350000, self.home.min_sane_wall_hits), target_repair)
            target = self.target_mind.get_existing_target(self, target_construction)
            if target:
                return self.execute_construction_target(target)

            target = self.get_new_repair_target(min(350000, self.home.min_sane_wall_hits), target_repair)
            if target:
                self.target_mind.untarget(self, target_big_repair)
                del self.memory.last_big_repair_max_hits
                return self.execute_repair_target(target, min(350000, self.home.min_sane_wall_hits), target_repair)

            target = self.get_new_construction_target()
            if target:
                self.target_mind.untarget(self, target_big_repair)
                del self.memory.last_big_repair_max_hits
                return self.execute_construction_target(target)

            if self.memory.last_big_repair_max_hits:
                max_hits = self.memory.last_big_repair_max_hits
                target = self.get_new_repair_target(max_hits, target_big_repair)
                if target:
                    return self.execute_repair_target(target, max_hits, target_big_repair)
            for max_hits in range(min(400000, self.home.min_sane_wall_hits), self.home.max_sane_wall_hits, 50000):
                target = self.get_new_repair_target(max_hits, target_big_repair)
                if target:
                    self.memory.last_big_repair_max_hits = max_hits
                    return self.execute_repair_target(target, max_hits, target_big_repair)
            target = self.get_new_repair_target(self.home.max_sane_wall_hits, target_big_repair)
            if target:
                self.memory.last_big_repair_max_hits = self.home.max_sane_wall_hits
                return self.execute_repair_target(target, self.home.max_sane_wall_hits, target_big_repair)

            # TODO: duplicated above
            if not self.home.upgrading_paused():
                return upgrading.Upgrader.run(self)
            else:
                self.memory.emptying = True  # flag for spawn fillers to not refill me.
                if not self.empty_to_storage():
                    self.go_to_depot()
                return False

    def get_new_repair_target(self, max_hits, ttype):
        return self.target_mind.get_new_target(self, ttype, max_hits)

    def get_new_construction_target(self):
        return self.target_mind.get_new_target(self, target_construction)

    def execute_repair_target(self, target, max_hits, ttype):
        self.report(speech.building_repair_target, target.structureType)
        if target.hits >= target.hitsMax or target.hits >= max_hits * 2:
            self.home.building.refresh_repair_targets()
            self.target_mind.untarget(self, ttype)
            del self.memory.last_big_repair_max_hits
            return True
        if not self.creep.pos.inRangeTo(target.pos, 3):
            self.move_to(target)
            return False

        self.memory.stationary = True
        result = self.creep.repair(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
            else:
                # TODO: make this also not move away from the target, and only move to a free space.
                self.creep.move(random.randint(1, 9))
        elif result == ERR_INVALID_TARGET:
            self.target_mind.untarget(self, ttype)
            del self.memory.last_big_repair_max_hits
            self.home.building.refresh_repair_targets()
            return True
        else:
            self.log("Unknown result from creep.repair({}): {}", target, result)

        return False

    def execute_construction_target(self, target):
        if not target.structureType and target.color:
            # it's a flag! ConstructionMind should have made a new construction site when adding this to the list of
            # available targets. Let's ask for a new target, so as to allow it to update the targets list.
            # this seems like an OK way to do this!
            self.home.building.refresh_building_targets()
            self.target_mind.untarget(self, target_construction)
            self.move_to(target)
            return True
        self.report(speech.building_build_target, target.structureType)
        if not self.creep.pos.inRangeTo(target.pos, 3):
            self.move_to(target)
            return False

        self.memory.stationary = True
        result = self.creep.build(target)
        if result == OK:
            if self.is_next_block_clear(target):
                self.move_to(target, True)
            else:
                # TODO: make this also not move away from the target, and only move to a free space.
                self.creep.move(random.randint(1, 9))
        elif result == ERR_INVALID_TARGET:
            self.target_mind.untarget(self, target_construction)
        else:
            self.log("Unknown result from creep.build({}): {}", target, result)
            return True

        return False


profiling.profile_whitelist(Builder, [
    "run",
    "get_new_repair_target",
    "get_new_construction_target",
    "execute_repair_target",
    "execute_construction_target",
])
