import math

import context
import flags
import speech
from constants import role_builder, role_upgrader, role_recycling, target_reserve_now, role_simple_claim
from role_base import RoleBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class Colonist(RoleBase):
    def run(self):
        if not self.memory.colonizing:
            closest_distance = math.pow(2, 30)
            closest_room_name = None
            for room in context.hive().my_rooms:
                if not len(room.spawns) and _.sum(room.role_counts) < 3:
                    distance = movement.distance_squared_room_pos(self.creep.pos,
                                                                  __new__(RoomPosition(25, 25, room.room_name)))
                    if distance < closest_distance:
                        closest_room_name = room.room_name

            # Colonize!
            self.memory.colonizing = closest_room_name

        colony = self.memory.colonizing

        if self.creep.room.name == colony:
            del self.memory.colonizing
            self.memory.home = colony
            room = context.hive().get_room(colony)
            if room.role_count(role_builder) < 2:
                self.memory.role = role_builder
            elif room.role_count(role_upgrader) < 1:
                self.memory.role = role_upgrader
            else:
                self.memory.role = role_builder
            meta = context.hive().get_room(colony).mem.meta
            if meta:
                meta.clear_next = 0  # clear next tick
        else:
            self.move_to(__new__(RoomPosition(25, 25, colony)))


profiling.profile_whitelist(Colonist, ["run"])


class Claim(RoleBase):
    def run(self):
        if not self.memory.claiming:
            # TODO: turn this into a target for TargetMind
            closest_distance = math.pow(2, 30)
            closest_room = None
            for flag in flags.find_flags_global(flags.CLAIM_LATER):
                room = context.hive().get_room(flag.pos.roomName)
                if not room or (not room.my and not room.room.controller.owner):
                    # claimable:
                    distance = movement.distance_squared_room_pos(self.creep.pos, __new__(RoomPosition(
                        25, 25, flag.pos.roomName)))
                    if distance < closest_distance:
                        closest_distance = distance
                        closest_room = flag.pos.roomName
            if closest_room:
                self.memory.claiming = closest_room
            else:
                self.log("ERROR: Claim can't find room to claim!")
                self.memory.role = role_recycling
                self.memory.last_role = role_simple_claim
                return False

        if self.creep.pos.roomName != self.memory.claiming:
            # TODO: multiroom path caching!
            self.move_to(__new__(RoomPosition(25, 25, self.memory.claiming)))
            return False

        target = self.creep.room.controller
        if not target:
            self.log("ERROR: Claim can't find controller in room {}!".format(self.creep.room.name))
            del self.memory.claiming
            return True

        if target.my:
            self.memory.home = self.creep.room.name
            del self.memory.claiming
            # I guess we can try and claim something else, if we have the life? otherwise this will go and activate the
            # recycle code.
            return True

        if not target.pos.isNearTo(self.creep.pos):
            self.move_to(target)
            return False

        self.creep.claimController(target)
        target.room.memory.sponsor = self.home.room_name


class ReserveNow(RoleBase):
    def run(self):
        reserve_flag = self.target_mind.get_new_target(self, target_reserve_now)

        if not reserve_flag:
            self.log("ReserveNow couldn't find controller to reserve.")
            self.recycle_me()
            return False

        if self.creep.pos.roomName != reserve_flag.pos.roomName:
            self.move_to(reserve_flag)
            # TODO: unique speech
            self.report(speech.remote_reserve_moving)
            return False

        controller = self.creep.room.controller

        if not self.creep.pos.isNearTo(controller.pos):
            self.move_to(controller)
            self.report(speech.remote_reserve_moving)
            return False

        self.memory.stationary = True
        if not self.memory.action_start_time:
            self.memory.action_start_time = Game.time

        if controller.reservation and controller.reservation.username != self.creep.owner.username:
            self.log("Remote reserve creep target owned by another player! {} has taken our reservation!",
                     controller.reservation.username)
        if not controller.reservation or controller.reservation.ticksToEnd < 5000:
            if len(flags.find_flags(controller.room, flags.CLAIM_LATER)):
                # claim this!
                self.creep.claimController(controller)
                controller.room.memory.sponsor = self.home.room_name
            self.creep.reserveController(controller)
            self.report(speech.remote_reserve_reserving)

    def _calculate_time_to_replace(self):
        controller = self.target_mind.get_new_target(self, target_reserve_now)
        if not controller:
            return -1
        target_pos = controller.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, target_pos)
        return movement.path_distance(spawn_pos, target_pos) + RoleBase._calculate_time_to_replace(self)
