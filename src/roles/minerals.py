from constants import role_mineral_hauler, role_recycling, role_mineral_miner
from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


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
        extractor = _.find(self.home.look_at(LOOK_STRUCTURES, mineral.pos), {'structureType': STRUCTURE_EXTRACTOR})
        if not extractor or not extractor.my:
            self.log("MineralMiner's mineral at {} does not have an extractor. D:".format(mineral.pos))
            self.go_to_depot()
            return False

        if not self.creep.pos.isNearTo(mineral.pos):
            self.move_to(mineral)
            return False

        if extractor.cooldown <= 0 and self.creep.carryCapacity - self.carry_sum() \
                >= 1 * self.creep.getActiveBodyparts(WORK):
            # let's be sure not to drop any on the ground

            result = self.creep.harvest(mineral)
            if result == ERR_NOT_ENOUGH_RESOURCES:
                self.log("Mineral depleted, going to recycle now!")
                self.memory.role = role_recycling
                self.memory.last_role = role_mineral_miner
            elif result != OK:
                self.log("Unknown result from creep.harvest({}): {}".format(mineral, result))

        else:
            if 'container' not in self.memory:
                container = _.find(self.room.look_for_in_area_around(LOOK_STRUCTURES, mineral.pos, 2),
                                   lambda c: c.structure.structureType == STRUCTURE_CONTAINER)
                if container:
                    self.memory.container = container.structure.id

            if self.memory.container:
                transfer_target = Game.getObjectById(self.memory.container)
                if not self.creep.pos.isNearTo(transfer_target):
                    pos = None
                    for x in range(mineral.pos.x - 1, mineral.pos.x + 2):
                        for y in range(mineral.pos.y - 1, mineral.pos.y + 2):
                            if abs(x - transfer_target.pos.x) <= 1 and abs(y - transfer_target.pos.y) <= 1 \
                                    and movement.is_block_empty(self.room, x, y):
                                pos = __new__(RoomPosition(x, y, mineral.pos.roomName))
                                break
                        if pos:
                            break
                    if pos:
                        self.basic_move_to(pos)
                        return
            else:
                hauler = _.find(self.room.look_for_in_area_around(LOOK_CREEPS, self.creep.pos, 1),
                                lambda c: c.creep.memory.role == role_mineral_hauler)
                if hauler:
                    transfer_target = hauler[0]
                else:
                    return

            resource = _.findKey(self.creep.carry)
            if resource:
                self.creep.transfer(transfer_target, resource)

    def _calculate_time_to_replace(self):
        minerals = self.home.find(FIND_MINERALS)

        if not len(minerals):
            return -1
        mineral_pos = minerals[0].pos
        spawn_pos = self.home.spawn.pos
        time = self.hive.honey.find_path_length(spawn_pos, mineral_pos) * 2 + _.size(self.creep.body) * 3 + 15
        return time


profiling.profile_whitelist(MineralMiner, ["run"])
_STORAGE_PICKUP = "storage_pickup"
_STORAGE_DROPOFF = "storage_dropoff"
_TERMINAL_PICKUP = "terminal_pickup"
_TERMINAL_DROPOFF = "terminal_dropoff"
_MINER_HARVEST = "miner_harvesting"
_DEAD = "recycling"
_DEPOT = "depot"
_FILL_LABS = "fill_lab"


class MineralHauler(RoleBase):
    def should_pickup(self, resource_type=None):
        return True

    def determine_next_state(self):
        mind = self.home.minerals
        now_held = self.carry_sum()
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
            if self.creep.carry[resource] > 0:
                if (mind.terminal.store[resource] or 0) < mind.get_all_terminal_targets()[resource]:
                    return _TERMINAL_DROPOFF
                elif mind.get_lab_target_mineral() == resource and mind.amount_needed_in_lab1():
                    return _FILL_LABS
                elif mind.get_lab2_target_mineral() == resource and mind.amount_needed_in_lab2():
                    return _FILL_LABS
                elif resource == RESOURCE_ENERGY and mind.energy_needed_in_labs():
                    return _FILL_LABS

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
        elif mind.amount_needed_in_lab1() or mind.amount_needed_in_lab2() or mind.energy_needed_in_labs():
            return _STORAGE_PICKUP
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
        elif state == _FILL_LABS:
            return self.run_lab_drop_off()
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
        if self.carry_sum() >= self.creep.carryCapacity:
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
        extractor = _.find(self.home.look_at(LOOK_STRUCTURES, mineral.pos),
                           {'my': True, 'structureType': STRUCTURE_EXTRACTOR})
        if not extractor:
            self.log("MineralHauler's mineral at {} does not have an extractor. D:".format(mineral.pos))
            self.go_to_depot()
            return False

        if 'containers' not in self.memory:
            self.memory.containers = _(self.home.find_in_range(FIND_STRUCTURES, 2, mineral.pos)) \
                .filter(lambda s: s.structureType == STRUCTURE_CONTAINER).map('id')

        if len(self.memory.containers):
            if len(self.memory.containers) > 1:
                container = _(self.memory.containers).map(Game.getObjectById).max(lambda c: _.sum(c.store))
            else:
                container = Game.getObjectById(self.memory.containers[0])
            container_filled = _.sum(container.store)
            if self.creep.pos.isNearTo(container.pos):
                if container_filled + self.carry_sum() >= self.creep.carryCapacity or not mineral.mineralAmount:
                    resource = _.findKey(container.store)
                    if resource:
                        self.creep.withdraw(container, resource)
                    elif self.carry_sum():
                        del self.memory.state
            else:
                self.move_to(container.pos)

            return False
        else:
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
        now_carrying = self.carry_sum()
        if now_carrying >= self.creep.carryCapacity:
            del self.memory.state
            return True
        if not self.creep.pos.isNearTo(mind.storage):
            self.move_to(mind.storage)
            return False
        for resource, needed_in_terminal in mind.adding_to_terminal() \
                .concat([(RESOURCE_ENERGY, mind.energy_needed_in_labs()),
                         (mind.get_lab_target_mineral(), mind.amount_needed_in_lab1()),
                         (mind.get_lab2_target_mineral(), mind.amount_needed_in_lab2())]):
            to_withdraw = min(self.creep.carryCapacity - now_carrying,
                              needed_in_terminal - (self.creep.carry[resource] or 0),
                              mind.storage.store[resource] or 0)
            if to_withdraw > 0:
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
        now_carrying = self.carry_sum()
        if now_carrying <= 0:
            del self.memory.state
            return True
        if not self.creep.pos.isNearTo(mind.storage):
            self.move_to(mind.storage)
            return False
        resource = _.findKey(self.creep.carry)
        result = self.creep.transfer(mind.storage, resource)
        if result != OK:
            self.log("Unknown result from mineral-hauler.transfer({}, {}): {}".format(mind.storage, resource, result))

    def run_terminal_pickup(self):
        mind = self.home.minerals
        now_carrying = self.carry_sum()
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
        now_carrying = self.carry_sum()
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

    def run_lab_drop_off(self):
        mind = self.home.minerals
        mineral1 = mind.get_lab_target_mineral()
        mineral2 = mind.get_lab2_target_mineral()

        mineral1_holding = self.creep.carry[mineral1]
        mineral2_holding = self.creep.carry[mineral2]
        energy_holding = self.creep.carry[RESOURCE_ENERGY]

        if mind.energy_needed_in_labs() and energy_holding:
            target = _(mind.labs()).filter(lambda l: l.energy < l.energyCapacity and l.mineralAmount) \
                .min(lambda l: movement.chebyshev_distance_room_pos(self.pos, l.pos))
            resource = RESOURCE_ENERGY
        elif mind.amount_needed_in_lab1() and mineral1_holding:
            labs = _(mind.labs()).filter(lambda l: l.mineralAmount < l.mineralCapacity)
            if labs.find(lambda l: l.mineralType == mineral1):
                labs = labs.filter(lambda l: l.mineralType == mineral1)
            else:
                labs = labs.filter(lambda l: not l.mineralAmount)

            target = labs.min(lambda l: movement.chebyshev_distance_room_pos(self.pos, l.pos))
            resource = mineral1
        elif mind.amount_needed_in_lab2() and mineral2_holding:
            labs = _(mind.labs()).filter(lambda l: l.mineralAmount < l.mineralCapacity)
            if labs.find(lambda l: l.mineralType == mineral2):
                labs = labs.filter(lambda l: l.mineralType == mineral2)
            else:
                labs = labs.filter(lambda l: not l.mineralAmount)

            target = labs.min(lambda l: movement.chebyshev_distance_room_pos(self.pos, l.pos))
            resource = mineral2
        else:
            del self.memory.state
            return True

        if not self.pos.isNearTo(target.pos):
            self.move_to(target)
            return False

        result = self.creep.transfer(target, resource)
        if result != OK:
            self.log("Unknown result from mineral-hauler.transfer({}, {}): {}".format(
                target, resource, result))

    def _calculate_time_to_replace(self):
        return _.size(self.creep.body) * 3  # Don't live replace mineral haulers


profiling.profile_whitelist(MineralHauler, [
    "determine_next_state",
    "run",
    "run_miner_harvbesting",
    "run_storage_pickup",
    "run_storage_dropoff",
    "run_terminal_pickup",
    "run_terminal_dropoff",
    "run_lab_drop_off",
])
