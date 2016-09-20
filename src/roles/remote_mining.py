import flags
import speech
from constants import target_remote_mine_miner, target_remote_mine_hauler, target_closest_energy_site, \
    role_remote_hauler, role_remote_miner, role_recycling, role_upgrader
from goals.transport import TransportPickup
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')
__pragma__('noalias', 'undefined')
__pragma__('noalias', 'Infinity')


# TODO: abstract path movement out of TransportPickup into a higher class.
class RemoteMiner(TransportPickup):
    def run(self):
        source_flag = self.targets.get_existing_target(self, target_remote_mine_miner)
        if not source_flag:
            self.log("WARNING: Getting new remote mine for remote miner!")
            source_flag = self.targets.get_new_target(self, target_remote_mine_miner)
        if not source_flag:
            self.log("Remote miner can't find any sources! Flag: {}".format(source_flag))
            self.memory.role = role_recycling
            self.memory.last_role = role_remote_miner
            self.report(speech.remote_miner_no_flag)
            return False
        if source_flag.memory.sponsor != self.home.room_name:
            self.memory.home = source_flag.memory.sponsor

        source_flag.memory.remote_miner_targeting = self.name

        if self.creep.hits < self.creep.hitsMax and (self.pos.roomName != self.home.room_name
                                                     or self.pos.x > 40 or self.pos.y > 40
                                                     or self.pos.x < 10 or self.pos.y < 10):
            self.follow_energy_path(source_flag, self.home.spawn)
            return
        if not self.creep.pos.isNearTo(source_flag.pos):
            if self.pos.roomName == source_flag.pos.roomName:
                if self.pos.getRangeTo(source_flag.pos) <= 5:
                    other_miner = _.find(self.room.find_in_range(FIND_MY_CREEPS, 1, source_flag.pos),
                                         lambda c: c.getActiveBodyparts(WORK) >= 5
                                                   and c.ticksToLive < self.creep.ticksToLive)
                    if other_miner:
                        other_miner.suicide()
                        del self.memory._move
                self.creep.moveTo(source_flag, {'ignoreCreeps': True})
            else:
                self.follow_energy_path(self.home.spawn, source_flag)
            self.report(speech.remote_miner_moving)
            return False
        if 'container_pos' not in self.memory:
            container = _.find(self.room.find_in_range(FIND_STRUCTURES, 1, source_flag.pos),
                               lambda s: s.structureType == STRUCTURE_CONTAINER)
            if container:
                self.memory.container_pos = container.pos.x | (container.pos.y << 6)
            else:
                biggest_pile = _.max(self.room.find_in_range(FIND_DROPPED_RESOURCES, 1, source_flag.pos),
                                     lambda e: e.amount)
                if biggest_pile != -Infinity:
                    self.memory.container_pos = biggest_pile.pos.x | (biggest_pile.pos.y << 6)
                else:
                    self.memory.container_pos = None
        this_pos_to_check = self.pos.x | self.pos.y << 6  # Transcrypt does this incorrectly in an if statement.
        if self.memory.container_pos and this_pos_to_check != self.memory.container_pos:
            self.basic_move_to(__new__(RoomPosition(self.memory.container_pos & 0x3F,
                                                    self.memory.container_pos >> 6 & 0x3F, self.pos.roomName)))

        sources_list = self.room.find_at(FIND_SOURCES, source_flag.pos)
        if not len(sources_list):
            self.log("Remote mining source flag {} has no sources under it!", source_flag.name)
            self.report(speech.remote_miner_flag_no_source)
            return False

        result = self.creep.harvest(sources_list[0])
        if result == OK:
            self.report(speech.remote_miner_ok)
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            self.report(speech.remote_miner_ner)
        else:
            self.log("Unknown result from remote-mining-creep.harvest({}): {}", source_flag, result)
            self.report(speech.remote_miner_unknown_result)

        return False

    def _calculate_time_to_replace(self):
        source = self.targets.get_new_target(self, target_remote_mine_miner)
        if not source:
            return -1
        path = self.hive.honey.find_path(self.home.spawn, source)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, source_pos)
        return len(path) + _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(RemoteMiner, ["run"])


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class RemoteHauler(SpawnFill, TransportPickup):
    def run(self):
        pickup = self.targets.get_existing_target(self, target_remote_mine_hauler)
        if not pickup:
            self.log("WARNING: Getting new remote mine for remote hauler!")
            self.targets.untarget(self, target_closest_energy_site)
            pickup = self.targets.get_new_target(self, target_remote_mine_hauler)

        if not pickup:
            self.memory.role = role_recycling
            self.memory.last_role = role_remote_hauler
            return

        if _.sum(self.creep.carry) > self.creep.carry.energy:
            fill = self.home.room.storage
        else:
            fill = self.home.mining.closest_deposit_point_to_mine(pickup)
            if fill and fill.energy >= fill.energyCapacity and fill.structureType == STRUCTURE_LINK and \
                    not self.home.links.enabled:
                fill = self.home.room.storage  # Just temporary, since we know a link manager will spawn eventually.

            if fill and fill.pos.getRangeTo(self.home.room.controller) <= 3.0 \
                    and self.home.role_count(role_upgrader) > 3:
                fill = self.home.room.storage  # if there's a large upgrader party, let's not stop there.

        if not fill:
            self.log("WARNING: Couldn't find fill site!")
            if self.home.room.storage:
                fill = self.home.room.storage
            elif self.home.spawn:
                fill = self.home.spawn
            else:
                self.log("WARNING: Remote hauler in room with no storage nor spawn!")
                return
            if fill == self.home.spawn and self.pos.roomName == fill.pos.roomName \
                    and not self.memory.filling:
                return SpawnFill.run(self)

        return self.transport(pickup, fill)

    def _calculate_time_to_replace(self):
        source = self.targets.get_new_target(self, target_remote_mine_hauler)
        if not source:
            return -1
        path = self.hive.honey.find_path(self.home.spawn, source)
        # TODO: find a good time here by calculating exactly how many trips we'll make before we drop.
        return len(path) * 1.7 + _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(RemoteHauler, ["run"])


class RemoteReserve(TransportPickup):
    def find_claim_room(self):
        claim_room = self.memory.claiming
        if claim_room:
            if Memory.reserving[claim_room] != self.name:
                if Memory.reserving[claim_room] in Game.creeps:
                    creep = Game.creeps[Memory.reserving[claim_room]]
                    if not creep.spawning:
                        if self.creep.ticksToLive > creep.ticksToLive:
                            Memory.reserving[claim_room] = self.name
                        elif self.pos.roomName != claim_room or \
                                        creep.pos.getRangeTo(self.creep.room.controller.pos) < 4:
                            self.creep.suicide()
                else:
                    Memory.reserving[claim_room] = self.name
            return claim_room
        self.log("WARNING: Calculating new reserve target for remote mining reserver!")
        if not Memory.reserving:
            Memory.reserving = {}

        lowest_time = Infinity
        best = None
        for op_flag in self.home.mining.active_mines:
            creep = Game.creeps[Memory.reserving[op_flag.pos.roomName]]
            if creep and creep.ticksToLive > 200:
                continue
            if Memory.no_controller and Memory.no_controller[op_flag.pos.roomName]:
                continue
            room = Game.rooms[op_flag.pos.roomName]
            if room and not room.controller:
                if Memory.no_controller:
                    Memory.no_controller[op_flag.pos.roomName] = True
                else:
                    Memory.no_controller = {op_flag.pos.roomName: True}
                continue
            time = room and room.controller.reservation and room.controller.reservation.ticksToEnd or 0
            if creep:
                time += creep.ticksToLive * (creep.getActiveBodyparts(CLAIM) - 1)
            if time >= 4999:
                continue
            if time < lowest_time:
                lowest_time = time
                best = op_flag.pos.roomName

        if best:
            Memory.reserving[best] = self.name
            self.memory.claiming = best
        return best

    def run(self):
        claim_room = self.find_claim_room()
        if not claim_room:
            self.creep.suicide()
            return

        if Game.rooms[claim_room] and not Game.rooms[claim_room].controller:
            del self.memory.claiming
            return True

        if self.creep.pos.roomName != claim_room:
            if Game.rooms[claim_room]:
                target = Game.rooms[claim_room].controller.pos
            else:
                target = __new__(RoomPosition(25, 25, claim_room))
            self.follow_energy_path(self.home.spawn, target)
            return

        controller = self.room.room.controller

        if controller.reservation and controller.reservation.ticksToEnd > 4999:
            if self.creep.pos.isNearTo(controller.pos):
                self.creep.suicide()
                return False
            else:
                del self.memory.claiming
                return True

        if not self.creep.pos.isNearTo(controller.pos):
            self.move_to(controller)
            return False

        if controller.reservation and controller.reservation.username != self.creep.owner.username:
            self.log("Remote reserve creep target owned by another player! {} has taken our reservation!",
                     controller.reservation.username)
        else:
            if len(flags.find_flags(controller.room, flags.CLAIM_LATER)):
                # claim this!
                self.creep.claimController(controller)
                controller.room.memory.sponsor = self.home.room_name
            else:
                self.creep.reserveController(controller)
                if controller.reservation:
                    controller.room.memory.rea = Game.time + controller.reservation.ticksToEnd
                else:
                    controller.room.memory.rea = Game.time + self.creep.getActiveBodyparts(CLAIM)

    def _calculate_time_to_replace(self):
        room = self.find_claim_room()
        if not room:
            return -1
        if Game.rooms[room]:
            target_pos = Game.rooms[room].controller.pos
        else:
            return -1
        path = self.hive.honey.find_path(self.home.spawn, target_pos)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, target_pos)
        return len(path) + _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(RemoteReserve, ["run"])
