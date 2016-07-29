import profiling
from role_base import RoleBase
from screeps_constants import *

__pragma__('noalias', 'name')


class Upgrader(RoleBase):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            return self.harvest_energy()
        elif not self.creep.room.controller.my:
            self.go_to_depot()
            self.report("U. D!!")
        else:
            target = self.creep.room.controller
            if not self.creep.pos.inRangeTo(target.pos, 3):
                self.move_to(target)
                return False

            result = self.creep.upgradeController(self.creep.room.controller)
            if result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                self.report("U. NER.")
            elif result == OK:
                self.move_to(self.creep.room.controller, True)
                self.report("U.")
            else:
                print("[{}] Unknown result from upgradeController({}): {}".format(
                    self.name, self.creep.room.controller, result
                ))

                if self.creep.carry.energy < self.creep.carryCapacity:
                    self.memory.harvesting = True
                else:
                    self.go_to_depot()
                    self.report("U. ???")

        return False


profiling.profile_class(Upgrader, profiling.ROLE_BASE_IGNORE)
