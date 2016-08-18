from constants import role_mineral_hauler, role_recycling, role_mineral_miner
from role_base import RoleBase
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


# TODO: awesome speech for this class
class MineralMiner(RoleBase):
    def run(self):
        minerals = self.home.find(FIND_MINERALS)

        if len(minerals) != 1:
            self.log("MineralMiner's home has an incomprehensible number of minerals: {}! To the depot it is."
                     .format(len(minerals)))
            self.go_to_depot()
            return False

        mineral = minerals[0]
        extractor = _.find(self.home.find_at(FIND_MY_STRUCTURES, mineral.pos), {'structureType': STRUCTURE_EXTRACTOR})
        if not extractor:
            self.log("MineralMiner's mineral at {} does not have an extractor. D:".format(mineral.pos))
            self.go_to_depot()
            return False

        if not self.creep.pos.isNearTo(mineral.pos):
            self.move_to(mineral)
            return False

        if self.creep.carryCapacity - _.sum(self.creep.carry) > 1 * self.creep.getActiveBodyparts(WORK):
            # let's be sure not to drop any on the ground

            result = self.creep.harvest(mineral)
            if result == ERR_NOT_ENOUGH_RESOURCES:
                self.log("Mineral depleted, going to recycle now!")
                self.memory.role = role_recycling
                self.memory.last_role = role_mineral_miner
            elif result != OK:
                self.log("Unknown result from creep.harvest({}): {}".format(mineral, result))

        haulers = _.sortBy(_.filter(self.room.find_in_range(FIND_MY_CREEPS, 1, self.creep.pos),
                                    {"memory": {"role": role_mineral_hauler}}), lambda c: -_.sum(c.carry))

        for mtype in Object.keys(self.creep.carry):
            if self.creep.carry[mtype] > 0:
                self.creep.transfer(haulers[0], mtype)
                break
        else:
            self.log("Not transfering from miner to hauler: no resources")


ideal_terminal_counts = {
    RESOURCE_ENERGY: 50000,
    # TODO: dynamically set this in room mind
}

class MineralHauler(RoleBase):
    def run(self):
        if self.memory.miner_harvesting is undefined:
            self.memory.miner_harvesting = True
        if self.memory.harvesting and _.sum(self.creep.carry) >= self.creep.carryCapacity \
                or (_.sum(self.creep.carry) > 0 and self.creep.ticksToLive < 100):
            self.memory.harvesting = False
        if not self.memory.harvesting and _.sum(self.creep.carry) <= 0:
            self.memory.harvesting = True
            # Every other trip should be storage -> terminal
            self.memory.miner_harvesting = not self.memory.miner_harvesting

        if self.memory.harvesting:
            if self.memory.miner_harvesting:
                if self.creep.ticksToLive < 100:
                    self.recycle_me()
                    return False
                minerals = self.home.find(FIND_MINERALS)

                if len(minerals) != 1:
                    self.log("MineralHauler's home has an incomprehensible number of minerals: {}! To the depot it is."
                             .format(len(minerals)))
                    self.go_to_depot()
                    return False

                mineral = minerals[0]
                extractor = _.find(self.home.find_at(FIND_MY_STRUCTURES, mineral.pos),
                                   {'structureType': STRUCTURE_EXTRACTOR})
                if not extractor:
                    self.log("MineralHauler's mineral at {} does not have an extractor. D:".format(mineral.pos))
                    self.go_to_depot()
                    return False

                # TODO: make this into a TargetMind target so we can have multiple mineral miners per mineral
                miner = _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, mineral.pos))
                if not miner:
                    # Let's spend some time filling up the terminal with energy, shall we?
                    self.memory.harvesting = False
                    return True

                if not self.creep.pos.isNearTo(miner.pos):
                    self.move_to(miner)  # Miner does the work of giving us the minerals, no need to pick any up.
            else:
                terminal = self.home.room.terminal
                # TODO: this should be a constant
                if not terminal or terminal.store.energy > self.home.get_target_terminal_energy():
                    # setting this to true again will re-toggle remote miner harvesting!
                    self.memory.harvesting = False
                    return True
                storage = self.home.room.storage
                if not self.creep.pos.isNearTo(storage):
                    self.move_to(storage)
                    return False
                result = self.creep.withdraw(storage, RESOURCE_ENERGY)
                if result != OK:
                    self.log("Unknown result from mineral-hauler.withdraw({}, {}): {}".format(
                        storage, RESOURCE_ENERGY, result))
        else:
            terminal = self.home.room.terminal
            storage = self.home.room.storage
            for mtype in Object.keys(self.creep.carry):
                if self.creep.carry[mtype] > 0:
                    resource = mtype
                    break
            else:
                self.log("MineralHauler failed to find resource to deposit, despite having a full carry...")
                return False

            if resource == RESOURCE_ENERGY:
                ideal =  self.home.get_target_terminal_energy()
            elif resource in ideal_terminal_counts:
                ideal = ideal_terminal_counts[resource]
            else:
                ideal = 10000
            if terminal and (terminal.store[resource] or 0) < ideal:
                target = terminal
            else:
                target = storage

            if not self.creep.pos.isNearTo(target):
                self.move_to(target)
                return False

            result = self.creep.transfer(target, resource)
            if result != OK:
                self.log("Unknown result from MineralHauler.transfer({}, {})".format(target, mtype))

        return False
