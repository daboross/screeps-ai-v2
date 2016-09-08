from constants import role_mineral_hauler, role_recycling, role_mineral_miner, recycle_time
from role_base import RoleBase
from utilities import movement
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

        if self.creep.carryCapacity - _.sum(self.creep.carry) >= 1 * self.creep.getActiveBodyparts(WORK):
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

        if len(haulers):
            transfer_target = haulers[0]
        else:
            containers = _.filter(self.room.find_in_range(FIND_STRUCTURES, 1, mineral.pos),
                                  lambda c: c.structureType == STRUCTURE_CONTAINER and _.sum(c.store) < c.storeCapacity)

            if len(containers):
                transfer_target = containers[0]
                if not self.creep.pos.isNearTo(transfer_target):
                    self.move_to(transfer_target)
                    return
            else:
                if not _.find(self.room.find_in_range(FIND_STRUCTURES, 1, mineral.pos),
                              {'structureType': STRUCTURE_CONTAINER}) \
                        and not _.find(self.room.find_in_range(FIND_MY_CONSTRUCTION_SITES, 1, mineral.pos),
                                       {"structureType": STRUCTURE_CONTAINER}):
                    self.creep.pos.createConstructionSite(STRUCTURE_CONTAINER)
                return

        for mtype in Object.keys(self.creep.carry):
            if self.creep.carry[mtype] > 0:
                self.creep.transfer(transfer_target, mtype)
                break

    def _calculate_time_to_replace(self):
        minerals = self.home.find(FIND_MINERALS)

        if not len(minerals):
            return -1
        mineral_pos = minerals[0].pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        time = movement.path_distance(spawn_pos, mineral_pos, True) * 2 + _.size(self.creep.body) * 3 + 15
        return time


ideal_terminal_counts = {
    RESOURCE_ENERGY: 50000,
    # TODO: dynamically set this in room mind
}


class MineralHauler(RoleBase):
    def should_pickup(self, resource_type=None):
        return True

    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_mineral_hauler
        if not self.memory.state:
            self.memory.state = "miner_harvesting"
        state = self.memory.state

        if state == "miner_harvesting" \
                and _.sum(self.creep.carry) >= self.creep.carryCapacity \
                or (_.sum(self.creep.carry) > 0 and self.creep.ticksToLive < 100):
            if self.home.get_emptying_terminal():
                self.memory.state = state = "empty_terminal_deposit"
            else:
                self.memory.state = state = "terminal_deposit_minerals"

        if state == state == "storage_harvest_energy" \
                and _.sum(self.creep.carry) >= self.creep.carryCapacity \
                or (_.sum(self.creep.carry) > 0 and self.creep.ticksToLive < 100):
            self.memory.state = state = "terminal_deposit_energy"

        if state == "terminal_deposit_minerals" and _.sum(self.creep.carry) <= 0:
            mineral = self.home.find(FIND_MINERALS)[0]
            if mineral and _.sum(self.room.find_in_range(FIND_STRUCTURES, 2, mineral.pos),
                                 lambda s: _.sum(s.store) if s.structureType == STRUCTURE_CONTAINER else 0) > 1000:
                self.memory.state = state = "miner_harvesting"
            else:
                self.memory.state = state = "storage_harvest_energy"

        if state == "terminal_deposit_energy" and _.sum(self.creep.carry) <= 0:
            if self.home.role_count(role_mineral_miner):
                self.memory.state = state = "miner_harvesting"
            else:
                self.memory.state = state = "storage_harvest_energy"

        if state == "miner_harvesting":
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

            containers = _.filter(_.filter(self.room.find_in_range(FIND_STRUCTURES, 2, mineral.pos),
                                           lambda s: s.structureType == STRUCTURE_CONTAINER and _.sum(s.store) > 0),
                                  lambda s: _.sum(s.store))

            if len(containers):
                if self.creep.pos.isNearTo(containers[0].pos):
                    for mtype in Object.keys(containers[0].store):
                        if containers[0].store[mtype] > 0:
                            self.creep.withdraw(containers[0], mtype)
                            break
                else:
                    self.move_to(containers[0].pos)

                return False

            # TODO: make this into a TargetMind target so we can have multiple mineral miners per mineral
            miner = _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, mineral.pos))
            if not miner:
                if self.home.get_target_mineral_miner_count():
                    self.go_to_depot()
                    return False
                else:
                    # Let's spend some time filling up the terminal with energy, shall we?
                    self.memory.state = "terminal_deposit_minerals"
                    return True

            if not self.creep.pos.isNearTo(miner.pos):
                self.move_to(miner)  # Miner does the work of giving us the minerals, no need to pick any up.
        elif state == "storage_harvest_energy":
            terminal = self.home.room.terminal
            if self.home.get_emptying_terminal():
                self.memory.state = "empty_terminal_withdraw"
                return True
            if not terminal or terminal.store.energy > max(ideal_terminal_counts[RESOURCE_ENERGY],
                                                           self.home.get_target_terminal_energy()):
                if self.home.role_count(role_mineral_miner):
                    self.memory.state = "miner_harvesting"
                    return True
                elif self.home.get_target_mineral_miner_count():
                    self.go_to_depot()
                else:
                    self.recycle_me()
                return False
            storage = self.home.room.storage
            if not self.creep.pos.isNearTo(storage):
                self.move_to(storage)
                return False
            resource = RESOURCE_ENERGY
            if self.home.get_all_filling_terminal() and not self.home.get_target_terminal_energy():
                mineral = _.find(Object.keys(storage.store), lambda r: storage.store[r] and r != RESOURCE_ENERGY)
                if mineral:
                    resource = mineral
            result = self.creep.withdraw(storage, resource)
            if result != OK:
                self.log("Unknown result from mineral-hauler.withdraw({}, {}): {}".format(
                    storage, resource, result))
        elif state == "terminal_deposit_minerals" or state == "terminal_deposit_energy":
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
                ideal = max(ideal_terminal_counts[resource], self.home.get_target_terminal_energy())
            elif resource in ideal_terminal_counts:
                ideal = ideal_terminal_counts[resource]
            else:
                ideal = 10000
            if terminal and ((terminal.store[resource] or 0) < ideal or state == "terminal_deposit_energy"):
                target = terminal
            else:
                target = storage

            if target is terminal and _.sum(terminal.store) >= terminal.storeCapacity:
                self.memory.state = "empty_terminal_deposit"
                return True

            if not self.creep.pos.isNearTo(target):
                self.move_to(target)
                return False

            result = self.creep.transfer(target, resource)
            if result != OK:
                self.log("Unknown result from MineralHauler.transfer({}, {}): {}".format(target, mtype, result))
        elif state == "empty_terminal_deposit":
            if _.sum(self.creep.carry) <= 0:
                if self.home.role_count(role_mineral_miner):
                    self.memory.state = "miner_harvesting"
                else:
                    self.memory.state = "empty_terminal_withdraw"
                return True
            storage = self.home.room.storage

            for mtype in Object.keys(self.creep.carry):
                if self.creep.carry[mtype] > 0:
                    resource = mtype
                    break
            else:
                self.log("No resources to remove to clear up terminal!")
                self.go_to_depot()
                return False

            if not self.creep.pos.isNearTo(storage.pos):
                self.move_to(storage)
                return False

            result = self.creep.transfer(storage, resource)
            if result != OK:
                self.log("Unknown result from mineral-creep.transfer({}, {}): {}".format(storage, resource, result))
        elif state == "empty_terminal_withdraw":
            terminal = self.home.room.terminal
            if (_.sum(terminal.store) < terminal.storeCapacity * 0.75
                or _.sum(terminal.store) == terminal.store.energy <= self.home.get_target_terminal_energy()) \
                    and not self.home.get_emptying_terminal():
                self.memory.state = "terminal_deposit_energy"
                return True
            if _.sum(self.creep.carry) >= self.creep.carryCapacity:
                self.memory.state = "empty_terminal_deposit"
                return True

            for mtype in Object.keys(terminal.store):
                if terminal.store[mtype] > 0:
                    if mtype != RESOURCE_ENERGY or terminal.store[mtype] > self.home.get_target_terminal_energy():
                        resource = mtype
                        break
            else:
                self.log("No resources to remove to clear up terminal!")
                self.go_to_depot()
                return False

            if not self.creep.pos.isNearTo(terminal.pos):
                self.move_to(terminal)
                return False

            result = self.creep.withdraw(terminal, resource)
            if result != OK:
                self.log("Unknown result from creep.withdraw({}, {}): {}".format(terminal, resource, result))

        return False

    def _calculate_time_to_replace(self):
        return _.size(self.creep.body) * 3  # Don't live replace mineral haulers
