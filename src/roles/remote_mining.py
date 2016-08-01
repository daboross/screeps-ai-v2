import speach
from constants import target_remote_mine_miner, target_remote_mine_hauler, target_remote_reserve, \
    target_closest_deposit_site
from role_base import RoleBase
from utils.screeps_constants import *

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

        if not source_flag:
            print("[{}] Remote miner can't find any sources!".format(self.name))
            self.go_to_depot()
            self.report(speach.remote_miner_no_flag)
            return False

        if not self.creep.pos.isNearTo(source_flag.pos):
            self.move_to(source_flag)
            self.report(speach.remote_miner_moving)
            return False

        self.memory.stationary = True
        sources_list = source_flag.pos.lookFor(LOOK_SOURCES)
        if not len(sources_list):
            print("[{}] Remote mining source flag {} has no sources under it!".format(self.name, source_flag.name))
            self.report(speach.remote_miner_flag_no_source)
            return False

        result = self.creep.harvest(sources_list[0])
        if result == OK:
            self.report(speach.remote_miner_ok)
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            self.report(speach.remote_miner_ner)
        else:
            print("[{}] Unknown result from remote-mining-creep.harvest({}): {}".format(
                self.name, source_flag, result
            ))
            self.report(speach.remote_miner_unknown_result)

        return False


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class RemoteHauler(RoleBase):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            source_flag = self.target_mind.get_new_target(self.creep, target_remote_mine_hauler)

            if not source_flag:
                # TODO: Re-enable after we get auto-respawning things *before* they die
                # print("[{}] Remote hauler can't find any sources!".format(self.name))
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                self.report(speach.remote_hauler_no_source)
                self.go_to_depot()
                return False

            miner = Game.creeps[source_flag.memory.remote_miner_targeting]
            if not miner:
                print("[{}] Remote hauler can't find remote miner!".format(self.name))
                Memory.meta.clear_now = True
                self.report(speach.remote_hauler_source_no_miner)
                self.target_mind.untarget(self.creep, target_remote_mine_hauler)
                return True

            if not self.creep.pos.isNearTo(miner.pos):
                if miner.pos.roomName == self.creep.pos.roomName and not miner.memory.stationary:
                    self.go_to_depot()
                    return False
                self.move_to(miner)
                maybe_energy = self.creep.pos.lookFor(LOOK_RESOURCES, {"filter": {"resourceType": RESOURCE_ENERGY}})
                if len(maybe_energy):
                    self.creep.pickup(maybe_energy[0])
                self.report(speach.remote_hauler_moving_to_miner)
                return False

            piles = miner.pos.lookFor(LOOK_RESOURCES, {"filter": {"resourceType": RESOURCE_ENERGY}})
            if not len(piles):
                self.report(speach.remote_hauler_ner)
                return False

            result = self.creep.pickup(piles[0])

            if result == OK:
                self.report(speach.remote_hauler_pickup_ok)
            elif result == ERR_FULL:
                self.memory.harvesting = False
                return True
            else:
                print("[{}] Unknown result from hauler-creep.pickup({}): {}".format(
                    self.name, source_flag, result
                ))
                self.report(speach.remote_hauler_pickup_unknown_result)

            return False
        else:
            storage = self.home.room.storage
            if not storage:
                print("[{}] Remote hauler can't find storage in home room: {}!".format(self.name, self.memory.home))
                self.go_to_depot()
                self.report(speach.remote_hauler_no_home_storage)
                return False

            if self.creep.pos.roomName != storage.pos.roomName:
                self.move_to(storage)
                self.report(speach.remote_hauler_moving_to_storage)
                return False

            target = self.target_mind.get_new_target(self.creep, target_closest_deposit_site)
            if target.energy >= target.energyCapacity:
                target = storage

            if not self.creep.pos.isNearTo(target.pos):
                self.move_to(target)
                self.report(speach.remote_hauler_moving_to_storage)
                return False

            result = self.creep.transfer(target, RESOURCE_ENERGY)
            if result == OK:
                self.report(speach.remote_hauler_transfer_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == ERR_FULL:
                print("[{}] {} in room {} full!".format(self.name, target, target.pos.roomName))
                self.go_to_depot()
                self.report(speach.remote_hauler_storage_full)
            else:
                print("[{}] Unknown result from hauler-creep.transfer({}): {}".format(
                    self.name, target, result
                ))
                self.report(speach.remote_hauler_transfer_unknown_result)

            return False


class RemoteReserve(RoleBase):
    def run(self):
        controller = self.target_mind.get_new_target(self.creep, target_remote_reserve)

        if not controller:
            print("[{}] Remote reserve couldn't find controller open!".format(self.name))
            self.go_to_depot()
            return

        if not self.creep.pos.isNearTo(controller.pos):
            self.move_to(controller)
            self.report(speach.remote_reserve_moving)
            return False

        self.memory.stationary = True
        if not self.memory.action_start_time:
            self.memory.action_start_time = Game.time

        if controller.reservation and controller.reservation.username != self.creep.owner.username:
            print("[{}] Remote reserve creep target owned by another player! {} has taken our reservation!".format(
                self.name, controller.reservation.username
            ))
        if not controller.reservation or controller.reservation.ticksToEnd < 5000:
            self.creep.reserveController(controller)
            self.report(speach.remote_reserve_reserving)
