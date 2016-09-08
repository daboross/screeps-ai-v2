import speech
from constants import target_big_source, target_source, target_closest_energy_site
from goals.transport import TransportPickup
from role_base import RoleBase
from roles.spawn_fill import SpawnFill
from tools import profiling
from utilities import movement
from utilities.screeps_constants import *

__pragma__('noalias', 'name')

_MOVE_ARGS = {"use_roads": True}


class DedicatedMiner(RoleBase):
    def run(self):
        source = self.targets.get_new_target(self, target_big_source)

        if not source:
            self.log("Dedicated miner could not find any new big sources.")
            self.recycle_me()
            return

        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source)
            self.report(speech.dedi_miner_moving)
            return False

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
        source = self.targets.get_new_target(self, target_big_source)
        if not source:
            return -1
        source_pos = source.pos
        spawn_pos = movement.average_pos_same_room(self.home.spawns)
        time = movement.path_distance(spawn_pos, source_pos, True) + _.size(self.creep.body) * 3 + 15
        # self.log("Calculated dedi-miner replacement time (using {} to {}): {}", spawn_pos, source_pos, time)
        return time


profiling.profile_whitelist(DedicatedMiner, ["run"])


# TODO: Merge duplicated functionality in LocalHauler and RemoteHauler into a super-class
class LocalHauler(SpawnFill, TransportPickup):
    def run(self):
        pickup = self.targets.get_new_target(self, target_source)

        if not pickup:
            return SpawnFill.run(self)

        if _.sum(self.creep.carry) > self.creep.carry.energy:
            fill = self.home.room.storage
        else:
            fill = self.targets.get_new_target(self, target_closest_energy_site, pickup.pos)

        if not pickup:
            self.go_to_depot()
            return

        if not fill:
            fill = self.home.spawn
            if self.pos.roomName == fill.pos.roomName and _.sum(self.creep.carry) >= self.creep.carryCapacity:
                return SpawnFill.run(self)

        return self.transport(pickup, fill)

    def _calculate_time_to_replace(self):
        return _.size(self.creep.body) * 3


profiling.profile_whitelist(LocalHauler, ["run"])
