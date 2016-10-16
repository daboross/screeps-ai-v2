import context
import flags
import role_base
import speech
from constants import role_builder, role_upgrader, role_recycling, target_reserve_now, role_simple_claim, \
    role_mineral_steal
from goals.transport import TransportPickup
from roles.offensive import MilitaryBase
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
            for room in self.home.subsidiaries:
                if not len(room.spawns) and _.sum(room.role_counts) < 3:
                    distance = movement.distance_squared_room_pos(self.creep.pos,
                                                                  __new__(RoomPosition(25, 25, room.room_name)))
                    if distance < closest_distance:
                        closest_room_name = room.room_name

            if not closest_room_name:
                for room in self.home.subsidiaries:
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
            sponsor = self.home
            self.memory.home = colony
            del self.memory.calculated_replacement_time
            room = self.hive.get_room(colony)
            storage = room.room.storage
            if storage and not storage.my:
                if _.sum(storage.store) > 0:
                    enemy_storage_exhausted = False
                else:
                    enemy_storage_exhausted = True
                    storage.destroy()
            else:
                enemy_storage_exhausted = True
            if room.role_count(role_upgrader) < 1 and not room.upgrading_paused():
                self.memory.role = role_upgrader
            elif (enemy_storage_exhausted and (room.rcl >= 5 or room.rcl >= sponsor.rcl)) \
                    or room.mem.prio_spawn or room.mem.prio_walls:
                self.memory.role = role_builder
            else:
                self.memory.role = role_upgrader
            meta = self.hive.get_room(colony).mem.meta
            if meta:
                meta.clear_next = 0  # clear next tick
        else:
            self.follow_military_path(self.home.spawn, __new__(RoomPosition(25, 25, colony)), {'range': 15})

    def _calculate_time_to_replace(self):
        colony = self.get_colony()
        path_len = self.get_military_path_length(self.home.spawn, __new__(RoomPosition(25, 25, colony)), {'range': 15})
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


profiling.profile_whitelist(Colonist, ["run"])


class Claim(MilitaryBase):
    def run(self):
        if not self.memory.claiming:
            # TODO: turn this into a target for TargetMind
            closest_distance = Infinity
            closest_room = None
            for flag in flags.find_flags_global(flags.CLAIM_LATER):
                room = context.hive().get_room(flag.pos.roomName)
                if not room or (not room.my and not room.room.controller.owner):
                    # claimable:
                    distance = movement.chebyshev_distance_room_pos(self.creep.pos, __new__(RoomPosition(
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
            target = __new__(RoomPosition(25, 25, self.memory.claiming))
            if movement.chebyshev_distance_room_pos(self.pos, target) > 50:
                if 'checkpoint' not in self.memory or \
                                movement.chebyshev_distance_room_pos(self.memory.checkpoint, self.pos) > 50:
                    self.memory.checkpoint = self.pos

                opts = {'range': 15}
                if self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) * 5 / 7:
                    opts.ignore_swamp = True
                    opts.use_roads = False
                elif self.creep.getActiveBodyparts(MOVE) >= len(self.creep.body) / 2:
                    opts.use_roads = False
                self.follow_military_path(_.create(RoomPosition.prototype, self.memory.checkpoint), target, opts)
            else:
                self.creep.moveTo(target, {'reusePath': 2, 'ignoreRoads': True,
                                           "costCallback": role_base.def_cost_callback})
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
        room = self.hive.get_room(target.pos.roomName)
        room.mem.sponsor = self.home.room_name
        if _.get(flags.find_flags(room, flags.CLAIM_LATER)[0], 'memory.prio_walls', False):
            room.mem.prio_walls = True
        if _.get(flags.find_flags(room, flags.CLAIM_LATER)[0], 'memory.prio_spawn', False):
            room.mem.prio_spawn = True

    def _calculate_time_to_replace(self):
        return 0


class ReserveNow(MilitaryBase):
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
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


# TODO: abstract path movement out of TransportPickup into a higher class.
class MineralSteal(TransportPickup):
    def get_colony(self):
        if not self.memory.colonizing:
            closest_distance = Infinity
            closest_room_name = None
            for room in self.hive.my_rooms:
                if room.room.storage and room.room.storage.storeCapacity <= 0 \
                        and _.sum(room.room.storage.store) > room.room.storage.store.energy:
                    distance = movement.distance_squared_room_pos(self.creep.pos,
                                                                  __new__(RoomPosition(25, 25, room.room_name)))
                    if distance < closest_distance:
                        closest_room_name = room.room_name

            if not closest_room_name:
                return None

            # Colonize!
            self.memory.colonizing = closest_room_name
        return self.memory.colonizing

    def run(self):
        colony_name = self.get_colony()
        colony = self.hive.get_room(colony_name)
        if not colony:
            self.memory.role = role_recycling
            self.memory.last_role = role_mineral_steal
            return
        pickup = colony.room.storage

        fill = self.home.room.storage

        return self.transport(pickup, fill)

    def _calculate_time_to_replace(self):
        # TODO: find a good time in a better way!
        return _.size(self.creep.body) * 3 + 15  # Don't live-replace as often.


profiling.profile_whitelist(MineralSteal, ["run"])
