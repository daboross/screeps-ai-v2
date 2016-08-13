import math

import speech
from constants import role_cleanup, role_local_hauler, role_remote_hauler
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class LinkManager(RoleBase):
    def run(self):
        if self.run_creep():
            if self.run_creep():
                if self.run_creep():
                    self.log("Link manager tried to rerun three times!")
        self.run_links()
        return False

    def run_creep(self):
        storage = self.creep.room.storage
        if not storage:
            self.log("Link manager can't find storage in {}!", self.creep.room.name)
            self.go_to_depot()
            self.report(speech.link_manager_something_not_found)
            return False

        if self.memory.gathering_from_link and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.gathering_from_link = False

        if not self.memory.gathering_from_link and self.creep.carry.energy <= 0:
            self.memory.gathering_from_link = True

        if self.memory.gathering_from_link:
            link = self.get_storage_link()

            if not self.creep.pos.isNearTo(link.pos):
                self.pick_up_available_energy()
                self.move_to(link)
                self.report(speech.link_manager_moving)
                return False

            if link.energy <= 0:
                if self.creep.carry.energy > 0:
                    self.memory.gathering_from_link = False
                    return True
                return False

            self.memory.stationary = True

            result = self.creep.withdraw(link, RESOURCE_ENERGY)

            if result == OK:
                self.report(speech.link_manager_ok)
            elif result == ERR_FULL:
                self.memory.gathering_from_link = False
            else:
                self.log("Unknown result from link-manager-creep.withdraw({}): {}", link, result)
                self.report(speech.link_manager_unknown_result)
        else:
            if not self.creep.pos.isNearTo(storage.pos):
                self.pick_up_available_energy()
                self.move_to(storage)
                self.report(speech.link_manager_moving)
                return False

            self.memory.stationary = True

            result = self.creep.transfer(storage, RESOURCE_ENERGY)
            if result == OK:
                self.report(speech.link_manager_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.gathering_from_link = True
                return True
            elif result == ERR_FULL:
                self.log("Storage in room {} full!", storage.room)
                self.report(speech.link_manager_storage_full)
            else:
                self.log("Unknown result from link-manager-creep.transfer({}): {}", storage, result)
                self.report(speech.link_manager_unknown_result)

        return False

    def get_storage_link(self):
        link = None
        if self.memory.target_link:
            link = Game.getObjectById(self.memory.target_link)

        if not link:
            link = self.room.find_closest_by_range(FIND_STRUCTURES, self.creep.pos, {"structureType": STRUCTURE_LINK})
            if not link:
                if self.creep.carry.energy > 0:
                    self.memory.gathering_from_link = False
                    return True
                self.log("Link-storage manager can't find link in {}!", self.creep.room.name)
                self.go_to_depot()
                self.report(speech.link_manager_something_not_found)
                return False
            self.memory.target_link = link.id
        return link

    def run_links(self):
        my_link = self.get_storage_link()
        if not my_link or my_link.energy >= my_link.energyCapacity:
            return
        for link in self.room.find(FIND_STRUCTURES):
            if link.structureType == STRUCTURE_LINK:
                # TODO: is a minimum like this ever helpful?
                if link.id != self.memory.gathering_from_link and link.cooldown <= 0 \
                        and (link.energy > link.energyCapacity / 4 or (link.energy > 0 >= my_link.energy)):
                    link.transferEnergy(my_link)

    def _calculate_time_to_replace(self):
        # TODO: maybe merge this logic with DedicatedMiner?
        link = self.get_storage_link()
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
            # This is the old code which is completely equivalent to the above, but much less optimized, and does not do any
            # caching of "find" results like the RoomMind.find_* functions do.
            # pile = self.creep.pos.findClosestByRange(FIND_DROPPED_RESOURCES, {
            #     "filter": lambda s: len(
            #         _.filter(s.pos.lookFor(LOOK_CREEPS), lambda c: c.memory and c.memory.stationary is True)
            #     ) == 0 and len(s.pos.findInRange(FIND_HOSTILE_CREEPS, 3)) == 0
            # })

            if not pile:
                if self.home.get_target_cleanup_count() + 1 < self.home.role_count(role_cleanup):
                    # The creep with the lowest lifetime left should die.
                    next_to_die = self.home.next_x_to_die_of_role(
                        role_cleanup,
                        self.home.role_count(role_cleanup) - 1 - self.home.get_target_cleanup_count())
                    if self.name in next_to_die:
                        if self.home.role_count(role_local_hauler) < self.home.get_target_local_hauler_count():
                            self.memory.role = role_local_hauler
                            self.home.mem.meta.clear_next = 0  # clear next tick
                            return False
                        if self.home.role_count(role_remote_hauler) < self.home.get_target_remote_hauler_count():
                            self.memory.role = role_remote_hauler
                            self.home.mem.meta.clear_next = 0  # clear next tick
                            return False
                        self.recycle_me()
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
                self.log("Unknown result from link-manager-creep.pickup({}): {}", pile, result)
                self.report(speech.link_manager_unknown_result)
        else:
            if not storage:
                return SpawnFill.run(self)
                # self.log("Cleanup can't find storage in {}!", self.creep.room.name)
                # self.go_to_depot()
                # self.report(speech.link_manager_something_not_found)
                # return False
            if not self.creep.pos.isNearTo(storage.pos):
                self.move_to(storage)
                self.report(speech.link_manager_moving)
                return False

            self.memory.stationary = True

            resource_type = Object.keys(self.creep.carry)[0]
            result = self.creep.transfer(storage, resource_type)
            if result == OK:
                self.report(speech.link_manager_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.gathering = True
                return True
            elif result == ERR_FULL:
                self.log("Storage in room {} full!", storage.room)
                self.report(speech.link_manager_storage_full)
            else:
                self.log("Unknown result from link-manager-creep.transfer({}, {}): {}", storage, resource_type, result)
                self.report(speech.link_manager_unknown_result)


profiling.profile_whitelist(Cleanup, ["run"])
