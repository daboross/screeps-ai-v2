import flags
import speech
from constants import target_remote_mine_miner, target_remote_mine_hauler, target_remote_reserve, \
    target_closest_deposit_site, role_remote_hauler, role_cleanup, role_recycling
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
            self.recycle_me()
            self.report(speech.remote_miner_no_flag)
            return False
        if source_flag.memory.sponsor != self.home.room_name:
            self.log("Remote miner currently targeting foreign mine! Mine: {}, sponsor: {}, home: {},"
                     " home.targeting: {}. Adjusting home accordingly!".format(source_flag, source_flag.memory.sponsor,
                                                                               self.home.room_name,
                                                                               self.home.remote_mining_operations))
            self.memory.home = source_flag.memory.sponsor

        if not self.creep.pos.isNearTo(source_flag.pos):
            self.move_to(source_flag)
            self.report(speech.remote_miner_moving)
            return False

        source_flag.memory.remote_miner_targeting = self.name
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
        return movement.path_distance(spawn_pos, source_pos, True) + RoleBase._calculate_time_to_replace(self)


profiling.profile_whitelist(RemoteMiner, ["run"])


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class RemoteHauler(SpawnFill):
    def run(self):
        source_flag = self.target_mind.get_new_target(self, target_remote_mine_hauler)

        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self)

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            if source_flag and self.creep.ticksToLive < 2.2 * self.home.distance_storage_to_mine(source_flag):
                self.memory.role = role_recycling
                return False
            self.memory.harvesting = True
            self.target_mind.untarget_all(self)

        if self.memory.harvesting:
            if not source_flag:
                # TODO: Re-enable after we get auto-respawning things *before* they die
                # self.log("Remote hauler can't find any sources!")
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                extra_haulers = self.home.extra_creeps_with_carry_in_role(
                    role_remote_hauler, self.home.get_target_remote_hauler_mass())
                if len(extra_haulers) and self.name in extra_haulers:
                    self.memory.role = role_cleanup
                    self.home.mem.meta.clear_next = 0  # TODO: method in RoomMind to re-register as another role.
                self.report(speech.remote_hauler_no_source)
                if self.creep.ticksToLive < 200:  # TODO: is this a good number?
                    self.recycle_me()
                else:
                    self.go_to_depot()
                return False

            if source_flag.memory.sponsor != self.home.room_name:
                self.log("Remote hauler currently targeting foreign mine! Mine: {}, sponsor: {}, home: {}."
                         "Adjusting home accordingly!".format(source_flag, source_flag.memory.sponsor,
                                                              self.home.room_name))
                self.memory.home = source_flag.memory.sponsor
            miner = Game.creeps[source_flag.memory.remote_miner_targeting]
            target_pos = None
            if self.creep.pos.roomName == source_flag.pos.roomName:
                piles = self.room.find_in_range(FIND_DROPPED_ENERGY, 1, source_flag.pos)
                if len(piles):
                    _.sortBy(piles, 'amount')
                    target_pos = piles[0].pos
                    if not miner:
                        # Update this here.
                        source_flag.memory.energy_sitting = _.sum(piles, 'amount')
                else:
                    source_flag.memory.energy_sitting = 0
                    if miner:
                        target_pos = miner.pos
            else:
                target_pos = source_flag.pos
            if not target_pos:
                self.log("Remote hauler can't find remote miner at {}! Miner name: {}!", source_flag,
                         source_flag.memory.remote_miner_targeting)
                if source_flag.memory.remote_miner_targeting and not \
                        Game.creeps[source_flag.memory.remote_miner_targeting]:
                    del source_flag.memory.remote_miner_targeting
                self.home.mem.meta.clear_next = 0  # clear next tick
                self.report(speech.remote_hauler_source_no_miner)
                self.target_mind.untarget(self, target_remote_mine_hauler)
                return True

            self.pick_up_available_energy()
            if not self.creep.pos.isNearTo(source_flag) and not self.creep.pos.isNearTo(target_pos):
                if miner and not miner.memory.stationary and target_pos.roomName == miner.pos.roomName:
                    self.memory.go_to_depot_until = Game.time + 20
                    self.go_to_depot()
                    return False
                elif self.memory.go_to_depot_until:
                    if Game.time > self.memory.go_to_depot_until:
                        del self.memory.go_to_depot_until
                    else:
                        self.go_to_depot()
                        return False
                if _.sum(self.creep.carry, 'amount') / self.creep.carryCapacity >= 0.75:
                    self.memory.harvesting = False
                    if self.creep.pos.roomName == source_flag.pos.roomName:
                        self.last_checkpoint = source_flag  # follow the reverse path back
                    else:
                        # best guess as to where we would have come into the room.
                        self.last_checkpoint = movement.get_exit_flag_to(self.creep.pos.roomName,
                                                                         source_flag.pos.roomName)
                    return True
                # TODO: should we really be targeting the source flag, or should we target the miner if he's here?
                self.move_to(source_flag, False, True)
                self.report(speech.remote_hauler_moving_to_miner)
                return False
            self.last_checkpoint = source_flag
            if not self.creep.pos.isNearTo(target_pos):
                self.move_to(target_pos, False, True)
                self.report(speech.remote_hauler_moving_to_miner)  # TODO: different message here
                return False
            self.memory.stationary = True

            piles = target_pos.lookFor(LOOK_RESOURCES, {"filter": {"resourceType": RESOURCE_ENERGY}})
            if not len(piles):
                self.report(speech.remote_hauler_ner)
                return False

            result = self.creep.pickup(piles[0])

            if result == OK:
                self.report(speech.remote_hauler_pickup_ok)
            elif result == ERR_FULL:
                self.memory.harvesting = False
                return True
            else:
                self.log("Unknown result from hauler-creep.pickup({}): {}", source_flag, result)
                self.report(speech.remote_hauler_pickup_unknown_result)

            return False
        else:
            storage = self.home.room.storage
            if not storage:
                # self.recycle_me()
                # self.report(speech.remote_hauler_no_home_storage)
                # return False
                return SpawnFill.run(self)

            if self.creep.pos.roomName != storage.pos.roomName:
                self.move_to(storage, False, True)
                self.report(speech.remote_hauler_moving_to_storage)
                return False

            target = self.target_mind.get_new_target(self, target_closest_deposit_site)
            if not target:
                target = storage
            if target.energy >= target.energyCapacity:
                target = storage

            if not self.creep.pos.isNearTo(target.pos):
                if self.creep.pos.isNearTo(storage):
                    # being blocked by a link manager to get to the link
                    target = storage
                    self.last_target = storage
                else:
                    self.move_to(target, False, True)
                    self.report(speech.remote_hauler_moving_to_storage, target.structureType)
                    return False

            self.last_checkpoint = storage.pos
            self.memory.stationary = True

            result = self.creep.transfer(target, RESOURCE_ENERGY)
            if result == OK:
                self.report(speech.remote_hauler_transfer_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == ERR_FULL:
                self.log("{} in room {} full!", target, target.pos.roomName)
                self.go_to_depot()
                self.report(speech.remote_hauler_storage_full)
            else:
                self.log("Unknown result from hauler-creep.transfer({}): {}", target, result)
                self.report(speech.remote_hauler_transfer_unknown_result)

            return False


profiling.profile_whitelist(RemoteHauler, ["run"])


class RemoteReserve(RoleBase):
    def run(self):
        controller = self.target_mind.get_new_target(self, target_remote_reserve)

        if not controller:
            self.log("Remote reserve couldn't find controller open!")
            self.recycle_me()
            return

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
        controller = self.target_mind.get_new_target(self, target_remote_reserve)
        if not controller:
            return -1
        target_pos = controller.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # self.log("Calculating replacement time using distance from {} to {}", spawn_pos, target_pos)
        return movement.path_distance(spawn_pos, target_pos) + RoleBase._calculate_time_to_replace(self)


profiling.profile_whitelist(RemoteReserve, ["run"])
