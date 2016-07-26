from base import *
from role_base import RoleBase

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
            self.creep.say("U. D!!")
        else:
            result = self.creep.upgradeController(self.creep.room.controller)
            if result == ERR_NOT_IN_RANGE:
                self.move_to(self.creep.room.controller)
                self.creep.say("U. F. C.")
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.harvesting = True
                self.creep.say("U. NER.")
            elif result == OK:
                self.move_to(self.creep.room.controller, True)
                self.creep.say("U.")
            else:
                print("[{}] Unknown result from upgradeController({}): {}".format(
                    self.name, self.creep.room.controller, result
                ))

                if self.creep.carry.energy < self.creep.carryCapacity:
                    self.harvesting = True
                else:
                    self.go_to_depot()
                self.creep.say("U. ???")

        return False
