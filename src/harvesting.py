import building
import hivemind
import profiling
from base import *

__pragma__('noalias', 'name')


class Harvester(building.Builder):
    def run(self):
        if _.size(Game.creeps) > 16:
            # TODO: currently fixed 16 cap
            # we have enough creeps right now, upgrade instead!
            # just do this so that someone reading memory can tell
            self.memory.running_as_builder = True
            self.target_mind.untarget(self.creep, hivemind.target_harvester_deposit)
            building.Builder.run(self)
            return
        else:
            del self.memory.running_as_builder
            del self.memory.running_as_upgrader
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.finished_energy_harvest()
        elif not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget(self.creep, hivemind.target_harvester_deposit)

        if self.memory.harvesting:
            return self.harvest_energy()
        else:
            target = self.target_mind.get_new_target(self.creep, hivemind.target_harvester_deposit)
            if target:
                if target.energy >= target.energyCapacity:
                    self.target_mind.untarget(self.creep, hivemind.target_harvester_deposit)
                    return True
                else:
                    if not self.creep.pos.isNearTo(target.pos):
                        self.move_to(target)
                        self.report("H. Find.")
                        return False

                    result = self.creep.transfer(target, RESOURCE_ENERGY)

                    if result == OK:
                        self.report("H. Fill.")
                    elif result == ERR_FULL:
                        self.target_mind.untarget(self.creep, hivemind.target_harvester_deposit)
                        return True
                    else:
                        print("[{}] Unknown result from creep.transfer({}): {}".format(
                            self.name, target, result
                        ))
                        self.target_mind.untarget(self.creep, hivemind.target_harvester_deposit)
                        return True
            else:
                self.memory.running_as_builder = True
                return building.Builder.run(self)
        return False


profiling.profile_class(Harvester, profiling.ROLE_BASE_IGNORE)
