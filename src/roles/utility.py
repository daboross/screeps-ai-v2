import spawning
import speech
from constants import role_cleanup, recycle_time, role_recycling, \
    target_closest_energy_site, role_link_manager, role_hauler
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class LinkManager(RoleBase):
    def run(self):
        link = self.home.links.main_link
        storage = self.home.room.storage
        if not link or not storage:
            self.log("ERROR: Link manager can't find main link or storage in {}.".format(self.home.room_name))
            self.go_to_depot()
            self.report(speech.link_manager_something_not_found)
            return False
        # Note: this does assume storage is directly within one space of the main link.
        if not self.creep.pos.isNearTo(link) or not self.creep.pos.isNearTo(storage):
            for x in range(link.pos.x - 1, link.pos.x + 2):
                for y in range(link.pos.y - 1, link.pos.y + 2):
                    if -1 <= x - storage.pos.x <= 1 and -1 <= y - storage.pos.y <= 1 \
                            and (storage.pos.x != x or storage.pos.y != y) \
                            and (link.pos.x != x or link.pos.y != y):
                        if not movement.is_block_empty(self.home, x, y):
                            continue
                        creeps = self.home.find_at(FIND_CREEPS, x, y)
                        if len(creeps) != 0:
                            creep = creeps[0]
                            if creep.memory.role == role_link_manager:
                                if self.creep.ticksTolive > creep.ticksToLive:
                                    creep.suicide()
                                else:
                                    self.creep.suicide()
                                    return False
                        pos = __new__(RoomPosition(x, y, self.home.room_name))
                        break
                else:
                    continue
                break
            else:
                self.go_to_depot()
                return False
            self.move_to(pos)
            self.report(speech.link_manager_moving)
            return False

        if self.ensure_no_minerals():
            return False

        if self.creep.carry.energy != self.creep.carryCapacity / 2:
            # this is not the norm.
            if self.creep.carry.energy > self.creep.carryCapacity / 2:
                result = self.creep.transfer(storage, RESOURCE_ENERGY, self.creep.carry.energy
                                             - self.creep.carryCapacity / 2)
                if result == ERR_FULL:
                    result = self.creep.transfer(self.home.links.main_link, RESOURCE_ENERGY, self.creep.carry.energy
                                                 - self.creep.carryCapacity / 2)
                self.ensure_ok(result, "transfer", storage, RESOURCE_ENERGY)

            else:
                self.ensure_ok(self.creep.withdraw(storage, RESOURCE_ENERGY, self.creep.carryCapacity / 2
                                                   - self.creep.carry.energy), "withdraw", storage,
                               RESOURCE_ENERGY)
            self.report((["balancing"], True))
            return False

        self.home.links.note_link_manager(self)

        return False

    def ensure_ok(self, result, action, p1, p2):
        # TODO: nicer messages for running out of energy, and also saying if this was a transfer or withdraw, from a
        # link or storage.
        if result != OK:
            self.log("ERROR: Unknown result from link creep.{}({},{}): {}!".format(action, p1, p2, result))

    def ensure_no_minerals(self):
        storage = self.home.room.storage
        if _.sum(self.creep.carry) > self.creep.carry.energy:
            for rtype in Object.keys(self.creep.carry):
                if rtype != RESOURCE_ENERGY:
                    self.ensure_ok(self.creep.transfer(storage, rtype), "transfer", storage, rtype)
                    return True
        return False

    def send_to_link(self, amount=None):
        storage = self.home.room.storage
        link = self.home.links.main_link

        if not amount or amount > self.creep.carryCapacity / 2:
            amount = self.creep.carryCapacity / 2
        if amount > link.energyCapacity - link.energy:
            amount = link.energyCapacity - link.energy
        if link.energy == link.energyCapacity:
            return

        self.ensure_ok(self.creep.transfer(link, RESOURCE_ENERGY, amount), "transfer", link, RESOURCE_ENERGY)
        self.ensure_ok(self.creep.withdraw(storage, RESOURCE_ENERGY, amount), "withdraw", link, RESOURCE_ENERGY)

    def send_from_link(self, amount=None):
        storage = self.home.room.storage
        link = self.home.links.main_link

        if not amount or amount > self.creep.carryCapacity / 2:
            amount = self.creep.carryCapacity / 2
        if amount > link.energy:
            amount = link.energy
        if link.energy == 0:
            return
        self.ensure_ok(self.creep.withdraw(link, RESOURCE_ENERGY, amount), "withdraw", link, RESOURCE_ENERGY)
        self.ensure_ok(self.creep.transfer(storage, RESOURCE_ENERGY, amount), "transfer", link, RESOURCE_ENERGY)

    def _calculate_time_to_replace(self):
        # TODO: maybe merge this logic with DedicatedMiner?
        link = self.home.links.main_link
        if not link:
            return -1
        link_pos = link.pos
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, link_pos)
        return movement.path_distance(self.home.spawn, link_pos) + _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(LinkManager, ["run_creep", "run_links"])


# TODO: Change the speech on this to something unique.
class Cleanup(SpawnFill):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_cleanup
            return False
        storage = self.creep.room.storage

        if self.memory.filling and _.sum(self.creep.carry) >= self.creep.carryCapacity:
            self.memory.filling = False

        if not self.memory.filling and _.sum(self.creep.carry) <= 0:
            self.memory.filling = True

        if self.memory.filling:
            # TODO: Make some cached memory map of all hostile creeps, and use it to avoid.
            resources = self.room.find(FIND_DROPPED_RESOURCES)
            if len(resources):
                closest = None
                closest_distance = Infinity
                for resource in resources:
                    if len(self.room.find_in_range(FIND_HOSTILE_CREEPS, 3, resource.pos)) == 0:

                        if self.memory.last_energy_target:
                            compressed_pos = resource.pos.x | (resource.pos.y << 6)
                            if compressed_pos == self.memory.last_energy_target:
                                closest = resource
                                break
                        if (resource.amount > 50 or
                                    len(self.room.find_in_range(FIND_SOURCES, 1, resource.pos)) == 0):

                            # we've confirmed now that this is a valid target! congrats.
                            distance = movement.distance_squared_room_pos(self.creep.pos, resource.pos)
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

            if not self.creep.pos.isNearTo(pile.pos):
                self.move_to(pile)
                self.report(speech.cleanup_found_energy, pile.pos.x, pile.pos.y)
                return False

            result = self.creep.pickup(pile)

            if result == OK:
                self.report(speech.link_manager_ok)
            elif result == ERR_FULL:
                self.memory.filling = False
                return True
            else:
                self.log("Unknown result from cleanup-creep.pickup({}): {}", pile, result)
                self.report(speech.link_manager_unknown_result)
        else:
            if not storage:
                # self.log("Cleanup can't find storage in {}!", self.creep.room.name)
                # self.go_to_depot()
                # self.report(speech.link_manager_something_not_found)
                # return False
                return SpawnFill.run(self)

            if self.creep.pos.roomName != storage.pos.roomName:
                self.move_to(storage)
                self.report(speech.remote_hauler_moving_to_storage)
                return False

            if _.sum(self.creep.carry) > self.creep.carry.energy:
                target = storage
            else:
                target = self.targets.get_new_target(self, target_closest_energy_site)
                if not target:
                    target = storage
            # if target.energy >= target.energyCapacity:
            #     target = storage
            if target.structureType == STRUCTURE_LINK:
                self.home.links.register_target_deposit(target, self, self.creep.carry.energy,
                                                        self.creep.pos.getRangeTo(target.pos))

            if not self.creep.pos.isNearTo(target.pos):
                if self.creep.pos.isNearTo(storage):
                    # being blocked by a link manager to get to the link
                    target = storage
                    self.last_target = storage
                else:
                    self.move_to(target)
                    self.report(speech.remote_hauler_moving_to_storage, target.structureType)
                    return False

            resource_type = _.find(Object.keys(self.creep.carry), lambda r: self.creep.carry[r] > 0)
            result = self.creep.transfer(target, resource_type)
            if result == OK:
                self.report(speech.link_manager_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.filling = True
                return True
            elif result == ERR_FULL:
                if target == storage:
                    self.log("Storage in room {} full!", storage.room.name)
                self.report(speech.link_manager_storage_full)
            else:
                self.log("Unknown result from cleanup-creep.transfer({}, {}): {}", target, resource_type, result)
                self.report(speech.link_manager_unknown_result)

    def _calculate_time_to_replace(self):
        return 0  # Don't live-replace


profiling.profile_whitelist(Cleanup, ["run"])
