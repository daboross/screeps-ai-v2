import flags
import speech
from constants import target_remote_mine_miner, target_remote_mine_hauler, target_closest_energy_site, role_remote_miner
from goals.transport import TransportPickup
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class RemoteMiner(RoleBase):
    def run(self):
        source_flag = self.target_mind.get_new_target(self, target_remote_mine_miner)
        if not source_flag:
            self.log("Remote miner can't find any sources!")
            if self.home.role_count(role_remote_miner) > self.home.get_target_remote_miner_count():
                self.recycle_me()
            else:
                self.go_to_depot()
            self.report(speech.remote_miner_no_flag)
            return False
        if source_flag.memory.sponsor != self.home.room_name:
            self.log("Remote miner currently targeting foreign mine! Mine: {}, sponsor: {}, home: {},"
                     " home.targeting: {}. Adjusting home accordingly!".format(source_flag, source_flag.memory.sponsor,
                                                                               self.home.room_name,
                                                                               self.home.remote_mining_operations))
            self.memory.home = source_flag.memory.sponsor

        source_flag.memory.remote_miner_targeting = self.name

        if not self.creep.pos.isNearTo(source_flag.pos):
            self.move_to(source_flag, False, True)
            self.report(speech.remote_miner_moving)
            return False

        self.memory.stationary = True
        sources_list = source_flag.pos.lookFor(LOOK_SOURCES)
        if not len(sources_list):
            self.log("Remote mining source flag {} has no sources under it!", source_flag.name)
            self.report(speech.remote_miner_flag_no_source)
            return False

        sitting = _.sum(self.room.find_in_range(FIND_DROPPED_RESOURCES, 1, source_flag.pos), 'amount')
        source_flag.memory.energy_sitting = sitting
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
        source = self.target_mind.get_new_target(self, target_remote_mine_miner)
        if not source:
            return -1
        source_pos = source.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, source_pos)
        return movement.path_distance(spawn_pos, source_pos, True) + _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(RemoteMiner, ["run"])


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class RemoteHauler(SpawnFill, TransportPickup):
    def run(self):
        pickup = self.target_mind.get_new_target(self, target_remote_mine_hauler)

        if not pickup:
            if not self.empty_to_storage():
                self.go_to_depot()
            return

        if _.sum(self.creep.carry) > self.creep.carry.energy:
            fill = self.home.room.storage
        else:
            if (Game.time - self.creep.ticksToLive) % 15:
                # Every so often (with an ofset for this creep), retarget.
                self.target_mind.untarget(self, target_closest_energy_site)
            fill = self.target_mind.get_new_target(self, target_closest_energy_site, pickup.pos)

        if not fill:
            fill = self.home.spawn
            if self.pos.roomName == fill.pos.roomName and _.sum(self.creep.carry) >= self.creep.carryCapacity:
                return SpawnFill.run(self)

        return self.transport(pickup, fill)

    def _calculate_time_to_replace(self):
        return _.size(self.creep.body) * 3 + 15  # Don't live-replace as often.


profiling.profile_whitelist(RemoteHauler, ["run"])


class RemoteReserve(RoleBase):
    def find_claim_room(self):
        claim_room = self.memory.claiming
        if claim_room:
            return claim_room
        if not Memory.reserving:
            Memory.reserving = {}

        second_best = None
        for op_flag in self.home.remote_mining_operations:
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
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, target_pos)
        return movement.path_distance(spawn_pos, target_pos) + _.size(self.creep.body) * 3 + 15


profiling.profile_whitelist(RemoteReserve, ["run"])
