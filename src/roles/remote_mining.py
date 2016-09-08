import flags
import speech
from constants import target_remote_mine_miner, target_remote_mine_hauler, target_closest_energy_site, \
    role_remote_hauler, role_remote_miner, role_recycling
from goals.transport import TransportPickup
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


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

        if not self.creep.pos.isNearTo(source_flag.pos):
            if self.pos.roomName == source_flag.pos.roomName:
                self.move_to(source_flag)
            else:
                self.follow_energy_path(self.home.spawn, source_flag.pos)
            self.report(speech.remote_miner_moving)
            return False

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
        path = self.home.honey.find_path(self.home.spawn, source)
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
            fill = self.targets.get_new_target(self, target_closest_energy_site, pickup.pos)
            if fill and fill.energy >= fill.energyCapacity and fill.structureType == STRUCTURE_LINK and \
                    not self.home.links.enabled:
                fill = self.home.room.storage  # Just temporary, since we know a link manager will spawn eventually.

        if not fill:
            self.log("WARNING: Couldn't find fill site!")
            fill = self.home.spawn
            if self.pos.roomName == fill.pos.roomName and _.sum(self.creep.carry) >= self.creep.carryCapacity:
                return SpawnFill.run(self)

        return self.transport(pickup, fill)

    def _calculate_time_to_replace(self):
        source = self.targets.get_new_target(self, target_remote_mine_hauler)
        if not source:
            return -1
        path = self.home.honey.find_path(self.home.spawn, source)
        # TODO: find a good time in a better way!
        return len(path) * 1.7 + _.size(self.creep.body) * 3 + 15  # Don't live-replace as often.


profiling.profile_whitelist(RemoteHauler, ["run"])


class RemoteReserve(RoleBase):
    def find_claim_room(self):
        claim_room = self.memory.claiming
        if claim_room:
            return claim_room
        self.log("WARNING: Calculating new reserve target for remote mining reserver!")
        if not Memory.reserving:
            Memory.reserving = {}

        second_best = None
        for op_flag in self.home.mining.available_mines:
            if Game.creeps[Memory.reserving[op_flag.pos.roomName]]:
                continue
            if Memory.no_controller and Memory.no_controller[op_flag.pos.roomName]:
                continue
            if Game.rooms[op_flag.pos.roomName] and not Game.rooms[op_flag.pos.roomName].controller:
                if Memory.no_controller:
                    Memory.no_controller[op_flag.pos.roomName] = True
                else:
                    Memory.no_controller = {op_flag.pos.roomName: True}
                continue
            if op_flag.remote_miner_targeting:
                Memory.reserving[op_flag.pos.roomName] = self.name
                self.memory.claiming = op_flag.pos.roomName
                return op_flag.pos.roomName
            else:
                second_best = op_flag.pos.roomName

        if second_best:
            Memory.reserving[second_best] = self.name
        self.memory.claiming = second_best
        return second_best

    def run(self):
        claim_room = self.find_claim_room()
        if not claim_room:
            self.go_to_depot()
            return

        if Game.rooms[claim_room] and not Game.rooms[claim_room].controller:
            del self.memory.claiming
            return True

        if self.creep.pos.roomName != claim_room:
            if Game.rooms[claim_room]:
                self.move_to(Game.rooms[claim_room].controller)
            else:
                self.move_to(__new__(RoomPosition(25, 25, claim_room)))
            self.report(speech.remote_reserve_moving)
            return

        controller = self.room.room.controller

        if controller.reservation and controller.reservation.ticksToEnd > 4900:
            del self.memory.claiming
            return True

        if not self.creep.pos.isNearTo(controller.pos):
            self.move_to(controller)
            return

        if controller.reservation and controller.reservation.username != self.creep.owner.username:
            self.log("Remote reserve creep target owned by another player! {} has taken our reservation!",
                     controller.reservation.username)
        if not controller.reservation or controller.reservation.ticksToEnd < 5000:
            if len(flags.find_flags(controller.room, flags.CLAIM_LATER)):
                # claim this!
                self.creep.claimController(controller)
                controller.room.memory.sponsor = self.home.room_name
            else:
                self.creep.reserveController(controller)
            self.report(speech.remote_reserve_reserving)

    def _calculate_time_to_replace(self):
        room = self.find_claim_room()
        if not room:
            return -1
        if Game.rooms[room]:
            target_pos = Game.rooms[room].controller.pos
        else:
            return -1
        path = self.home.honey.find_path(self.home.spawn, target_pos)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, target_pos)
        return len(path) + _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(RemoteReserve, ["run"])
