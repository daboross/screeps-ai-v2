import math

from constants import UPGRADER_SPOT, creep_base_worker, recycle_time, role_builder, role_link_manager, role_recycling, \
    role_upgrade_fill, role_upgrader, target_home_flag
from creep_management import spawning
from creeps.base import RoleBase
from jstools.screeps_constants import *
from position_management import flags

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


def split_pos_str(pos_str):
    pos_split = pos_str.split(",")
    x = int(pos_split[0])
    y = int(pos_split[1])
    return x, y


class Upgrader(RoleBase):
    def run(self):
        link = self.home.get_upgrader_energy_struct()
        if link:
            return self.run_dedicated_upgrading(link)
        else:
            return self.run_individual_upgrading()

    def run_dedicated_upgrading(self, link):
        controller = self.home.room.controller

        if self.memory.set_till > Game.time:
            result = self.upgrade(controller)
            if result == ERR_NOT_IN_RANGE:
                del self.memory.set_till
            else:
                result = self.harvest_from(link)
                if result == ERR_NOT_IN_RANGE:
                    del self.memory.set_till
                else:
                    return

        if not self.home.upgrading_deprioritized() or self.creep.room.controller.ticksToDowngrade <= 5000:
            self.upgrade(controller)
        elif Game.time % 15 == 2 or self.memory.set_till == Game.time:
            if not self.home.get_target_upgrader_work_mass() or not self.home.spawn:
                if len(self.creep.body) > 3 and spawning.find_base_type(self) == creep_base_worker:
                    self.memory.role = role_builder
                    return False
                elif self.home.spawn:
                    self.memory.role = role_recycling
                    self.memory.last_role = role_upgrader
                    return False
        if Game.time % 15 == 7 or self.memory.set_till == Game.time:
            if self.home.overprioritize_building():
                # TODO: do this via push immediately after controller upgrade, instead of polling
                if len(self.creep.body) > 3 and spawning.find_base_type(self) == creep_base_worker:
                    self.memory.role = role_builder
                    return False
            if self.home.rcl >= 8 and self.home.role_count(role_upgrader) > 1 \
                    and self.home.work_mass_of(role_upgrader) > self.home.get_target_upgrader_work_mass():
                needed = self.home.get_target_upgrader_work_mass()
                any_big_enough = _.find(self.home.creeps, lambda c: c.memory.role == role_upgrader
                                                                    and c.getBodyparts(WORK) >= needed)
                if any_big_enough:
                    for creep in self.home.creeps:
                        if creep.memory.role == role_upgrader and creep.name != any_big_enough.name:
                            creep.suicide()
                    self.home.check_all_creeps_next_tick()

        self.harvest_from(link)

        spot = self.targets.get_new_target(self, target_home_flag, UPGRADER_SPOT)
        if spot and self.home.role_count(role_upgrader) <= len(flags.find_flags(self.home, UPGRADER_SPOT)):
            if self.pos.isEqualTo(spot.pos):
                self.memory.set_till = Game.time + 30
            else:
                self.move_to(spot)
        else:
            if self.creep.ticksToLive < 50:
                self.creep.suicide()
                self.home.check_all_creeps_next_tick()
                return
            self.log("WARNING: Not enough set upgrader spots in {}".format(self.memory.home))
            available_positions = self.memory.controller_positions
            if not available_positions or (Game.time + self.creep.ticksToLive) % 25:
                available_positions = []
                for x in range(link.pos.x - 1, link.pos.x + 2):
                    for y in range(link.pos.y - 1, link.pos.y + 2):
                        if x != link.pos.x or y != link.pos.y:
                            if abs(x - controller.pos.x) <= 3 and abs(y - controller.pos.y) <= 3 \
                                    and Game.map.getTerrainAt(x, y, self.pos.roomName) != 'wall':
                                available_positions.append("{},{}".format(x, y))
                self.memory.controller_positions = available_positions

            if self.memory.get_near_controller:
                if self.creep.carry.energy > self.creep.carryCapacity * 0.5:
                    if self.pos.isNearTo(link) or not self.pos.isNearTo(controller):
                        if self.home.role_count(role_upgrader) < 4:
                            basic_moved = self.basic_move_to(controller)
                        else:
                            self_empty = self.creep.carryCapacity - self.carry_sum()
                            basic_moved = self.force_basic_move_to(controller,
                                                                   lambda other: (other.carryCapacity - _.sum(
                                                                       other.carry)) > self_empty)
                        if not basic_moved:
                            self.move_to(controller)
                    return
                else:
                    del self.memory.get_near_controller

            if not self.pos.inRangeTo(controller, 3) or not self.pos.isNearTo(link):
                a_creep_with_energy = None
                for pos in available_positions:
                    x, y = split_pos_str(pos)
                    that_creep = _.find(self.home.look_at(LOOK_CREEPS, x, y))
                    if not that_creep:
                        self.move_to(__new__(RoomPosition(x, y, self.home.name)))
                        break
                    elif that_creep.carry.energy >= that_creep.carryCapacity * 0.5 \
                            and that_creep.memory.role == role_upgrader and not that_creep.memory.get_near_controller:
                        a_creep_with_energy = that_creep
                else:
                    if self.creep.carry.energy < self.creep.carryCapacity * 0.25:
                        closest_full = _.find(self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1),
                                              lambda c: c.creep.memory.role == role_upgrader
                                                        and c.creep.carry.energy >= c.creep.carryCapacity * 0.75
                                                        and c.creep.pos.inRangeTo(link.pos, 1))
                        if closest_full:
                            closest_full.creep.move(closest_full.creep.pos.getDirectionTo(self.pos))
                            self.creep.move(self.pos.getDirectionTo(closest_full.creep.pos))
                        elif a_creep_with_energy:
                            a_creep_with_energy.memory.get_near_controller = True
                            self.creep.move(self.pos.getDirectionTo(link.pos))
                    elif not self.pos.inRangeTo(controller, 3):
                        self.move_to(controller)
                return

            if not _.find(self.room.look_for_in_area_around(LOOK_CREEPS, self.pos, 1),
                          lambda c: c.creep.memory.role != role_upgrader and c.creep.memory.role != role_link_manager):
                return  # No need to shuffle around if there's no one to move around for

            if len(available_positions):
                target_x, target_y = split_pos_str(available_positions[(Game.time + 2) % len(available_positions)])
                self.basic_move_to({'x': target_x, 'y': target_y})

    def upgrade(self, controller):
        result = self.creep.upgradeController(controller)
        if result != OK and result != ERR_NOT_IN_RANGE and result != ERR_NOT_ENOUGH_RESOURCES:
            self.log("Unknown result from creep.upgradeController({}): {}", self.creep.room.controller, result)
        return result

    def harvest_from(self, link):
        if self.creep.ticksToLive < 20 or self.creep.carry.energy >= self.creep.getActiveBodyparts(WORK) * 3:
            return OK
        if link.structureType == STRUCTURE_LINK:
            self.home.links.register_target_withdraw(link, self, self.creep.carryCapacity - self.creep.carry.energy,
                                                     self.pos.getRangeTo(link))
        result = self.creep.withdraw(link, RESOURCE_ENERGY)
        if result != OK and result != ERR_NOT_IN_RANGE and result != ERR_NOT_ENOUGH_RESOURCES:
            self.log("Unknown result from creep.withdraw({}): {}", link, result)
        return result

    def should_pickup(self, resource_type=None):
        return RoleBase.should_pickup(self, resource_type) and not self.home.upgrading_paused()

    def run_individual_upgrading(self):
        if self.creep.ticksToLive < recycle_time and self.home.spawn:
            self.memory.role = role_recycling
            self.memory.last_role = role_upgrader
            return False
        if self.home.overprioritize_building() and self.home.room.controller.ticksToDowngrade >= 500:
            self.memory.role = role_builder
            return False
        if self.memory.filling and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.filling = False
            self.finished_energy_harvest()
        elif not self.memory.filling and self.creep.carry.energy <= 0 \
                and self.creep.getBodyparts(CARRY) > self.creep.getBodyparts(WORK):
            # If we're a dedicated upgrader, just wait for a spawn filler to come give us more energy.
            self.memory.filling = True
            self.finished_energy_harvest()

        if Game.time % 5 == 0 and not (self.creep.hasActiveBodyparts(WORK) & self.creep.hasActiveBodyparts(CARRY)) and \
                not self.home.defense.healing_capable():
            self.memory.last_role = self.memory.role
            self.memory.role = role_recycling
            return

        if self.home.upgrading_deprioritized() and self.creep.room.controller.ticksToDowngrade > 5000:
            if self.home.room.storage and self.empty_to_storage():
                return False
            elif not self.home.get_target_upgrader_work_mass() or not self.home.spawn:
                if len(self.creep.body) > 3 and spawning.find_base_type(self) == creep_base_worker:
                    self.memory.role = role_builder
                    return False
                elif self.home.spawn:
                    self.memory.role = role_recycling
                    self.memory.last_role = role_upgrader
                    return False

        if not self.home.room.controller.my or (self.home.upgrading_paused()
                                                and self.creep.room.controller.ticksToDowngrade >= 9900):
            if not self.empty_to_storage():
                self.go_to_depot()
            return False

        # When upgrading is deprioritized, and we're not paused, we should sit by the controller and wait for a hauler
        # to bring us energy, if there is any energy spare. Otherwise we should just sit there, and wait.
        if self.memory.filling and (not self.home.upgrading_deprioritized()
                                    or self.creep.room.controller.ticksToDowngrade <= 5000):
            self.targets.untarget(self, target_home_flag)
            self.build_swamp_roads()
            self.harvest_energy()
        else:
            spot = self.targets.get_new_target(self, target_home_flag, UPGRADER_SPOT)
            target = self.home.room.controller
            if spot:
                if self.pos.isEqualTo(spot.pos):
                    result = self.creep.upgradeController(target)
                    if result == ERR_NOT_ENOUGH_RESOURCES:
                        if not self.memory.filling and self.creep.getActiveBodyparts(CARRY) \
                                > self.creep.getActiveBodyparts(WORK):
                            self.memory.filling = True
                            return True
                    elif result != OK:
                        self.log("Unknown result from upgradeController({}): {}", self.creep.room.controller, result)
                else:
                    self.build_swamp_roads()
                    self.move_to(spot)
            else:
                if not self.pos.inRangeTo(target, 3):
                    self.build_swamp_roads()
                    self.move_to(target)
                    return False

                result = self.creep.upgradeController(target)
                if result == ERR_NOT_ENOUGH_RESOURCES:
                    if not self.memory.filling and self.creep.getActiveBodyparts(CARRY) \
                            > self.creep.getActiveBodyparts(WORK):
                        self.memory.filling = True
                        return True
                if result == OK or result == ERR_NOT_ENOUGH_RESOURCES:
                    if self.home.full_storage_use or self.home.being_bootstrapped():
                        if self.home.role_count(role_upgrader) < 4:

                            self.basic_move_to(target)
                        else:
                            # Simpler than below, doesn't include transferring energy
                            self_empty = self.creep.carryCapacity - self.carry_sum()
                            self.force_basic_move_to(target,
                                                     lambda other: (other.carryCapacity - _.sum(
                                                         other.carry)) > self_empty)

                    else:
                        self_empty = self.creep.carryCapacity - self.carry_sum()

                        # empty_percent =  self_empty / self.creep.carryCapacity
                        def can_move_over(other_creep):
                            other_empty = other_creep.carryCapacity - _.sum(other_creep.carry)
                            if other_empty > self_empty:
                                self.creep.transfer(other_creep, RESOURCE_ENERGY,
                                                    math.ceil((other_empty - self_empty) / 3))
                                return True
                            elif self_empty < other_empty:
                                other_creep.transfer(self.creep, RESOURCE_ENERGY,
                                                     math.ceil((self_empty - other_empty) / 3))
                            return False

                        self.force_basic_move_to(target, can_move_over)
                else:
                    self.log("Unknown result from upgradeController({}): {}", self.creep.room.controller, result)

                    if self.creep.carry.energy < self.creep.carryCapacity:
                        self.memory.filling = True
                    else:
                        self.go_to_depot()

    def build_swamp_roads(self):
        if not _.get(self.home.room, 'storage.storeCapacity') and self.creep.carry.energy > 0:
            if Game.map.getTerrainAt(self.pos.x, self.pos.y, self.pos.roomName) == 'swamp':
                repair = _.find(self.room.look_at(LOOK_STRUCTURES, self.pos),
                                lambda s: s.structureType == STRUCTURE_ROAD and s.hits < s.hitsMax)
                if repair:
                    result = self.creep.repair(repair)
                    if result != OK:
                        self.log("Unknown result from passingby-road-repair on {}: {}".format(repair, result))
                else:
                    build = self.room.look_at(LOOK_CONSTRUCTION_SITES, self.pos)
                    if len(build):
                        build = _.find(build, lambda s: s.structureType == STRUCTURE_ROAD)
                        if build:
                            result = self.creep.build(build)
                            if result != OK:
                                self.log("Unknown result from passingby-road-build on {}: {}".format(build, result))

    def _calculate_time_to_replace(self):
        if self.home.spawn:
            path_length = self.hive.honey.find_path_length(self.home.spawn, self.home.room.controller)
            # No leeway because we're assuming that we A: won't need to go all the way to the controller and B: the road
            # will be somewhat paved
            return path_length * 2 + _.size(self.creep.body) * 3
        else:
            return _.size(self.creep.body) * 3 + 15


class DedicatedUpgradeFiller(RoleBase):
    def run(self):
        if self.memory.filling and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.filling = False
        elif not self.memory.filling and self.creep.carry.energy <= 0:
            self.memory.filling = True

        if 'set' not in self.memory or Game.time % 100 == 92:
            if self.memory.emptying_container:
                container = Game.getObjectById(self.memory.emptying_container)
                if not container:
                    del self.memory.emptying_container
                    return True
                if self.memory.filling:
                    if self.pos.isNearTo(container):
                        resource = _.findKey(container.store)
                        if not resource:
                            container.destroy()
                            return False
                        result = self.creep.withdraw(container, resource)
                        if result != OK:
                            self.log("Unknown result from creep.withdraw({}, {})".format(container, resource))
                    else:
                        self.move_to(container)
                else:
                    if self.pos.isNearTo(self.home.room.storage):
                        resource = _.findKey(self.creep.carry)
                        result = self.creep.transfer(self.home.room.storage, resource)
                        if result != OK:
                            self.log("Unknown result from creep.withdraw({}, {})".format(
                                self.home.room.storage, resource))
                    else:
                        self.move_to(self.home.room.storage)
                return False

            if not self.home.get_target_upgrade_fill_mass():
                current_target = self.home.get_upgrader_energy_struct()
                if not current_target or current_target.structureType != STRUCTURE_CONTAINER:
                    old_container = _.find(self.home.look_for_in_area_around(LOOK_STRUCTURES,
                                                                             self.home.room.controller, 4),
                                           lambda obj: obj.structure.structureType == STRUCTURE_CONTAINER)
                    if old_container:
                        self.memory.emptying_container = old_container.structure.id
                        del self.memory.set
                        return True
                    else:
                        # No containers! let's recycle
                        if not current_target or current_target.structureType != STRUCTURE_CONTAINER:
                            self.memory.role = role_recycling
                            self.memory.last_role = role_upgrade_fill
                            return False
            mineral_held = _.findKey(self.creep.carry,
                                     lambda amount, mineral: amount > 0 and mineral != RESOURCE_ENERGY)
            if mineral_held:
                if not self.empty_to_storage():
                    result = self.creep.drop(mineral_held)
                    if result != OK:
                        self.log("Unknown result from ufill-creep.drop({}): {}".format(mineral_held, result))
                return False
            self.memory.set = True

        if self.memory.filling:
            self.harvest_energy()
        else:
            target = self.home.get_upgrader_energy_struct()
            if self.pos.isNearTo(target):
                result = self.creep.transfer(target, RESOURCE_ENERGY)
                if result != OK and result != ERR_FULL:
                    self.log("Unknown result from ufill-creep.transfer({}, {}): {}"
                             .format(target, RESOURCE_ENERGY, result))
            else:
                self.move_to(target)
