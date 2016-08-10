import speech
from constants import target_big_source, target_source, role_dedi_miner, target_closest_deposit_site
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_MOVE_ARGS = {"use_roads": True}


class DedicatedMiner(RoleBase):
    def run(self):
        source = self.target_mind.get_new_target(self.creep, target_big_source)

        if not source:
            self.log("Dedicated miner could not find any new big sources.")
            self.recycle_me()
            return

        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source)
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
            self.log("Unknown result from mining-creep.harvest({}): {}", source, result)
            self.report(speech.dedi_miner_unknown_result)

        return False

    def _calculate_time_to_replace(self):
        source = self.target_mind.get_new_target(self.creep, target_big_source)
        if not source:
            return -1
        source_pos = source.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        time = movement.path_distance(spawn_pos, source_pos, True) + RoleBase._calculate_time_to_replace(self)
        # self.log("Calculated dedi-miner replacement time (using {} to {}): {}", spawn_pos, source_pos, time)
        return time


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class LocalHauler(SpawnFill):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget_all(self.creep)

        if self.memory.harvesting:
            source = self.target_mind.get_new_target(self.creep, target_source)

            if not source:
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                self.go_to_depot()
                self.report(speech.local_hauler_no_source)
                return False
            miner_name = Memory.dedicated_miners_stationed and Memory.dedicated_miners_stationed[source.id]
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
                self.target_mind.untarget(self.creep, target_source)
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
                self.log("Unknown result from hauler-creep.pickup({}): {}", source, result)
                self.report(speech.local_hauler_pickup_unknown_result)

            return False
        else:
            storage = self.creep.room.storage
            if not storage:
                # self.log("Local hauler can't find storage in {}!", self.creep.room.name)
                # self.go_to_depot()
                # self.report(speech.local_hauler_no_storage)
                # return False
                return SpawnFill.run(self)

            target = self.target_mind.get_new_target(self.creep, target_closest_deposit_site)
            if not target:
                target = self.creep.room.storage  # This apparently has happened, I don't know why though?
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
                self.log("{} in room {} full!", target, target.pos.roomName)
                self.go_to_depot()
                self.report(speech.local_hauler_storage_full)
            else:
                self.log("Unknown result from hauler-creep.transfer({}): {}", target, result)
                self.report(speech.local_hauler_transfer_unknown_result)

            return False
