import speach
from constants import target_harvester_deposit
from roles import building
from utils.screeps_constants import *

__pragma__('noalias', 'name')


class SpawnFill(building.Builder):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget(self.creep, target_harvester_deposit)

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_new_target(self.creep, target_harvester_deposit)
            if target:
                if target.energy >= target.energyCapacity:
                    self.target_mind.untarget(self.creep, target_harvester_deposit)
                    return True
                else:
                    self.pick_up_available_energy()
                    if not self.creep.pos.isNearTo(target.pos):
                        self.move_to(target)
                        self.report(speach.spawn_fill_moving_to_target)
                        return False

                    result = self.creep.transfer(target, RESOURCE_ENERGY)

                    if result == OK:
                        self.report(speach.spawn_fill_ok)
                    elif result == ERR_FULL:
                        self.target_mind.untarget(self.creep, target_harvester_deposit)
                        return True
                    else:
                        print("[{}] Unknown result from creep.transfer({}): {}".format(
                            self.name, target, result
                        ))
                        self.target_mind.untarget(self.creep, target_harvester_deposit)
                        self.report(speach.spawn_fill_unknown_result)
                        return True
            else:
                self.memory.running_as_builder = True
                return building.Builder.run(self)
        return False
