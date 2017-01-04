import flags
from constants import CLAIM_LATER, role_builder, role_mineral_steal, role_recycling, role_upgrader, target_reserve_now, \
    target_single_flag, role_tower_fill_once
from goals.transport import TransportPickup
from roles.offensive import MilitaryBase
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')
__pragma__('noalias', 'keys')
__pragma__('noalias', 'get')
__pragma__('noalias', 'set')
__pragma__('noalias', 'type')


class Colonist(MilitaryBase):
    def get_colony(self):
        if not self.memory.colonizing:
            closest_distance = Infinity
            closest_room_name = None
            for room in self.home.subsidiaries:
                if not len(room.spawns) and _.sum(room.role_counts) < 3:
                    distance = movement.distance_squared_room_pos(self.pos, movement.center_pos(room.name))
                    if distance < closest_distance:
                        closest_room_name = room.name

            if not closest_room_name:
                for room in self.home.subsidiaries:
                    if not len(room.spawns):
                        distance = movement.distance_squared_room_pos(self.pos,movement.center_pos(room.name))
                        if distance < closest_distance:
                            closest_room_name = room.name

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
            if _.some(room.defense.towers(), lambda t: t.energy < t.energyCapacity * 0.9):
                self.memory.old_role = self.memory.role
                self.memory.role = role_tower_fill_once
            meta = room.mem.meta
            if meta:
                meta.clear_next = 0  # clear next tick
        else:
            self.follow_military_path(self.home.spawn, movement.center_pos(colony), {'range': 20})

    def _calculate_time_to_replace(self):
        colony = self.get_colony()
        path_len = self.get_military_path_length(self.home.spawn, movement.center_pos(colony), {'range': 20})
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class Claim(MilitaryBase):
    def run(self):
        claim_flag = self.targets.get_new_target(self, target_single_flag, CLAIM_LATER)
        if not claim_flag:
            self.recycle_me()
            return
        if self.pos.roomName != claim_flag.pos.roomName:
            target = claim_flag.pos
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
            return False

        target = self.creep.room.controller
        if not target:
            self.log("ERROR: Claim can't find controller in room {}!".format(self.creep.room.name))
            self.targets.untarget_all(self)
            return True

        if target.my:
            self.memory.home = self.pos.roomName
            self.targets.untarget_all(self)
            # I guess we can try and claim something else, if we have the life? otherwise this will go and activate the
            # recycle code.
            return True

        if not self.pos.isNearTo(target):
            self.move_to(target)
            return False

        if target.owner:
            self.creep.attackController(target)
        else:
            self.creep.claimController(target)
        room = self.hive.get_room(target.pos.roomName)
        room.mem.sponsor = self.home.name
        if _.get(flags.find_flags(room, CLAIM_LATER)[0], 'memory.prio_walls', False):
            room.mem.prio_walls = True
        if _.get(flags.find_flags(room, CLAIM_LATER)[0], 'memory.prio_spawn', False):
            room.mem.prio_spawn = True

    def _calculate_time_to_replace(self):
        if self.creep.getActiveBodyparts(CLAIM) > 1:
            target = self.targets.get_new_target(self, target_single_flag, CLAIM_LATER)
            if not target:
                return -1
            path_len = self.get_military_path_length(self.home.spawn, target)
            return path_len + _.size(self.creep.body) * 3
        else:
            return 0


class ReserveNow(MilitaryBase):
    def run(self):
        reserve_flag = self.targets.get_new_target(self, target_reserve_now)

        if not reserve_flag:
            self.log("ReserveNow couldn't find controller to reserve.")
            self.recycle_me()
            return False

        if self.pos.roomName != reserve_flag.pos.roomName:
            self.follow_military_path(self.home.spawn, reserve_flag)
            return False

        controller = self.creep.room.controller

        if not self.pos.isNearTo(controller):
            self.move_to(controller)
            return False

        if controller.reservation and controller.reservation.username != self.creep.owner.username:
            self.log("Remote reserve creep target owned by another player! {} has taken our reservation!",
                     controller.reservation.username)
        if not controller.reservation or controller.reservation.ticksToEnd < 4998:
            if len(flags.find_flags(controller.room, CLAIM_LATER)):
                # claim this!
                self.creep.claimController(controller)
                controller.room.memory.sponsor = self.home.name
            self.creep.reserveController(controller)

    def _calculate_time_to_replace(self):
        target = self.targets.get_new_target(self, target_reserve_now)
        if not target:
            return -1
        path_len = self.get_military_path_length(self.home.spawn, target)
        if self.creep.getActiveBodyparts(MOVE) < len(self.creep.body) / 2:
            path_len *= 2
        return path_len + _.size(self.creep.body) * 3 + 10


class MineralSteal(TransportPickup):
    def get_colony(self):
        if not self.memory.colonizing:
            closest_distance = Infinity
            closest_room_name = None
            for room in self.hive.my_rooms:
                if room.room.storage and room.room.storage.storeCapacity <= 0 \
                        and _.sum(room.room.storage.store) > room.room.storage.store.energy:
                    distance = movement.distance_squared_room_pos(self.pos, movement.center_pos(room.name))
                    if distance < closest_distance:
                        closest_room_name = room.name

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
