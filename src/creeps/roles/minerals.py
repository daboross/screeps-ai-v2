from constants import role_mineral_hauler, role_mineral_miner, role_recycling
from creeps.base import RoleBase
from jstools.screeps import *
from utilities import movement

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')


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

        if not self.pos.isNearTo(mineral):
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
                if not self.pos.isNearTo(transfer_target):
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
                hauler = _.find(self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1),
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
        time = (self.hive.honey.find_path_length(spawn_pos, mineral_pos) * 2
                + _.size(self.creep.body) * CREEP_SPAWN_TIME + 15)
        return time


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

    def determine_next_state(self, debug=False):
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
                        if resource != mineral.resourceType and self.creep.carry[resource] > 0:
                            if sending_resource_to_storage:
                                if (mind.terminal.store[resource] or 0) < mind.get_all_terminal_targets()[resource]:
                                    break
                            else:
                                if mind.terminal.store[resource] > (mind.get_all_terminal_targets()[resource] or 0):
                                    break
                    else:
                        if debug:
                            self.log('Choosing miner_harvest as there\'s a miner with 1000 minerals and we have space.')
                        return _MINER_HARVEST

        for resource in Object.keys(self.creep.carry):
            if self.creep.carry[resource] > 0:
                if resource in mind.get_labs_needing_mineral():
                    if debug:
                        self.log("Choosing fill_labs as we have a mineral that is needed.")
                    return _FILL_LABS

        if mind.energy_needed_in_labs() >= self.creep.carryCapacity / 2 and self.creep.carry[RESOURCE_ENERGY]:
            if debug:
                self.log("Choosing fill_labs as we have energy that is needed.")
            return _FILL_LABS

        terminal_can_handle_more = _.sum(mind.terminal.store) <= mind.terminal.storeCapacity - self.creep.carryCapacity

        if not terminal_can_handle_more:
            if now_held:
                if debug:
                    self.log("Choosing storage_dropoff as we have something held and there is no room in the terminal.")
                return _STORAGE_DROPOFF
            elif len(mind.removing_from_terminal()):
                if debug:
                    self.log("Choosing remove_from_terminal as there is no room in the terminal.")
                return _TERMINAL_PICKUP
            else:
                if debug:
                    self.log("Choosing depot as there is no room in the terminal.")
                return _DEPOT

        for resource in Object.keys(self.creep.carry):
            if self.creep.carry[resource] > 0:
                if (mind.terminal.store[resource] or 0) < mind.get_all_terminal_targets()[resource]:
                    if debug:
                        self.log("Choosing terminal_dropoff as we have a mineral which we need in the terminal.")
                    return _TERMINAL_DROPOFF

        if now_held:
            # We have a store which has no minerals needed by the terminal
            if debug:
                self.log("Choosing storage_dropoff as we have no resources which are needed anywhere else.")
            return _STORAGE_DROPOFF
        elif self.creep.ticksToLive < 100:
            if debug:
                self.log("Choosing dead because we are near death.")
            return _DEAD
        elif mind.energy_needed_in_labs():
            if debug:
                self.log("Choosing storage_pickup as there is something needed in labs.")
            return _STORAGE_PICKUP

        for lab, mineral, amount in mind.get_lab_targets():
            if lab.mineralAmount < amount:
                if mineral in mind.storage.store:
                    if debug:
                        self.log("Choosing storage_pickup as {} is needed in a lab.".format(mineral))
                    return _STORAGE_PICKUP
                elif mineral in mind.terminal.store:
                    if debug:
                        self.log("Choosing terminal_pickup as {} is needed in a lab.".format(mineral))
                    return _TERMINAL_PICKUP

        if len(mind.removing_from_terminal()) and self.pos.isNearTo(mind.terminal):
            if debug:
                self.log("Choosing terminal_pickup as we are close to the terminal, and we have things to remove.")
            return _TERMINAL_PICKUP
        # elif self.pos.isNearTo(mind.storage) and len(mind.adding_to_terminal()):
        #     return _STORAGE_PICKUP
        elif len(mind.adding_to_terminal()):
            if debug:
                self.log("Choosing storage_pickup as there are things to add to the terminal.")
            return _STORAGE_PICKUP
        elif len(mind.removing_from_terminal()):
            if debug:
                self.log("Choosing terminal_pickup as there are things to remove from the terminal.")
            return _TERMINAL_PICKUP
        elif self.home.role_count(role_mineral_miner):
            if debug:
                self.log("Choosing miner_harvest as there is a target miner count.")
            return _MINER_HARVEST
        else:
            if debug:
                self.log("Choosing depot because there is nothing else to do.")
            return _DEPOT

    def run(self):
        mind = self.home.minerals
        if mind.has_no_terminal_or_storage():
            self.memory.role = role_recycling
            self.memory.last_role = role_mineral_hauler
            return
        mind.note_mineral_hauler(self.name)
        if 'state' not in self.memory:
            if 'debug' in self.memory:
                if self.memory.debug is True:
                    self.memory.state = self.determine_next_state(True)
                    self.memory.debug = Game.time + 50
                if self.memory.debug > Game.time:
                    self.memory.state = self.determine_next_state(True)
                else:
                    self.memory.state = self.determine_next_state()
                    del self.memory.debug
            else:
                self.memory.state = self.determine_next_state()
            if self.memory.last_state == self.memory.state:
                self.log("State loop on state {}!".format(self.memory.state))
                del self.memory.last_state
                self.memory.debug = Game.time + 10
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
                .filter('structureType', STRUCTURE_CONTAINER).pluck('id').value()

        if len(self.memory.containers):
            if len(self.memory.containers) > 1:
                container = _(self.memory.containers).map(Game.getObjectById).max(lambda c: _.sum(c.store))
            else:
                container = Game.getObjectById(self.memory.containers[0])
            container_filled = _.sum(container.store)
            if self.pos.isNearTo(container):
                if container_filled + self.carry_sum() >= self.creep.carryCapacity or not mineral.mineralAmount:
                    resource = _.findKey(container.store)
                    if resource:
                        self.creep.withdraw(container, resource)
                    elif self.carry_sum() or not mineral.mineralAmount:
                        del self.memory.state
            else:
                self.move_to(container)

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

            if not self.pos.isNearTo(miner):
                self.move_to(miner)  # Miner does the work of giving us the minerals, no need to pick any up.

    def run_storage_pickup(self):
        mind = self.home.minerals
        now_carrying = self.carry_sum()
        if now_carrying >= self.creep.carryCapacity:
            del self.memory.state
            return True
        if not self.pos.isNearTo(mind.storage):
            access = mind.storage_terminal_access_pos()
            if access:
                closest = movement.room_pos_of_closest_serialized(self.home, self, access)
                if closest:
                    self.move_to(closest)
                else:
                    self.move_to(mind.storage)
            else:
                self.move_to(mind.storage)
            return False
        for resource, needed_in_terminal in mind.adding_to_terminal() \
                .concat([(RESOURCE_ENERGY, mind.energy_needed_in_labs())]) \
                .concat([(mineral, amount)
                         for lab, mineral, amount in mind.get_lab_targets()
                         if lab.mineralAmount < amount]):
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
        if not self.pos.isNearTo(mind.storage):
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
        if not self.pos.isNearTo(mind.terminal):
            access = mind.storage_terminal_access_pos()
            if access:
                closest = movement.room_pos_of_closest_serialized(self.home, self, access)
                if closest:
                    self.move_to(closest)
                else:
                    self.move_to(mind.terminal)
            else:
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
        if not self.pos.isNearTo(mind.terminal):
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

        best_lab = None
        best_resource = None
        closest_distance = Infinity

        for lab, mineral, amount in mind.get_lab_targets():
            if lab.mineralAmount < amount and self.creep.carry[mineral]:
                distance = movement.chebyshev_distance_room_pos(self.pos, lab.pos)
                if distance < closest_distance:
                    closest_distance = distance
                    best_lab = lab
                    best_resource = mineral
        if not best_lab:
            for lab in mind.labs():
                if lab.energy < lab.energyCapacity and self.creep.carry[RESOURCE_ENERGY]:
                    distance = movement.chebyshev_distance_room_pos(self.pos, lab.pos)
                    if distance < closest_distance:
                        closest_distance = distance
                        best_lab = lab
                        best_resource = RESOURCE_ENERGY
        if not best_lab:
            if self.memory.debug:
                self.log("Untargetting labs: no minerals needed that we have.")
            del self.memory.state
            return

        if not self.pos.isNearTo(best_lab):
            self.move_to(best_lab)
            return False

        result = self.creep.transfer(best_lab, best_resource)
        if result != OK:
            self.log("Unknown result from mineral-hauler.transfer({}, {}): {}".format(
                best_lab, best_resource, result))

    def _calculate_time_to_replace(self):
        return _.size(self.creep.body) * CREEP_SPAWN_TIME  # Don't live replace mineral haulers
