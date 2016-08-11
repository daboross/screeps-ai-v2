import speech
from role_base import RoleBase
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class Upgrader(RoleBase):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            if self.home.full_storage_use:
                if self.home.upgrading_paused and self.creep.room.controller.ticksToDowngrade >= 5000:
                    self.go_to_depot()
                    return False
            self.memory.stationary = False
            return self.harvest_energy()
        elif not self.creep.room.controller.my:
            self.memory.stationary = False
            self.go_to_depot()
            self.report(speech.upgrading_controller_not_owned)
        else:
            target = self.creep.room.controller
            if not self.creep.pos.inRangeTo(target.pos, 3):
                self.pick_up_available_energy()
                self.move_to(target)
                self.memory.stationary = False
                self.report(speech.upgrading_moving_to_controller)
                return False

            self.memory.stationary = True
            result = self.creep.upgradeController(self.creep.room.controller)
            if result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == OK:
                self.pick_up_available_energy()
                self.move_to(self.creep.room.controller, True)
                self.report(speech.upgrading_ok)
            else:
                self.log("Unknown result from upgradeController({}): {}", self.creep.room.controller, result)

                if self.creep.carry.energy < self.creep.carryCapacity:
                    self.memory.harvesting = True
                else:
                    self.go_to_depot()
                    self.report(speech.upgrading_unknown_result)

        return False
