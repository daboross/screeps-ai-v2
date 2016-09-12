import context
import flags
import speech
from constants import role_builder, role_upgrader, role_recycling, target_reserve_now, role_simple_claim
from role_base import RoleBase
from roles.military import MilitaryBase
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


class Colonist(MilitaryBase):
    def get_colony(self):
        if not self.memory.colonizing:
            closest_distance = Infinity
            closest_room_name = None
            for room in self.hive.my_rooms:
                if not len(room.spawns) and _.sum(room.role_counts) < 3:
                    distance = movement.distance_squared_room_pos(self.creep.pos,
                                                                  __new__(RoomPosition(25, 25, room.room_name)))
                    if distance < closest_distance:
                        closest_room_name = room.room_name

            if not closest_room_name:
                for room in self.hive.my_rooms:
                    if not len(room.spawns):
                        distance = movement.distance_squared_room_pos(self.creep.pos,
                                                                      __new__(RoomPosition(25, 25, room.room_name)))
                        if distance < closest_distance:
                            closest_room_name = room.room_name

            # Colonize!
            self.memory.colonizing = closest_room_name
        return self.memory.colonizing

    def run(self):
        colony = self.get_colony()

        if self.creep.room.name == colony:
            del self.memory.colonizing
            self.memory.home = colony
            room = self.hive.get_room(colony)
            if room.role_count(role_builder) < 2:
                self.memory.role = role_builder
            elif room.role_count(role_upgrader) < 1 and not room.upgrading_paused():
                self.memory.role = role_upgrader
            else:
                self.memory.role = role_builder
            meta = self.hive.get_room(colony).mem.meta
            if meta:
                meta.clear_next = 0  # clear next tick
        else:
            self.follow_military_path(self.home.spawn, __new__(RoomPosition(25, 25, colony)), {'range': 15})

    def _calculate_time_to_replace(self):
        colony = self.get_colony()
        path = self.get_military_path(self.home.spawn, __new__(RoomPosition(25, 25, colony)), {'range': 15})
        if self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) / 2:
            path_len = len(path)
        else:
            path_len = len(path) * 2
        return path_len + _.size(self.creep.body) * 3 + 10


profiling.profile_whitelist(Colonist, ["run"])


class Claim(RoleBase, MilitaryBase):
    def run(self):
        if not self.memory.claiming:
            # TODO: turn this into a target for TargetMind
            closest_distance = Infinity
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
            self.follow_military_path(self.home.spawn, __new__(RoomPosition(25, 25, self.memory.claiming)),
                                      {'range': 15})
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

    def _calculate_time_to_replace(self):
        return 0


class ReserveNow(RoleBase, MilitaryBase):
    def run(self):
        reserve_flag = self.targets.get_new_target(self, target_reserve_now)

        if not reserve_flag:
            self.log("ReserveNow couldn't find controller to reserve.")
            self.recycle_me()
            return False

        if self.creep.pos.roomName != reserve_flag.pos.roomName:
            self.follow_military_path(self.home.spawn, reserve_flag)
            return False

        controller = self.creep.room.controller

        if not self.creep.pos.isNearTo(controller.pos):
            self.move_to(controller)
            self.report(speech.remote_reserve_moving)
            return False

        if controller.reservation and controller.reservation.username != self.creep.owner.username:
            self.log("Remote reserve creep target owned by another player! {} has taken our reservation!",
                     controller.reservation.username)
        if not controller.reservation or controller.reservation.ticksToEnd < 4998:
            if len(flags.find_flags(controller.room, flags.CLAIM_LATER)):
                # claim this!
                self.creep.claimController(controller)
                controller.room.memory.sponsor = self.home.room_name
            self.creep.reserveController(controller)
            self.report(speech.remote_reserve_reserving)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_reserve_now)
        if not target:
            return -1
        path = self.get_military_path(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) / 2:
            path_len = len(path)
        else:
            path_len = len(path) * 2
        return path_len + _.size(self.creep.body) * 3 + 10
