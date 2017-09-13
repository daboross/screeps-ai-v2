from typing import List, cast

from constants import recycle_time, role_cleanup, role_link_manager, role_recycling, target_closest_energy_site
from creeps.base import RoleBase
from creeps.roles.spawn_fill import SpawnFill
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
__pragma__('noalias', 'values')


class LinkManager(RoleBase):
    def run(self):
        link = self.home.links.main_link
        storage = self.home.room.storage
        if not link or not storage:
            self.log("ERROR: Link manager can't find main link or storage in {}.".format(self.home.name))
            self.go_to_depot()
            return False
        # Note: this does assume storage is directly within one space of the main link.
        if 'station_pos' not in self.memory:
            secondary = self.home.links.secondary_link
            best_priority = 0
            best = None
            for x in range(link.pos.x - 1, link.pos.x + 2):
                for y in range(link.pos.y - 1, link.pos.y + 2):
                    if -1 <= x - storage.pos.x <= 1 and -1 <= y - storage.pos.y <= 1 \
                            and (storage.pos.x != x or storage.pos.y != y) \
                            and (link.pos.x != x or link.pos.y != y):
                        if not movement.is_block_empty(self.home, x, y):
                            continue
                        creeps = cast(List[Creep], self.home.look_at(LOOK_CREEPS, x, y))
                        if len(creeps) != 0:
                            creep = creeps[0]
                            if creep.memory.role == role_link_manager:
                                if self.creep.ticksToLive > creep.ticksToLive:
                                    creep.suicide()
                                else:
                                    self.creep.suicide()
                                    return False
                        pos = __new__(RoomPosition(x, y, self.home.name))
                        priority = 1
                        if secondary and movement.chebyshev_distance_xy(secondary.pos.x, secondary.pos.y, x, y) <= 1:
                            priority += 20
                        if link.pos.x == storage.pos.x == pos.x:
                            priority += 5
                        elif link.pos.y == storage.pos.y == pos.y:
                            priority += 5
                        if priority >= best_priority:
                            best = pos
                            best_priority = priority
            if best is None:
                self.go_to_depot()
                return False
            self.memory.station_pos = best.x | best.y << 6
        current_pos = (self.pos.x | self.pos.y << 6)
        if current_pos != self.memory.station_pos:
            self.move_to(__new__(RoomPosition(self.memory.station_pos & 0x3F,
                                              self.memory.station_pos >> 6 & 0x3F, self.home.name)))
            return False

        if self.ensure_no_minerals():
            return False

        half_capacity = int(self.creep.carryCapacity / 2)
        if self.creep.carry[RESOURCE_ENERGY] != half_capacity:
            # this is not the norm.
            if self.creep.carry[RESOURCE_ENERGY] > half_capacity:
                target = storage
                result = self.creep.transfer(target, RESOURCE_ENERGY, self.creep.carry[RESOURCE_ENERGY]
                                             - half_capacity)
                if result == ERR_FULL:
                    target = self.home.links.main_link
                    result = self.creep.transfer(target, RESOURCE_ENERGY, self.creep.carry[RESOURCE_ENERGY]
                                                 - half_capacity)
                    if result == ERR_FULL:
                        secondary = self.home.links.secondary_link
                        if secondary:
                            target = secondary
                            result = self.creep.transfer(target, RESOURCE_ENERGY, self.creep.carry[RESOURCE_ENERGY]
                                                         - half_capacity)

                self.ensure_ok(result, "transfer", target, RESOURCE_ENERGY)

            else:
                target = storage
                result = self.creep.withdraw(target, RESOURCE_ENERGY, half_capacity
                                             - self.creep.carry[RESOURCE_ENERGY])
                if result == ERR_NOT_ENOUGH_RESOURCES:
                    target = self.home.links.main_link
                    result = self.creep.withdraw(target, RESOURCE_ENERGY, half_capacity
                                                 - self.creep.carry[RESOURCE_ENERGY])
                    if result == ERR_NOT_ENOUGH_RESOURCES:
                        secondary = self.home.links.secondary_link
                        if secondary:
                            target = secondary
                            result = self.creep.withdraw(target, RESOURCE_ENERGY, half_capacity
                                                         - self.creep.carry[RESOURCE_ENERGY])
                self.ensure_ok(result, "withdraw", target, RESOURCE_ENERGY)
            return False

        self.home.links.note_link_manager(self)

        return False

    def ensure_ok(self, result, action, p1, p2, p3=None):
        # TODO: nicer messages for running out of energy, and also saying if this was a transfer or withdraw, from a
        # link or storage.
        if result != OK:
            if p3:
                self.log("ERROR: Unknown result from link creep.{}({},{},{}): {}!".format(action, p1, p2, p3, result))
            else:
                self.log("ERROR: Unknown result from link creep.{}({},{}): {}!".format(action, p1, p2, result))

    def ensure_no_minerals(self):
        storage = self.home.room.storage
        if self.carry_sum() > self.creep.carry[RESOURCE_ENERGY]:
            for rtype in Object.keys(self.creep.carry):
                if rtype != RESOURCE_ENERGY:
                    self.ensure_ok(self.creep.transfer(storage, rtype), "transfer", storage, rtype)
                    return True
        return False

    def send_to_link(self, link, amount=None):
        storage = self.home.room.storage

        if not amount or amount > self.creep.carryCapacity / 2:
            amount = self.creep.carryCapacity / 2
        if amount > link.energyCapacity - link.energy:
            amount = link.energyCapacity - link.energy
        if link.energy == link.energyCapacity:
            return

        self.ensure_ok(self.creep.transfer(link, RESOURCE_ENERGY, amount), "transfer", link, RESOURCE_ENERGY)
        self.ensure_ok(self.creep.withdraw(storage, RESOURCE_ENERGY, amount), "withdraw", storage, RESOURCE_ENERGY)

    def send_from_link(self, link, amount=None):
        storage = self.home.room.storage

        if not amount or amount > self.creep.carryCapacity / 2:
            amount = self.creep.carryCapacity / 2
        if amount > link.energy:
            amount = link.energy
        if link.energy == 0:
            return
        self.ensure_ok(self.creep.withdraw(link, RESOURCE_ENERGY, amount), "withdraw", link, RESOURCE_ENERGY)
        self.ensure_ok(self.creep.transfer(storage, RESOURCE_ENERGY, amount), "transfer", storage, RESOURCE_ENERGY)

    def _calculate_time_to_replace(self):
        link = self.home.links.main_link
        if not link:
            return -1
        link_pos = link.pos
        # No leeway because we assume the path will be at least partially paved
        return (self.hive.honey.find_path_length(self.home.spawn.pos, link_pos) * 2
                + _.size(self.creep.body) * CREEP_SPAWN_TIME)


class Cleanup(SpawnFill):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_cleanup
            return False
        storage = self.creep.room.storage

        if self.memory.filling and self.carry_sum() >= self.creep.carryCapacity:
            self.memory.filling = False

        if not self.memory.filling and self.carry_sum() <= 0:
            self.memory.filling = True

        if self.memory.filling:
            # TODO: Make some cached memory map of all hostile creeps, and use it to avoid.
            resources = cast(List[Resource], self.room.find(FIND_DROPPED_RESOURCES))
            if len(resources):
                closest = None
                closest_distance = Infinity
                for resource in resources:
                    if len(self.room.find_in_range(FIND_HOSTILE_CREEPS, 3, resource.pos)) == 0:
                        if len(self.room.find_in_range(FIND_SOURCES, 1, resource.pos)) == 0:
                            if self.memory.last_energy_target:
                                compressed_pos = resource.pos.x | (resource.pos.y << 6)
                                if compressed_pos == self.memory.last_energy_target:
                                    closest = resource
                                    break

                            # we've confirmed now that this is a valid target! congrats.
                            distance = movement.distance_squared_room_pos(self.pos, resource.pos)
                            if distance < closest_distance:
                                closest = resource
                                closest_distance = distance
                pile = closest
            else:
                pile = None

            if not pile:
                del self.memory.last_energy_target
                self.go_to_depot()  # wait
                return

            self.memory.last_energy_target = pile.pos.x | (pile.pos.y << 6)

            if not self.pos.isNearTo(pile):
                self.move_to(pile)
                return False

            result = self.creep.pickup(pile)

            if result == ERR_FULL:
                self.memory.filling = False
                return True
            elif result != OK:
                self.log("Unknown result from cleanup-creep.pickup({}): {}", pile, result)
        else:
            if not storage:
                # self.log("Cleanup can't find storage in {}!", self.creep.room.name)
                # self.go_to_depot()
                # return False
                return SpawnFill.run(self)

            if self.pos.roomName != storage.pos.roomName:
                self.move_to(storage)
                return False

            if self.carry_sum() > self.creep.carry[RESOURCE_ENERGY]:
                target = storage
            else:
                target = self.targets.get_new_target(self, target_closest_energy_site)
                if not target:
                    target = storage
            # if target.energy >= target.energyCapacity:
            #     target = storage
            if target.structureType == STRUCTURE_LINK:
                assert isinstance(target, StructureLink)
                self.home.links.register_target_deposit(target, self, self.creep.carry[RESOURCE_ENERGY],
                                                        self.pos.getRangeTo(target))

            if not self.pos.isNearTo(target):
                if self.pos.isNearTo(storage):
                    # being blocked by a link manager to get to the link
                    target = storage
                else:
                    self.move_to(target)
                    return False

            resource_type = _.find(Object.keys(self.creep.carry), lambda r: self.creep.carry[r] > 0)
            result = self.creep.transfer(target, resource_type)
            if result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.filling = True
                return True
            elif result == ERR_FULL:
                if target == storage:
                    self.log("Storage in room {} full!", storage.room.name)
            elif result != OK:
                self.log("Unknown result from cleanup-creep.transfer({}, {}): {}", target, resource_type, result)

    def _calculate_time_to_replace(self):
        return 0  # Don't live-replace
