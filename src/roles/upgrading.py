import speach
from role_base import RoleBase
from utils.screeps_constants import *

__pragma__('noalias', 'name')


class Upgrader(RoleBase):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            self.memory.stationary = False
            return self.harvest_energy()
        elif not self.creep.room.controller.my:
            self.memory.stationary = False
            self.go_to_depot()
            self.report(speach.upgrading_controller_not_owned)
        else:
            target = self.creep.room.controller
            if not self.creep.pos.inRangeTo(target.pos, 3):
                self.move_to(target)
                self.memory.stationary = False
                self.report(speach.upgrading_moving_to_controller)
                return False

            self.memory.stationary = True
            result = self.creep.upgradeController(self.creep.room.controller)
            if result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == OK:
                self.move_to(self.creep.room.controller, True)
                self.report(speach.upgrading_ok)
            else:
                print("[{}] Unknown result from upgradeController({}): {}".format(
                    self.name, self.creep.room.controller, result
                ))

                if self.creep.carry.energy < self.creep.carryCapacity:
                    self.memory.harvesting = True
                else:
                    self.go_to_depot()
                    self.report(speach.upgrading_unknown_result)

        return False
