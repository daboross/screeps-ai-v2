from constants import target_remote_mine_miner, target_remote_mine_hauler, target_remote_reserve
from role_base import RoleBase
from screeps_constants import *

__pragma__('noalias', 'name')

_MOVE_OPTIONS = {"maxRooms": 1, "ignoreCreeps": True}


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
            return False

        if not self.creep.pos.isNearTo(source_flag.pos):
            self.move_to(source_flag, False, _MOVE_OPTIONS)
            self.report("RM. Moving.")
            return False

        sources_list = source_flag.pos.lookFor(LOOK_SOURCES)
        if not len(sources_list):
            print("[{}] Remote mining source flag {} has no sources under it!".format(self.name, source_flag.name))
            return False

        result = self.creep.harvest(sources_list[0])
        if result == OK:
            self.report("RM. Mining.")
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            self.report("RM. WW.")
        else:
            print("[{}] Unknown result from remote-mining-creep.harvest({}): {}".format(
                self.name, source_flag, result
            ))
            self.report("RM. ???")

        return False


class RemoteHauler(RoleBase):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            source_flag = self.target_mind.get_new_target(self.creep, target_remote_mine_hauler)

            if not source_flag:
                print("[{}] Remote hauler can't find any sources!".format(self.name))
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                self.report("RH. N. S.")
                self.go_to_depot()
                return False

            miner = Game.creeps[source_flag.memory.remote_miner_targeting]
            if not miner:
                print("[{}] Remote hauler can't find remote miner!".format(self.name))
                self.report("RH. N. M.")
                self.target_mind.untarget(self.creep, target_remote_mine_hauler)
                return True

            if not self.creep.pos.isNearTo(miner.pos):
                self.move_to(miner, False, _MOVE_OPTIONS)
                self.report("RH. Move.")
                return False

            piles = miner.pos.lookFor(LOOK_RESOURCES, {"filter": {"resourceType": RESOURCE_ENERGY}})
            if not len(piles):
                self.report("RH. WW.")
                return True

            result = self.creep.pickup(piles[0])

            if result == OK:
                self.report("RH. Collect!")
            elif result == ERR_FULL:
                self.memory.harvesting = False
                return True
            else:
                print("[{}] Unknown result from hauler-creep.pickup({}): {}".format(
                    self.name, source_flag, result
                ))
                self.report("RH. ???")

            return False
        else:
            storage = self.home.room.storage
            if not storage:
                print("[{}] Remote hauler can't find storage in home room: {}!".format(self.name, self.memory.home))
                self.go_to_depot()
                return False

            if not self.creep.pos.isNearTo(storage.pos):
                self.move_to(storage, False, _MOVE_OPTIONS)
                self.report("RH. Haul.")
                return False

            result = self.creep.transfer(storage, RESOURCE_ENERGY)
            if result == OK:
                self.report("RH. Store.")
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == ERR_FULL:
                print("[{}] Storage in room {} full!".format(self.name, storage.room))
                self.go_to_depot()
                self.report("RH. Full!!")
            else:
                print("[{}] Unknown result from hauler-creep.transfer({}): {}".format(
                    self.name, storage, result
                ))
                self.report("RH. ???")

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
            self.report("R.R. F. C.")
            return False

        if not self.memory.currently_upgrading and (not controller.reservation
                                                    or controller.reservation.ticksToEnd < 4000):
            self.memory.currently_upgrading = True
        elif self.memory.currently_upgrading and controller.reservation and controller.reservation.ticksToEnd > 5000:
            self.memory.currently_upgrading = False

        if self.memory.currently_upgrading:
            if controller.reservation and controller.reservation.username != self.creep.owner.username:
                print("[{}] Remote reserve creep target owned by another player! {} has taken our reservation!".format(
                    self.name, controller.reservation.username
                ))
            self.creep.reserveController(controller)
            self.report("R.R. C. C.")
