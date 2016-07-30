import profiling
from constants import target_big_source, target_source_local_hauler
from role_base import RoleBase
from screeps_constants import *

__pragma__('noalias', 'name')

_MOVE_OPTIONS = {"maxRooms": 1, "ignoreCreeps": True}


class DedicatedMiner(RoleBase):
    def run(self):
        source = self.target_mind.get_new_target(self.creep, target_big_source)

        if not source:
            print("[{}] Dedicated miner could not find any new big sources.".format(self.name))
            return

        if not self.creep.pos.isNearTo(source.pos):
            self.move_to(source, False, _MOVE_OPTIONS)
            self.report("HB. F. S.")
            return False

        result = self.creep.harvest(source)
        if result == OK:
            if Memory.big_harvesters_placed:
                Memory.big_harvesters_placed[source.id] = self.name
            else:
                Memory.big_harvesters_placed = {
                    source.id: self.name
                }
            self.report("HB.")
        elif result == ERR_NOT_ENOUGH_RESOURCES:
            # TODO: trigger some flag on the global mind here, to search for other rooms to settle!
            self.report("HB. WW.")
        else:
            print("[{}] Unknown result from mining-creep.harvest({}): {}".format(
                self.name, source, result
            ))
            self.report("HB. ???")

        return False


profiling.profile_class(DedicatedMiner, profiling.ROLE_BASE_IGNORE)


class LocalHauler(RoleBase):
    def run(self):
        if self.memory.harvesting and self.creep.carry.energy >= self.creep.carryCapacity:
            self.memory.harvesting = False

        if not self.memory.harvesting and self.creep.carry.energy <= 0:
            self.memory.harvesting = True

        if self.memory.harvesting:
            source = self.target_mind.get_new_target(self.creep, target_source_local_hauler)

            if not source:
                if self.creep.carry.energy > 0:
                    self.memory.harvesting = False
                    return True
                self.report("H. N. S.")
                self.go_to_depot()
                return False

            miner = Game.creeps[Memory.big_harvesters_placed[source.id]]
            if not miner:
                self.report("H. N. M.")
                self.go_to_depot()
                return True

            if not self.creep.pos.isNearTo(miner.pos):
                self.move_to(miner, False, _MOVE_OPTIONS)
                self.report("H. Move.")
                return False

            piles = miner.pos.lookFor(LOOK_RESOURCES, {"filter": {"resourceType": RESOURCE_ENERGY}})
            if not len(piles):
                self.report("H. WW.")
                return False

            result = self.creep.pickup(piles[0])

            if result == OK:
                self.report("H. Collect!")
            elif result == ERR_FULL:
                self.memory.harvesting = False
                return True
            else:
                print("[{}] Unknown result from hauler-creep.pickup({}): {}".format(
                    self.name, source, result
                ))
                self.report("H. ???")

            return False
        else:
            storage = self.creep.room.storage
            if not storage:
                print("[{}] Local hauler can't find storage in {}!".format(self.name, self.creep.room.name))
                self.go_to_depot()
                self.report("H. N. S!!!")
                return False

            if not self.creep.pos.isNearTo(storage.pos):
                self.move_to(storage)
                self.report("H. Haul.")
                return False

            result = self.creep.transfer(storage, RESOURCE_ENERGY)
            if result == OK:
                self.report("H. Store.")
            elif result == ERR_NOT_ENOUGH_RESOURCES:
                self.memory.harvesting = True
                return True
            elif result == ERR_FULL:
                print("[{}] Storage in room {} full!".format(self.name, storage.room))
                self.go_to_depot()
                self.report("H. Full!!")
            else:
                print("[{}] Unknown result from hauler-creep.transfer({}): {}".format(
                    self.name, storage, result
                ))
                self.report("H. ???")

            return False
