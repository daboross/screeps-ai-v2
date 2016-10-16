import math

import flags
import spawning
import speech
from constants import recycle_time, role_recycling, role_upgrader, role_builder, creep_base_worker, role_upgrade_fill, \
    role_link_manager, target_single_flag, target_home_flag
from role_base import RoleBase
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


def split_pos_str(pos_str):
    pos_split = pos_str.split(",")
    x = int(pos_split[0])
    y = int(pos_split[1])
    return x, y


class Upgrader(RoleBase):
    def run(self):
        link = self.get_dedicated_upgrading_energy_structure()
        if link:
            return self.run_dedicated_upgrading(link)
        else:
            return self.run_individual_upgrading()

    def get_dedicated_upgrading_energy_structure(self):
        return self.home.get_upgrader_energy_struct()

    def run_dedicated_upgrading(self, link):
        controller = self.home.room.controller

        if not self.home.upgrading_deprioritized() or self.creep.room.controller.ticksToDowngrade <= 5000:
            self.upgrade(controller)
        elif Game.time % 15 == 2 and not self.home.get_target_upgrader_work_mass() or not self.home.spawn:
            if len(self.creep.body) > 3 and spawning.find_base_type(self) == creep_base_worker:
                self.memory.role = role_builder
                return False
            elif self.home.spawn:
                self.memory.role = role_recycling
                self.memory.last_role = role_upgrader
                return False
        if Game.time % 15 == 7 and self.home.overprioritize_building():
            # TODO: do this via push immediately after controller upgrade, instead of polling
            if len(self.creep.body) > 3 and spawning.find_base_type(self) == creep_base_worker:
                self.memory.role = role_builder
                return False

        self.harvest_from(link)

        spot = self.targets.get_new_target(self, target_home_flag, flags.UPGRADER_SPOT)
        if spot and self.home.role_count(role_upgrader) <= len(flags.find_flags(self.home, flags.UPGRADER_SPOT)):
            if not self.pos.isEqualTo(spot.pos):
                self.move_to(spot)
        else:
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
                    if self.pos.isNearTo(link):
                        if not self.basic_move_to(controller):
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
                        self.move_to(__new__(RoomPosition(x, y, self.home.room_name)))
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
                            closest_full.move(closest_full.creep.pos.getDirectionTo(self.pos))
                            self.creep.move(self.pos.getDirectionTo(closest_full.pos))
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
        if self.creep.carry.energy <= 0:
            return
        result = self.creep.upgradeController(controller)
        if result != OK and result != ERR_NOT_IN_RANGE:
            self.log("Unknown result from creep.upgradeController({}): {}", self.creep.room.controller, result)

    def harvest_from(self, link):
        if self.creep.ticksToLive < 20 or self.creep.carry.energy >= self.creep.getActiveBodyparts(WORK) * 3:
            return
        energy = _.find(self.room.look_for_in_area_around(LOOK_RESOURCES, 1, self.pos),
                        lambda x: x.resource.resourceType == RESOURCE_ENERGY)
        if energy:
            self.creep.pickup(energy)
            return
        if link.structureType == STRUCTURE_LINK:
            self.home.links.register_target_withdraw(link, self, self.creep.carryCapacity - self.creep.carry.energy,
                                                     self.creep.pos.getRangeTo(link))
        if (link.energyCapacity and link.energy <= 0) or (link.storeCapacity and link.store.energy <= 0) \
                or not self.pos.isNearTo(link):
            return
        result = self.creep.withdraw(link, RESOURCE_ENERGY)
        if result != OK:
            self.log("Unknown result from creep.withdraw({}): {}", link, result)

    def should_pickup(self, resource_type=None):
        return not self.get_dedicated_upgrading_energy_structure() and RoleBase.should_pickup(self, resource_type) \
               and not self.home.upgrading_paused()

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
                and self.creep.getActiveBodyparts(CARRY) > self.creep.getActiveBodyparts(WORK):
            # If we're a dedicated upgrader, just wait for a spawn filler to come give us more energy.
            self.memory.filling = True
            self.finished_energy_harvest()

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
            self.report(speech.upgrading_upgrading_paused)
            if not self.empty_to_storage():
                self.go_to_depot()
            return False

        # When upgrading is deprioritized, and we're not paused, we should sit by the controller and wait for a hauler
        # to bring us energy, if there is any energy spare. Otherwise we should just sit there, and wait.
        if self.memory.filling and (not self.home.upgrading_deprioritized()
                                    or self.creep.room.controller.ticksToDowngrade <= 5000):
            self.build_swamp_roads()
            self.harvest_energy()
        else:
            target = self.home.room.controller
            if not self.creep.pos.inRangeTo(target.pos, 3):
                self.build_swamp_roads()
                self.move_to(target)
                self.report(speech.upgrading_moving_to_controller)
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
                                                 lambda other: (other.carryCapacity - _.sum(other.carry)) > self_empty)

                else:
                    self_empty = self.creep.carryCapacity - self.carry_sum()

                    # empty_percent =  self_empty / self.creep.carryCapacity
                    def can_move_over(other_creep):
                        other_empty = other_creep.carryCapacity - _.sum(other_creep.carry)
                        if other_empty > self_empty:
                            self.creep.transfer(other_creep, RESOURCE_ENERGY, math.ceil((other_empty - self_empty) / 3))
                            return True
                        elif self_empty < other_empty:
                            other_creep.transfer(self.creep, RESOURCE_ENERGY, math.ceil((self_empty - other_empty) / 3))
                        return False

                    self.force_basic_move_to(target, can_move_over)
                self.report(speech.upgrading_ok)
            else:
                self.log("Unknown result from upgradeController({}): {}", self.creep.room.controller, result)

                if self.creep.carry.energy < self.creep.carryCapacity:
                    self.memory.filling = True
                else:
                    self.go_to_depot()
                    self.report(speech.upgrading_unknown_result)

    def build_swamp_roads(self):
        if not self.home.room.storage and self.creep.carry.energy > 0:
            if Game.map.getTerrainAt(self.pos.x, self.pos.y, self.pos.roomName) == 'swamp':
                repair = self.room.look_at(LOOK_STRUCTURES, self.pos)
                if len(repair):
                    result = self.creep.repair(repair[0])
                    if result != OK:
                        self.log("Unknown result from passingby-road-repair on {}: {}".format(repair[0], result))
                else:
                    build = self.room.look_at(LOOK_CONSTRUCTION_SITES, self.pos)
                    if len(build):
                        result = self.creep.build(build[0])
                        if result != OK:
                            self.log("Unknown result from passingby-road-build on {}: {}".format(build[0], result))
                            # repair = _.find(self.room.find_in_range(PYFIND_REPAIRABLE_ROADS, 2, self.creep.pos),
                            #                 lambda r: Game.map.getTerrainAt(r.pos.x, r.pos.y, r.pos.roomName) == 'swamp')
                            # if repair:
                            #     result = self.creep.repair(repair)
                            #     if result != OK:
                            #         self.log("Unknown result from passingby-road-repair on {}: {}".format(repair[0], result))
                            # else:
                            #     build = _.find(self.room.find_in_range(PYFIND_BUILDABLE_ROADS, 2, self.creep.pos),
                            #                    lambda r: Game.map.getTerrainAt(r.pos.x, r.pos.y, r.pos.roomName) == 'swamp')
                            #     if build:
                            #         result = self.creep.build(build)
                            #         if result != OK:
                            #             self.log("Unknown result from passingby-road-build on {}: {}".format(build[0], result))

    def _calculate_time_to_replace(self):
        if self.home.spawn:
            path = self.hive.honey.find_path(self.home.spawn, self.home.room.controller)
            # No leeway because we're assuming that we A: won't need to go all the way to the controller and B: the road
            # will be somewhat paved
            return len(path) * 2 + _.size(self.creep.body) * 3
        else:
            return _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(Upgrader, [
    "run",
    "get_dedicated_upgrading_energy_structure",
    "run_dedicated_upgrading",
    "upgrade",
    "harvest_from",
    "should_pickup",
    "run_individual_upgrading",
    "build_swamp_roads",
])


class DedicatedUpgradeFiller(RoleBase):
    def run(self):
        if not self.home.get_target_upgrade_fill_mass():
            self.memory.role = role_recycling
            self.memory.last_role = role_upgrade_fill
            return False
        mineral_held = _.find(_.keys(self.creep.carry), lambda x: x != RESOURCE_ENERGY)
        if mineral_held:
            if not self.empty_to_storage():
                result = self.creep.drop(mineral_held)
                if result != OK:
                    self.log("Unknown result from ufill-creep.drop({}): {}".format(mineral_held, result))
            return False

        if self.memory.filling and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.filling = False
        elif not self.memory.filling and self.creep.carry.energy <= 0:
            self.memory.filling = True

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


profiling.profile_whitelist(DedicatedUpgradeFiller, ["run"])
