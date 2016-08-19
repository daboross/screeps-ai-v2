import flags
import speech
from constants import target_big_source, target_source, role_dedi_miner, target_closest_energy_site, role_recycling, \
    recycle_time, role_local_hauler
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_MOVE_ARGS = {"use_roads": True}


class DedicatedMiner(RoleBase):
    def run(self):
        source = self.target_mind.get_new_target(self, target_big_source)

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
        source = self.target_mind.get_new_target(self, target_big_source)
        if not source:
            return -1
        source_pos = source.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        time = movement.path_distance(spawn_pos, source_pos, True) + RoleBase._calculate_time_to_replace(self)
        # self.log("Calculated dedi-miner replacement time (using {} to {}): {}", spawn_pos, source_pos, time)
        return time


profiling.profile_whitelist(DedicatedMiner, ["run"])


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class LocalHauler(SpawnFill):
    def run(self):
        del self.memory.emptying
        if self.creep.ticksToLive < recycle_time:
            self.memory.role = role_recycling
            self.memory.last_role = role_local_hauler
            return False
        # just always be running this - TODO: do local haulers want to do this, or just remote haulers?
        # a local hauler could definitely be a repurposed remote hauler though, in which case this is a good idea.
        self.repair_nearby_roads()
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True
            self.target_mind.untarget_all(self)

        # NOTE HERE: Instead of checking if we are over-stationed on LocalHaulers in this class (as remote miner does),
        # we check in consistency.reassign_room_roles().

        if self.memory.harvesting:
            source = self.target_mind.get_new_target(self, target_source)

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
                    self.home.mem.meta.clear_next = 0  # clear next tick
                    self.report(speech.local_hauler_no_miner, miner_name)
                else:
                    self.report(speech.local_hauler_no_miner_name, source.id[-4:])
                self.go_to_depot()
                self.target_mind.untarget(self, target_source)
                return False

            if not self.creep.pos.isNearTo(target_pos):
                self.move_to_with_queue(target_pos, flags.SOURCE_QUEUE_START)
                self.pick_up_available_energy()
                self.report(speech.local_hauler_moving_to_miner)
                return False

            self.memory.stationary = True

            piles = target_pos.lookFor(LOOK_RESOURCES, {"filter": {"resourceType": RESOURCE_ENERGY}})
            if not len(piles):
                # TODO: temporary hack...
                miner_near = _.find(self.room.find_in_range(FIND_MY_CREEPS, 2, self.creep.pos),
                          {"memory": {"role": role_dedi_miner}})
                if miner_near and not miner_near.pos.isNearTo(source.pos):
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

            self.memory.emptying = True
            target = self.target_mind.get_new_target(self, target_closest_energy_site)
            if not target:
                target = self.creep.room.storage  # This apparently has happened, I don't know why though?
            if target.energy >= target.energyCapacity and not self.home.links.enabled:
                target = storage
            if target.structureType == STRUCTURE_LINK and self.creep.pos.inRangeTo(target, 2):
                self.home.links.register_target_deposit(target, self, self.creep.carry.energy)

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
                if target == storage:
                    self.log("Storage in {} full!".format(self.creep.pos.roomName))
                    self.go_to_depot()
                    self.report(speech.local_hauler_storage_full)
            else:
                self.log("Unknown result from hauler-creep.transfer({}): {}", target, result)
                self.report(speech.local_hauler_transfer_unknown_result)

            return False


profiling.profile_whitelist(LocalHauler, ["run"])
