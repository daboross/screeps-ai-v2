from constants import role_mineral_hauler, role_recycling, role_mineral_miner
from role_base import RoleBase
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


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

        if extractor.cooldown <= 0 and self.creep.carryCapacity - _.sum(self.creep.carry) \
                >= 1 * self.creep.getActiveBodyparts(WORK):
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

        resource = _.findKey(self.creep.carry, lambda amount: amount > 0)
        if resource:
            self.creep.transfer(transfer_target, resource)

    def _calculate_time_to_replace(self):
        minerals = self.home.find(FIND_MINERALS)

        if not len(minerals):
            return -1
        mineral_pos = minerals[0].pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        time = movement.path_distance(spawn_pos, mineral_pos, True) * 2 + _.size(self.creep.body) * 3 + 15
        return time


_STORAGE_PICKUP = "storage_pickup"
_STORAGE_DROPOFF = "storage_dropoff"
_TERMINAL_PICKUP = "terminal_pickup"
_TERMINAL_DROPOFF = "terminal_dropoff"
_MINER_HARVEST = "miner_harvesting"
_DEAD = "recycling"
_DEPOT = "depot"


class MineralHauler(RoleBase):
    def should_pickup(self, resource_type=None):
        return True

    def determine_next_state(self):
        mind = self.home.minerals
        now_held = _.sum(self.creep.carry)
        if now_held < self.creep.carryCapacity:
            mineral = self.home.find(FIND_MINERALS)[0]
            if mineral:
                containers = _.filter(self.home.find_in_range(FIND_STRUCTURES, 2, mineral.pos),
                                      {'structureType': STRUCTURE_CONTAINER})
                if _.sum(containers, lambda s: _.sum(s.store)) > 1000 or \
                        (not len(containers) and _.find(self.home.find_in_range(FIND_MY_CREEPS, 1, mineral.pos),
                                                        lambda c: c.memory.role == role_mineral_miner)):
                    sending_resource_to_storage = (mind.terminal.store[mineral.resourceType] or 0) >= \
                                                  (mind.get_all_terminal_targets()[mineral.resourceType] or 0)
                    # If we have a resource in our carry which isn't headed to the same place as the miner's resource,
                    # let's not pick up that miner's resource until we've dealt with what we're already carrying.
                    for resource in Object.keys(self.creep.carry):
                        if resource != mineral.resourceType:
                            if sending_resource_to_storage:
                                if (mind.terminal.store[resource] or 0) < mind.get_all_terminal_targets()[resource]:
                                    break
                            else:
                                if mind.terminal.store[resource] > (mind.get_all_terminal_targets()[resource] or 0):
                                    break
                    else:
                        return _MINER_HARVEST

        terminal_can_handle_more = _.sum(mind.terminal.store) <= mind.terminal.storeCapacity - self.creep.carryCapacity

        if not terminal_can_handle_more:
            if now_held:
                return _STORAGE_DROPOFF
            elif len(mind.removing_from_terminal()):
                return _TERMINAL_PICKUP
            else:
                return _DEPOT

        for resource in Object.keys(self.creep.carry):
            if self.creep.carry[resource] > 0 and \
                            (mind.terminal.store[resource] or 0) < mind.get_all_terminal_targets()[resource]:
                return _TERMINAL_DROPOFF

        if now_held:
            # We have a store which has no minerals needed by the terminal
            return _STORAGE_DROPOFF
        elif self.creep.ticksToLive < 100:
            return _DEAD
        elif len(mind.removing_from_terminal()) and self.pos.isNearTo(mind.terminal):
            return _TERMINAL_PICKUP
        # elif self.pos.isNearTo(mind.storage) and len(mind.adding_to_terminal()):
        #     return _STORAGE_PICKUP
        elif len(mind.adding_to_terminal()):
            return _STORAGE_PICKUP
        elif len(mind.removing_from_terminal()):
            return _TERMINAL_PICKUP
        elif self.home.role_count(role_mineral_miner):
            return _MINER_HARVEST
        else:
            return _DEPOT

    def run(self):
        mind = self.home.minerals
        if mind.has_no_terminal_or_storage():
            self.memory.role = role_recycling
            self.memory.last_role = role_mineral_hauler
            return
        mind.note_mineral_hauler(self.name)
        if 'state' not in self.memory:
            self.memory.state = self.determine_next_state()
            if self.memory.last_state == self.memory.state:
                self.log("State loop on state {}!".format(self.memory.state))
                del self.memory.last_state
                return False
            else:
                self.memory.last_state = self.memory.state

        state = self.memory.state
        if state == _MINER_HARVEST:
            return self.run_miner_harvesting()
        elif state == _STORAGE_PICKUP:
            return self.run_storage_pickup()
        elif state == _STORAGE_DROPOFF:
            return self.run_storage_dropoff()
        elif state == _TERMINAL_PICKUP:
            return self.run_terminal_pickup()
        elif state == _TERMINAL_DROPOFF:
            return self.run_terminal_deposit()
        elif state == _DEAD:
            self.memory.role = role_recycling
            self.memory.last_role = role_mineral_hauler
        elif state == _DEPOT:
            self.go_to_depot()
            if Game.time % 10 == 0:
                del self.memory.state
                del self.memory.last_state
        else:
            self.log("ERROR: mineral-hauler in unknown state '{}'".format(self.memory.state))
            del self.memory.state
        return False

    def run_miner_harvesting(self):
        if _.sum(self.creep.carry) >= self.creep.carryCapacity:
            del self.memory.state
            return True
        if self.creep.ticksToLive < 50:
            del self.memory.state
            return True
        mind = self.home.minerals
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

        containers = _.filter(_.filter(self.home.find_in_range(FIND_STRUCTURES, 2, mineral.pos),
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
        miner = _.find(self.home.find_in_range(FIND_MY_CREEPS, 1, mineral.pos),
                       lambda c: c.memory.role == role_mineral_miner)
        if not miner:
            if mind.get_target_mineral_miner_count():
                self.go_to_depot()
                return False
            else:
                del self.memory.state
                return True

        if not self.creep.pos.isNearTo(miner.pos):
            self.move_to(miner)  # Miner does the work of giving us the minerals, no need to pick any up.

    def run_storage_pickup(self):
        mind = self.home.minerals
        now_carrying = _.sum(self.creep.carry)
        if now_carrying >= self.creep.carryCapacity:
            del self.memory.state
            return True
        if not self.creep.pos.isNearTo(mind.storage):
            self.move_to(mind.storage)
            return False
        for resource, needed_in_terminal in mind.adding_to_terminal():
            to_withdraw = min(self.creep.carryCapacity - now_carrying,
                              needed_in_terminal - (self.creep.carry[resource] or 0),
                              mind.storage.store[resource] or 0)
            if to_withdraw:
                result = self.creep.withdraw(mind.storage, resource, to_withdraw)
                if result != OK:
                    self.log("Unknown result from mineral-hauler.withdraw({}, {}, {}): {}".format(
                        mind.storage, resource, to_withdraw, result))
                break
        else:
            del self.memory.state
            return True

    def run_storage_dropoff(self):
        mind = self.home.minerals
        now_carrying = _.sum(self.creep.carry)
        if now_carrying <= 0:
            del self.memory.state
            return True
        if not self.creep.pos.isNearTo(mind.storage):
            self.move_to(mind.storage)
            return False
        resource = _.findKey(self.creep.carry, lambda amount: amount > 0)
        result = self.creep.transfer(mind.storage, resource)
        if result != OK:
            self.log("Unknown result from mineral-hauler.transfer({}, {}): {}".format(mind.storage, resource, result))

    def run_terminal_pickup(self):
        mind = self.home.minerals
        now_carrying = _.sum(self.creep.carry)
        if now_carrying >= self.creep.carryCapacity:
            del self.memory.state
            return True
        if not self.creep.pos.isNearTo(mind.terminal):
            self.move_to(mind.terminal)
            return False
        for resource, remove_from_terminal in mind.removing_from_terminal():
            if resource == RESOURCE_ENERGY and len(mind.removing_from_terminal()) > 1:
                continue
            to_withdraw = min(self.creep.carryCapacity - now_carrying,
                              remove_from_terminal)
            if to_withdraw:
                result = self.creep.withdraw(mind.terminal, resource, to_withdraw)
                if result != OK:
                    self.log("Unknown result from mineral-hauler.withdraw({}, {}, {}): {}".format(
                        mind.terminal, resource, to_withdraw, result))
                break
        else:
            del self.memory.state
            return True

    def run_terminal_deposit(self):
        mind = self.home.minerals
        now_carrying = _.sum(self.creep.carry)
        if now_carrying <= 0:
            del self.memory.state
            return True
        if not self.creep.pos.isNearTo(mind.terminal):
            self.move_to(mind.terminal)
            return False

        resource = _.findKey(self.creep.carry,
                             lambda amount, resource:
                             amount > 0 and (mind.terminal.store[resource] or 0)
                                            < mind.get_all_terminal_targets()[resource])
        if not resource:
            del self.memory.state
            return False
        amount = min(self.creep.carry[resource], mind.get_all_terminal_targets()[resource]
                     - (mind.terminal.store[resource] or 0))
        result = self.creep.transfer(mind.terminal, resource, amount)
        if result == ERR_FULL:
            del self.memory.state
            return False
        elif result != OK:
            self.log("Unknown result from mineral-hauler.transfer({}, {}, {}): {}".format(
                mind.terminal, resource, amount, result))

    def _calculate_time_to_replace(self):
        return _.size(self.creep.body) * 3  # Don't live replace mineral haulers
