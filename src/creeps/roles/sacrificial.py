from typing import Optional, cast

from constants import recycle_time, role_recycling, role_sacrificial_cleanup
from constants.memkeys.room import mem_key_sell_all_but_empty_resources_to
from creeps.behaviors.military import MilitaryBase
from creeps.behaviors.refill import Refill
from jstools.screeps import *
from utilities import movement, positions

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')
__pragma__('noalias', 'update')
__pragma__('noalias', 'values')


class Sacrifice(MilitaryBase):
    def get_colony(self):
        if not self.memory.target:
            self.log("WARNING: sacrificial has no target room!")
            self.memory.target = self.home.mem[mem_key_sell_all_but_empty_resources_to]
        return self.memory.target

    def run(self):
        if not self.memory.filling and self.carry_sum() <= 0:
            self.memory.filling = True
        elif self.memory.filling and self.carry_sum() >= self.creep.carryCapacity:
            self.memory.filling = False

        if self.memory.filling:
            return self.harvest_energy()
        else:
            target = self.get_colony()

            if self.creep.room.name == target:
                del self.memory.target
                del self.memory.calculated_replacement_time

                self.memory.home = target
                self.memory.last_role = "sacrifice"
                self.memory.role = role_recycling
            else:
                self.follow_military_path(self.home.spawn.pos, movement.center_pos(target), {'range': 15})

    def _calculate_time_to_replace(self):
        colony = self.get_colony()
        path_len = self.get_military_path_length(self.home.spawn.pos, movement.center_pos(colony), {'range': 15})
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * CREEP_SPAWN_TIME + 10


class SacrificialCleanup(Refill):
    def run(self):
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_sacrificial_cleanup
            return False

        if self.memory.filling and self.carry_sum() >= self.creep.carryCapacity:
            self.memory.filling = False
        elif not self.memory.filling and self.carry_sum() <= 0:
            self.memory.filling = True

        if self.memory.filling:
            target = None
            if self.memory.target:
                target = cast(Optional[Resource], self.room.look_at(LOOK_RESOURCES,
                                                                    positions.deserialize_xy_to_pos(self.memory.target,
                                                                                                    self.room.name))[0])

            if not target:
                resources = self.room.find(FIND_DROPPED_RESOURCES)
                closest_distance = Infinity
                for resource in resources:
                    if len(self.room.find_in_range(FIND_HOSTILE_CREEPS, 3, resource.pos)) == 0:
                        if len(self.room.find_in_range(FIND_SOURCES, 1, resource.pos)) == 0:
                            # we've confirmed now that this is a valid target! congrats.
                            distance = movement.distance_squared_room_pos(self.pos, resource.pos)
                            if distance < closest_distance:
                                target = resource
                                closest_distance = distance
                self.memory.target = positions.serialize_pos_xy(target.pos)

            if not target:
                self.log("sacrificial cleanup found no energy, recycling.")
                self.memory.role = role_recycling
                self.memory.last_role = role_sacrificial_cleanup
                return

            if self.pos.isNearTo(target):
                result = self.creep.pickup(target)

                if result == ERR_FULL:
                    self.memory.filling = False
                    return True
                elif result != OK:
                    self.log("Unknown result from cleanup-creep.pickup({}): {}", target, result)
            else:
                self.move_to(target)
                return False
        else:
            target = self.creep.room.storage
            if not target:
                return self.refill_creeps()

            if self.pos.roomName != target.pos.roomName:
                self.move_to(target)
                return False

            if self.pos.isNearTo(target):
                resource = _.findKey(self.creep.carry)

                result = self.creep.transfer(target, resource)
                if result == ERR_NOT_ENOUGH_RESOURCES:
                    self.memory.filling = True
                    return True
                elif result == ERR_FULL:
                    self.log("Storage in room {} full!", target.room.name)
                elif result != OK:
                    self.log("Unknown result from cleanup-creep.transfer({}, {}): {}", target, resource, result)
            else:
                self.move_to(target)
            return False

    def _calculate_time_to_replace(self):
        return 0  # Don't live-replace
