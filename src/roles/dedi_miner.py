import speech
from constants import target_big_source, target_source_local_hauler, target_closest_deposit_site, role_dedi_miner
from role_base import RoleBase
from utils import movement
from utils.screeps_constants import *

__pragma__('noalias', 'name')

_MOVE_ARGS = {"use_roads": True}


class DedicatedMiner(RoleBase):
    def run(self):
        source = self.target_mind.get_new_target(self.creep, target_big_source)

        if not source:
            print("[{}] Dedicated miner could not find any new big sources.".format(self.name))
            self.recycle_me()
            return

        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source)  #, False, _MOVE_ARGS) # TODO: WHY DOES THIS MAKE THE CREEP AVOID ROADS? WHY?
            self.report(speech.dedi_miner_moving)
            return False

        self.memory.stationary = True
        if not self.memory.action_start_time:
            self.memory.action_start_time = Game.time
        result = self.creep.harvest(source)
        if result == OK:
            if Memory.dedicated_miners_stationed:
                Memory.dedicated_miners_stationed[source.id] = self.name
            else:
                Memory.dedicated_miners_stationed = {
                    source.id: self.name
                }
            self.report(speech.dedi_miner_ok)
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
            self.report(speech.dedi_miner_ner)
        else:
            print("[{}] Unknown result from mining-creep.harvest({}): {}".format(
                self.name, source, result
            ))
            self.report(speech.dedi_miner_unknown_result)

        return False

    def _calculate_time_to_replace(self):
        source = self.target_mind.get_new_target(self.creep, target_big_source)
        if not source:
            return -1
        source_pos = source.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        time = movement.path_distance(spawn_pos, source_pos, True) + RoleBase._calculate_time_to_replace(self)
        # print("[{}] Calculated dedi-miner replacement time (using {} to {}): {}".format(
        #     self.name, spawn_pos, source_pos, time
        # ))
        return time


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class LocalHauler(RoleBase):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget_all(self.creep)

        if self.memory.harvesting:
            source = self.target_mind.get_new_target(self.creep, target_source_local_hauler)

            if not source:
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                self.go_to_depot()
                self.report(speech.local_hauler_no_source)
                return False
            miner_name = Memory.dedicated_miners_stationed[source.id]
            miner = Game.creeps[miner_name]
            if miner:
                target_pos = miner.pos
                self.memory.stored_miner_position = miner.pos
            elif self.memory.stored_miner_position:
                temp_pos = self.memory.stored_miner_position
                target_pos = __new__(RoomPosition(temp_pos.x, temp_pos.y, temp_pos.roomName))
            else:
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                if miner_name and not miner:
                    del Memory.dedicated_miners_stationed[source.id]
                    Memory.meta.clear_now = True
                    self.report(speech.local_hauler_no_miner, miner_name)
                else:
                    self.report(speech.local_hauler_no_miner_name, source.id[-4:])
                self.go_to_depot()
                self.target_mind.untarget(self.creep, target_source_local_hauler)
                return False

            if not self.creep.pos.isNearTo(target_pos):
                self.move_to(target_pos)
                self.pick_up_available_energy()
                self.report(speech.local_hauler_moving_to_miner)
                return False

            self.memory.stationary = True

            piles = target_pos.lookFor(LOOK_RESOURCES, {"filter": {"resourceType": RESOURCE_ENERGY}})
            if not len(piles):
                if len(self.creep.pos.findInRange(FIND_MY_CREEPS, 2,
                                                  {"filter": {"memory": {"role": role_dedi_miner}}})):
                    self.go_to_depot()
                    return False
                if not miner:
                    del self.memory.stored_miner_position
                self.report(speech.local_hauler_waiting)
                return False

            result = self.creep.pickup(piles[0])

            if result == OK:
                self.report(speech.local_hauler_pickup_ok)
            elif result == ERR_FULL:
                self.memory.harvesting = False
                return True
            else:
                print("[{}] Unknown result from hauler-creep.pickup({}): {}".format(
                    self.name, source, result
                ))
                self.report(speech.local_hauler_pickup_unknown_result)

            return False
        else:
            storage = self.creep.room.storage
            if not storage:
                print("[{}] Local hauler can't find storage in {}!".format(self.name, self.creep.room.name))
                self.go_to_depot()
                self.report(speech.local_hauler_no_storage)
                return False

            target = self.target_mind.get_new_target(self.creep, target_closest_deposit_site)
            if target.energy >= target.energyCapacity:
                target = storage

            if not self.creep.pos.isNearTo(target.pos):
                self.move_to(target)
                self.report(speech.local_hauler_moving_to_storage)
                return False

            self.memory.stationary = True

            result = self.creep.transfer(target, RESOURCE_ENERGY)
            if result == OK:
                self.report(speech.local_hauler_transfer_ok)
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == ERR_FULL:
                print("[{}] {} in room {} full!".format(self.name, target, target.pos.roomName))
                self.go_to_depot()
                self.report(speech.local_hauler_storage_full)
            else:
                print("[{}] Unknown result from hauler-creep.transfer({}): {}".format(
                    self.name, target, result
                ))
                self.report(speech.local_hauler_transfer_unknown_result)

            return False
