import math

import spawning
import speech
from constants import role_cleanup, role_local_hauler, role_remote_hauler, recycle_time, role_recycling, \
    target_closest_energy_site
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class LinkManager(RoleBase):
    def run(self):
        link = self.home.links.main_link
        storage = self.home.room.storage
        if not link or not storage:
            self.log("ERROR: Link manager can't find main link or storage in {}.".format(self.room.room_name))
            self.go_to_depot()
            self.report(speech.link_manager_something_not_found)
            return False
        # TODO: this could go quite wrong if there are more than two squares between the storage and the main link.
        if not self.creep.pos.isNearTo(link):
            self.move_to(link)
            self.report(speech.link_manager_moving)
            return False
        elif not self.creep.pos.isNearTo(storage):
            self.move_to(storage)
            self.report(speech.link_manager_moving)
            return False

        self.memory.stationary = True

        if self.ensure_no_minerals():
            return False

        if self.creep.carry.energy != self.creep.carryCapacity / 2:
            # this is not the norm.
            if self.creep.carry.energy > self.creep.carryCapacity / 2:
                self.ensure_ok(self.creep.transfer(storage, RESOURCE_ENERGY, self.creep.carry.energy
                                                   - self.creep.carryCapacity / 2), "transfer", storage,
                               RESOURCE_ENERGY)
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

        self.ensure_ok(self.creep.transfer(link, RESOURCE_ENERGY, amount), "transfer", link, RESOURCE_ENERGY)
        self.ensure_ok(self.creep.withdraw(storage, RESOURCE_ENERGY, amount), "withdraw", link, RESOURCE_ENERGY)

    def send_from_link(self, amount=None):
        storage = self.home.room.storage
        link = self.home.links.main_link

        if not amount or amount > self.creep.carryCapacity / 2:
            amount = self.creep.carryCapacity / 2

        self.ensure_ok(self.creep.withdraw(link, RESOURCE_ENERGY, amount), "withdraw", link, RESOURCE_ENERGY)
        self.ensure_ok(self.creep.transfer(storage, RESOURCE_ENERGY, amount), "transfer", link, RESOURCE_ENERGY)

    def _calculate_time_to_replace(self):
        # TODO: maybe merge this logic with DedicatedMiner?
        link = self.home.links.main_link
        if not link:
            return -1
        link_pos = link.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, link_pos)
        return movement.path_distance(spawn_pos, link_pos) + RoleBase._calculate_time_to_replace(self)


profiling.profile_whitelist(LinkManager, ["run_creep", "run_links"])


# TODO: Change the speech on this to something unique.
class Cleanup(SpawnFill):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_cleanup
            return False
        storage = self.creep.room.storage

        if self.memory.gathering and _.sum(self.creep.carry) >= self.creep.carryCapacity:
            self.memory.gathering = False

        if not self.memory.gathering and _.sum(self.creep.carry) <= 0:
            self.memory.gathering = True

        if self.memory.gathering:
            # TODO: Make some cached memory map of all hostile creeps, and use it to avoid.
            resources = self.room.find(FIND_DROPPED_RESOURCES)
            if len(resources):
                closest = None
                closest_distance = math.pow(2, 30)
                for resource in resources:
                    if len(self.room.find_in_range(FIND_HOSTILE_CREEPS, 3, resource.pos)) == 0:
                        creeps = self.room.find_at(FIND_MY_CREEPS, resource.pos)
                        any_stationary = False
                        for creep in creeps:
                            if creep.memory and creep.memory.stationary:
                                any_stationary = True
                                break
                        if not any_stationary:
                            # we've confirmed now that this is a valid target! congrats.
                            distance = movement.distance_squared_room_pos(self.creep.pos, resource.pos)
                            if distance < closest_distance:
                                closest = resource
                                closest_distance = distance
                pile = closest
            else:
                pile = None
            # This is the old code which is completely equivalent to the above, but much less optimized, and does not do
            # any caching of "find" results like the RoomMind.find_* functions do.
            # pile = self.creep.pos.findClosestByRange(FIND_DROPPED_RESOURCES, {
            #     "filter": lambda s: len(
            #         _.filter(s.pos.lookFor(LOOK_CREEPS), lambda c: c.memory and c.memory.stationary is True)
            #     ) == 0 and len(s.pos.findInRange(FIND_HOSTILE_CREEPS, 3)) == 0
            # })

            if not pile:
                extra_cleanup = self.home.extra_creeps_with_carry_in_role(role_cleanup,
                                                                          self.home.get_target_cleanup_mass() + 1)
                if len(extra_cleanup) and self.name in extra_cleanup:
                    if self.home.carry_mass_of(role_local_hauler) < self.home.get_target_local_hauler_mass():
                        self.memory.role = role_local_hauler
                        # in case we have multiple cleanup looking at this.
                        # TODO: utility method for this in RoomMind
                        self.home.carry_mass_map[role_local_hauler] += spawning.carry_count(self)
                        self.home.mem.meta.clear_next = 0  # clear next tick
                        return False
                    if self.home.carry_mass_of(role_remote_hauler) < self.home.get_target_remote_hauler_mass():
                        self.memory.role = role_remote_hauler
                        # in case we have multiple cleanup looking at this.
                        # TODO: utility method for this in RoomMind
                        self.home.carry_mass_map[role_remote_hauler] += spawning.carry_count(self)
                        self.home.mem.meta.clear_next = 0  # clear next tick
                        return False
                    self.memory.role = role_recycling
                    self.memory.last_role = role_cleanup
                    # TODO: utility method for this kind of thing.
                    if role_cleanup in self.home.role_counts:
                        self.home.role_counts[role_cleanup] -= 1
                        self.home.carry_mass_map[role_cleanup] -= spawning.carry_count(self)
                    if role_recycling in self.home.role_counts:
                        self.home.role_counts[role_recycling] += 1
                        self.home.carry_mass_map[role_recycling] += spawning.carry_count(self)
                    return
                if _.sum(self.creep.carry) >= 0:
                    self.memory.gathering = False
                self.go_to_depot()  # wait
                return

            if not self.creep.pos.isNearTo(pile.pos):
                self.move_to(pile)
                self.report(speech.cleanup_found_energy, pile.pos.x, pile.pos.y)
                return False

            result = self.creep.pickup(pile)

            if result == OK:
                self.report(speech.link_manager_ok)
            elif result == ERR_FULL:
                self.memory.gathering = False
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
                target = self.target_mind.get_new_target(self, target_closest_energy_site)
                if not target:
                    target = storage
            # if target.energy >= target.energyCapacity:
            #     target = storage
            if target.structureType == STRUCTURE_LINK and self.creep.pos.inRangeTo(target, 2):
                self.home.links.register_target_deposit(target, self, self.creep.carry.energy)

            if not self.creep.pos.isNearTo(target.pos):
                if self.creep.pos.isNearTo(storage):
                    # being blocked by a link manager to get to the link
                    target = storage
                    self.last_target = storage
                else:
                    self.move_to(target)
                    self.report(speech.remote_hauler_moving_to_storage, target.structureType)
                    return False

            self.memory.stationary = True

            resource_type = Object.keys(self.creep.carry)[0]
            result = self.creep.transfer(target, resource_type)
            if result == OK:
                self.report(speech.link_manager_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.gathering = True
                return True
            elif result == ERR_FULL:
                self.log("Storage in room {} full!", storage.room)
                self.report(speech.link_manager_storage_full)
            else:
                self.log("Unknown result from cleanup-creep.transfer({}, {}): {}", target, resource_type, result)
                self.report(speech.link_manager_unknown_result)


profiling.profile_whitelist(Cleanup, ["run"])
