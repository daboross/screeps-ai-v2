import speech
from constants import recycle_time, role_recycling, role_upgrader
from role_base import RoleBase
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class Upgrader(RoleBase):
    def run(self):
        del self.memory.emptying
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_upgrader
            return False
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.finished_energy_harvest()

        if not self.home.room.controller.my or (self.home.upgrading_paused()
                                                 and self.creep.room.controller.ticksToDowngrade >= 5000):
            self.report(speech.upgrading_upgrading_paused)
            self.memory.emptying = True  # flag for spawn fillers to not refill me.
            if not self.empty_to_storage():
                self.go_to_depot()
            return False

        if self.memory.harvesting:
            self.memory.stationary = False
            if self.harvest_energy():
                return True

        target = self.home.room.controller
        if not self.creep.pos.inRangeTo(target.pos, 3):
            if self.memory.harvesting:
                # Let's upgrade if we're in range while we're harvesting, but otherwise we can just harvest.
                return False
            self.move_to(target)
            self.memory.stationary = False
            self.report(speech.upgrading_moving_to_controller)
            return False

        self.memory.stationary = True
        result = self.creep.upgradeController(target)
        if result == ERR_NOT_ENOUGH_RESOURCES:
            if not self.memory.harvesting:
                self.memory.harvesting = True
                return True
        elif result == OK:
            # If we're a "full upgrader", with carry capacity just 50, let's keep close to the link we're gathering
            # from. Otherwise, move towards the controller to leave room for other upgraders

            if self.creep.carryCapacity > 100:
                if not self.memory.harvesting and self.is_next_block_clear(target):
                    self.move_to(target, True)
            else:
                if not self.memory.harvesting and self.creep.carry.energy < self.creep.carryCapacity:
                    self.harvest_energy()
            self.report(speech.upgrading_ok)
        else:
            self.log("Unknown result from upgradeController({}): {}", self.creep.room.controller, result)

            if self.creep.carry.energy < self.creep.carryCapacity:
                self.memory.harvesting = True
            else:
                self.go_to_depot()
                self.report(speech.upgrading_unknown_result)

        return False


profiling.profile_whitelist(Upgrader, ["run"])
