import flags
import speech
from constants import target_remote_mine_miner, target_remote_mine_hauler, target_remote_reserve, \
    target_closest_deposit_site
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')


class RemoteMiner(RoleBase):
    def run(self):
        source_flag = self.target_mind.get_existing_target(self.creep, target_remote_mine_miner)
        if not source_flag:
            # use get_existing_target in order to set memory.remote_miner_target exactly once.
            source_flag = self.target_mind.get_new_target(self.creep, target_remote_mine_miner)
            if source_flag:
                source_flag.memory.remote_miner_targeting = self.name
                source_flag.memory.remote_miner_death_tick = Game.time + self.creep.ticksToLive
        elif not source_flag.memory.remote_miner_targeting:
            source_flag.memory.remote_miner_targeting = self.name
            source_flag.memory.remote_miner_death_tick = Game.time + self.creep.ticksToLive
        if not source_flag:
            print("[{}] Remote miner can't find any sources!".format(self.name))
            self.recycle_me()
            self.report(speech.remote_miner_no_flag)
            return False

        if not self.creep.pos.isNearTo(source_flag.pos):
            self.move_to(source_flag)
            self.report(speech.remote_miner_moving)
            return False

        source_flag.memory.remote_miner_targeting = self.name
        self.memory.stationary = True
        sources_list = source_flag.pos.lookFor(LOOK_SOURCES)
        if not len(sources_list):
            print("[{}] Remote mining source flag {} has no sources under it!".format(self.name, source_flag.name))
            self.report(speech.remote_miner_flag_no_source)
            return False

        sitting = _.sum(source_flag.pos.findInRange(FIND_DROPPED_ENERGY, 1), 'amount')
        source_flag.memory.energy_sitting = sitting
        result = self.creep.harvest(sources_list[0])
        if result == OK:
            self.report(speech.remote_miner_ok)
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            self.report(speech.remote_miner_ner)
        else:
            print("[{}] Unknown result from remote-mining-creep.harvest({}): {}".format(
                self.name, source_flag, result
            ))
            self.report(speech.remote_miner_unknown_result)

        return False

    def _calculate_time_to_replace(self):
        source = self.target_mind.get_new_target(self.creep, target_remote_mine_miner)
        if not source:
            return -1
        source_pos = source.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # print("[{}] Calculating replacement time using distance from {} to {}".format(
        #     self.name, spawn_pos, source_pos
        # ))
        return movement.path_distance(spawn_pos, source_pos, True) + RoleBase._calculate_time_to_replace(self)


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class RemoteHauler(SpawnFill):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False
            self.target_mind.untarget_all(self.creep)

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget_all(self.creep)

        if self.memory.harvesting:
            source_flag = self.target_mind.get_new_target(self.creep, target_remote_mine_hauler)

            if not source_flag:
                # TODO: Re-enable after we get auto-respawning things *before* they die
                # print("[{}] Remote hauler can't find any sources!".format(self.name))
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                self.report(speech.remote_hauler_no_source)
                self.recycle_me()
                return False

            miner = Game.creeps[source_flag.memory.remote_miner_targeting]
            target_pos = None
            if self.creep.pos.roomName == source_flag.pos.roomName:
                piles = source_flag.pos.findInRange(FIND_DROPPED_ENERGY, 1)
                if len(piles):
                    _.sortBy(piles, 'amount')
                    target_pos = piles[0].pos
                elif miner:
                    target_pos = miner.pos
            else:
                target_pos = source_flag.pos
            if not target_pos:
                print("[{}] Remote hauler can't find remote miner at {}! Miner name: {}!".format(
                    self.name, source_flag, source_flag.memory.remote_miner_targeting
                ))
                if source_flag.memory.remote_miner_targeting and not \
                        Game.creeps[source_flag.memory.remote_miner_targeting]:
                    del source_flag.memory.remote_miner_targeting
                Memory.meta.clear_now = True
                self.report(speech.remote_hauler_source_no_miner)
                self.target_mind.untarget(self.creep, target_remote_mine_hauler)
                return True

            self.pick_up_available_energy()
            if not self.creep.pos.isNearTo(target_pos):
                if target_pos.roomName == self.creep.pos.roomName and miner and not miner.memory.stationary:
                    self.go_to_depot()
                    return False
                self.move_to(target_pos)
                self.report(speech.remote_hauler_moving_to_miner)
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
                print("[{}] Unknown result from hauler-creep.pickup({}): {}".format(
                    self.name, source_flag, result
                ))
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
                self.move_to(storage)
                self.report(speech.remote_hauler_moving_to_storage)
                return False

            target = self.target_mind.get_new_target(self.creep, target_closest_deposit_site)
            if target.energy >= target.energyCapacity:
                target = storage

            if not self.creep.pos.isNearTo(target.pos):
                self.move_to(target)
                self.report(speech.remote_hauler_moving_to_storage)
                return False

            self.memory.stationary = True

            result = self.creep.transfer(target, RESOURCE_ENERGY)
            if result == OK:
                self.report(speech.remote_hauler_transfer_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == ERR_FULL:
                print("[{}] {} in room {} full!".format(self.name, target, target.pos.roomName))
                self.go_to_depot()
                self.report(speech.remote_hauler_storage_full)
            else:
                print("[{}] Unknown result from hauler-creep.transfer({}): {}".format(
                    self.name, target, result
                ))
                self.report(speech.remote_hauler_transfer_unknown_result)

            return False


class RemoteReserve(RoleBase):
    def run(self):
        controller = self.target_mind.get_new_target(self.creep, target_remote_reserve)

        if not controller:
            print("[{}] Remote reserve couldn't find controller open!".format(self.name))
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
            print("[{}] Remote reserve creep target owned by another player! {} has taken our reservation!".format(
                self.name, controller.reservation.username
            ))
        if not controller.reservation or controller.reservation.ticksToEnd < 5000:
            if len(flags.find_flags(controller.room, flags.CLAIM_LATER)):
                # claim this!
                self.creep.claimController(controller)
                controller.room.memory.sponsor = self.home.room_name
            self.creep.reserveController(controller)
            self.report(speech.remote_reserve_reserving)

    def _calculate_time_to_replace(self):
        controller = self.target_mind.get_new_target(self.creep, target_remote_reserve)
        if not controller:
            return -1
        target_pos = controller.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        # print("[{}] Calculating replacement time using distance from {} to {}".format(
        #     self.name, spawn_pos, target_pos
        # ))
        return movement.path_distance(spawn_pos, target_pos) + RoleBase._calculate_time_to_replace(self)
